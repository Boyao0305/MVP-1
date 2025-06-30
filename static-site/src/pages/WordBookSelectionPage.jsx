import { useState } from 'react';
import LoadingBar from '../components/LoadingBar';
import { getUser } from '../utils/auth';

const wordBooks = [
  { id: 3, name: '四级' },
  { id: 4, name: '六级' },
  { id: 2, name: '高中' },
  { id: 1, name: '初中' },
  { id: 8, name: '雅思' },
  { id: 7, name: '考研' },
  { id: 5, name: '专四' },
  { id: 6, name: '专八' },
  { id: 9, name: '托福' },
];

const dailyGoals = [
  { id: 10, name: '一篇文章 (10个单词)' },
  { id: 20, name: '两篇文章 (20个单词)' },
  { id: 30, name: '三篇文章 (30个单词)' },
];

export default function WordBookSelectionPage({ onSelectionSuccess, onBack }) {
  const [selectedBook, setSelectedBook] = useState(wordBooks[0].id);
  const [selectedGoal, setSelectedGoal] = useState(dailyGoals[0].id);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setError('');
    setLoading(true);

    const userData = await getUser();
    if (!userData || !userData.id) {
      setError('无法获取用户信息，请重新登录。');
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`https://masterwordai.com/api/account_initiation/${userData.id}/${selectedBook}/${selectedGoal}`, {
        method: 'POST', // Assuming POST, as it's an initiation action.
      });

      if (!response.ok) {
        throw new Error('设置失败，请稍后重试。');
      }

      onSelectionSuccess();

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="main-bg">
      <div className="selection-card">
        <h2 className="selection-title">制定学习计划</h2>
        
        <div className="selection-group">
          <label>选择单词本</label>
          <div className="selection-options">
            {wordBooks.map(book => (
              <button
                key={book.id}
                className={`selection-btn ${selectedBook === book.id ? 'active' : ''}`}
                onClick={() => setSelectedBook(book.id)}
              >
                {book.name}
              </button>
            ))}
          </div>
        </div>

        <div className="selection-group">
          <label>选择每日目标</label>
          <div className="selection-options">
            {dailyGoals.map(goal => (
              <button
                key={goal.id}
                className={`selection-btn ${selectedGoal === goal.id ? 'active' : ''}`}
                onClick={() => setSelectedGoal(goal.id)}
              >
                {goal.name}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="form-error">{error}</p>}

        {loading && <LoadingBar />}

        <button onClick={handleSubmit} className="form-button" disabled={loading}>
          {loading ? '正在制定学习计划' : '确定'}
        </button>

        {onBack && (
          <button onClick={onBack} className="switch-auth-btn" style={{ marginTop: '15px' }}>
            返回
          </button>
        )}
      </div>
    </div>
  );
} 