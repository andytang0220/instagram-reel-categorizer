import ReelTile from './ReelTile'

export default function ReelGrid({ reels }) {
  if (!reels.length) {
    return <p className="empty">No reels match those tags.</p>
  }
  return (
    <div className="grid">
      {reels.map((reel) => (
        <ReelTile key={reel.page_id || reel.shortcode} reel={reel} />
      ))}
    </div>
  )
}
