// Debug logging utility
// Logs are only shown when ?debug=1 is present in the URL

const isDebugMode = () => {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('debug') === '1';
};

export const debug = {
  log: (...args) => {
    if (isDebugMode()) {
      console.log('[DEBUG]', ...args);
    }
  },
  warn: (...args) => {
    if (isDebugMode()) {
      console.warn('[DEBUG]', ...args);
    }
  },
  error: (...args) => {
    // Always show errors, but add DEBUG prefix in debug mode
    if (isDebugMode()) {
      console.error('[DEBUG]', ...args);
    } else {
      console.error(...args);
    }
  },
  info: (...args) => {
    if (isDebugMode()) {
      console.info('[DEBUG]', ...args);
    }
  },
  group: (label) => {
    if (isDebugMode()) {
      console.group(`[DEBUG] ${label}`);
    }
  },
  groupEnd: () => {
    if (isDebugMode()) {
      console.groupEnd();
    }
  },
  table: (data) => {
    if (isDebugMode()) {
      console.table(data);
    }
  },
  // Check if debug mode is enabled
  enabled: isDebugMode,
};

// Export a function to add debug info to the page
export const showDebugInfo = (info) => {
  if (!isDebugMode()) return;
  
  console.group('[DEBUG] Debug Info');
  console.log('Timestamp:', new Date().toISOString());
  console.log('User Agent:', navigator.userAgent);
  console.log('URL:', window.location.href);
  // Only log count of sessionStorage keys for security
  console.log('SessionStorage key count:', sessionStorage.length);
  if (info) {
    console.log('Additional Info:', info);
  }
  console.groupEnd();
};

export default debug;