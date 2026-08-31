import { useState } from 'react'
import { formatViews } from '../reels'

/**
 * One reel, linking out to Instagram.
 *
 * Thumbnails come from the local cache, which can miss for reels saved before
 * thumbnails were captured or whose download failed — so a 404 falls back to a
 * placeholder rather than showing a broken image.
 */
export default function ReelTile({ reel, rank }) {
  const [failed, setFailed] = useState(false)

  return (
    <a
      className={`tile${rank ? ' tile--featured' : ''}`}
      href={reel.url}
      target="_blank"
      rel="noopener noreferrer"
    >
      <div className="tile__frame">
        {rank && <span className="tile__rank">#{rank}</span>}
        {failed ? (
          <div className="tile__placeholder" aria-hidden="true">▶</div>
        ) : (
          <img
            className="tile__image"
            src={`/thumbs/${reel.shortcode}.jpg`}
            alt=""
            loading="lazy"
            onError={() => setFailed(true)}
          />
        )}
        <span className="tile__views">{formatViews(reel.views)} views</span>
      </div>
      <div className="tile__meta">
        <span className="tile__title">{reel.title || reel.shortcode}</span>
        {reel.author && <span className="tile__author">@{reel.author}</span>}
      </div>
    </a>
  )
}
