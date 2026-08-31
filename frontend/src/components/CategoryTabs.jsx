export default function CategoryTabs({ categories, counts, active, onSelect }) {
  return (
    <nav className="tabs" aria-label="Categories">
      {categories.map((category) => (
        <button
          key={category}
          type="button"
          className={`tab${category === active ? ' tab--active' : ''}`}
          aria-current={category === active ? 'page' : undefined}
          onClick={() => onSelect(category)}
        >
          {category}
          <span className="tab__count">{counts[category] || 0}</span>
        </button>
      ))}
    </nav>
  )
}
