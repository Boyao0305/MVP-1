import { useState } from 'react';
import ProgressBar from '../components/ProgressBar'
import { getUser } from '../utils/auth';

const wordbookMap = {
  1: '初中',
  2: '高中',
  3: '四级',
  4: '六级',
  5: '专四',
  6: '专八',
  7: '考研',
  8: '雅思',
  9: '托福',
}

export default function HomePage({ data, loading, error, onStartStudy, onChangeWordBook, onDataRefresh, onLogout }) {
  const [isEditingGoal, setIsEditingGoal] = useState(false);
  const [isSubmittingGoal, setIsSubmittingGoal] = useState(false);
  const [goalError, setGoalError] = useState('');

  if (loading) return <div className="centered">加载中...</div>
  if (error) return <div className="centered">{error}</div>
  if (!data) return null

  const wordbook = wordbookMap[data.additional_information.word_book_id] || '未知'
  const { learning_proportion, learned_proportion, progression, total, daily_goal } = data.additional_information

  const handleGoalChange = async (newGoal) => {
    if (newGoal === daily_goal) {
      setIsEditingGoal(false);
      return;
    }
    setIsSubmittingGoal(true);
    setGoalError('');
    const userData = await getUser();
    if (!userData || !userData.id) {
      setGoalError('无法获取用户信息，请重新登录。');
      setIsSubmittingGoal(false);
      return;
    }

    try {
      const response = await fetch(`https://masterwordai.com/api/set_daily_goal/${userData.id}/${newGoal}`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('设置失败，请重试。');
      }
      await onDataRefresh();
      setIsEditingGoal(false);
    } catch (err) {
      setGoalError(err.message);
    } finally {
      setIsSubmittingGoal(false);
    }
  };

  const dailyGoals = [
    { goal: 10, text: '一篇文章' },
    { goal: 20, text: '两篇文章' },
    { goal: 30, text: '三篇文章' },
  ];

  return (
    <div className="main-bg">
      <div className="card-ui">
        <div className="section-title">当前单词本：{wordbook}</div>
        <ProgressBar learning={learning_proportion} learned={learned_proportion} />
        <div className="progress-text">学习进度: {progression}/{total} (每日{daily_goal}词)</div>
        
        {isEditingGoal ? (
          <div style={{ width: '100%', textAlign: 'center' }}>
            <div className="selection-group" style={{ marginBottom: '15px' }}>
              <label style={{ fontSize: '1rem', fontWeight: '500', color: '#333' }}>选择新的每日目标</label>
              <div className="selection-options" style={{ marginTop: '10px' }}>
                {dailyGoals.map(({ goal, text }) => (
                  <button
                    key={goal}
                    className={`selection-btn ${daily_goal === goal ? 'active' : ''}`}
                    onClick={() => handleGoalChange(goal)}
                    disabled={isSubmittingGoal}
                  >
                    {isSubmittingGoal ? '...' : text}
                  </button>
                ))}
              </div>
            </div>
            {goalError && <p className="form-error">{goalError}</p>}
            <button
              className="switch-auth-btn"
              style={{ marginTop: '5px' }}
              onClick={() => { setIsEditingGoal(false); setGoalError(''); }}
              disabled={isSubmittingGoal}
            >
              取消
            </button>
          </div>
        ) : (
          <div className="home-actions">
            <div className="home-links">
              <button className="btn-link" onClick={onChangeWordBook}>更换单词本</button>
              <button className="btn-link" onClick={() => setIsEditingGoal(true)}>更改每日目标</button>
              <button className="btn-link" onClick={onLogout}>退出登录</button>
            </div>
            <button className="btn-main btn-main-long" onClick={onStartStudy}>开始学习</button>
          </div>
        )}
      </div>
    </div>
  )
}