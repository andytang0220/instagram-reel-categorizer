// Selection and ranking logic, kept free of React so it can be tested directly.

export function byCategory(reels, category) {
  return reels.filter((r) => r.category === category)
}

// Reels whose like count was never captured rank below every known count,
// including zero.
const likeRank = (r) => (typeof r.likes === 'number' ? r.likes : -1)

export function topThree(reels) {
  return [...reels]
    .sort((a, b) => likeRank(b) - likeRank(a) ||
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

export function formatCount(likes) {
  if (typeof likes !== 'number') return '—'
  if (likes >= 1_000_000) return `${trim(likes / 1_000_000)}M`
  if (likes >= 1_000) return `${trim(likes / 1_000)}K`
  return String(likes)
}

// 1.5K but 12K, not 12.0K.
const trim = (n) => (n >= 10 ? Math.round(n) : Math.round(n * 10) / 10)
