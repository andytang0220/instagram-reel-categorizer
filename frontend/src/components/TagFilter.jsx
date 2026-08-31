export default function TagFilter({ tags, selected, onToggle, onClear }) {
  if (!tags.length) return null
  return (
    <div className="tagbar">
      {tags.map((tag) => {
        const on = selected.includes(tag)
        return (
          <button
            key={tag}
            type="button"
            className={`chip${on ? ' chip--on' : ''}`}
            aria-pressed={on}
            onClick={() => onToggle(tag)}
          >
            {tag}
          </button>
        )
      })}
      {selected.length > 0 && (
        <button type="button" className="chip chip--clear" onClick={onClear}>
          clear
        </button>
      )}
    </div>
  )
}
