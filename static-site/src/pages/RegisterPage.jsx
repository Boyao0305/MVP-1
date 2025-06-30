import { useState } from 'react';
import { saveUser } from '../utils/auth';

export default function RegisterPage({ onRegisterSuccess, onSwitchToLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [invitationCode, setInvitationCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch('https://masterwordai.com/api/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username,
          password,
          invitation_code: invitationCode,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || '邀请码不正确');
      }

      // On success, parse the response to get the ID
      const data = await response.json();

      // Save user credentials and ID
      if (data.id) {
        await saveUser({
          id: data.id,
          username,
          password, // Note: Storing plaintext passwords is not recommended for production.
        });
      }

      onRegisterSuccess();

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="main-bg">
      <div className="register-card">
        <h2 className="register-title">欢迎来到仝文馆</h2>
        <form onSubmit={handleSubmit} className="register-form">
          <div className="form-group">
            <label htmlFor="invitationCode">邀请码</label>
            <input
              type="text"
              id="invitationCode"
              className="form-input"
              value={invitationCode}
              onChange={(e) => setInvitationCode(e.target.value)}
              required
            />
          </div>
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
            {loading ? '注册中...' : '注册'}
          </button>
        </form>
        <div className="switch-auth-section">
          <p>已有账号？</p>
          <button onClick={onSwitchToLogin} className="switch-auth-btn">
            前往登录
          </button>
        </div>
      </div>
    </div>
  );
} 