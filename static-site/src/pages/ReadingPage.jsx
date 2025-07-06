import { useEffect, useState, useRef, useMemo, useLayoutEffect } from 'react'

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

const ReadingPage = ({ log, onArticleCompleted, onFinishEarly, dailyGoal, articlesReadCount, userId }) => {
  const [rawArticle, setRawArticle] = useState('');
  const [articleTitle, setArticleTitle] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [popup, setPopup] = useState({ visible: false, type: 'definition', content: '', x: 0, y: 0, word: null, phrase: null, isStreaming: false, translation: '' });
  const [isFinishing, setIsFinishing] = useState(false);
  const [clickedWords, setClickedWords] = useState(new Set());
  const [isPhraseSelectionMode, setIsPhraseSelectionMode] = useState(false);
  const [phraseStartNodeId, setPhraseStartNodeId] = useState(null);
  const [highlightedPhraseNodeIds, setHighlightedPhraseNodeIds] = useState([]);
  const [explainedPhraseNodeIds, setExplainedPhraseNodeIds] = useState([]);
  const [showSelectionToast, setShowSelectionToast] = useState(false);
  const [explanationModal, setExplanationModal] = useState({ visible: false, phrase: '', explanation: '' });
  const isMouseDownRef = useRef(false);
  const contentRef = useRef(null);
  const readingCardRef = useRef(null);
  const wordCounter = useRef(0);
  const popupRef = useRef(null);

  useLayoutEffect(() => {
    if (popup.visible && popupRef.current) {
      const popupEl = popupRef.current;
      const screenWidth = window.innerWidth;
      const margin = 10;
      
      const popupWidth = popupEl.offsetWidth;

      // Calculate the ideal left position to center the popup
      let left = popup.x - popupWidth / 2;

      // Constrain the left position
      if (left < margin) {
        left = margin;
      } else if (left + popupWidth > screenWidth - margin) {
        left = screenWidth - margin - popupWidth;
      }

      popupEl.style.left = `${left}px`;
    }
  }, [popup]);

  const processTextForClicking = (htmlString, clickedWords, startNodeId, highlightedIds, explainedIds) => {
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
            const wordId = `word-${wordCounter.current++}`;
            span.id = wordId;
            span.style.cursor = 'pointer';
            span.textContent = part;
            if (clickedWords.has(part.toLowerCase())) {
              span.style.color = 'red';
            }
            if (wordId === startNodeId) {
              span.style.backgroundColor = 'rgba(100, 149, 237, 0.2)';
            }
            if (highlightedIds.includes(wordId)) {
              span.style.backgroundColor = 'yellow';
            }
            if (explainedIds.includes(wordId)) {
              span.classList.add('explained-phrase');
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
    wordCounter.current = 0;
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

  const handlePhraseSearch = async () => {
    const phrase = popup.phrase;
    if (!phrase) return;
  
    setHighlightedPhraseNodeIds([]);
    setPopup(p => ({ ...p, type: 'phrase-result', content: '', isStreaming: true }));
  
    const category = phrase.split(/\s+/).length > 5 ? 'phrase' : 'word_group';
  
    try {
      const response = await fetch(`api/content_search/${category}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: phrase }),
      });
  
      if (!response.ok || !response.body) {
        throw new Error('Search failed');
      }
  
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedResult = '';
  
      const read = () => {
        reader.read().then(({ done, value }) => {
          if (done) {
            setPopup(p => ({ ...p, isStreaming: false, translation: accumulatedResult }));
            return;
          }
          const chunk = decoder.decode(value, { stream: true });
          accumulatedResult += chunk;
          setPopup(p => {
            if (p.visible && p.type === 'phrase-result') {
              return { ...p, content: p.content + chunk };
            }
            return p;
          });
          read();
        });
      };
      read();
    } catch (err) {
      setPopup(p => ({ ...p, content: 'Search failed.', isStreaming: false }));
    }
  };

  const handlePhraseExplanation = async () => {
    if (!userId || !popup.phrase || !popup.translation) return;

    if (popup.phraseNodeIds && popup.phraseNodeIds.length > 0) {
      setExplainedPhraseNodeIds(prev => [...new Set([...prev, ...popup.phraseNodeIds])]);
    }

    const phraseToExplain = popup.phrase;
    const translation = popup.translation;

    setPopup(p => ({ ...p, visible: false }));
    setExplanationModal({ visible: true, phrase: phraseToExplain, explanation: '' });

    try {
      const response = await fetch(`api/phrase_explanation/${userId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: phraseToExplain, translation: translation }),
      });

      if (!response.ok || !response.body) {
        throw new Error('Explanation failed');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      const read = () => {
        reader.read().then(({ done, value }) => {
          if (done) {
            return;
          }
          const chunk = decoder.decode(value, { stream: true });
          setExplanationModal(prev => ({ ...prev, explanation: prev.explanation + chunk }));
          read();
        });
      };
      read();
    } catch (err) {
      setExplanationModal(prev => ({ ...prev, explanation: 'Explanation failed.' }));
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
    wordCounter.current = 0;
    return processTextForClicking(highlightedContent, clickedWords, phraseStartNodeId, highlightedPhraseNodeIds, explainedPhraseNodeIds);
  }, [rawArticle, clickedWords, phraseStartNodeId, highlightedPhraseNodeIds, explainedPhraseNodeIds]);

  const clickableTitle = useMemo(() => {
    if (!articleTitle) return '\u00A0';
    wordCounter.current = 0;
    return processTextForClicking(articleTitle, clickedWords, phraseStartNodeId, highlightedPhraseNodeIds, explainedPhraseNodeIds);
  }, [articleTitle, clickedWords, phraseStartNodeId, highlightedPhraseNodeIds, explainedPhraseNodeIds]);


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
      if (isMouseDownRef.current) {
        timeoutId = setTimeout(flushBuffer, 100);
        return;
      }
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
    // if (contentRef.current) {
    //   contentRef.current.scrollTop = contentRef.current.scrollHeight
    // }
  }, [articleTitle])

  // Effect to handle clicks outside the popup
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (popupRef.current && !popupRef.current.contains(event.target)) {
        setPopup(p => ({ ...p, visible: false }));
      }
    };

    if (popup.visible) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [popup.visible]);

  useEffect(() => {
    if (showSelectionToast) {
      const timer = setTimeout(() => setShowSelectionToast(false), 4000);
      return () => clearTimeout(timer);
    }
  }, [showSelectionToast]);

  const handleContentClick = async (event) => {
    const target = event.target;
    if (target.tagName !== 'SPAN' || !target.id.startsWith('word-')) {
      if (isPhraseSelectionMode) {
        setIsPhraseSelectionMode(false);
        setPhraseStartNodeId(null);
        setHighlightedPhraseNodeIds([]);
      }
      return;
    }

    if (isPhraseSelectionMode) {
      if (!phraseStartNodeId) {
        setPhraseStartNodeId(target.id);
      } else {
        const allSpans = Array.from(readingCardRef.current.querySelectorAll('span[id^="word-"]'));
        const startIndex = allSpans.findIndex(s => s.id === phraseStartNodeId);
        const endIndex = allSpans.findIndex(s => s.id === target.id);

        setPhraseStartNodeId(null);
        setIsPhraseSelectionMode(false);

        if (startIndex !== -1 && endIndex !== -1 && endIndex >= startIndex) {
          const selectedSpans = allSpans.slice(startIndex, endIndex + 1);
          const phrase = selectedSpans.map(s => s.textContent).join(' ');
          const idsToHighlight = selectedSpans.map(s => s.id);
          setHighlightedPhraseNodeIds(idsToHighlight);
          
          const rect = target.getBoundingClientRect();
          const x = rect.left + rect.width / 2;
          const y = rect.bottom + window.scrollY;

          setPopup({
            visible: true,
            type: 'phrase-search',
            phrase: phrase,
            phraseNodeIds: idsToHighlight,
            x, y,
            content: '', word: null, isStreaming: false, translation: ''
          });
        }
      }
      return;
    }

    const word = target.innerText.trim().toLowerCase().replace(/[.,!?:;]$/, '');

    if (word && word.length > 1 && !/^\d+$/.test(word)) {
      const rect = target.getBoundingClientRect();
      let x = rect.left + (rect.width / 2);
      let y = rect.bottom + window.scrollY;

      const popupWidth = 220;
      if (x - (popupWidth / 2) < 10) x = (popupWidth / 2) + 10;
      if (x + (popupWidth / 2) > window.innerWidth - 10) x = window.innerWidth - (popupWidth / 2) - 10;
      
      if (clickedWords.has(word)) {
        setPopup({
          visible: true,
          type: 'options',
          word: word,
          x,
          y,
          content: ''
        });
      } else {
        setClickedWords(prev => new Set(prev).add(word));
        await searchWord(word, x, y);
      }
    }
  };

  const handleTogglePhraseSelectionMode = () => {
    setPopup({ visible: false });
    setIsPhraseSelectionMode(prev => {
      const newMode = !prev;
      if (newMode) {
        setShowSelectionToast(true);
      }
      return newMode;
    });
    setPhraseStartNodeId(null);
    setHighlightedPhraseNodeIds([]);
  }

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

  return (
    <div className="main-bg">
      <div className="reading-card" ref={readingCardRef} onClick={handleContentClick}>
        <div className="reading-info-bar">
          tips: 请阅读文章并查询不认识的单词，我们会根据您的反馈提供个性化的学习体验
        </div>
        <h2 className="reading-title" dangerouslySetInnerHTML={{ __html: clickableTitle }} />
        <div 
          className="reading-content" 
          ref={contentRef} 
        >
          {loading && !finalContent ? (
            <div className="reading-loading">正在生成文章...</div>
          ) : (
            <div dangerouslySetInnerHTML={{ __html: (finalContent || '').replace(/\n/g, '<br />') }} />
          )}
        </div>
        {error && <div className="reading-error">{error}</div>}
        
        <div className="reading-footer">
          <div className="footer-main-actions">
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
          <div className="footer-secondary-actions">
            <button onClick={handleTogglePhraseSelectionMode} className={`select-phrase-btn ${isPhraseSelectionMode ? 'active' : ''}`}>
              {isPhraseSelectionMode ? '取消选择' : '选择句子翻译'}
            </button>
          </div>
        </div>
      </div>

      {showSelectionToast && (
        <div className="selection-toast">
          点击选择句子的首尾以翻译句子
        </div>
      )}

      {/* Popups for word definitions, options, and phrase results */}
      {popup.visible && popup.type !== 'phrase-search' && (
        <div 
          className="word-popup" 
          ref={popupRef} 
          style={{ top: `${popup.y + 10}px` }}
          onMouseUp={e => e.stopPropagation()}
        >
          {popup.type === 'options' && (
            <div className="popup-options">
              <button onClick={handleRemoveMark} className="popup-option-btn">消除标记</button>
              <button onClick={handleSearchAgain} className="popup-option-btn">再查一遍</button>
            </div>
          )}
          {popup.type === 'definition' && popup.content}
          {popup.type === 'phrase-result' && (
            <div>
              {popup.content}
              {!popup.isStreaming && popup.phrase && popup.phrase.split(/\s+/).length > 5 && (
                <button onClick={handlePhraseExplanation} className="popup-explain-btn">
                  深度解析
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Standalone button for phrase search */}
      {popup.visible && popup.type === 'phrase-search' && (
        <button
          onClick={handlePhraseSearch}
          className="phrase-search-btn"
          ref={popupRef}
          style={{
            position: 'absolute',
            top: `${popup.y + 8}px`,
          }}
          onMouseUp={e => e.stopPropagation()}
        >
          查询
        </button>
      )}

      {explanationModal.visible && (
        <div className="explanation-modal-overlay">
          <div className="explanation-modal-content">
            <button
              onClick={() => setExplanationModal({ visible: false, phrase: '', explanation: '' })}
              className="explanation-modal-close-btn"
            >
              &times;
            </button>
            <h3 className="explanation-modal-phrase">{explanationModal.phrase}</h3>
            <div className="explanation-modal-explanation" dangerouslySetInnerHTML={{ __html: explanationModal.explanation.replace(/\n/g, '<br />') }} />
          </div>
        </div>
      )}
    </div>
  )
}

export default ReadingPage 