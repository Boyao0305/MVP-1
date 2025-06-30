import { useEffect, useState, useRef } from 'react'

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
  const [article, setArticle] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [popup, setPopup] = useState({ visible: false, content: '', x: 0, y: 0 })
  const [isFinishing, setIsFinishing] = useState(false);
  const contentRef = useRef(null)
  const popupRef = useRef(null); // Ref for the popup element

  const processArticleContent = (htmlString) => {
    if (typeof window === 'undefined') return htmlString;
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
            fragment.appendChild(span);
          } else {
            fragment.appendChild(document.createTextNode(part));
          }
        });
        if (node.parentNode) {
          node.parentNode.replaceChild(fragment, node);
        }
      } else if (node.nodeType === 1) {
        if (node.tagName === 'SPAN' && node.classList.contains('highlight')) {
            node.style.cursor = 'pointer';
        }
        Array.from(node.childNodes).forEach(walk);
      }
    };

    walk(container);
    return container.innerHTML;
  };

  useEffect(() => {
    let isMounted = true
    setArticle('')
    setLoading(true)
    setError(null)

    let result = ''
    let buffer = ''
    let timeoutId = null

    const flushBuffer = () => {
      if (buffer.length > 0 && isMounted) {
        result += buffer
        const { title, highlightedContent } = parseArticle(result, log.daily_review_words);
        const finalContent = processArticleContent(highlightedContent);
        setArticle({ title, finalContent });
        buffer = ''
      }
      timeoutId = null
    }

    fetch(`https://masterwordai.com/api/generation/${log.id}`, {
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
  }, [log.id, log.daily_review_words])

  useEffect(() => {
    // if (contentRef.current) {
    //   contentRef.current.scrollTop = contentRef.current.scrollHeight
    // }
  }, [article])

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

  const handleWordSelection = async (event) => {
    const target = event.target;
    if (target.tagName !== 'SPAN' || !target.style.cursor) {
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

      setPopup({ visible: true, content: 'Searching...', x, y });

      try {
        const response = await fetch(`https://masterwordai.com/api/word_search/${log.id}/${word}`);
        if (!response.ok) throw new Error('Word not found');
        const resultText = await response.text();
        setPopup(p => ({ ...p, content: resultText, visible: true }));
      } catch (err) {
        setPopup(p => ({ ...p, content: 'Definition not found.', visible: true }));
      }
    }
  };

  const handleFinishClick = async () => {
    setIsFinishing(true);
    try {
      const response = await fetch(`https://masterwordai.com/api/finish_reading/${log.id}`, {
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
      const response = await fetch(`https://masterwordai.com/api/finish_reading/${log.id}`, {
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

  const { title, finalContent } = article || { title: '', finalContent: '' };
  
  const articlesPerDay = dailyGoal / 10;
  const isLastArticle = articlesReadCount + 1 >= articlesPerDay;

  return (
    <div className="main-bg">
      <div className="reading-card">
        {title && <h2 className="reading-title">{title}</h2>}
        <div 
          className="reading-content" 
          ref={contentRef} 
          onClick={handleWordSelection}
          dangerouslySetInnerHTML={{ __html: (finalContent || '').replace(/\n/g, '<br />') }} 
        />
        {loading && !finalContent && <div className="reading-loading">正在生成文章...</div>}
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
          {popup.content}
        </div>
      )}
    </div>
  )
}

export default ReadingPage 