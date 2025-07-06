import { useEffect, useState, useRef, useMemo } from 'react'

// Checks if a word is a variant of any word in the review set.
// Handles simple plural (-s) and verb (-ing) forms.
const isReviewWord = (wordToCheck, reviewWordsSet) => {
  const lowerWord = wordToCheck.toLowerCase();
  if (reviewWordsSet.has(lowerWord)) return true;

  // Check for plural form: 'goals' vs 'goal'
  if (lowerWord.endsWith('s') && reviewWordsSet.has(lowerWord.slice(0, -1))) {
    return true;
  }

  // Check for -ing form: 'doing' vs 'do'
  if (lowerWord.endsWith('ing')) {
    // 'do' + 'ing' -> 'doing'
    if (reviewWordsSet.has(lowerWord.slice(0, -3))) {
      return true;
    }
    // 'hope' + 'ing' -> 'hoping' (handles words ending in 'e')
    if (reviewWordsSet.has(lowerWord.slice(0, -3) + 'e')) {
      return true;
    }
  }

  return false;
};

const parseArticle = (text, reviewWords = []) => {
  let title = '';
  let content = text;

  const titleRegex = /^\s*\*\*(.*?)\*\*/;
  const match = text.match(titleRegex);

  if (match) {
    title = match[1];
    content = text.replace(titleRegex, '').trim();
  }

  const reviewWordsSet = new Set(reviewWords.map(w => w.word.toLowerCase()));

  const highlightedContent = content.replace(/\*\*(.*?)\*\*/g, (match, word) => {
    // if (isReviewWord(word, reviewWordsSet)) {
    //   return word; // It's a review word, so don't highlight.
    // }
    return `<span class="highlight">${word}</span>`; // It's a new word, highlight it.
  });


  return { title, highlightedContent };
};

