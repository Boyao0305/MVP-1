import { useState } from 'react';
import { getUser } from '../utils/auth';

const ratings = [
  { level: 1, text: '没法读' },
  { level: 2, text: '不好看' },
  { level: 3, text: '一般' },
  { level: 4, text: '挺好的' },
  { level: 5, text: '精彩' },
];

export default function AppreciationPage({ logId, onFinish, isLastArticle }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleRatingSubmit = async (level) => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`https://masterwordai.com/api/appreciation/${logId}/${level}`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('评分失败，请稍后重试。');
      }
      setIsSubmitted(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFinishStudy = async () => {
    setLoading(true);
    setError('');
    
    const userData = await getUser();
    if (!userData || !userData.id) {
      setError('无法获取用户信息，请重新登录。');
      setLoading(false);
      return;
    }

    try {
      await fetch(`https://masterwordai.com/api/finish_study/${userData.id}`, {
        method: 'POST',
      });
      // We proceed even if this fails, as it's a non-critical logging action.
    } catch (err) {
      // Log error to console but don't block user
      console.error('Failed to log finish_study:', err);
    }

    sessionStorage.removeItem('learning_logs');
    onFinish();
  };

  if (isSubmitted) {
    return (
      <div className="main-bg">
        <div className="appreciation-card">
          <h2 className="appreciation-thanks">谢谢！</h2>
          {isLastArticle ? (
            <button onClick={handleFinishStudy} className="form-button" disabled={loading}>
              {loading ? '正在生成明天的学习计划… 请明天再继续学习哦' : '结束学习'}
            </button>
          ) : (
            <button onClick={onFinish} className="form-button">
              继续学习
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="main-bg">
      <div className="appreciation-card">
        <h2 className="appreciation-title">请给今天的文章评分</h2>
        <div className="appreciation-options">
          {ratings.map(rating => (
            <button
              key={rating.level}
              className="selection-btn"
              disabled={loading}
              onClick={() => handleRatingSubmit(rating.level)}
            >
              {rating.text}
            </button>
          ))}
        </div>
        {error && <p className="form-error">{error}</p>}
      </div>
    </div>
  );
} 