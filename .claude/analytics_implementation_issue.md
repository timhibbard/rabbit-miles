# Implement Google Analytics 4 for User Insights

## Overview

Implement Google Analytics 4 (GA4) to track user behavior, measure engagement, and inform decisions about funding models. This data will help determine:
- Number of active users (daily/weekly/monthly)
- Feature usage patterns
- User retention and engagement
- Geographic distribution
- Most popular features
- User journey and drop-off points

## Google Analytics 4 Setup

### Step 1: Create GA4 Property

1. Go to [Google Analytics](https://analytics.google.com/)
2. Click **Admin** (gear icon in bottom left)
3. Click **Create Property**
4. Fill in property details:
   - **Property name:** RabbitMiles
   - **Reporting time zone:** Your timezone
   - **Currency:** USD
5. Click **Next**
6. Fill in business details:
   - **Industry:** Sports & Recreation
   - **Business size:** Small
7. Click **Next**
8. Select business objectives: **Examine user behavior**
9. Click **Create**
10. Accept Terms of Service

### Step 2: Set Up Data Stream

1. Select platform: **Web**
2. Fill in website details:
   - **Website URL:** https://rabbitmiles.com
   - **Stream name:** RabbitMiles Production
3. Click **Create stream**
4. **Copy the Measurement ID** (format: `G-XXXXXXXXXX`)
5. Toggle on **Enhanced measurement** (automatic event tracking)

### Step 3: Get Measurement ID

Your measurement ID will look like: `G-XXXXXXXXXX`

Save this for the next steps.

---

## Frontend Implementation

### Option A: Using react-ga4 Library (Recommended)

#### 1. Install Dependencies

```bash
npm install react-ga4
```

#### 2. Create Analytics Utility

**File:** `src/utils/analytics.js`

```javascript
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

  ReactGA.event({
    category,
    action,
    label,
    value,
  });
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
};

export default analytics;
```

#### 3. Initialize in App.jsx

**File:** `src/App.jsx`

```jsx
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { initGA, trackPageView } from './utils/analytics';

function App() {
  const location = useLocation();

  // Initialize GA on app mount
  useEffect(() => {
    initGA();
  }, []);

  // Track page views on route changes
  useEffect(() => {
    const path = location.pathname + location.search;
    const title = document.title;
    trackPageView(path, title);
  }, [location]);

  return (
    // ... your app JSX
  );
}

export default App;
```

#### 4. Add Events Throughout App

**Dashboard.jsx - Track activity views:**
```jsx
import analytics from '../utils/analytics';

function Dashboard() {
  const handleRefresh = async () => {
    analytics.trackActivitiesRefresh();
    // ... refresh logic
  };

  return (
    // ... JSX
  );
}
```

**ConnectStrava.jsx - Track auth events:**
```jsx
import analytics from '../utils/analytics';

function ConnectStrava() {
  useEffect(() => {
    if (searchParams.get('connected') === '1') {
      analytics.trackLogin();
    }
  }, [searchParams]);

  const handleDisconnect = async () => {
    analytics.trackLogout();
    // ... disconnect logic
  };

  return (
    // ... JSX
  );
}
```

**Leaderboard.jsx - Track leaderboard usage:**
```jsx
import analytics from '../utils/analytics';

function Leaderboard() {
  useEffect(() => {
    analytics.trackLeaderboardView(selectedWindow, selectedActivityType);
  }, [selectedWindow, selectedActivityType]);

  return (
    // ... JSX
  );
}
```

**Settings.jsx - Track settings changes:**
```jsx
import analytics from '../utils/analytics';

function Settings() {
  const handleSettingsUpdate = async (updates) => {
    analytics.trackSettingsUpdate(Object.keys(updates).join(','));
    // ... update logic
  };

  return (
    // ... JSX
  );
}
```

**Support.jsx - Track donation clicks:**
```jsx
import analytics from '../utils/analytics';

function Support() {
  useEffect(() => {
    analytics.trackSupportPageView();
  }, []);

  return (
    <div>
      <a 
        href="https://github.com/sponsors/timhibbard"
        onClick={() => analytics.trackDonationClick('GitHub Sponsors')}
      >
        Sponsor on GitHub
      </a>
      
      <a 
        href="https://ko-fi.com/rabbitmiles"
        onClick={() => analytics.trackDonationClick('Ko-fi')}
      >
        Buy Me a Coffee
      </a>
    </div>
  );
}
```

**SupportBanner.jsx - Track banner interactions:**
```jsx
import analytics from '../utils/analytics';

function SupportBanner() {
  const handleDismiss = () => {
    analytics.trackSupportBannerDismiss();
    localStorage.setItem('supportBannerDismissed', 'true');
    setDismissed(true);
  };

  return (
    // ... JSX with dismiss button
  );
}
```

---

### Option B: Direct gtag.js Integration (Alternative)

If you prefer not to use the library, you can use gtag.js directly:

**File:** `index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>RabbitMiles</title>
  
  <!-- Google Analytics 4 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-XXXXXXXXXX', {
      send_page_view: false // We'll track page views manually in React
    });
  </script>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
```

**File:** `src/utils/analytics.js`

```javascript
export const trackPageView = (path) => {
  if (typeof window.gtag === 'function') {
    window.gtag('config', 'G-XXXXXXXXXX', {
      page_path: path,
    });
  }
};

export const trackEvent = (action, category, label, value) => {
  if (typeof window.gtag === 'function') {
    window.gtag('event', action, {
      event_category: category,
      event_label: label,
      value: value,
    });
  }
};
```

---

## Environment Variables

### Add to `.env`

```bash
# Google Analytics 4 Measurement ID
VITE_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

### Add to `.env.example`

```bash
# Google Analytics 4 Measurement ID
VITE_GA_MEASUREMENT_ID=your_measurement_id_here
```

### Update GitHub Actions Workflow

**File:** `.github/workflows/deploy.yml`

```yaml
- name: Build
  run: npm run build
  env:
    VITE_API_BASE_URL: ${{ secrets.VITE_API_BASE_URL }}
    VITE_GA_MEASUREMENT_ID: ${{ secrets.VITE_GA_MEASUREMENT_ID }}
```

### Add GitHub Secret

1. Go to repository **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `VITE_GA_MEASUREMENT_ID`
4. Value: `G-XXXXXXXXXX` (your measurement ID)
5. Click **Add secret**

---

## Key Metrics to Track

### Automatic Events (Enhanced Measurement)

These are tracked automatically by GA4:
- ✅ **page_view** - Page views
- ✅ **scroll** - User scrolled to bottom (90%)
- ✅ **click** - Outbound link clicks
- ✅ **view_search_results** - Site search
- ✅ **video_start/complete** - Video engagement
- ✅ **file_download** - File downloads

### Custom Events to Implement

High-priority events for decision making:

| Event | Purpose | Implementation |
|-------|---------|----------------|
| **login** | Track user authentication | After successful OAuth |
| **logout** | Track disconnections | When user disconnects |
| **activities_refresh** | Measure feature usage | Manual refresh button |
| **leaderboard_view** | Track leaderboard engagement | Window/type changes |
| **settings_update** | Track preference changes | Settings saved |
| **support_page_view** | Donation funnel start | Support page loaded |
| **donation_click** | Donation intent | Click GitHub/Ko-fi link |
| **banner_dismiss** | Support banner effectiveness | Dismiss button clicked |
| **trail_match** | Feature success metric | Activity matched to trail |
| **email_verification** | Email feature adoption | Verification completed |

---

## Custom Dimensions (Optional Advanced)

Track additional user properties:

**In `src/utils/analytics.js`:**

```javascript
// Set user properties
export const setUserProperties = (properties) => {
  if (!MEASUREMENT_ID || !IS_PRODUCTION) return;

  ReactGA.set(properties);
};

// Example: Track user's leaderboard opt-in status
setUserProperties({
  show_on_leaderboards: true,
  email_notifications_enabled: false,
  user_timezone: 'America/New_York',
});
```

---

## Privacy Considerations

### 1. Privacy Policy Update

Add to your Privacy Policy (or create one):

```markdown
## Analytics

RabbitMiles uses Google Analytics to understand how users interact with the service. 
This helps us improve the app and make informed decisions about features.

**Data collected:**
- Pages visited
- Features used
- Device and browser type
- Geographic location (city/country level)
- User engagement metrics

**Data NOT collected:**
- Personal information (names, emails)
- Strava activity data
- Precise location data

You can opt out of Google Analytics by installing the 
[Google Analytics Opt-out Browser Add-on](https://tools.google.com/dlpage/gaoptout).
```

### 2. Cookie Consent (Optional for GDPR)

If you have European users, consider adding cookie consent:

**File:** `src/components/CookieConsent.jsx`

```jsx
import React, { useState, useEffect } from 'react';

function CookieConsent() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem('cookieConsent');
    if (!consent) {
      setShow(true);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem('cookieConsent', 'accepted');
    setShow(false);
    // Initialize GA here if you want opt-in consent
  };

  const handleDecline = () => {
    localStorage.setItem('cookieConsent', 'declined');
    setShow(false);
  };

  if (!show) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray-900 text-white p-4 z-50">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <p className="text-sm">
          We use cookies and analytics to improve your experience. 
          By continuing to use RabbitMiles, you agree to our use of cookies.
          {' '}
          <a href="/privacy" className="underline">Learn more</a>
        </p>
        <div className="flex gap-2">
          <button
            onClick={handleAccept}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Accept
          </button>
          <button
            onClick={handleDecline}
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
          >
            Decline
          </button>
        </div>
      </div>
    </div>
  );
}

