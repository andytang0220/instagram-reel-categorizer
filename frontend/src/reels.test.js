import { describe, expect, it } from 'vitest'
import { byCategory, filterByTags, formatViews, tagsIn, topThree } from './reels'

const reel = (shortcode, { category = 'Tech', views = null, tags = [], date_added = '2026-01-01T00:00:00Z' } = {}) =>
  ({ shortcode, category, views, tags, date_added })

describe('byCategory', () => {
  it('keeps only reels in the given category', () => {
    const reels = [reel('a'), reel('b', { category: 'Fitness' })]
    expect(byCategory(reels, 'Fitness').map((r) => r.shortcode)).toEqual(['b'])
  })

  it('preserves the incoming order', () => {
    const reels = [reel('a'), reel('b'), reel('c')]
    expect(byCategory(reels, 'Tech').map((r) => r.shortcode)).toEqual(['a', 'b', 'c'])
  })
})

describe('topThree', () => {
  it('returns the three highest view counts, descending', () => {
    const reels = [reel('a', { views: 10 }), reel('b', { views: 500 }),
      reel('c', { views: 200 }), reel('d', { views: 50 })]
    expect(topThree(reels).map((r) => r.shortcode)).toEqual(['b', 'c', 'd'])
  })

  it('sorts reels with unknown view counts last', () => {
    const reels = [reel('unknown'), reel('low', { views: 1 })]
    expect(topThree(reels).map((r) => r.shortcode)).toEqual(['low', 'unknown'])
  })

  it('treats zero views as a real count, above unknown', () => {
    const reels = [reel('unknown'), reel('zero', { views: 0 })]
    expect(topThree(reels).map((r) => r.shortcode)).toEqual(['zero', 'unknown'])
  })

  it('breaks ties by newest first', () => {
    const reels = [reel('older', { views: 5, date_added: '2025-01-01T00:00:00Z' }),
      reel('newer', { views: 5, date_added: '2026-06-01T00:00:00Z' })]
    expect(topThree(reels).map((r) => r.shortcode)).toEqual(['newer', 'older'])
  })

  it('returns however many exist when there are fewer than three', () => {
    expect(topThree([reel('a', { views: 1 })])).toHaveLength(1)
    expect(topThree([])).toEqual([])
  })

  it('does not mutate the input array', () => {
    const reels = [reel('a', { views: 1 }), reel('b', { views: 9 })]
    topThree(reels)
    expect(reels.map((r) => r.shortcode)).toEqual(['a', 'b'])
  })
})

describe('tagsIn', () => {
  it('returns distinct tags ordered by frequency then alphabetically', () => {
    const reels = [reel('a', { tags: ['ai', 'gpu'] }), reel('b', { tags: ['ai'] }),
      reel('c', { tags: ['ai', 'benchmarks'] })]
    expect(tagsIn(reels)).toEqual(['ai', 'benchmarks', 'gpu'])
  })

  it('is empty when no reel carries a tag', () => {
    expect(tagsIn([reel('a'), reel('b')])).toEqual([])
  })
})

describe('filterByTags', () => {
  const reels = [reel('a', { tags: ['ai'] }), reel('b', { tags: ['gpu'] }),
    reel('c', { tags: ['ai', 'gpu'] })]

  it('returns everything when nothing is selected', () => {
    expect(filterByTags(reels, [])).toEqual(reels)
  })

  it('matches a reel carrying any selected tag', () => {
    expect(filterByTags(reels, ['ai']).map((r) => r.shortcode)).toEqual(['a', 'c'])
    expect(filterByTags(reels, ['ai', 'gpu']).map((r) => r.shortcode))
      .toEqual(['a', 'b', 'c'])
  })

  it('returns nothing when no reel carries the selected tag', () => {
    expect(filterByTags(reels, ['cooking'])).toEqual([])
  })

  it('tolerates reels with no tags', () => {
    expect(filterByTags([reel('a')], ['ai'])).toEqual([])
  })
})

describe('formatViews', () => {
  it('abbreviates large counts', () => {
    expect(formatViews(999)).toBe('999')
    expect(formatViews(1500)).toBe('1.5K')
    expect(formatViews(12000)).toBe('12K')
    expect(formatViews(1200000)).toBe('1.2M')
  })

  it('renders an unknown count as a dash', () => {
    expect(formatViews(null)).toBe('—')
    expect(formatViews(undefined)).toBe('—')
  })

  it('renders zero as zero, not unknown', () => {
    expect(formatViews(0)).toBe('0')
  })
})
