import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { login } from '../api/auth';
import { useAuthStore } from '../store/authStore';

const LoginPage = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const result = await login(values);
      if (result.code === 200 && result.data) {
        message.success('登录成功');
        setAuth(result.data.token, result.data.refreshToken, result.data.user.username);
        navigate('/');
      } else {
        message.error(result.message || '登录失败');
      }
    } catch {
      message.error('登录失败,请检查网络连接');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center overflow-hidden bg-gray-900">
      {/* 动态渐变背景 */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-blue-900 to-cyan-800 animate-gradient" />

      {/* 网格装饰 */}
      <div
        className="absolute inset-0 opacity-15"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, rgba(255,255,255,0.12) 1px, transparent 0)`,
          backgroundSize: '50px 50px',
        }}
      />

      {/* 光晕装饰 */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500 rounded-full blur-[128px] opacity-20" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan-500 rounded-full blur-[128px] opacity-15" />

      {/* 玻璃态卡片 */}
      <div className="relative z-10 backdrop-blur-xl bg-white/10 rounded-2xl shadow-2xl p-10 w-[420px] border border-white/20">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white/10 mb-4">
            <img src="/flowai.svg" alt="FlowAI" className="w-10 h-10" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-1">FlowAI</h1>
          <p className="text-cyan-200 text-sm">AI Agent 可视化工作流编排平台</p>
        </div>

        <Form name="login" onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input
              prefix={<UserOutlined className="text-white/50" />}
              placeholder="用户名"
              className="bg-white/10 border-white/20 text-white placeholder:text-white/40 h-12 rounded-xl
                         hover:bg-white/15 hover:border-white/30 focus:bg-white/15"
            />
          </Form.Item>

          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password
              prefix={<LockOutlined className="text-white/50" />}
              placeholder="密码"
              className="bg-white/10 border-white/20 text-white placeholder:text-white/40 h-12 rounded-xl
                         hover:bg-white/15 hover:border-white/30"
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              className="w-full h-12 rounded-xl text-base font-medium
                         bg-gradient-to-r from-blue-500 to-cyan-500 border-0
                         hover:from-blue-400 hover:to-cyan-400"
              loading={loading}
            >
              登 录
            </Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  );
};

export default LoginPage;
