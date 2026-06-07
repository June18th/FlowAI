from __future__ import annotations

from typing import Any

import httpx

from app.engine.models import WorkflowNode
from app.engine.node_executor.base import NodeExecutor
from app.engine.node_executor.factory import node_executor_factory


class WebSearchNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "web_search"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        query = node.data.get("query", input_data.get("input", ""))
        return {
            "query": query,
            "summary": f"Web search results for: {query}",
            "results": [],
            "citations": [],
            "metadata": {"source": "web_search"},
        }


class WebFetchNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "web_fetch"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        urls = node.data.get("urls", node.data.get("url", ""))
        if isinstance(urls, str):
            urls = [urls] if urls else []
        if not urls:
            urls = [input_data.get("input", "")]

        pages = []
        contents = []
        async with httpx.AsyncClient(timeout=30) as client:
            for url in urls:
                if not url:
                    continue
                try:
                    resp = await client.get(url, follow_redirects=True)
                    text = resp.text[:8000]
                    pages.append({"url": url, "status": resp.status_code})
                    contents.append(text)
                except Exception as e:
                    pages.append({"url": url, "status": "error", "error": str(e)})

        return {
            "pages": pages,
            "content": "\n\n".join(contents),
            "citations": urls,
        }


class TTSNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "tts"

    def _resolve_text(self, node: WorkflowNode, input_data: dict) -> str:
        # Match Java extractInputText exactly
        input_params = node.data.get("inputParams")
        if input_params:
            for param in input_params:
                if param.get("name") == "text":
                    ptype = param.get("type")
                    if ptype == "input":
                        return str(param.get("value", ""))
                    elif ptype == "reference":
                        ref = param.get("referenceNode", "")
                        if ref:
                            parts = ref.split(".")
                            if len(parts) == 2:
                                param_key = parts[1]
                                val = input_data.get(param_key)
                                if isinstance(val, str) and val:
                                    return val
        # Fallbacks matching Java
        text = str(input_data.get("output", ""))
        if text:
            return text
        text = str(input_data.get("input", ""))
        if text:
            return text
        return str(input_data.get("text", ""))

    # Match Java constants
    QWEN_MAX_CHARS = 400
    QWEN_MAX_BYTES = 600

    def _resolve_config(self, data: dict) -> dict:
        """Match Java resolveConfig for TTS."""
        import logging
        log = logging.getLogger(__name__)

        config_id = self._parse_int(data.get("configId"))
        provider = ""
        api_url = ""
        api_key = ""
        model = ""
        explicit_tts_model = False

        if config_id:
            from app.database import async_session
            from sqlalchemy import select
            from app.models.llm_config import LLMGlobalConfig
            import asyncio

            async def _get_config():
                async with async_session() as db:
                    stmt = select(LLMGlobalConfig).where(LLMGlobalConfig.id == config_id)
                    result = await db.execute(stmt)
                    return result.scalar_one_or_none()

            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
            global_config = asyncio.get_event_loop().run_until_complete(_get_config()) if asyncio.get_event_loop().is_running() else asyncio.run(_get_config())

            if global_config:
                provider = self._canonicalize_provider(global_config.provider or "")
                api_url = (global_config.api_url or "").strip()
                api_key = (global_config.api_key or "").strip()
                model = (global_config.tts_model or "").strip()
                explicit_tts_model = bool(model)
                if not explicit_tts_model:
                    model = (global_config.model or "").strip()
                log.info("TTS using global config: %s", global_config.config_name)

        if not api_key:
            api_key = str(data.get("apiKey", "")).strip()
        if not api_url:
            api_url = str(data.get("apiUrl", "")).strip()
        if not model:
            model = str(data.get("model", "")).strip()
        if not provider:
            provider = self._canonicalize_provider(str(data.get("provider", "")).strip())
        if not provider:
            provider = self._infer_provider(model)

        voice = str(data.get("voice", "")).strip() or ("cixingnansheng" if provider == "step" else "Cherry")
        language = str(data.get("languageType", "")).strip() or "Auto"
        model = self._normalize_tts_model(provider, model, explicit_tts_model)

        return {"provider": provider, "api_url": api_url, "api_key": api_key, "model": model,
                "voice": voice, "language": language}

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        import httpx, uuid, time as _time, logging
        from app.config import settings as app_settings
        log = logging.getLogger(__name__)

        node_id = node.id
        node_name = node.display_name

        text = self._resolve_text(node, input_data)
        if not text or not text.strip():
            return {"audioUrl": "", "output": "", "message": "TTS text is empty"}

        cfg = self._resolve_config(node.data)
        if not cfg["api_key"]:
            return {"audioUrl": "", "output": "", "message": "TTS API key not configured"}
        if not cfg["provider"] or cfg["provider"] not in ("qwen", "step"):
            return {"audioUrl": "", "output": "", "message": f"TTS unsupported provider: {cfg['provider']}"}

        max_chars = 1000 if cfg["provider"] == "step" else self.QWEN_MAX_CHARS
        max_bytes = 999999 if cfg["provider"] == "step" else self.QWEN_MAX_BYTES
        chunks = self._split_text(text, max_chars, max_bytes)
        log.info("TTS: text split into %d chunks", len(chunks))

        if progress_callback:
            progress_callback({"eventType": "NODE_PROGRESS", "nodeId": node_id, "nodeName": node_name,
                               "message": f"文本已分割为 {len(chunks)} 个片段",
                               "data": {"totalChunks": len(chunks)}})

        audio_chunks = []
        for i, chunk in enumerate(chunks):
            chunk_no = i + 1
            if progress_callback:
                progress_callback({"eventType": "NODE_PROGRESS", "nodeId": node_id, "nodeName": node_name,
                                   "message": f"正在处理第 {chunk_no}/{len(chunks)} 个片段",
                                   "data": {"chunkIndex": chunk_no, "totalChunks": len(chunks)}})
            try:
                audio_data = await self._synthesize(cfg, chunk, chunk_no, len(chunks))
                audio_chunks.append(audio_data)
                if progress_callback:
                    progress_callback({"eventType": "NODE_PROGRESS", "nodeId": node_id, "nodeName": node_name,
                                       "message": f"已完成第 {chunk_no}/{len(chunks)} 个片段",
                                       "data": {"chunkIndex": chunk_no, "totalChunks": len(chunks)}})
            except Exception as e:
                import traceback
                logging.getLogger(__name__).error("TTS chunk %d failed: %s\n%s", chunk_no, e, traceback.format_exc())
                return {"audioUrl": "", "output": "", "message": f"TTS chunk {chunk_no} failed: {e}"}

        if not audio_chunks:
            return {"audioUrl": "", "output": "", "message": "TTS produced no audio"}

        if progress_callback:
            progress_callback({"eventType": "NODE_PROGRESS", "nodeId": node_id, "nodeName": node_name,
                               "message": f"正在合并 {len(audio_chunks)} 个音频片段...",
                               "data": {"mergeChunks": len(audio_chunks)}})

        import asyncio
        loop = asyncio.get_event_loop()
        merged = await loop.run_in_executor(None, self._merge_wav, audio_chunks)

        from minio import Minio
        from io import BytesIO
        minio_client = Minio(
            app_settings.minio_endpoint.replace("http://", "").replace("https://", ""),
            access_key=app_settings.minio_access_key,
            secret_key=app_settings.minio_secret_key,
            secure=app_settings.minio_endpoint.startswith("https"),
        )
        bucket = app_settings.minio_bucket_name

        def _ensure_bucket():
            if not minio_client.bucket_exists(bucket):
                minio_client.make_bucket(bucket)
                minio_client.set_bucket_policy(bucket,
                    f'{{"Version":"2012-10-17","Statement":[{{"Effect":"Allow","Principal":{{"AWS":["*"]}},"Action":["s3:GetObject"],"Resource":["arn:aws:s3:::{bucket}/*"]}}]}}'
                )
        await loop.run_in_executor(None, _ensure_bucket)

        obj = f"audio_{uuid.uuid4().hex}.wav"
        obj_data = BytesIO(merged)
        await loop.run_in_executor(None, lambda: minio_client.put_object(bucket, obj, obj_data, len(merged), content_type="audio/wav"))
        public_url = f"{app_settings.minio_public_url}/{bucket}/{obj}"

        if progress_callback:
            progress_callback({"eventType": "NODE_PROGRESS", "nodeId": node_id, "nodeName": node_name,
                               "message": f"音频已上传至 MinIO，共 {len(chunks)} 个片段",
                               "data": {"audioUrl": public_url, "totalChunks": len(chunks)}})

        return {"audioUrl": public_url, "fileName": obj, "output": public_url, "chunks": len(chunks)}

    async def _synthesize(self, cfg: dict, chunk: str, idx: int, total: int) -> bytes:
        import httpx, logging
        log = logging.getLogger(__name__)
        if cfg["provider"] == "qwen":
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
                    headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
                    json={"model": cfg["model"], "input": {"text": chunk, "voice": cfg["voice"]},
                          "parameters": {"output_format": "url"}},
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"DashScope HTTP {resp.status_code}")
                data = resp.json()
                audio_url = ""
                out = data.get("output", {})
                audio = out.get("audio", {})
                audio_url = audio.get("url", "")
                if not audio_url:
                    raise RuntimeError(f"DashScope returned no audio URL: {data.get('message', data.get('code', ''))}")
                log.info("TTS chunk %d/%d: %s", idx, total, audio_url[:80])
                audio_resp = await client.get(audio_url, timeout=60)
                return audio_resp.content
        else:
            raise RuntimeError(f"Unsupported TTS provider: {cfg['provider']}")

    def _split_text(self, text: str, max_len: int, max_bytes: int) -> list[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + max_len, len(text))
            while end > start:
                candidate = text[start:end]
                if len(candidate.encode("utf-8")) <= max_bytes:
                    if end < len(text):
                        last_punc = self._find_last_punctuation(text, start, end)
                        if last_punc > start:
                            end = last_punc + 1
                    chunks.append(text[start:end])
                    start = end
                    break
                end -= 10
            if end <= start:
                end = start + 1
                while end <= len(text):
                    if len(text[start:end].encode("utf-8")) > max_bytes:
                        chunks.append(text[start:end - 1])
                        start = end - 1
                        break
                    end += 1
        return chunks if chunks else [text]

    @staticmethod
    def _find_last_punctuation(text: str, start: int, end: int) -> int:
        for i in range(end - 1, start - 1, -1):
            if text[i] in "。！？；,.!?;":
                return i
        return -1

    @staticmethod
    def _merge_wav(chunks: list[bytes]) -> bytes:
        if len(chunks) == 1:
            return chunks[0]
        if len(chunks[0]) < 44:
            return chunks[0]
        import io
        result = bytearray(chunks[0][:44])  # header from first
        for c in chunks:
            result.extend(c[44:])  # audio data
        data_size = len(result) - 44
        file_size = len(result) - 8
        result[4:8] = file_size.to_bytes(4, "little")
        result[40:44] = data_size.to_bytes(4, "little")
        return bytes(result)

    def _canonicalize_provider(self, provider: str) -> str:
        p = provider.strip().lower()
        m = {"stepfun": "step", "阶跃星辰": "step", "通义千问": "qwen", "dashscope": "qwen", "aliyun": "qwen"}
        return m.get(p, p)

    def _infer_provider(self, model: str) -> str:
        if not model:
            return "qwen"
        m = model.strip().lower()
        return "step" if m.startswith("step") or "stepaudio" in m else "qwen"

    def _normalize_tts_model(self, provider: str, model: str, explicit: bool) -> str:
        if explicit:
            return model
        if provider == "step":
            return model if "tts" in model.lower() else "stepaudio-2.5-tts"
        return model if "tts" in model.lower() else "qwen3-tts-flash"

    @staticmethod
    def _parse_int(val) -> int | None:
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None


class ImageGenerateNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "image_generate"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        prompt = node.data.get("prompt", input_data.get("input", ""))
        return {
            "imageUrl": "",
            "imageUrls": [],
            "prompt": prompt,
            "model": node.data.get("model", ""),
            "metadata": {"provider": node.data.get("provider", "")},
        }


class VideoGenerateNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "video_generate"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        prompt = node.data.get("prompt", input_data.get("input", ""))
        return {
            "taskId": "",
            "status": "created",
            "videoUrl": "",
            "coverUrl": "",
            "model": node.data.get("model", ""),
            "metadata": {"prompt": prompt},
        }


class VisionAnalyzeNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "vision_analyze"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        return {
            "description": "Vision analysis result",
            "score": 0,
            "issues": [],
            "pass": True,
        }


class KnowledgeRetrieveNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "knowledge_retrieve"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        query = node.data.get("query", input_data.get("input", ""))
        return {"query": query, "chunks": [], "context": ""}


class KnowledgeUpsertNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "knowledge_upsert"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        content = node.data.get("content", input_data.get("input", ""))
        return {"inserted": True, "content": content}


class MemoryRetrieveNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "memory_retrieve"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        query = node.data.get("query", input_data.get("input", ""))
        return {"query": query, "memories": []}


class MemoryWriteNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "memory_write"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        content = node.data.get("content", input_data.get("input", ""))
        return {"memoryId": "generated-uuid", "written": True}


