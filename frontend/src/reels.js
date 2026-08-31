// Selection and ranking logic, kept free of React so it can be tested directly.

export function byCategory(reels, category) {
  return reels.filter((r) => r.category === category)
}

// Reels whose view count was never captured rank below every known count,
// including zero.
const viewRank = (r) => (typeof r.views === 'number' ? r.views : -1)

export function topThree(reels) {
  return [...reels]
    .sort((a, b) => viewRank(b) - viewRank(a) ||
      String(b.date_added).localeCompare(String(a.date_added)))
    .slice(0, 3)
}

export function tagsIn(reels) {
  const counts = new Map()
  for (const reel of reels) {
    for (const tag of reel.tags || []) {
      counts.set(tag, (counts.get(tag) || 0) + 1)
    }
  }
  return [...counts.entries()]
    .sort(([tagA, countA], [tagB, countB]) =>
      countB - countA || tagA.localeCompare(tagB))
    .map(([tag]) => tag)
}

/**
 * Narrow reels to those carrying ANY of the selected tags.
 *
 * "Any" rather than "all" because reels carry only a handful of tags each, so
 * requiring every selected tag would usually return nothing.
 */
export function filterByTags(reels, selectedTags) {
  if (!selectedTags.length) return reels
  const wanted = new Set(selectedTags)
  return reels.filter((r) => (r.tags || []).some((t) => wanted.has(t)))
}

export function formatViews(views) {
  if (typeof views !== 'number') return '—'
  if (views >= 1_000_000) return `${trim(views / 1_000_000)}M`
  if (views >= 1_000) return `${trim(views / 1_000)}K`
  return String(views)
}

// 1.5K but 12K, not 12.0K.
const trim = (n) => (n >= 10 ? Math.round(n) : Math.round(n * 10) / 10)
