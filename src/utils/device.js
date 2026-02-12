/**
 * Device detection utilities
 */

/**
 * Detect if the user is on an iOS device
 * @returns {boolean} true if iOS device detected
 */
export function isIOS() {
  // Check user agent for iOS devices
  const userAgent = window.navigator.userAgent || window.navigator.vendor || window.opera;
  
  // Check for iPhone, iPad, or iPod
  if (/iPad|iPhone|iPod/.test(userAgent) && !window.MSStream) {
    return true;
  }
  
  // Check for iOS 13+ on iPad which may report as Mac
  // This uses the maxTouchPoints property
  if (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1) {
    return true;
  }
  
  return false;
}

/**
 * Attempt to open a URL and provide a fallback after a timeout
 * Useful for deep linking to native apps with web fallback
 * 
 * @param {string} primaryUrl - The URL to try first (e.g., app deep link)
 * @param {string} fallbackUrl - The URL to use if primary fails
 * @param {number} timeoutMs - How long to wait before assuming primary failed
 */
export function openWithFallback(primaryUrl, fallbackUrl, timeoutMs = 2000) {
  // Try to open the primary URL
  window.location.href = primaryUrl;
  
  // Set a timeout to fall back to the web URL
  // This fires if the app doesn't open (not installed)
  const fallbackTimer = setTimeout(() => {
    window.location.href = fallbackUrl;
  }, timeoutMs);
  
  // If the page visibility changes (app opened), cancel the fallback
  const handleVisibilityChange = () => {
    if (document.hidden) {
      clearTimeout(fallbackTimer);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    }
  };
  
  document.addEventListener('visibilitychange', handleVisibilityChange);
  
  // Also cancel if the page is about to unload (app is opening)
  window.addEventListener('pagehide', () => {
    clearTimeout(fallbackTimer);
  });
}
