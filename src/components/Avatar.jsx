import { useState } from 'react';

// Renders an athlete's profile picture, falling back to a placeholder when the
// image is missing or fails to load. Strava versions its avatar URLs, so a URL
// stored before an athlete changed their photo will 404 — onError catches that
// and swaps in the placeholder instead of showing a broken-image icon.
function Avatar({ src, alt, className = '' }) {
  // Track the specific URL that failed rather than a boolean, so that when
  // `src` changes (e.g. after a background profile-picture refresh) the new URL
  // is retried instead of staying stuck on the placeholder.
  const [failedSrc, setFailedSrc] = useState(null);

  const showImage = src && failedSrc !== src;

  if (showImage) {
    return (
      <img
        src={src}
        alt={alt}
        className={`rounded-full ${className}`}
        onError={() => setFailedSrc(src)}
      />
    );
  }

  return (
    <div className={`rounded-full bg-gray-200 flex items-center justify-center ${className}`}>
      <span className="text-gray-500">👤</span>
    </div>
  );
}

export default Avatar;