const ReadingPage = ({ log, onArticleCompleted, onFinishEarly, dailyGoal, articlesReadCount }) => {
  const [rawArticle, setRawArticle] = useState('');
  const [articleTitle, setArticleTitle] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [popup, setPopup] = useState({ visible: false, type: 'definition', content: '', x: 0, y: 0, word: null });
  const [queryButton, setQueryButton] = useState({ visible: false, text: '', rect: null });
  const [phrasePopup, setPhrasePopup] = useState({ visible: false, content: '', x: 0, y: 0 });
  const [isFinishing, setIsFinishing] = useState(false);
  const [clickedWords, setClickedWords] = useState(new Set());
  const contentRef = useRef(null);
  const popupRef = useRef(null);
  const queryButtonRef = useRef(null);
  const phrasePopupRef = useRef(null);

  const processTextForClicking = (htmlString, clickedWords) => {
    if (typeof window === 'undefined' || !htmlString) return '';
    const container = document.createElement('div');
    container.innerHTML = htmlString;

    const walk = (node) => {
      if (node.nodeType === 3) { // Text node
        const text = node.nodeValue;
        const fragment = document.createDocumentFragment();
        text.split(/([a-zA-Z'-]+)/g).forEach(part => {
          if (part.match(/^[a-zA-Z'-]+$/)) {
            const span = document.createElement('span');
            span.style.cursor = 'pointer';
            span.textContent = part;
            if (clickedWords.has(part.toLowerCase())) {
              span.style.color = 'red';
            }
            fragment.appendChild(span);
          } else {
            fragment.appendChild(document.createTextNode(part));
          }
        });
        if (node.parentNode) {
          node.parentNode.replaceChild(fragment, node);
        }
      } else if (node.nodeType === 1) { // Element node
        if (node.tagName === 'SPAN' && node.classList.contains('highlight')) {
          node.style.cursor = 'pointer';
        }
        Array.from(node.childNodes).forEach(walk);
      }
    };

    walk(container);
    return container.innerHTML;
  }

  const searchWord = async (word, x, y) => {
    setPopup({ visible: true, type: 'definition', content: 'Searching...', x, y, word });

    try {
      const response = await fetch(`api/word_search/${log.id}/${word}`);
      if (!response.ok) throw new Error('Word not found');
      const resultText = await response.text();
      setPopup(p => ({ ...p, content: resultText, visible: true }));
    } catch (err) {
      setPopup(p => ({ ...p, content: 'Definition not found.', visible: true }));
    }
  };

  const finalContent = useMemo(() => {
    if (!rawArticle) return '';
    let content = rawArticle;
    const titleRegex = /^\s*\*\*(.*?)\*\*/;
    content = content.replace(titleRegex, '').trim();
    const highlightedContent = content.replace(/\*\*(.*?)\*\*/g, (match, word) => {
      return `<span class="highlight">${word}</span>`;
    });
    return processTextForClicking(highlightedContent, clickedWords);
  }, [rawArticle, clickedWords]);

  const clickableTitle = useMemo(() => {
    if (!articleTitle) return '\u00A0';
    return processTextForClicking(articleTitle, clickedWords);
  }, [articleTitle, clickedWords]);


  useEffect(() => {
    let isMounted = true
    setRawArticle('')
    setArticleTitle('');
    setClickedWords(new Set());
    setLoading(true)
    setError(null)

    let result = ''
    let buffer = ''
    let timeoutId = null

    const flushBuffer = () => {
      if (buffer.length > 0 && isMounted) {
        result += buffer
        const titleRegex = /^\s*\*\*(.*?)\*\*/;
        const match = result.match(titleRegex);
        if (match && match[1]) {
          setArticleTitle(match[1]);
        }
        setRawArticle(result);
        buffer = ''
      }
      timeoutId = null
    }

    fetch(`api/generation/${log.id}`, {
      method: 'POST',
    }).then(response => {
      if (!response.body) throw new Error('No stream')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      
      function read() {
        reader.read().then(({ done, value }) => {
          if (done) {
            if (timeoutId) clearTimeout(timeoutId)
            flushBuffer()
            if (isMounted) setLoading(false)
            return
          }
          const chunk = decoder.decode(value, { stream: true })
          buffer += chunk
          
          if (!timeoutId) {
            timeoutId = setTimeout(flushBuffer, 300)
          }

          read()
        })
      }
      read()
    }).catch(e => {
      if (isMounted) {
        setError('加载文章失败')
        setLoading(false)
      }
    })

    return () => {
      isMounted = false
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [log.id])

  useEffect(() => {
    const handleInteractionEnd = () => {
      // Use a short timeout to allow the browser's selection to update fully.
      setTimeout(() => {
        const selection = window.getSelection();
        if (!selection) return;

        // Case 1: A range of text was selected (phrase search).
        if (selection.type === 'Range') {
          const selectedText = selection.toString().trim();
          if (selectedText.length > 0) {
            const range = selection.getRangeAt(0);
            const rect = range.getBoundingClientRect();
            setQueryButton({ visible: true, text: selectedText, rect });
            // Hide other popups to avoid overlap.
            setPopup({ visible: false, type: 'definition', content: '', x: 0, y: 0, word: null });
          }
          return; // Stop processing to avoid conflicts.
        }

        // Case 2: A single point was clicked (word search).
        if (selection.type === 'Caret') {
          const parentElement = selection.anchorNode.parentElement;
          // Ensure the click was on a clickable word span.
          if (parentElement && parentElement.tagName === 'SPAN' && parentElement.style.cursor === 'pointer') {
            const word = parentElement.innerText.trim().toLowerCase().replace(/[.,!?:;]$/, '');

            if (word && word.length > 1 && !/^\d+$/.test(word)) {
              const rect = parentElement.getBoundingClientRect();
              let x = rect.left + (rect.width / 2);
              let y = rect.bottom + window.scrollY;
              
              const popupWidth = 220;
              if (x - (popupWidth / 2) < 10) x = (popupWidth / 2) + 10;
              if (x + (popupWidth / 2) > window.innerWidth - 10) x = window.innerWidth - (popupWidth / 2) - 10;
              
              setQueryButton({ visible: false, text: '', rect: null });

              if (clickedWords.has(word)) {
                setPopup({ visible: true, type: 'options', word: word, x, y, content: '' });
              } else {
                setClickedWords(prev => new Set(prev).add(word));
                searchWord(word, x, y);
              }
            }
          }
        }
      }, 50);
    };

    document.addEventListener('mouseup', handleInteractionEnd);
    document.addEventListener('touchend', handleInteractionEnd);
    return () => {
      document.removeEventListener('mouseup', handleInteractionEnd);
      document.removeEventListener('touchend', handleInteractionEnd);
    };
  }, [clickedWords]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        popupRef.current?.contains(event.target) ||
        queryButtonRef.current?.contains(event.target) ||
        phrasePopupRef.current?.contains(event.target)
      ) {
        return;
      }
      setPopup(p => ({ ...p, visible: false }));
      setQueryButton(q => ({ ...q, visible: false }));
      setPhrasePopup(p => ({ ...p, visible: false }));
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleRemoveMark = async () => {
    if (!popup.word) return;
    const wordToRemove = popup.word;
    
    setClickedWords(prev => {
      const newSet = new Set(prev);
      newSet.delete(wordToRemove);
      return newSet;
    });
    setPopup({ visible: false, type: 'definition', content: '', x: 0, y: 0, word: null });
    
    try {
      await fetch(`api/word_unsearch/${log.id}/${wordToRemove}`);
    } catch (err) {
      console.error("Failed to unsearch word:", err);
    }
  };
  
  const handleSearchAgain = async () => {
      if (!popup.word) return;
      await searchWord(popup.word, popup.x, popup.y);
  };

  const handleFinishClick = async () => {
    setIsFinishing(true);
    try {
      const response = await fetch(`api/finish_reading/${log.id}`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('操作失败，请重试。');
      }
      onArticleCompleted(log.id);
    } catch (err) {
      setError(err.message);
      setIsFinishing(false);
    }
  };

  const handleFinishEarlyClick = async () => {
    setIsFinishing(true);
    try {
      const response = await fetch(`api/finish_reading/${log.id}`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('操作失败，请重试。');
      }
      onFinishEarly(log.id);
    } catch (err) {
      setError(err.message);
      setIsFinishing(false);
    }
  };
  
  const articlesPerDay = dailyGoal / 10;
  const isLastArticle = articlesReadCount + 1 >= articlesPerDay;

  const handlePhraseSearch = async () => {
    const text = queryButton.text;
    const rect = queryButton.rect;
    if (!text || !rect) return;

    setQueryButton({ visible: false, text: '', rect: null });

    let x = rect.left + (rect.width / 2);
    let y = rect.bottom + window.scrollY;
    const popupWidth = 220;
    if (x - popupWidth / 2 < 10) x = popupWidth / 2 + 10;
    if (x + popupWidth / 2 > window.innerWidth - 10) x = window.innerWidth - popupWidth / 2 - 10;
    
    setPhrasePopup({ visible: true, content: 'Searching...', x, y });

    const category = text.split(/\s+/).length > 5 ? 'phrase' : 'word_group';
    
    try {
      const response = await fetch(`api/content_search/${category}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text })
      });
      if (!response.body) throw new Error('No stream');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let result = '';
      setPhrasePopup(p => ({ ...p, content: '' }));

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        result += chunk;
        setPhrasePopup(p => ({ ...p, content: result }));
      }
    } catch (err) {
      setPhrasePopup(p => ({ ...p, content: 'Search failed.' }));
    }
  };

  return (
    <div className="main-bg">
      <div className="reading-card">
        <div className="reading-info-bar">
          tips: 请阅读文章并查询不认识的单词，我们会根据您的反馈提供个性化的学习体验
        </div>
        <h2 className="reading-title" dangerouslySetInnerHTML={{ __html: clickableTitle }} />
        <div
          className="reading-content"
        >
          {loading && !finalContent ? (
            <div className="reading-loading">正在生成文章...</div>
          ) : (
            <div dangerouslySetInnerHTML={{ __html: (finalContent || '').replace(/\n/g, '<br />') }} />
          )}
        </div>
        {error && <div className="reading-error">{error}</div>}
        
        <div className="reading-footer">
          {isFinishing ? (
            <button className="form-button" disabled>请稍候...</button>
          ) : isLastArticle ? (
            <button className="form-button" onClick={handleFinishClick} disabled={loading}>
              完成今日学习
            </button>
          ) : (
            <div className="btn-row" style={{ justifyContent: 'space-around', width: '100%' }}>
              <button className="btn-outline" onClick={handleFinishEarlyClick} disabled={loading}>
                提前完成学习
              </button>
              <button className="btn-main" onClick={handleFinishClick} disabled={loading} style={{ flexGrow: 1, marginLeft: '12px' }}>
                继续阅读
              </button>
            </div>
          )}
        </div>
      </div>

      {popup.visible && (
        <div 
          className="word-popup" 
          ref={popupRef} 
          style={{ top: `${popup.y + 10}px`, left: `${popup.x}px` }}
          onMouseUp={e => e.stopPropagation()}
        >
          {popup.type === 'options' ? (
            <div className="popup-options">
              <button onClick={handleRemoveMark} className="popup-option-btn">消除标记</button>
              <button onClick={handleSearchAgain} className="popup-option-btn">再查一遍</button>
            </div>
          ) : (
            popup.content
          )}
        </div>
      )}

      {queryButton.visible && (
        <button
          ref={queryButtonRef}
          className="query-btn"
          style={{
            top: `${queryButton.rect.bottom + window.scrollY + 5}px`,
            left: `${queryButton.rect.left + window.scrollX + (queryButton.rect.width / 2) - 40}px`,
          }}
          onClick={handlePhraseSearch}
        >
          查询
        </button>
      )}

      {phrasePopup.visible && (
        <div
          ref={phrasePopupRef}
          className="word-popup"
          style={{ top: `${phrasePopup.y + 10}px`, left: `${phrasePopup.x}px` }}
          onMouseUp={e => e.stopPropagation()}
        >
          {phrasePopup.content}
        </div>
      )}
    </div>
  )
}

export default ReadingPage 