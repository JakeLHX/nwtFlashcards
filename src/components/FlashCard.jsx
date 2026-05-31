export default function FlashCard({ scripture, mode, flipped, onFlip }) {
  const reference = scripture.text
  const text = scripture.scripture || 'Scripture text unavailable.'

  const front =
    mode === 'text'
      ? { label: 'Scripture', content: text, className: 'scripture-text' }
      : { label: 'Reference', content: reference, className: 'reference' }

  const back =
    mode === 'text'
      ? { label: 'Reference', content: reference, className: 'reference reference-back' }
      : { label: 'Scripture', content: text, className: 'scripture-text' }

  return (
    <button
      type="button"
      className={`flashcard ${flipped ? 'flipped' : ''}`}
      onClick={onFlip}
      aria-label={flipped ? 'Hide answer' : 'Reveal answer'}
    >
      <div className="flashcard-inner">
        <div className="flashcard-face flashcard-front">
          <span className="face-label">{front.label}</span>
          <p className={front.className}>{front.content}</p>
          <span className="hint">Tap to reveal</span>
        </div>
        <div className="flashcard-face flashcard-back">
          <span className="face-label">{back.label}</span>
          <p className={back.className}>{back.content}</p>
          <a
            href={scripture.url}
            target="_blank"
            rel="noopener noreferrer"
            className="bible-link"
            onClick={(e) => e.stopPropagation()}
          >
            Open in Bible
          </a>
          <span className="hint">Tap to flip back</span>
        </div>
      </div>
    </button>
  )
}
