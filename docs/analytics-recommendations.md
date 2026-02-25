# Analytics Options for RabbitMiles

**Date:** February 23, 2026  
**Status:** Recommendations  
**Purpose:** Evaluate analytics options and their privacy policy implications

---

## Executive Summary

RabbitMiles currently has **no analytics implementation**, which aligns with its privacy-first approach. This document evaluates analytics options that balance insight gathering with user privacy, considering the application's commitment to minimal data collection.

---

## Current State

### What We Have
- ✅ Cookie-based session authentication (essential, functional cookies only)
- ✅ No third-party tracking
- ✅ No advertising cookies
- ✅ Privacy policy explicitly states: "We do not use third-party tracking or advertising cookies"
- ✅ Debug logging (internal, not external tracking)

### What We're Missing
- ❌ No visibility into user behavior patterns
- ❌ No error tracking or monitoring
- ❌ No performance metrics
- ❌ No feature usage analytics
- ❌ No conversion funnel insights (Strava connection, leaderboard opt-in)

---

## Analytics Options Analysis

### Option 1: Privacy-First Analytics (RECOMMENDED)

**Tools:**
- **Plausible Analytics** (https://plausible.io)
- **Fathom Analytics** (https://usefathom.com)
- **Simple Analytics** (https://simpleanalytics.com)

**Characteristics:**
- ✅ No cookies required
- ✅ No personal data collection
- ✅ GDPR/CCPA compliant by default
- ✅ No IP address tracking or storage
- ✅ Lightweight (<1KB script)
- ✅ Open source options available (Plausible)
- ✅ Can self-host (for full control)

**What You Get:**
- Page views and unique visitors
- Traffic sources and referrers
- Browser, OS, device type (aggregated)
- Geographic data (country level only)
- Popular pages
- Custom event tracking (e.g., "Strava Connect", "Join Leaderboard")

**Cost:**
- Plausible: $9/mo (up to 10k pageviews), self-hosted free
- Fathom: $14/mo (up to 100k pageviews)
- Simple Analytics: $9/mo (up to 10k pageviews)

**Privacy Policy Impact:** ⭐ MINIMAL
- Add section: "Anonymous Analytics"
- Clarify: No cookies, no personal data, no tracking
- Example: "We use privacy-friendly analytics to understand how people use RabbitMiles (like which pages are visited most often) without collecting any personal information or using cookies."

**Recommended Implementation:**
```javascript
// Plausible (recommended) - add to index.html
<script defer data-domain="rabbitmiles.com" src="https://plausible.io/js/script.js"></script>

// Custom events (for feature usage)
window.plausible('Strava Connect');
window.plausible('Join Leaderboard');
window.plausible('Activity View', {props: {trail: 'Swamp Rabbit'}});
```

---

### Option 2: Error & Performance Monitoring

**Tools:**
- **Sentry** (https://sentry.io)
- **LogRocket** (for session replay)
- **Rollbar**

**Characteristics:**
- ✅ Error tracking and debugging
- ✅ Performance monitoring
- ✅ Source map support
- ⚠️ May collect user context (can be configured to minimal)
- ⚠️ Session replay captures interactions (privacy concerns)

**What You Get:**
- JavaScript errors with stack traces
- API request failures
- Performance metrics (Core Web Vitals)
- User impact (how many users affected)
- Release tracking

**Cost:**
- Sentry: Free tier (5k errors/mo), paid from $26/mo
- LogRocket: $99/mo+ (includes session replay)

**Privacy Policy Impact:** ⭐⭐ MODERATE
- Must disclose error tracking
- Should specify: "We collect error data to improve service reliability, including error messages, browser type, and page visited when error occurred"
- If using session replay: Must explicitly disclose and potentially require consent
- Can configure to exclude sensitive data (PII scrubbing)

**Recommended Implementation:**
```javascript
// Sentry with privacy-friendly config
Sentry.init({
  dsn: "YOUR_DSN",
  integrations: [new Sentry.BrowserTracing()],
  tracesSampleRate: 0.1, // 10% of transactions
  beforeSend(event) {
    // Scrub sensitive data
    delete event.user;
    return event;
  },
  denyUrls: [
    // Don't track errors from extensions
    /extensions\//i,
    /^chrome:\/\//i,
  ],
});
```

---

### Option 3: Full-Featured Analytics (NOT RECOMMENDED)

**Tools:**
- Google Analytics 4
- Mixpanel
- Amplitude

**Characteristics:**
- ❌ Requires cookies
- ❌ Collects personal data
- ❌ Third-party tracking
- ❌ Complex privacy requirements
- ❌ Cookie consent banners required (GDPR)
- ❌ Conflicts with current privacy policy

**Privacy Policy Impact:** ⭐⭐⭐⭐⭐ SIGNIFICANT
- Would require complete privacy policy rewrite
- Must implement cookie consent mechanism
- Must disclose data sharing with Google/third parties
- May require Data Processing Agreements
- Contradicts current "no third-party tracking" promise

**Why Not Recommended:**
- Breaks privacy-first promise
- Requires intrusive consent banners
- Overkill for RabbitMiles' needs
- Damages user trust
- More complex to implement and maintain

---

### Option 4: Self-Hosted Analytics

**Tools:**
- **Umami** (https://umami.is) - Simple, fast, privacy-focused
- **Matomo** (https://matomo.org) - Full-featured, self-hosted
- **PostHog** (https://posthog.com) - Product analytics, can self-host

**Characteristics:**
- ✅ Full data control (you own everything)
- ✅ No third-party data sharing
- ✅ GDPR compliant (if configured properly)
- ✅ Can be cookie-free
- ⚠️ Requires hosting infrastructure
- ⚠️ Maintenance burden

**What You Get:**
- Page views, user flows
- Event tracking
- Funnel analysis (PostHog)
- Feature flags (PostHog)
- Session recordings (optional, privacy concerns)

**Cost:**
- Software: Free (open source)
- Hosting: AWS/DigitalOcean ~$10-20/mo
- Maintenance: Developer time

**Privacy Policy Impact:** ⭐ MINIMAL
- Similar to Option 1
- Extra benefit: "We self-host our analytics, meaning your data never leaves our infrastructure"
- More trustworthy for privacy-conscious users

**Recommended Implementation:**
```javascript
// Umami (lightweight, easiest to self-host)
<script async src="https://analytics.rabbitmiles.com/script.js" 
        data-website-id="YOUR_WEBSITE_ID"></script>

// PostHog (more features, heavier)
posthog.init('YOUR_PROJECT_API_KEY', {
  api_host: 'https://analytics.rabbitmiles.com',
  autocapture: false, // Disable for privacy
  disable_session_recording: true, // Disable for privacy
});
```

---

## Recommendation Matrix

| Option | Privacy Impact | Usefulness | Cost | Implementation | Maintenance |
|--------|---------------|------------|------|----------------|-------------|
| **Plausible** (Cloud) | ⭐ Minimal | ⭐⭐⭐ Good | $9/mo | ⭐⭐⭐ Easy | ⭐⭐⭐ Easy |
| **Plausible** (Self-hosted) | ⭐ Minimal | ⭐⭐⭐ Good | $15/mo | ⭐⭐ Medium | ⭐⭐ Medium |
| **Umami** (Self-hosted) | ⭐ Minimal | ⭐⭐⭐ Good | $15/mo | ⭐⭐ Medium | ⭐⭐ Medium |
| **Sentry** (Errors only) | ⭐⭐ Moderate | ⭐⭐⭐⭐ Excellent | Free-$26/mo | ⭐⭐⭐ Easy | ⭐⭐⭐ Easy |
| **Google Analytics** | ⭐⭐⭐⭐⭐ High | ⭐⭐⭐⭐⭐ Excellent | Free | ⭐⭐ Medium | ⭐⭐ Medium |
| **PostHog** (Self-hosted) | ⭐⭐ Moderate | ⭐⭐⭐⭐⭐ Excellent | $20/mo | ⭐ Hard | ⭐ Hard |

---

## Final Recommendations

### Phase 1: Essential (Implement Now)
**✅ Plausible Analytics (Cloud-Hosted)**
- **Why:** Best balance of privacy, simplicity, and usefulness
- **Cost:** $9/mo
- **Privacy Impact:** Minimal - no cookies, no personal data
- **Implementation Time:** 1 hour
- **Key Metrics to Track:**
  - Page views (Dashboard, Leaderboard, Activity pages)
  - Strava Connect clicks & completions
  - Leaderboard join rate
  - Settings page visits
  - Privacy/Terms page views

**Custom Events:**
```javascript
// Track key user actions
plausible('Strava Connect');
plausible('Strava Connected', {props: {success: 'true'}});
plausible('Join Leaderboard');
plausible('Leave Leaderboard');
plausible('Refresh Activities');
plausible('View Activity', {props: {trail: 'Swamp Rabbit'}});
```

### Phase 2: Error Monitoring (Implement After Phase 1)
**✅ Sentry (Free Tier)**
- **Why:** Critical for production reliability
- **Cost:** Free (up to 5k errors/month)
- **Privacy Impact:** Moderate - configure PII scrubbing
- **Implementation Time:** 2 hours
- **Benefits:**
  - Catch React errors
  - API call failures
  - Performance issues
  - Better user experience

### Phase 3: Advanced (Optional, Future)
**🔮 Self-Hosted Umami or PostHog**
- **When:** If scaling up or want full data control
- **Why:** Complete data ownership
- **Cost:** $15-20/mo hosting
- **Effort:** Higher initial setup and ongoing maintenance

---

## Privacy Policy Updates Required

### For Plausible Analytics (Phase 1)

**Add new section after "Cookies and Tracking" (line 88-94):**

```markdown
### Analytics

To understand how people use RabbitMiles and improve the service, we use Plausible Analytics, 
a privacy-friendly analytics service. 

Plausible does not use cookies and does not collect any personal data. It provides us with 
anonymous aggregate statistics about page views, traffic sources, and feature usage. No 
information collected can be used to identify you.

You can learn more about Plausible's privacy practices at https://plausible.io/data-policy.
```

### For Sentry Error Tracking (Phase 2)

**Add to "Analytics" section:**

```markdown
We also use Sentry for error monitoring to improve service reliability. When an error occurs 
in the application, Sentry collects technical information such as the error message, browser 
type, and page visited. We configure Sentry to exclude any personal information from error 
reports.
```

### Updated "Cookies and Tracking" Section

**Replace current text (lines 89-93) with:**

```markdown
We use minimal cookies for essential functionality (maintaining your session). 

We use privacy-friendly analytics that do not require cookies or collect personal information. 
We do not use third-party advertising cookies or invasive tracking technologies.
```

---

## Implementation Checklist

### Phase 1: Plausible Analytics

- [ ] Sign up for Plausible account (rabbitmiles.com)
- [ ] Add Plausible script to `index.html`
- [ ] Add custom event tracking to key user actions:
  - [ ] Strava connect flow
  - [ ] Leaderboard opt-in/opt-out
  - [ ] Activity refresh
  - [ ] Activity detail views
- [ ] Update Privacy Policy with Analytics section
- [ ] Test events in development
- [ ] Deploy and verify in production
- [ ] Set up weekly/monthly reports

### Phase 2: Sentry Error Monitoring

- [ ] Sign up for Sentry account (free tier)
- [ ] Install Sentry SDK: `npm install @sentry/react`
- [ ] Configure Sentry in `main.jsx` with privacy settings
- [ ] Add error boundary components
- [ ] Configure source maps for production
- [ ] Test error reporting in development
- [ ] Update Privacy Policy with error monitoring disclosure
- [ ] Deploy and monitor

---

## Alternative: Do Nothing (Valid Option)

**Considerations:**
- RabbitMiles is a small, focused app for a specific community
- Current approach (no analytics) is transparent and privacy-respecting
- Can gather feedback directly from users via Strava
- Reduces technical complexity
- Maintains trust with privacy-conscious athletes

**When this makes sense:**
- If user base is small (<100 active users)
- If direct user feedback is sufficient
- If minimizing operational costs is priority
- If absolute privacy commitment is core value

---

## Questions to Consider

1. **What are your goals?**
   - Understanding user behavior?
   - Measuring feature adoption?
   - Debugging errors?
   - Optimizing conversion funnel?

2. **What's your privacy philosophy?**
   - Absolute minimum (no analytics)?
   - Privacy-friendly analytics OK?
   - Willing to compromise for insights?

3. **What's your budget?**
   - $0/month: Self-hosted or no analytics
   - $10-30/month: Plausible + Sentry
   - $50+/month: Full analytics suite

4. **What's your technical capacity?**
   - Low: Use cloud services (Plausible, Sentry)
   - High: Self-host (Umami, PostHog)

---

## Conclusion

**Recommended Approach: Plausible Analytics + Sentry**

This combination provides:
- ✅ Privacy-first approach (maintains current values)
- ✅ Valuable insights without compromising user trust
- ✅ Error tracking for better reliability
- ✅ Minimal privacy policy changes
- ✅ Low cost ($9-35/month)
- ✅ Easy implementation (4-6 hours total)
- ✅ No cookie consent banners needed

**Next Steps:**
1. Review this document and decide on approach
2. If approved, implement Phase 1 (Plausible)
3. Update Privacy Policy
4. Monitor for 2-4 weeks
5. Implement Phase 2 (Sentry) if needed
6. Iterate based on insights

---

**Document Version:** 1.0  
**Author:** GitHub Copilot  
**Review Required:** Product Owner / Legal
