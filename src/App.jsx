import { useCallback, useMemo, useState } from 'react'
import scriptures from './data/scriptures.json'
import FlashCard from './components/FlashCard'
import './App.css'

function shuffleArray(items) {
  const arr = [...items]
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

export default function App() {
  const [mode, setMode] = useState('reference')
  const [deck, setDeck] = useState(() => shuffleArray(scriptures))
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)

  const setStudyMode = useCallback((nextMode) => {
    setMode(nextMode)
    setFlipped(false)
  }, [])

  const lessons = useMemo(() => {
    const set = new Set()
    for (const s of scriptures) {
      for (const l of s.lessons) set.add(l)
    }
    return [...set].sort((a, b) => a - b)
  }, [])

  const current = deck[index]

  const shuffle = useCallback(() => {
    setDeck(shuffleArray(scriptures))
    setIndex(0)
    setFlipped(false)
  }, [scriptures])

  const goNext = useCallback(() => {
    setFlipped(false)
    setIndex((i) => (i + 1) % deck.length)
  }, [deck.length])

  const goPrev = useCallback(() => {
    setFlipped(false)
    setIndex((i) => (i - 1 + deck.length) % deck.length)
  }, [deck.length])

  return (
    <div className="app">
      <header className="header">
        <h1>NWT Flashcards</h1>
        <p className="subtitle">Enjoy Life Forever — scripture memorisation</p>
      </header>

      <main className="main">
        <div className="controls">
          <div className="mode-toggle" role="group" aria-label="Study mode">
            <button
              type="button"
              className={`mode-btn ${mode === 'reference' ? 'active' : ''}`}
              onClick={() => setStudyMode('reference')}
            >
              Verse → Text
            </button>
            <button
              type="button"
              className={`mode-btn ${mode === 'text' ? 'active' : ''}`}
              onClick={() => setStudyMode('text')}
            >
              Text → Verse
            </button>
          </div>
          <button type="button" className="btn btn-secondary" onClick={shuffle}>
            Shuffle
          </button>
        </div>

        {deck.length === 0 ? (
          <p className="empty">No scriptures available.</p>
        ) : (
          <>
            <FlashCard
              scripture={current}
              mode={mode}
              flipped={flipped}
              onFlip={() => setFlipped((f) => !f)}
            />

            <div className="nav">
              <button type="button" className="btn btn-nav" onClick={goPrev}>
                ← Previous
              </button>
              <span className="counter">
                {index + 1} / {deck.length}
              </span>
              <button type="button" className="btn btn-nav" onClick={goNext}>
                Next →
              </button>
            </div>
          </>
        )}
      </main>

      <footer className="footer">
        <p>{scriptures.length} unique scriptures from the Enjoy Life Forever course</p>
      </footer>
    </div>
  )
}
