import api from '../utils/request';

export interface McpToolConfig {
  id: number;
  name: string;
  description?: string;
  toolType: string;
  toolName: string;
  transport: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  enabled: number;
  preset: number;
  createdAt?: string;
  updatedAt?: string;
}

interface ApiResult<T> {
  code: number;
  message: string;
  data: T;
}

export const getMcpTools = (): Promise<ApiResult<McpToolConfig[]>> =>
  api.get('/api/v1/mcp-tools');

export const createAgentPlanWebSearchMcp = (data: {
  name?: string;
  description?: string;
  apiKey: string;
}): Promise<ApiResult<McpToolConfig>> =>
  api.post('/api/v1/mcp-tools', {
    name: data.name || 'Agent Plan Web Search',
    description: data.description || '',
    toolType: 'agent_plan_web_search',
    toolName: 'web_search',
    transport: 'stdio',
    command: 'uvx',
    args: ['git+https://github.com/volcengine/mcp-server#subdirectory=server/mcp_server_askecho_search_infinity'],
    env: { API_KEY: data.apiKey },
    enabled: 1,
  });

export const deleteMcpTool = (id: number): Promise<ApiResult<void>> =>
  api.delete(`/api/v1/mcp-tools/${id}`);

export const testMcpTool = (
  id: number,
  data: { query?: string }
): Promise<ApiResult<Record<string, unknown>>> =>
  api.post(`/api/v1/mcp-tools/${id}/actions/test`, data);
