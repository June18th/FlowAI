import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import EditorPage from './pages/EditorPage';
import KnowledgePage from './pages/KnowledgePage';
import McpToolPage from './pages/McpToolPage';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { useDarkMode } from './hooks/useDarkMode';

function App() {
  const { isDark } = useDarkMode();

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: isDark ? {
          colorText: '#e2e8f0',
          colorTextQuaternary: '#94a3b8',
          colorTextDisabled: '#94a3b8',
          colorBgContainer: '#242b3b',
          colorBorder: '#38405a',
        } : {},
        components: isDark ? {
          Button: {
            defaultColor: '#e2e8f0',
            defaultBorderColor: '#334155',
            defaultBg: '#242b3b',
            defaultHoverBorderColor: '#38bdf8',
            defaultHoverColor: '#38bdf8',
          },
        } : {},
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<DashboardPage />} />
          <Route path="/editor" element={<EditorPage />} />
          <Route path="/editor/:id" element={<EditorPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/mcp-tools" element={<McpToolPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
