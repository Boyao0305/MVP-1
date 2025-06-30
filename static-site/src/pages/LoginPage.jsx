import { useState } from 'react';
import { saveUser } from '../utils/auth';

export default function LoginPage({ onLoginSuccess, onSwitchToRegister }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch('https://masterwordai.com/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username,
          password,
        }),
      });

      if (!response.ok) {
        throw new Error('用户名或密码不正确');
      }

      const data = await response.json();

      if (data.id) {
        await saveUser({
          id: data.id,
          username,
          password,
        });
      }

      onLoginSuccess();

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="main-bg">
      <div className="register-card">
        <h2 className="register-title">欢迎回来</h2>
        <form onSubmit={handleSubmit} className="register-form">
          <div className="form-group">
            <label htmlFor="username">账号</label>
            <input
              type="text"
              id="username"
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">密码</label>
            <input
              type="password"
              id="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && <p className="form-error">{error}</p>}

          <button type="submit" className="form-button" disabled={loading}>
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
        <div className="switch-auth-section">
          <p>还没有账号？</p>
          <button onClick={onSwitchToRegister} className="switch-auth-btn">
            前往注册
          </button>
        </div>
      </div>
    </div>
  );
} 