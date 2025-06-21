import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';

export default function ArticlePage() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const logId = searchParams.get('log_id');
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const controllerRef = useRef(null);

  // For translation popup
  const [popup, setPopup] = useState({ word: '', defs: [], coords: null });
  const popupRef = useRef();
  const preRef = useRef();
  const wordRefs = useRef({});

  // Get learned words from navigation state
  const learnedWords = (location.state && location.state.learnedWords) || [];

  useEffect(() => {
    if (!logId) return;
    setLoading(true);
    controllerRef.current = new AbortController();
    fetch(`/api/generate_artical/${logId}`, {
      method: 'POST',
      signal: controllerRef.current.signal
    })
      .then(async res => {
        if (!res.body) throw new Error('No response body');
        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let result = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          result += decoder.decode(value, { stream: true });
          setText(result);
        }
        setLoading(false);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setText('加载失败: ' + err.message);
          setLoading(false);
        }
      });
    return () => controllerRef.current?.abort();
  }, [logId]);

  // Helper to render each word, highlighting learned words, and making all English words clickable
  function renderArticleWithHighlights(str) {
    // Remove all asterisks from the text
    str = str.replace(/\*/g, '');
    // Split by word boundaries, keep punctuation
    return str.split(/(\b)/).map((w, idx) => {
      // Only match English words
      if (/^[A-Za-z][A-Za-z'-]*$/.test(w)) {
        const isLearned = learnedWords.map(lw => lw.toLowerCase()).includes(w.toLowerCase());
        return (
          <span
            key={idx}
            ref={el => { if (el) wordRefs.current[w + '-' + idx] = el; }}
            style={{
              cursor: 'pointer',
              background: popup.word === w && popup.coords ? '#6495ED22' : undefined,
              borderRadius: '4px',
              position: 'relative',
              color: isLearned ? '#6495ED' : undefined,
              fontWeight: isLearned ? 700 : undefined
            }}
            onClick={e => handleWordClick(w, idx)}
          >
            {w}
          </span>
        );
      }
      return w;
    });
  }

  // Handle word click
  function handleWordClick(word, idx) {
    // If popup is open, close it on any word click
    if (popup.coords) {
      setPopup({ word: '', defs: [], coords: null });
      return;
    }
    // Otherwise, open popup for the word
    const wordEl = wordRefs.current[word + '-' + idx];
    const preEl = preRef.current;
    if (wordEl && preEl) {
      const wordRect = wordEl.getBoundingClientRect();
      const preRect = preEl.getBoundingClientRect();
      const left = wordRect.left - preRect.left + wordRect.width / 2;
      const top = wordRect.bottom - preRect.top;
      setPopup({ word, defs: [], coords: { left, top } });
      // Fetch definition
      fetch(`/api/word_search/${encodeURIComponent(word)}`)
        .then(res => res.json())
        .then(defStr => setPopup(p => ({ ...p, defs: [defStr] })))
        .catch(() => setPopup(p => ({ ...p, defs: ['查词失败'] })));
    }
  }

  // Hide popup on click outside
  useEffect(() => {
    function onClick(e) {
      setPopup({ word: '', defs: [], coords: null });
    }
    if (popup.coords) {
      document.addEventListener('mousedown', onClick);
      return () => document.removeEventListener('mousedown', onClick);
    }
  }, [popup.coords]);

  return (
    <div style={{maxWidth:800,margin:'2rem auto',padding:'0 1rem',background:'#f4f8ff',borderRadius:'16px',boxShadow:'0 2px 8px #6495ed22',position:'relative'}}>
      <div style={{marginBottom:'1rem',color:'#6495ED',fontWeight:600,fontSize:'1rem'}}>点击单词查词</div>
      <h2 style={{color:'#6495ED'}}>生成的文章</h2>
      {loading && <p>生成中…</p>}
      <pre ref={preRef} style={{whiteSpace:'pre-wrap',overflowWrap:'break-word',wordBreak:'normal',background:'#fff',padding:'1.5rem',borderRadius:'12px',minHeight:'200px',fontSize:'1.1rem',boxShadow:'0 1px 4px #6495ed11',position:'relative',fontFamily:'Segoe UI, Arial, sans-serif',textAlign:'justify'}}>
        {renderArticleWithHighlights(text)}
      </pre>
      {popup.coords && (
        <div
          ref={popupRef}
          style={{
            position: 'absolute',
            left: popup.coords.left,
            top: popup.coords.top + 4,
            transform: 'translate(-50%, 0)',
            minWidth: 120,
            maxWidth: 260,
            background: '#fff',
            color: '#333',
            border: '1px solid #6495ED',
            borderRadius: 8,
            boxShadow: '0 2px 8px #6495ed22',
            padding: '0.5rem 1rem',
            zIndex: 1000,
            fontSize: '1rem',
            pointerEvents: 'auto',
          }}
        >
          <div style={{color:'#6495ED',fontWeight:600,marginBottom:4}}>{popup.word}</div>
          <div>{popup.defs.length ? popup.defs.join(', ') : '加载中…'}</div>
        </div>
      )}
    </div>
  );
} 