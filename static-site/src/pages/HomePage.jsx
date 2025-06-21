import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const difficultyOptions = [
  { label: '简单', value: 1 },
  { label: '中等', value: 2 },
  { label: '困难', value: 3 }
];

const topicOptions = [
  'Tech','Economy','Science','Art','History','Politics',
  'Environment','Health','Sports','Fashion','Media','Literature',
  'Education','Society','Laws','Travel'
];

const wordBookOptions = [
  { label: '初中', value: 1 },
  { label: '高中', value: 2 },
  { label: '四级', value: 3 },
  { label: '六级', value: 4 },
  { label: '专四', value: 5 },
  { label: '专八', value: 6 },
  { label: '考研', value: 7 },
  { label: '雅思', value: 8 },
  { label: '托福', value: 9 },
];

export default function HomePage() {
  const [level,setLevel] = useState(1);
  const [topic,setTopic] = useState('Tech');
  const [wordBookId, setWordBookId] = useState(1);
  const navigate = useNavigate();

  const go = () => {
    navigate(`/learn?level=${level}&topic=${topic}&word_book_id=${wordBookId}`);
  };

  return (
    <div style={{maxWidth:600,margin:'4rem auto',textAlign:'center'}}>
      <h1 style={{color:'#6495ED'}}>背单词神器</h1>
      <div style={{marginTop:'2rem'}}>
        <select value={level} onChange={e=>setLevel(e.target.value)}
          style={{padding:'0.5rem 1rem',borderRadius:'999px',border:'1px solid #6495ED',outline:'none',fontSize:'1rem',color:'#333',background:'#f4f8ff'}}>
          {difficultyOptions.map(opt=><option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
        <select style={{marginLeft:'1rem',padding:'0.5rem 1rem',borderRadius:'999px',border:'1px solid #6495ED',outline:'none',fontSize:'1rem',color:'#333',background:'#f4f8ff'}} value={topic} onChange={e=>setTopic(e.target.value)}>
          {topicOptions.map(t=><option key={t} value={t}>{t}</option>)}
        </select>
        <select style={{marginLeft:'1rem',padding:'0.5rem 1rem',borderRadius:'999px',border:'1px solid #6495ED',outline:'none',fontSize:'1rem',color:'#333',background:'#f4f8ff'}} value={wordBookId} onChange={e=>setWordBookId(Number(e.target.value))}>
          {wordBookOptions.map(opt=><option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
      </div>
      <button style={{marginTop:'2rem',background:'#6495ED',color:'#fff',border:'none',borderRadius:'999px',padding:'0.75rem 2.5rem',fontSize:'1.2rem',cursor:'pointer',boxShadow:'0 2px 8px #6495ed33'}} onClick={go}>继续</button>
    </div>
  );
}