class WeatherQueryNodeExecutor(NodeExecutor):
    """Query weather data from Amap (高德地图) API."""

    def get_supported_node_type(self) -> str:
        return "weather_query"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        api_key = node.data.get("apiKey", "")
        city = node.data.get("city", input_data.get("input", "110000"))

        if not api_key:
            return {"error": "请配置高德地图 API Key", "weather": None}

        url = "https://restapi.amap.com/v3/weather/weatherInfo"
        params = {"key": api_key, "city": str(city), "extensions": "all"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                data = resp.json()

            if data.get("status") == "1" and data.get("forecasts"):
                forecasts = data["forecasts"]
                live = data.get("lives", [])

                forecast_list = []
                for fcity in forecasts:
                    for cast in fcity.get("casts", []):
                        forecast_list.append({
                            "date": cast.get("date"),
                            "week": cast.get("week"),
                            "dayWeather": cast.get("dayweather"),
                            "nightWeather": cast.get("nightweather"),
                            "dayTemp": cast.get("daytemp"),
                            "nightTemp": cast.get("nighttemp"),
                            "dayWind": cast.get("daywind"),
                            "nightWind": cast.get("nightwind"),
                            "dayPower": cast.get("daypower"),
                            "nightPower": cast.get("nightpower"),
                        })

                live_info = None
                if live:
                    l = live[0]
                    live_info = {
                        "city": l.get("city"),
                        "weather": l.get("weather"),
                        "temperature": l.get("temperature"),
                        "windDirection": l.get("winddirection"),
                        "windPower": l.get("windpower"),
                        "humidity": l.get("humidity"),
                        "reportTime": l.get("reporttime"),
                    }

                return {
                    "city": forecasts[0].get("city") if forecasts else str(city),
                    "live": live_info,
                    "forecasts": forecast_list,
                    "forecastSummary": "\n".join(
                        f"{f['date']} {f['week']}: {f['dayWeather']} {f['dayTemp']}°C ~ {f['nightTemp']}°C, {f['dayWind']} {f['dayPower']}级"
                        for f in forecast_list
                    ) if forecast_list else "暂无预报数据",
                }
            else:
                return {"error": f"天气查询失败: {data.get('info', '未知错误')}", "weather": None}
        except Exception as e:
            return {"error": f"请求异常: {str(e)}", "weather": None}


class WeatherNodeExecutor(WeatherQueryNodeExecutor):
    """Alias: 'weather' node type (compat with PaiAgent workflows)."""
    def get_supported_node_type(self) -> str:
        return "weather"


for cls in [WebSearchNodeExecutor, WebFetchNodeExecutor, TTSNodeExecutor, ImageGenerateNodeExecutor,
            VideoGenerateNodeExecutor, VisionAnalyzeNodeExecutor, KnowledgeRetrieveNodeExecutor,
            KnowledgeUpsertNodeExecutor, MemoryRetrieveNodeExecutor, MemoryWriteNodeExecutor,
            WeatherQueryNodeExecutor, WeatherNodeExecutor]:
    node_executor_factory.register(cls())
