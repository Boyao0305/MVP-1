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

export default function HomePage() {
  const [level,setLevel] = useState(1);
  const [topic,setTopic] = useState('Tech');
  const navigate = useNavigate();

  const go = () => {
    navigate(`/learn?level=${level}&topic=${topic}`);
  };

  return (
    <div style={{maxWidth:600,margin:'4rem auto',textAlign:'center'}}>
      <h1>背单词神器</h1>
      <div style={{marginTop:'2rem'}}>
        <select value={level} onChange={e=>setLevel(e.target.value)}>
          {difficultyOptions.map(opt=><option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
        <select style={{marginLeft:'1rem'}} value={topic} onChange={e=>setTopic(e.target.value)}>
          {topicOptions.map(t=><option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <button style={{marginTop:'2rem'}} onClick={go}>继续</button>
    </div>
  );
}
