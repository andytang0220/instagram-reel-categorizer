import { useEffect, useMemo, useState } from 'react'
import CategoryTabs from './components/CategoryTabs'
import ReelGrid from './components/ReelGrid'
import TagFilter from './components/TagFilter'
import TopThree from './components/TopThree'
import { byCategory, filterByTags, tagsIn, topThree } from './reels'

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [activeCategory, setActiveCategory] = useState(null)
  const [activeTags, setActiveTags] = useState([])

  useEffect(() => {
    fetch('/api/reels')
      .then((res) => (res.ok ? res.json() : res.json().then((body) => {
        throw new Error(body.detail || `Request failed (${res.status})`)
      })))
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  const reels = data?.reels ?? []
  const categories = data?.categories ?? []

  const counts = useMemo(() => {
    const out = {}
    for (const reel of reels) {
      out[reel.category] = (out[reel.category] || 0) + 1
    }
    return out
  }, [reels])

  // Open on the first category that actually has something in it, so an empty
  // tab is never the landing view.
  useEffect(() => {
    if (activeCategory || !categories.length) return
    setActiveCategory(categories.find((c) => counts[c]) || categories[0])
  }, [categories, counts, activeCategory])

  const inCategory = useMemo(
    () => (activeCategory ? byCategory(reels, activeCategory) : []),
    [reels, activeCategory],
  )
  const featured = useMemo(() => topThree(inCategory), [inCategory])
  const tags = useMemo(() => tagsIn(inCategory), [inCategory])
  const visible = useMemo(
    () => filterByTags(inCategory, activeTags), [inCategory, activeTags],
  )

  const selectCategory = (category) => {
    setActiveCategory(category)
    setActiveTags([])  // tags are category-specific; carrying them over hides everything
  }

  const toggleTag = (tag) => setActiveTags((current) =>
    current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag])

  if (error) {
    return (
      <main className="page">
        <h1 className="title">Reels</h1>
        <p className="empty">Couldn&rsquo;t load your reels: {error}</p>
      </main>
    )
  }
  if (!data) {
    return (
      <main className="page">
        <h1 className="title">Reels</h1>
        <p className="empty">Loading&hellip;</p>
      </main>
    )
  }
  if (!reels.length) {
    return (
      <main className="page">
        <h1 className="title">Reels</h1>
        <p className="empty">
          Nothing saved yet. Send a reel to your Telegram bot to get started.
        </p>
      </main>
    )
  }

  return (
    <main className="page">
      <h1 className="title">Reels</h1>
      <CategoryTabs
        categories={categories}
        counts={counts}
        active={activeCategory}
        onSelect={selectCategory}
      />
      {inCategory.length === 0 ? (
        <p className="empty">Nothing saved under {activeCategory} yet.</p>
      ) : (
        <>
          <TopThree reels={featured} />
          <section className="section">
            <h2 className="section__heading">
              All {activeCategory}{' '}
              <span className="section__count">
                {activeTags.length
                  ? `${visible.length} of ${inCategory.length}`
                  : `${inCategory.length}`}
              </span>
            </h2>
            <TagFilter
              tags={tags}
              selected={activeTags}
              onToggle={toggleTag}
              onClear={() => setActiveTags([])}
            />
            <ReelGrid reels={visible} />
          </section>
        </>
      )}
    </main>
  )
}
