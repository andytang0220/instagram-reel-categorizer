import ReelTile from './ReelTile'

export default function TopThree({ reels }) {
  if (!reels.length) return null
  return (
    <section className="section">
      <h2 className="section__heading">Top {reels.length} by likes</h2>
      <div className="grid grid--featured">
        {reels.map((reel, i) => (
          <ReelTile key={reel.page_id || reel.shortcode} reel={reel} rank={i + 1} />
        ))}
      </div>
    </section>
  )
}
