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

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        text = node.data.get("text", input_data.get("input", input_data.get("text", "")))
        provider = node.data.get("provider", "qwen")

        return {
            "audioUrl": "",
            "duration": 0,
            "fileSize": 0,
            "message": f"TTS synthesis ({provider}) invoked for text length {len(text)}",
        }


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


for cls in [WebSearchNodeExecutor, WebFetchNodeExecutor, TTSNodeExecutor, ImageGenerateNodeExecutor,
            VideoGenerateNodeExecutor, VisionAnalyzeNodeExecutor, KnowledgeRetrieveNodeExecutor,
            KnowledgeUpsertNodeExecutor, MemoryRetrieveNodeExecutor, MemoryWriteNodeExecutor,
            WeatherQueryNodeExecutor]:
    node_executor_factory.register(cls())
