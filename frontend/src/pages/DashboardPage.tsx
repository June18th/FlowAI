import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Spin, message, Tag } from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  ThunderboltOutlined,
  ShareAltOutlined,
  AppstoreOutlined,
  ArrowRightOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import { getWorkflows, Workflow, PageData } from '../api/workflow';
import { getAllConfigs, LLMGlobalConfig } from '../api/llmConfig';

const DashboardPage = () => {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [configs, setConfigs] = useState<LLMGlobalConfig[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadWorkflows();
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    try {
      const result = await getAllConfigs();
      if (result.code === 200) {
        setConfigs(Array.isArray(result.data) ? result.data : (result.data as any)?.items || []);
      }
    } catch {
      // 静默失败
    }
  };

  const loadWorkflows = async () => {
    setLoading(true);
    try {
      const result = await getWorkflows();
      if (result.code === 200) {
        const data = result.data as PageData<Workflow>;
        setWorkflows(data.items || []);
      }
    } catch {
      message.error('加载工作流列表失败');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  const recentWorkflows = workflows.slice(0, 6);
  const dagCount = workflows.filter((w) => w.engineType !== 'langgraph').length;
  const langgraphCount = workflows.filter((w) => w.engineType === 'langgraph').length;

  return (
    <div className="dashboard-shell">
      <header className="dashboard-header">
        <div className="dashboard-header-content">
          <div>
            <h1 className="dashboard-title">FlowAI</h1>
            <p className="dashboard-subtitle">AI Agent 可视化工作流编排平台</p>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'stretch' }}>
            <Button
              type="primary"
              size="large"
              icon={<EditOutlined />}
              onClick={() => navigate('/editor')}
            >
              进入编辑器
            </Button>
            <Button
              size="large"
              icon={<PlusOutlined />}
              onClick={() => navigate('/editor')}
            >
              创建新工作流
            </Button>
          </div>
        </div>
      </header>

      <div className="dashboard-body">
        {/* 统计卡片 */}
        <div className="dashboard-stats">
          <Card className="dashboard-stat-card" size="small">
            <div className="stat-icon" style={{ background: 'var(--brand-gradient)' }}>
              <AppstoreOutlined />
            </div>
            <div>
              <div className="stat-value">{workflows.length}</div>
              <div className="stat-label">工作流</div>
            </div>
          </Card>
          <Card className="dashboard-stat-card" size="small">
            <div className="stat-icon" style={{ background: '#059669' }}>
              <ThunderboltOutlined />
            </div>
            <div>
              <div className="stat-value">{dagCount}</div>
              <div className="stat-label">DAG 引擎</div>
            </div>
          </Card>
          <Card className="dashboard-stat-card" size="small">
            <div className="stat-icon" style={{ background: '#7c3aed' }}>
              <ShareAltOutlined />
            </div>
            <div>
              <div className="stat-value">{langgraphCount}</div>
              <div className="stat-label">LangGraph</div>
            </div>
          </Card>
        </div>

        {/* 模型配置 */}
        {configs.length > 0 && (
          <Card
            title="模型配置"
            className="dashboard-config-card"
            style={{ marginBottom: 20 }}
          >
            <div className="dashboard-config-grid">
              {configs.map((c) => (
                <div key={c.id} className="dashboard-config-item">
                  <div className="dashboard-config-item-top">
                    <span className="dashboard-config-provider">{c.provider}</span>
                    {c.isDefault === 1 && <Tag color="blue" style={{ fontSize: 10, lineHeight: '18px' }}>默认</Tag>}
                    {c.ttsModel && <Tag color="green" style={{ fontSize: 10, lineHeight: '18px' }}>TTS</Tag>}
                  </div>
                  <div className="dashboard-config-model">{c.model}</div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* 最近工作流 */}
        <Card
          title="最近工作流"
          className="dashboard-workflow-card"
          extra={
            workflows.length > 6 && (
              <Button type="link" size="small">
                查看全部 <ArrowRightOutlined />
              </Button>
            )
          }
        >
          <Spin spinning={loading}>
            {recentWorkflows.length === 0 ? (
              <div className="dashboard-empty">
                <AppstoreOutlined style={{ fontSize: 48, opacity: 0.3 }} />
                <p>暂无工作流，点击上方按钮创建第一个</p>
              </div>
            ) : (
              <div className="dashboard-workflow-grid">
                {recentWorkflows.map((w) => (
                  <div
                    key={w.id}
                    className="dashboard-workflow-item"
                    onClick={() => navigate(`/editor/${w.id}`)}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="dashboard-workflow-item-top">
                      <div className="dashboard-workflow-icon">
                        <AppstoreOutlined />
                      </div>
                      <div className="dashboard-workflow-info">
                        <div className="dashboard-workflow-name">{w.name}</div>
                        <div className="dashboard-workflow-meta">
                          {w.description || '无描述'}
                        </div>
                      </div>
                      <ArrowRightOutlined className="dashboard-workflow-arrow" />
                    </div>
                    <div className="dashboard-workflow-item-bottom">
                      <Tag color={w.engineType === 'langgraph' ? 'purple' : 'blue'}>
                        {w.engineType === 'langgraph' ? 'LangGraph' : 'DAG'}
                      </Tag>
                      <span className="dashboard-workflow-time">{formatDate(w.updatedAt)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Spin>
        </Card>
      </div>
    </div>
  );
};

export default DashboardPage;