export default CookieConsent;
```

### 3. GA4 Privacy Settings

In Google Analytics Admin:
1. Go to **Data Settings → Data Collection**
2. Enable **Google signals** (optional - for cross-device tracking)
3. Go to **Data Settings → Data Retention**
4. Set event retention: **14 months** (balance between insights and privacy)
5. Enable **Reset user data on new activity** (recommended)

---

## Useful GA4 Reports

### 1. Active Users
**Where:** Reports → Life cycle → Engagement → Overview

Shows:
- Daily Active Users (DAU)
- Weekly Active Users (WAU)
- Monthly Active Users (MAU)

**Why it matters:** Determine if you have 50, 100, or 500+ active users to estimate donation potential.

### 2. User Acquisition
**Where:** Reports → Life cycle → Acquisition → User acquisition

Shows:
- How users find your app
- Traffic sources
- User growth trends

### 3. Engagement
**Where:** Reports → Life cycle → Engagement → Events

Shows:
- Most popular features
- Event counts
- User engagement score

**Custom exploration ideas:**
- Leaderboard view rate: % of users who visit leaderboard
- Refresh frequency: How often users refresh activities
- Support page conversion: % who visit support page → click donation link

### 4. Retention
**Where:** Reports → Life cycle → Retention → User retention

Shows:
- How many users return after first visit
- Weekly/monthly retention cohorts

**Why it matters:** High retention = users find value = more likely to donate.

### 5. Real-time
**Where:** Reports → Realtime

Shows:
- Users active right now
- What they're doing
- Geographic location

---

## Key Questions GA4 Will Answer

### For Funding Decisions:

1. **How many active users do I have?**
   - Reports → Engagement → Overview
   - Look at MAU (Monthly Active Users)

2. **Are users engaged enough to potentially donate?**
   - Reports → Engagement → Pages and screens
   - Average engagement time
   - Pages per session

3. **What's the support page conversion rate?**
   - Create funnel: All users → Support page view → Donation click
   - Exploration → Funnel exploration

4. **Which features are most valuable?**
   - Reports → Events
   - Compare: leaderboard_view vs activities_refresh vs trail_match

5. **What's user retention like?**
   - Reports → Retention
   - If 50%+ return weekly = high engagement = donation potential

### Expected Thresholds:

**You can likely absorb costs if:**
- MAU < 100 users
- Low feature usage (< 5 sessions/user/month)
- High churn (< 30% weekly retention)

**Donations might work if:**
- MAU 100-500 users
- High engagement (> 10 sessions/user/month)
- Good retention (> 50% monthly retention)
- Strong feature usage

**Need freemium/paid if:**
- MAU > 500 users
- Very high engagement
- Power users driving most API costs

---

## Testing & Validation

### 1. Test in Development

Temporarily enable GA in dev mode:

```javascript
// In src/utils/analytics.js
const IS_PRODUCTION = import.meta.env.PROD || true; // Force enable for testing
```

### 2. Verify Events in GA4

1. Go to GA4 → **Reports → Realtime**
2. Perform actions in your app
3. Check if events appear within 30 seconds
4. Verify event parameters are correct

### 3. Use GA4 DebugView

Enable debug mode:

```javascript
// In src/utils/analytics.js
ReactGA.initialize(MEASUREMENT_ID, {
  gtagOptions: {
    debug_mode: true, // Enable debug mode
  },
});
```

Then check: **Admin → DebugView** in GA4

### 4. Browser Console Verification

```javascript
// Check if gtag is loaded
console.log(typeof window.gtag); // Should be 'function'

