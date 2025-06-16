import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

export default function WordsPage() {
  const [searchParams] = useSearchParams();
  const level = searchParams.get('level');
  const topic = searchParams.get('topic');
  const [words,setWords] = useState([]);
  const [loading,setLoading] = useState(false);
  const [learningLogId,setLearningLogId] = useState(
    localStorage.getItem('learning_log_id') || null
  );
  const navigate = useNavigate();

  const fetchWords = useCallback(async ()=>{
    if(!level || !topic) return;
    setLoading(true);
    try{
      const res = await fetch(`http://localhost/api/words/generate/${level}/${topic}`,{
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
    <div style={{maxWidth:800,margin:'2rem auto',padding:'0 1rem',background:'#f4f8ff',borderRadius:'16px',boxShadow:'0 2px 8px #6495ed22'}}>
      <h2 style={{color:'#6495ED'}}>Level {level} · {topic}</h2>
      {learningLogId && <p>学习日志 ID: {learningLogId}</p>}
      {loading ? <p>加载中…</p> :
        <ul style={{paddingLeft:0,listStyle:'none'}}>
          {words.map(w=>(
            <li key={w.id} style={{marginBottom:'0.5rem',padding:'0.5rem 1rem',borderRadius:'8px',background:'#fff',boxShadow:'0 1px 4px #6495ed11'}}>
              <strong style={{color:'#6495ED'}}>{w.word}</strong> — {w.definition ?? '（暂无中文释义）'}
            </li>
          ))}
        </ul>
      }
      <div style={{marginTop:'1.5rem'}}>
        <button onClick={fetchWords} style={{background:'#6495ED',color:'#fff',border:'none',borderRadius:'999px',padding:'0.6rem 2rem',fontSize:'1rem',cursor:'pointer',marginRight:'1rem',boxShadow:'0 2px 8px #6495ed33'}}>换一批</button>
        {learningLogId && words.length > 0 && !loading && (
          <button style={{background:'#6495ED',color:'#fff',border:'none',borderRadius:'999px',padding:'0.6rem 2rem',fontSize:'1rem',cursor:'pointer',boxShadow:'0 2px 8px #6495ed33'}} onClick={() => navigate(`/article?log_id=${learningLogId}`)}>下一步</button>
        )}
      </div>
    </div>
  );
}