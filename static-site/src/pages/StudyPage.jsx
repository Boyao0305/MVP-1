export default function StudyPage({ logs, onSelect }) {
  return (
    <div className="main-bg">
      <div className="study-container">
        {logs.slice(0, 5).map((log) => (
          <button className="study-card study-card-btn" key={log.id} onClick={() => onSelect(log.id)}>
            <div className="study-title">{log.english_title}</div>
            <div className="study-subtitle">{log.chinese_title}</div>
            <div className="study-tag">{log.tag}</div>
          </button>
        ))}
      </div>
    </div>
  )
} 