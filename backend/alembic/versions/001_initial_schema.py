"""Initial schema — FlowAI

Revision ID: 001
Revises:
Create Date: 2026-06-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # workflow
    op.create_table(
        "workflow",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("flow_data", mysql.JSON(), nullable=False),
        sa.Column("engine_type", sa.String(50), server_default="dag"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_created_at", "workflow", ["created_at"])
    op.create_index("idx_updated_at", "workflow", ["updated_at"])

    # node_definition
    op.create_table(
        "node_definition",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("node_type", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("icon", sa.String(255)),
        sa.Column("input_schema", mysql.JSON()),
        sa.Column("output_schema", mysql.JSON()),
        sa.Column("config_schema", mysql.JSON()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("node_type"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_category", "node_definition", ["category"])

    # execution_record
    op.create_table(
        "execution_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("flow_id", sa.BigInteger(), nullable=False),
        sa.Column("input_data", mysql.JSON()),
        sa.Column("output_data", mysql.JSON()),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("node_results", mysql.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("duration", sa.Integer()),
        sa.Column("executed_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_flow_id", "execution_record", ["flow_id"])
    op.create_index("idx_flow_latest", "execution_record", ["flow_id", "id"])
    op.create_index("idx_executed_at", "execution_record", ["executed_at"])
    op.create_index("idx_status", "execution_record", ["status"])

    # execution_snapshot
    op.create_table(
        "execution_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("execution_id", sa.BigInteger(), nullable=False),
        sa.Column("flow_id", sa.BigInteger(), nullable=False),
        sa.Column("node_id", sa.String(100), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("node_name", sa.String(255)),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("input_data", mysql.JSON()),
        sa.Column("output_data", mysql.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("duration", sa.Integer()),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("execution_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_execution_snapshot_exec_id", "execution_snapshot", ["execution_id"])
    op.create_index("idx_execution_snapshot_flow_id", "execution_snapshot", ["flow_id"])
    op.create_index("idx_execution_snapshot_node_id", "execution_snapshot", ["node_id"])
    op.create_index("idx_execution_snapshot_status", "execution_snapshot", ["status"])
    op.create_index("idx_execution_snapshot_created_at", "execution_snapshot", ["created_at"])

    # execution_variable
    op.create_table(
        "execution_variable",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("execution_id", sa.BigInteger(), nullable=False),
        sa.Column("variable_name", sa.String(100), nullable=False),
        sa.Column("variable_type", sa.String(50), server_default="STRING"),
        sa.Column("variable_value", sa.Text()),
        sa.Column("is_modified", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id", "variable_name", name="uk_execution_variable"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_execution_variable_exec_id", "execution_variable", ["execution_id"])

    # llm_global_config
    op.create_table(
        "llm_global_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("config_name", sa.String(100), nullable=False),
        sa.Column("api_url", sa.String(255), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tts_model", sa.String(100), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("image_model", sa.String(100), nullable=True),
        sa.Column("video_model", sa.String(100), nullable=True),
        sa.Column("memory_enabled", sa.Integer(), server_default="0"),
        sa.Column("temperature", sa.Numeric(3, 2), server_default="0.70"),
        sa.Column("is_default", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "config_name", name="uk_provider_config_name"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_provider", "llm_global_config", ["provider"])
    op.create_index("idx_is_default", "llm_global_config", ["is_default"])

    # agent_memory
    op.create_table(
        "agent_memory",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(50), nullable=False, server_default="workflow"),
        sa.Column("memory_type", sa.String(50), server_default="fact"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.String(500), nullable=True),
        sa.Column("source", sa.String(255)),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_scope", "agent_memory", ["scope"])
    op.create_index("idx_memory_type", "agent_memory", ["memory_type"])

    # agent_memory_embedding
    op.create_table(
        "agent_memory_embedding",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("memory_id", sa.BigInteger(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=True),
        sa.Column("embedding", mysql.JSON()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_memory_id", "agent_memory_embedding", ["memory_id"])

    # mcp_tool_config
    op.create_table(
        "mcp_tool_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("tool_type", sa.String(50), server_default="custom"),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("transport", sa.String(30), server_default="stdio"),
        sa.Column("command", sa.String(500), nullable=False),
        sa.Column("args", mysql.JSON()),
        sa.Column("env", mysql.JSON()),
        sa.Column("enabled", sa.Integer(), server_default="1"),
        sa.Column("preset", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_mcp_tool_name", "mcp_tool_config", ["tool_name"])
    op.create_index("idx_mcp_tool_type", "mcp_tool_config", ["tool_type"])

    # knowledge_base
    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("config_id", sa.BigInteger(), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("chunk_size", sa.Integer(), server_default="800"),
        sa.Column("chunk_overlap", sa.Integer(), server_default="100"),
        sa.Column("status", sa.String(30), server_default="DRAFT"),
        sa.Column("document_count", sa.Integer(), server_default="0"),
        sa.Column("chunk_count", sa.Integer(), server_default="0"),
        sa.Column("char_count", sa.BigInteger(), server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_knowledge_base_status", "knowledge_base", ["status"])

    # knowledge_document
    op.create_table(
        "knowledge_document",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("knowledge_base_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("source_type", sa.String(30), server_default="TEXT"),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("raw_text", mysql.MEDIUMTEXT()),
        sa.Column("tags", mysql.JSON()),
        sa.Column("status", sa.String(30), server_default="IMPORTED"),
        sa.Column("char_count", sa.BigInteger(), server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_knowledge_document_base", "knowledge_document", ["knowledge_base_id"])
    op.create_index("idx_knowledge_document_status", "knowledge_document", ["status"])

    # knowledge_chunk
    op.create_table(
        "knowledge_chunk",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("knowledge_base_id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), server_default="0"),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("tags", mysql.JSON()),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("embedding", mysql.JSON()),
        sa.Column("status", sa.String(30), server_default="READY"),
        sa.Column("char_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_knowledge_chunk_base_id", "knowledge_chunk", ["knowledge_base_id"])
    op.create_index("idx_knowledge_chunk_doc_id", "knowledge_chunk", ["document_id"])

    # knowledge_index_task
    op.create_table(
        "knowledge_index_task",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("knowledge_base_id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(30), server_default="RUNNING"),
        sa.Column("progress", sa.Integer(), server_default="0"),
        sa.Column("total_chunks", sa.Integer(), server_default="0"),
        sa.Column("finished_chunks", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_knowledge_index_task_base", "knowledge_index_task", ["knowledge_base_id"])
    op.create_index("idx_knowledge_index_task_document", "knowledge_index_task", ["document_id"])

    # Seed data: node definitions
    op.execute("""
        INSERT INTO node_definition (node_type, display_name, category, icon, input_schema, output_schema, config_schema) VALUES
        ('input', '输入', 'IO', '📥',
         '{"type": "object", "properties": {}}',
         '{"type": "object", "properties": {"input": {"type": "string"}}}',
         '{"type": "object", "properties": {"defaultValue": {"type": "string"}}}'),
        ('output', '输出', 'IO', '📤',
         '{"type": "object", "properties": {"input": {"type": "string"}}}',
         '{"type": "object", "properties": {"output": {"type": "string"}}}',
         '{"type": "object", "properties": {}}'),
        ('openai', 'OpenAI', 'LLM', '🤖',
         '{"type": "object", "properties": {"input": {"type": "string"}}}',
         '{"type": "object", "properties": {"output": {"type": "string"}, "tokens": {"type": "number"}}}',
         '{"type": "object", "properties": {"apiKey": {"type": "string"}, "model": {"type": "string", "default": "gpt-3.5-turbo"}, "prompt": {"type": "string"}, "temperature": {"type": "number", "default": 0.7}, "maxTokens": {"type": "number", "default": 1000}}}'),
        ('deepseek', 'DeepSeek', 'LLM', '🧠',
         '{"type": "object", "properties": {"input": {"type": "string"}}}',
         '{"type": "object", "properties": {"output": {"type": "string"}, "tokens": {"type": "number"}}}',
         '{"type": "object", "properties": {"apiKey": {"type": "string"}, "model": {"type": "string", "default": "deepseek-chat"}, "prompt": {"type": "string"}, "temperature": {"type": "number", "default": 0.7}, "maxTokens": {"type": "number", "default": 1000}}}'),
        ('qwen', '通义千问', 'LLM', '🌟',
         '{"type": "object", "properties": {"input": {"type": "string"}}}',
         '{"type": "object", "properties": {"output": {"type": "string"}, "tokens": {"type": "number"}}}',
         '{"type": "object", "properties": {"apiKey": {"type": "string"}, "model": {"type": "string", "default": "qwen-turbo"}, "prompt": {"type": "string"}, "temperature": {"type": "number", "default": 0.7}, "maxTokens": {"type": "number", "default": 1000}}}'),
        ('step', 'Step', 'LLM', '🟆',
         '{"type": "object", "properties": {"input": {"type": "string"}}}',
         '{"type": "object", "properties": {"output": {"type": "string"}, "tokens": {"type": "number"}}}',
         '{"type": "object", "properties": {"apiKey": {"type": "string"}, "model": {"type": "string", "default": "claude-3-5-sonnet-20241022"}, "prompt": {"type": "string"}, "temperature": {"type": "number", "default": 0.7}, "maxTokens": {"type": "number", "default": 1000}}}'),
        ('react_agent', 'ReAct Agent', 'LLM', 'RA',
         '{"type": "object", "properties": {"input": {"type": "string"}}}',
         '{"type": "object", "properties": {"output": {"type": "string"}, "finalAnswer": {"type": "string"}, "toolTrace": {"type": "array"}, "steps": {"type": "number"}, "tokens": {"type": "number"}}}',
         '{"type": "object", "properties": {"provider": {"type": "string"}, "configId": {"type": "number"}, "apiKey": {"type": "string"}, "model": {"type": "string"}, "prompt": {"type": "string"}, "temperature": {"type": "number", "default": 0.7}, "maxSteps": {"type": "number", "default": 5}, "tools": {"type": "array"}}}'),
        ('tts', '超拟人音频合成', 'TOOL', '🔊',
         '{"type": "object", "properties": {"text": {"type": "string"}}}',
         '{"type": "object", "properties": {"audioUrl": {"type": "string"}, "duration": {"type": "number"}, "fileSize": {"type": "number"}}}',
         '{"type": "object", "properties": {"provider": {"type": "string"}, "configId": {"type": "number"}, "apiUrl": {"type": "string"}, "apiKey": {"type": "string"}, "model": {"type": "string", "default": "qwen3-tts-flash"}, "voice": {"type": "string", "default": "Cherry"}, "languageType": {"type": "string", "default": "Auto"}, "instruction": {"type": "string"}, "speed": {"type": "number", "default": 1.0}, "volume": {"type": "number", "default": 1.0}, "sampleRate": {"type": "number", "default": 24000}}}'),
        ('condition', '条件分支', 'CONTROL', '🔀',
         '{"type": "object", "properties": {"input": {"type": "object"}}}',
         '{"type": "object", "properties": {"__selectedBranch__": {"type": "string"}, "__conditionNodeId__": {"type": "string"}}}',
         '{"type": "object", "properties": {"conditions": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "field": {"type": "string"}, "operator": {"type": "string", "enum": ["eq", "neq", "gt", "gte", "lt", "lte", "contains", "notContains", "startsWith", "endsWith", "isEmpty", "isNotEmpty"]}, "value": {"type": "string"}}}}}}')
    """)


def downgrade() -> None:
    op.drop_table("knowledge_index_task")
    op.drop_table("knowledge_chunk")
    op.drop_table("knowledge_document")
    op.drop_table("knowledge_base")
    op.drop_table("mcp_tool_config")
    op.drop_table("agent_memory_embedding")
    op.drop_table("agent_memory")
    op.drop_table("llm_global_config")
    op.drop_table("execution_variable")
    op.drop_table("execution_snapshot")
    op.drop_table("execution_record")
    op.drop_table("node_definition")
    op.drop_table("workflow")
