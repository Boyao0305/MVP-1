import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

export default function WordsPage() {
  const [searchParams] = useSearchParams();
  const level = searchParams.get('level');
  const topic = searchParams.get('topic');
  const [words,setWords] = useState([]);
  const [loading,setLoading] = useState(false);
  const [learningLogId,setLearningLogId] = useState(
    localStorage.getItem('learning_log_id') || null
  );

  const fetchWords = useCallback(async ()=>{
    if(!level || !topic) return;
    setLoading(true);
    try{
      const res = await fetch(`http://localhost/words/generate/${level}/${topic}`,{
        method:'POST',
        headers:{
          'Content-Type':'application/json'
        }
      });
      const data = await res.json();
      setWords(data.words || []);
      setLearningLogId(data.learning_log_id);
      localStorage.setItem('learning_log_id',data.learning_log_id);
    }catch(err){
      console.error(err);
    }finally{
      setLoading(false);
    }
  },[level,topic]);

  useEffect(()=>{
    fetchWords();
  },[fetchWords]);

  return (
    <div style={{maxWidth:800,margin:'2rem auto',padding:'0 1rem'}}>
      <h2>Level {level} · {topic}</h2>
      {learningLogId && <p>学习日志 ID: {learningLogId}</p>}
      {loading ? <p>加载中…</p> :
        <ul>
          {words.map(w=>(
            <li key={w.id} style={{marginBottom:'0.5rem'}}>
              <strong>{w.word}</strong> — {w.definition ?? '（暂无中文释义）'}
            </li>
          ))}
        </ul>
      }
      <button onClick={fetchWords}>换一批</button>
    </div>
  );
}