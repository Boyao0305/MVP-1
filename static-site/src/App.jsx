import { useEffect, useState } from 'react'
import './App.css'
import HomePage from './pages/HomePage'
import StudyPage from './pages/StudyPage'
import ReadingPage from './pages/ReadingPage'
import RegisterPage from './pages/RegisterPage'
import LoginPage from './pages/LoginPage'
import WordBookSelectionPage from './pages/WordBookSelectionPage'
import AppreciationPage from './pages/AppreciationPage'
import { getUser, clearUser } from './utils/auth'

function App() {
  const [authStatus, setAuthStatus] = useState('loading'); // loading, unauthenticated, needs_selection, authenticated
  const [authPage, setAuthPage] = useState('register'); // 'register' or 'login'
  const [userData, setUserData] = useState(null);
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState('home')
  const [readingLogId, setReadingLogId] = useState(null)
  const [articlesReadCount, setArticlesReadCount] = useState(0);
  const [readLogIds, setReadLogIds] = useState([]);

  useEffect(() => {
    const checkAuth = async () => {
      const user = await getUser();
      if (user && user.id) {
        setUserData(user);
        // This part is tricky. If they have user data, are they 'authenticated' or 'needs_selection'?
        // For now, let's assume if they exist, they are authenticated.
        // The logic might need to be adjusted based on whether they have completed the word book selection.
        // A simple way is to check if a learning log exists.
        setAuthStatus('authenticated');
      } else {
        setAuthStatus('unauthenticated');
      }
    };
    checkAuth();
  }, []);

  const fetchLearningData = (userId) => {
    if (!userId) {
      setAuthStatus('unauthenticated');
      return;
    }
    
    setLoading(true);
    setError(null);
    fetch(`https://masterwordai.com/api/daily_learning_logs/${userId}`)
      .then(res => res.json())
      .then(json => {
        setData(json)
        if (json.logs) {
          const logsToSave = json.logs.map(({ id, user_id, english_title, chinese_title, outline, daily_new_words, daily_review_words, tag }) => ({
            id, user_id, english_title, chinese_title, outline, daily_new_words, daily_review_words, tag
          }))
          sessionStorage.setItem('learning_logs', JSON.stringify(logsToSave))
        }
      })
      .catch(e => {
        setError('加载学习日志失败')
      })
      .finally(() => {
        setLoading(false)
      });
  };

  useEffect(() => {
    if (authStatus === 'authenticated' && userData) {
      fetchLearningData(userData.id);
    } else if (authStatus !== 'loading') {
      setLoading(false);
      setData(null);
    }
  }, [authStatus, userData])

  const handleLoginSuccess = async () => {
    const user = await getUser();
    setUserData(user);
    setAuthStatus('authenticated');
  };

  const handleRegisterSuccess = async () => {
    const user = await getUser();
    setUserData(user);
    setAuthStatus('needs_selection');
  };

  const handleLogout = async () => {
    await clearUser();
    setUserData(null);
    setData(null);
    setAuthStatus('unauthenticated');
    setAuthPage('login'); // Default to login page
    setPage('home'); // This will be caught by the auth guard and show login
  };

  const handleFinishAndReturnHome = () => {
    setPage('home');
    if (userData) {
      fetchLearningData(userData.id);
    }
  };

  const handleStartStudy = () => {
    setArticlesReadCount(0);
    setReadLogIds([]);
    setPage('study');
  };

  const handleArticleCompleted = (completedLogId) => {
    setArticlesReadCount(prev => prev + 1);
    setReadLogIds(prev => [...prev, completedLogId]);
    setReadingLogId(completedLogId);
    setPage('appreciation');
  };

  const handleFinishEarly = (completedLogId) => {
    // Force the articlesReadCount to the goal to signal the end of the session.
    const articlesPerDay = data?.additional_information?.daily_goal / 10 || 1;
    setArticlesReadCount(articlesPerDay);
    setReadLogIds(prev => [...prev, completedLogId]);
    setReadingLogId(completedLogId);
    setPage('appreciation');
  };

  // Authentication Flow
  if (authStatus === 'loading') {
    return <div className="centered">Loading...</div>;
  }
  if (authStatus === 'unauthenticated') {
    if (authPage === 'login') {
      return <LoginPage onLoginSuccess={handleLoginSuccess} onSwitchToRegister={() => setAuthPage('register')} />;
    }
    return <RegisterPage onRegisterSuccess={handleRegisterSuccess} onSwitchToLogin={() => setAuthPage('login')} />;
  }
  
  if (authStatus === 'needs_selection') {
    return <WordBookSelectionPage onSelectionSuccess={handleLoginSuccess} />;
  }

  if (page === 'wordbook_selection') {
    return <WordBookSelectionPage onSelectionSuccess={() => {
      setPage('home');
      if (userData) {
        fetchLearningData(userData.id);
      }
    }} onBack={() => setPage('home')} />;
  }

  // Main App Flow
  if (page === 'appreciation' && readingLogId) {
    const dailyGoal = data?.additional_information?.daily_goal || 10;
    const articlesPerDay = dailyGoal / 10;
    const isLastArticle = articlesReadCount >= articlesPerDay;

    return <AppreciationPage
      logId={readingLogId}
      onFinish={isLastArticle ? handleFinishAndReturnHome : () => setPage('study')}
      isLastArticle={isLastArticle}
      userId={userData?.id}
    />;
  }
  
  if (page === 'study') {
    const logs = (data?.logs || []).filter(l => !readLogIds.includes(l.id));
    return <StudyPage logs={logs} onSelect={(logId) => { setReadingLogId(logId); setPage('reading') }} />
  }

  if (page === 'reading' && readingLogId) {
    const log = data?.logs.find(l => l.id === readingLogId);
    if (!log) {
      // If the log isn't found (e.g., after a refresh), go back to study page.
      const logs = (data?.logs || []).filter(l => !readLogIds.includes(l.id));
      return <StudyPage logs={logs} onSelect={(logId) => { setReadingLogId(logId); setPage('reading') }} />
    }
    const dailyGoal = data?.additional_information?.daily_goal || 10;
    return <ReadingPage
      log={log}
      onArticleCompleted={handleArticleCompleted}
      onFinishEarly={handleFinishEarly}
      dailyGoal={dailyGoal}
      articlesReadCount={articlesReadCount}
    />
  }

  return (
    <HomePage
      data={data}
      loading={loading}
      error={error}
      onStartStudy={handleStartStudy}
      onChangeWordBook={() => setPage('wordbook_selection')}
      onDataRefresh={() => userData && fetchLearningData(userData.id)}
      onLogout={handleLogout}
    />
  )
}

export default App
