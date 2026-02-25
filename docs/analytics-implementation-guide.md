# Analytics Implementation Guide

**Quick-start guide for implementing analytics in RabbitMiles**

---

## Recommended Solution: Plausible Analytics

**Why Plausible?**
- ✅ No cookies, no personal data collection
- ✅ GDPR, CCPA, PECR compliant out of the box
- ✅ Lightweight (< 1KB script)
- ✅ Simple to implement
- ✅ Great UI for insights
- ✅ No consent banner needed
- ✅ $9/month for up to 10K page views
- ✅ Can self-host (open source)

---

## Implementation Steps

### Step 1: Sign Up for Plausible (5 minutes)

1. Go to [https://plausible.io/register](https://plausible.io/register)
2. Create account
3. Add website: `rabbitmiles.com`
4. Get your tracking script (will look like below)

---

### Step 2: Add Plausible to Frontend (10 minutes)

**File:** `/src/index.html`

Add this script to the `<head>` section:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>RabbitMiles - Track Your Swamp Rabbit Trail Runs</title>
    
    <!-- Plausible Analytics -->
    <script defer data-domain="rabbitmiles.com" src="https://plausible.io/js/script.js"></script>
    <!-- End Plausible -->
    
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

**Important:** If you're using a staging/development domain, add it separately in Plausible settings.

---

### Step 3: Add Custom Event Tracking (20 minutes)

Custom events let you track specific user actions like "Strava Connect" or "Join Leaderboard."

**File:** `/src/utils/analytics.js` (NEW FILE)

```javascript
/**
 * Analytics utility for tracking custom events
 * Uses Plausible Analytics - privacy-friendly, no cookies
 */

/**
 * Track a custom event
 * @param {string} eventName - Name of the event (e.g., "Strava Connect")
 * @param {object} props - Optional properties (e.g., {result: "success"})
 */
export function trackEvent(eventName, props = {}) {
  // Only track in production
  if (import.meta.env.DEV) {
    console.log('[Analytics - DEV]', eventName, props);
    return;
  }

  // Check if Plausible is loaded
  if (typeof window.plausible === 'function') {
    if (Object.keys(props).length > 0) {
      window.plausible(eventName, { props });
    } else {
      window.plausible(eventName);
    }
  } else {
    console.warn('[Analytics] Plausible not loaded');
  }
}

// Common events (for autocomplete and consistency)
export const EVENTS = {
  STRAVA_CONNECT_CLICKED: 'Strava Connect Clicked',
  STRAVA_CONNECTED: 'Strava Connected',
  STRAVA_CONNECT_FAILED: 'Strava Connect Failed',
  STRAVA_DISCONNECTED: 'Strava Disconnected',
  
  LEADERBOARD_JOINED: 'Leaderboard Joined',
  LEADERBOARD_LEFT: 'Leaderboard Left',
  
  ACTIVITIES_REFRESHED: 'Activities Refreshed',
  ACTIVITY_VIEWED: 'Activity Viewed',
  
  SETTINGS_UPDATED: 'Settings Updated',
  
  PRIVACY_POLICY_VIEWED: 'Privacy Policy Viewed',
  TERMS_VIEWED: 'Terms Viewed',
};
```

---

### Step 4: Add Events to Key User Actions

#### 4.1 Track Strava Connect

**File:** `/src/pages/Connect.jsx`

```javascript
import { trackEvent, EVENTS } from '../utils/analytics';

function Connect() {
  const handleConnect = () => {
    trackEvent(EVENTS.STRAVA_CONNECT_CLICKED);
    // Existing code...
  };
  
  // Rest of component...
}
```

**File:** `/src/pages/Callback.jsx`

```javascript
import { trackEvent, EVENTS } from '../utils/analytics';

function Callback() {
  useEffect(() => {
    // After successful OAuth callback
    const handleCallback = async () => {
      try {
        // Existing OAuth logic...
        
        // Track successful connection
        trackEvent(EVENTS.STRAVA_CONNECTED);
      } catch (error) {
        trackEvent(EVENTS.STRAVA_CONNECT_FAILED, { 
          error: error.message 
        });
      }
    };
    
    handleCallback();
  }, []);
  
  // Rest of component...
}
```

#### 4.2 Track Leaderboard Actions

**File:** `/src/pages/Settings.jsx`

```javascript
import { trackEvent, EVENTS } from '../utils/analytics';

function Settings() {
  const handleLeaderboardToggle = async (enabled) => {
    try {
      // Existing API call...
      
      trackEvent(enabled ? EVENTS.LEADERBOARD_JOINED : EVENTS.LEADERBOARD_LEFT);
    } catch (error) {
      console.error(error);
    }
  };
  
  // Rest of component...
}
```

#### 4.3 Track Activity Views

**File:** `/src/pages/ActivityDetail.jsx`

```javascript
import { trackEvent, EVENTS } from '../utils/analytics';

function ActivityDetail() {
  useEffect(() => {
    if (activity) {
      trackEvent(EVENTS.ACTIVITY_VIEWED, {
        trail: 'Swamp Rabbit', // or get from activity data
        distance: Math.round(activity.distance / 1000) + 'km'
      });
    }
  }, [activity]);
  
  // Rest of component...
}
```

#### 4.4 Track Page Views (Automatic)

Page views are tracked automatically by Plausible. No code needed!

But you can track Privacy/Terms specifically:

**File:** `/src/pages/Privacy.jsx`

```javascript
import { useEffect } from 'react';
import { trackEvent, EVENTS } from '../utils/analytics';

function Privacy() {
  useEffect(() => {
    trackEvent(EVENTS.PRIVACY_POLICY_VIEWED);
  }, []);
  
  // Rest of component...
}
```

---

### Step 5: Update Privacy Policy (15 minutes)

**File:** `/src/pages/Privacy.jsx`

Add new section after "Cookies and Tracking" (around line 95):

```jsx
<section className="mb-8">
  <h2 className="text-2xl font-semibold text-gray-900 mb-4">Analytics and Usage Data</h2>
  <p className="mb-4">
    To understand how people use RabbitMiles and improve the service, we use Plausible Analytics, 
    a privacy-friendly analytics service.
  </p>
  <p className="mb-4">
    <strong>What Plausible collects:</strong>
  </p>
  <ul className="list-disc pl-6 mb-4 space-y-2">
    <li>Page views and visitor counts (anonymous, aggregated)</li>
    <li>Traffic sources (which websites refer visitors)</li>
    <li>Browser type and operating system (for compatibility)</li>
    <li>Country-level geographic data (for localization)</li>
    <li>Feature usage (like button clicks on key features)</li>
  </ul>
  <p className="mb-4">
    <strong>What Plausible does NOT collect:</strong>
  </p>
  <ul className="list-disc pl-6 mb-4 space-y-2">
    <li>Personal information or user IDs</li>
    <li>Cookies (Plausible is completely cookie-free)</li>
    <li>IP addresses (anonymized immediately)</li>
    <li>Cross-site or cross-device tracking</li>
    <li>Any data that could identify you</li>
  </ul>
  <p className="mb-4">
    All analytics data is aggregated and anonymous. No information can be used to identify you personally.
  </p>
  <p className="mb-4">
    Learn more about Plausible&apos;s privacy practices at{' '}
    <a 
      href="https://plausible.io/data-policy" 
      target="_blank" 
      rel="noopener noreferrer"
      className="text-orange-600 hover:text-orange-700 underline"
    >
      plausible.io/data-policy
    </a>.
  </p>
</section>
```

Also update the "Cookies and Tracking" section:

```jsx
<section className="mb-8">
  <h2 className="text-2xl font-semibold text-gray-900 mb-4">Cookies and Tracking</h2>
  <p className="mb-4">
    We use minimal cookies for essential functionality (maintaining your session).
  </p>
  <p className="mb-4">
    We use privacy-friendly analytics that do not require cookies or collect personal information. 
    We do not use third-party advertising cookies or invasive tracking technologies.
  </p>
  <p className="mb-4">
    <strong>Cookies we use:</strong>
  </p>
  <ul className="list-disc pl-6 mb-4 space-y-2">
    <li><strong>Session cookie (rm_session):</strong> Essential for keeping you logged in</li>
    <li><strong>OAuth state cookie (rm_state):</strong> Temporary cookie for Strava authentication security</li>
  </ul>
</section>
```

---

### Step 6: Test in Development (10 minutes)

1. Run development server:
   ```bash
   npm run dev
   ```

2. Open browser console

3. Navigate through the app and check for console logs:
   ```
   [Analytics - DEV] Strava Connect Clicked {}
   [Analytics - DEV] Activity Viewed {trail: 'Swamp Rabbit', distance: '5km'}
   ```

4. Verify events are being called correctly

---

### Step 7: Deploy to Production

1. Commit changes:
   ```bash
   git add .
   git commit -m "Add Plausible Analytics with privacy-first approach"
   git push
   ```

2. Deploy to GitHub Pages (existing workflow should handle this)

3. Verify in Plausible dashboard (may take 5-10 minutes for first data)

---

### Step 8: Verify Live Events (After Deploy)

1. Visit https://rabbitmiles.com in incognito mode
2. Click through key flows:
   - Strava Connect
   - View activities
   - Join leaderboard
3. Check Plausible dashboard (plausible.io/rabbitmiles.com)
4. Verify events are appearing

---

## What You'll See in Plausible

### Default Metrics (Automatic)
- **Unique Visitors:** Number of people visiting
- **Page Views:** Total pages viewed
- **Bounce Rate:** % of single-page visits
- **Visit Duration:** Average time spent
- **Top Pages:** Most visited pages
- **Top Sources:** Where visitors come from
- **Locations:** Countries (anonymized)
- **Devices:** Desktop vs Mobile

### Custom Events (What We Added)
- Strava Connect Clicked → Conversion funnel start
- Strava Connected → Successful connections
- Strava Connect Failed → Connection issues
- Leaderboard Joined → Feature adoption
- Activity Viewed → Engagement

---

## Monitoring & Insights

### Weekly Check
Look at:
- **Unique visitors** - Is the user base growing?
- **Strava Connected** events - Connection success rate
- **Leaderboard Joined** - Feature adoption rate
- **Top Pages** - What users find valuable

### Monthly Analysis
- **Trends:** Are visits increasing?
- **Conversion:** Connect clicks → Connected (should be >80%)
- **Engagement:** Activities Viewed per user
- **Issues:** Any spike in "Connect Failed" events?

### Setting Up Alerts
Plausible can email you weekly/monthly reports automatically.

---

## Cost Management

**Plausible Pricing:**
- 0 - 10k pageviews/month: $9/month
- 10k - 100k pageviews/month: $19/month

**Estimate for RabbitMiles:**
- Small user base (50-100 active users): ~2-5k pageviews/month
- Medium (100-500 users): ~10-20k pageviews/month
- Stay on $9/month plan for foreseeable future

---

## Self-Hosting Option (Advanced)

If you want full control and no monthly cost:

### Install Plausible on a VPS

1. **Requirements:**
   - VPS with Docker (DigitalOcean, AWS, etc.)
   - $10-15/month for small droplet
   - Domain/subdomain (analytics.rabbitmiles.com)

2. **Installation:**
   ```bash
   git clone https://github.com/plausible/hosting
   cd hosting
   # Edit plausible-conf.env with your settings
   docker-compose up -d
   ```

3. **Update Script in index.html:**
   ```html
   <script defer data-domain="rabbitmiles.com" 
           src="https://analytics.rabbitmiles.com/js/script.js"></script>
   ```

4. **Benefit:**
   - 100% data ownership
   - No external dependencies
   - More privacy for users
   - No monthly analytics cost (only hosting ~$15)

---

## Troubleshooting

### Events Not Showing in Plausible

**Check:**
1. Is script loaded? (View source, look for plausible.io)
2. Browser console errors?
3. Ad blocker enabled? (They may block analytics)
4. Correct domain in Plausible settings?
5. Wait 5-10 minutes (real-time can lag slightly)

### Events Showing in Dev Console but Not Live

**Check:**
1. `import.meta.env.DEV` check is working correctly
2. Production build has correct environment
3. Script loaded in production build

### Too Many Events

**If:** Events firing multiple times
**Fix:** Add dependencies to useEffect hooks

```javascript
useEffect(() => {
  trackEvent(EVENTS.PAGE_VIEWED);
}, []); // Empty array = only once on mount
```

---

## Future Enhancements

### Phase 2: Error Monitoring (Sentry)

**After analytics are stable, add:**

```bash
npm install @sentry/react
```

**File:** `/src/main.jsx`

```javascript
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: "YOUR_SENTRY_DSN",
  integrations: [new Sentry.BrowserTracing()],
  tracesSampleRate: 0.1,
  beforeSend(event) {
    // Strip sensitive data
    delete event.user;
    return event;
  },
});
```

**Privacy Policy:** Add section about error monitoring

---

## Key Principles

✅ **Privacy First:** Never collect personal data  
✅ **Transparency:** Disclose what we track  
✅ **Minimal:** Only track what's useful  
✅ **Respect:** No consent banners needed (cookie-free)  
✅ **Trust:** Use tools that respect user privacy  

---

## Questions?

If you have questions about this implementation:
1. Check Plausible docs: https://plausible.io/docs
2. Review this guide
3. Test in development first
4. Reach out to Plausible support (they're responsive)

---

**Estimated Total Time:** 2-3 hours  
**Monthly Cost:** $9  
**Privacy Impact:** Minimal  
**User Trust Impact:** None (fully transparent)  
**Benefit:** Valuable insights for improvement