// Check dataLayer
console.log(window.dataLayer); // Should be an array with events
```

---

## Implementation Checklist

### Setup
- [ ] Create Google Analytics 4 property
- [ ] Set up Web data stream
- [ ] Copy Measurement ID
- [ ] Enable Enhanced Measurement
- [ ] Configure data retention settings

### Development
- [ ] Install `react-ga4` package
- [ ] Create `src/utils/analytics.js`
- [ ] Add `VITE_GA_MEASUREMENT_ID` to `.env`
- [ ] Add `VITE_GA_MEASUREMENT_ID` to `.env.example`
- [ ] Initialize GA in `App.jsx`
- [ ] Add page view tracking
- [ ] Add event tracking to key features:
  - [ ] Login/logout
  - [ ] Activities refresh
  - [ ] Leaderboard views
  - [ ] Settings updates
  - [ ] Support page
  - [ ] Donation clicks
- [ ] Add cookie consent banner (if needed for GDPR)
- [ ] Update Privacy Policy

### Testing
- [ ] Test events in development mode
- [ ] Verify events in GA4 Realtime
- [ ] Check DebugView for event parameters
- [ ] Test page view tracking
- [ ] Test all custom events
- [ ] Verify on mobile devices

### Deployment
- [ ] Add `VITE_GA_MEASUREMENT_ID` to GitHub Secrets
- [ ] Update GitHub Actions workflow
- [ ] Deploy to production
- [ ] Verify production events in GA4 Realtime
- [ ] Disable debug mode

### Post-Launch
- [ ] Monitor for 1-2 weeks
- [ ] Review user counts (DAU, WAU, MAU)
- [ ] Check engagement metrics
- [ ] Review top events
- [ ] Create custom reports/explorations
- [ ] Make funding decision based on data

---

## Timeline

**Week 1: Setup & Development**
- Day 1-2: Create GA4 property, install dependencies
- Day 3-4: Implement tracking code
- Day 5-7: Add event tracking throughout app

**Week 2: Testing & Deployment**
- Day 1-3: Test all events in development
- Day 4-5: Deploy to production
- Day 6-7: Monitor and verify production data

**Week 3-4: Data Collection**
- Gather baseline metrics
- Let data accumulate for 2-4 weeks
- Minimum 2 weeks needed for meaningful insights

**Week 5: Analysis & Decision**
- Review user counts and engagement
- Calculate potential donation revenue
- Decide on funding approach based on data

---

## Cost

Google Analytics 4 is **completely free** for up to 10 million events per month. 

Given RabbitMiles' likely traffic, you'll never hit this limit.

---

## Alternative: Simple Self-Hosted Analytics

If you prefer privacy-focused analytics without Google:

**Options:**
- **Plausible** (plausible.io) - $9/month, simple and privacy-focused
- **Umami** (umami.is) - Free, self-hosted, privacy-focused
- **Simple Analytics** (simpleanalytics.com) - €19/month, GDPR-compliant

These are simpler but may lack advanced features like funnels and retention cohorts.

---

## Next Steps After Implementation

1. **Collect 2-4 weeks of data** (minimum)
2. **Review key metrics:**
   - Monthly Active Users (MAU)
   - Average engagement time
   - Feature usage rates
   - Support page conversion
3. **Make informed decision:**
   - < 50 MAU + low engagement → Absorb costs yourself
   - 50-200 MAU + good engagement → Try donations
   - 200+ MAU + high engagement → Consider freemium
   - 500+ MAU → Definitely need revenue strategy

---

## Resources

- [Google Analytics 4 Documentation](https://support.google.com/analytics/answer/10089681)
- [react-ga4 Documentation](https://github.com/codler/react-ga4)
- [GA4 Event Reference](https://support.google.com/analytics/answer/9267735)
- [GA4 Measurement Protocol](https://developers.google.com/analytics/devguides/collection/protocol/ga4)
