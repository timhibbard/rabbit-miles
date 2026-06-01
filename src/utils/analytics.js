import ReactGA from 'react-ga4';

const MEASUREMENT_ID = import.meta.env.VITE_GA_MEASUREMENT_ID;
const IS_PRODUCTION = import.meta.env.PROD;

// Initialize GA4
export const initGA = () => {
  if (!MEASUREMENT_ID) {
    console.warn('Google Analytics Measurement ID not found');
    return;
  }

  // Only track in production (optional - can enable in dev for testing)
  if (!IS_PRODUCTION) {
    console.log('GA4 disabled in development mode');
    return;
  }

  ReactGA.initialize(MEASUREMENT_ID, {
    gtagOptions: {
      send_page_view: false, // We'll manually track page views
    },
  });

  console.log('GA4 initialized:', MEASUREMENT_ID);
};

// Track page views
export const trackPageView = (path, title) => {
  if (!MEASUREMENT_ID || !IS_PRODUCTION) return;

  ReactGA.send({
    hitType: 'pageview',
    page: path,
    title: title,
  });
};

// Track custom events
export const trackEvent = (category, action, label = null, value = null) => {
  if (!MEASUREMENT_ID || !IS_PRODUCTION) return;

  const eventParams = {
    category,
    action,
  };

  if (label) eventParams.label = label;
  if (value !== null) eventParams.value = value;

  ReactGA.event(eventParams);
};

// Track specific user actions
export const analytics = {
  // Authentication events
  trackLogin: () => {
    trackEvent('Auth', 'login', 'Strava OAuth Success');
  },

  trackLogout: () => {
    trackEvent('Auth', 'logout', 'User Disconnected');
  },

  // Activity events
  trackActivityView: (activityId) => {
    trackEvent('Activity', 'view', `Activity ${activityId}`);
  },

  trackActivitiesRefresh: () => {
    trackEvent('Activity', 'refresh', 'Manual Refresh');
  },

  trackActivityDetail: (activityId) => {
    trackEvent('Activity', 'view_detail', `Activity ${activityId}`);
  },

  // Leaderboard events
  trackLeaderboardView: (window, activityType) => {
    trackEvent('Leaderboard', 'view', `${window}_${activityType}`);
  },

  trackLeaderboardFilter: (filter) => {
    trackEvent('Leaderboard', 'filter', filter);
  },

  // Settings events
  trackSettingsUpdate: (setting) => {
    trackEvent('Settings', 'update', setting);
  },

  trackEmailVerification: (status) => {
    trackEvent('Settings', 'email_verification', status);
  },

  // Support/donation events
  trackSupportPageView: () => {
    trackEvent('Support', 'page_view', 'Support Page');
  },

  trackDonationClick: (platform) => {
    trackEvent('Support', 'donation_click', platform);
  },

  trackSupportBannerDismiss: () => {
    trackEvent('Support', 'banner_dismiss', 'Support Banner');
  },

  // Error tracking
  trackError: (errorType, errorMessage) => {
    trackEvent('Error', errorType, errorMessage);
  },

  // Trail matching
  trackTrailMatch: (trailName, distanceMiles) => {
    trackEvent('Trail', 'match', trailName, Math.round(distanceMiles));
  },

  // Admin events
  trackAdminAccess: () => {
    trackEvent('Admin', 'access', 'Admin Page View');
  },

  // About/Privacy/Terms
  trackStaticPageView: (pageName) => {
    trackEvent('StaticPage', 'view', pageName);
  },
};

export default analytics;
