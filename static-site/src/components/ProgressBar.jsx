export default function ProgressBar({ learning, learned }) {
  return (
    <div style={{ width: '80%', margin: '24px auto 16px', height: 16, background: '#e6eaf6', borderRadius: 8, position: 'relative' }}>
      <div style={{
        position: 'absolute',
        left: 0,
        top: 0,
        height: '100%',
        width: `${learned * 100}%`,
        background: 'rgb(100, 149, 237)',
        opacity: 0.7,
        borderRadius: 8,
        zIndex: 1,
        transition: 'width 0.5s',
      }} />
      <div style={{
        position: 'absolute',
        left: 0,
        top: 0,
        height: '100%',
        width: `${learning * 100}%`,
        background: 'rgb(100, 149, 237)',
        opacity: 1,
        borderRadius: 8,
        zIndex: 2,
        transition: 'width 0.5s',
      }} />
    </div>
  )
} 