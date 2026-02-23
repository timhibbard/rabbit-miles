# Analytics Quick Reference Card

**One-page decision guide for RabbitMiles analytics**

---

## ✅ Recommended Solution

```
┌─────────────────────────────────────────────────────┐
│  PLAUSIBLE ANALYTICS (Cloud) + SENTRY (Errors)      │
│                                                     │
│  Cost: $9-35/month                                  │
│  Privacy Impact: ⭐ Minimal (9/10)                  │
│  Setup Time: 2-4 hours                              │
│  Maintenance: Low                                   │
│  No Cookie Banner: ✅ Yes                           │
│  GDPR/CCPA Compliant: ✅ Yes                        │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 What You'll Track

| Category | Metric | How | Why |
|----------|--------|-----|-----|
| **Traffic** | Page views | Auto | Understand popularity |
| **Traffic** | Unique visitors | Auto | Measure growth |
| **Traffic** | Traffic sources | Auto | Marketing insights |
| **Conversion** | Strava Connect clicks | Event | Funnel start |
| **Conversion** | Strava Connected | Event | Conversion rate |
| **Engagement** | Leaderboard joins | Event | Feature adoption |
| **Engagement** | Activity views | Event | Usage patterns |
| **Quality** | JavaScript errors | Sentry | Fix bugs faster |

---

## 📋 Implementation Checklist

### Phase 1: Plausible (2 hours)
- [ ] Sign up at plausible.io ($9/mo)
- [ ] Add script to `/src/index.html`
- [ ] Create `/src/utils/analytics.js`
- [ ] Add events to key user actions
- [ ] Update privacy policy (1 new section)
- [ ] Deploy and verify

### Phase 2: Sentry (2 hours) - Optional
- [ ] Sign up at sentry.io (free tier)
- [ ] `npm install @sentry/react`
- [ ] Configure in `/src/main.jsx`
- [ ] Update privacy policy (1 paragraph)
- [ ] Deploy and verify

---

## 🔒 Privacy Policy Updates

**Add 1 new section after "Cookies and Tracking":**

### Analytics and Usage Data

We use Plausible Analytics, a privacy-friendly service that:
- ✅ Does NOT use cookies
- ✅ Does NOT collect personal information
- ✅ Provides anonymous, aggregated statistics
- ✅ Cannot identify individual users

**Optional: Add if using Sentry:**

We use Sentry for error monitoring to improve reliability. 
When errors occur, we collect technical information (error message, 
browser type, page) but exclude personal data.

---

## 💻 Code Snippets

### 1. Add to `/src/index.html`
```html
<!-- In <head> -->
<script defer data-domain="rabbitmiles.com" 
        src="https://plausible.io/js/script.js"></script>
```

### 2. Create `/src/utils/analytics.js`
```javascript
export function trackEvent(eventName, props = {}) {
  if (import.meta.env.DEV) {
    console.log('[Analytics]', eventName, props);
    return;
  }
  if (typeof window.plausible === 'function') {
    window.plausible(eventName, { props });
  }
}

export const EVENTS = {
  STRAVA_CONNECT_CLICKED: 'Strava Connect Clicked',
  STRAVA_CONNECTED: 'Strava Connected',
  LEADERBOARD_JOINED: 'Leaderboard Joined',
  ACTIVITY_VIEWED: 'Activity Viewed',
};
```

### 3. Track Events (example)
```javascript
import { trackEvent, EVENTS } from '../utils/analytics';

// On button click
const handleConnect = () => {
  trackEvent(EVENTS.STRAVA_CONNECT_CLICKED);
  // ... existing code
};

// On successful OAuth
useEffect(() => {
  if (connected) {
    trackEvent(EVENTS.STRAVA_CONNECTED);
  }
}, [connected]);
```

---

## 📊 What You'll See in Plausible

### Dashboard Shows:
- **Unique Visitors** - Growth trend
- **Page Views** - Popular pages
- **Top Sources** - Where visitors come from
- **Locations** - Countries (anonymous)
- **Devices** - Desktop vs Mobile
- **Custom Events** - Your tracked actions

### Key Metrics to Watch:
- **Connect Success Rate:** (Strava Connected) ÷ (Strava Connect Clicked)
  - Target: >80%
- **Leaderboard Adoption:** (Leaderboard Joined) ÷ (Strava Connected)
  - Target: >30%
- **Weekly Active Users:** Unique visitors per week
  - Track growth trend

---

## 💰 Cost Breakdown

| Item | Cost/Month | When |
|------|-----------|------|
| Plausible Analytics | $9 | Immediately |
| Sentry (Free Tier) | $0 | Phase 2 |
| Sentry (Paid) | $26 | If >5k errors/mo |
| **Total (Recommended)** | **$9** | **Start here** |

---

## ⚖️ Trade-offs

### ✅ What You Get
- Anonymous usage statistics
- Conversion funnel insights
- Feature adoption data
- Error tracking and fixing
- Better user experience (fewer bugs)

### ❌ What You Give Up
- User-level tracking (can't follow individuals)
- Session recordings (privacy concern anyway)
- Advanced cohort analysis
- A/B testing (can do manually)

### 🤝 What Stays the Same
- No cookies for analytics
- No personal data collection
- No data selling
- No advertising
- Users maintain full privacy

---

## 🚦 Go/No-Go Decision

### ✅ GO if:
- You want to understand user behavior
- You're OK with anonymous, aggregated data
- You can spend $9/month
- You have 2-4 hours for implementation
- You value data-driven decisions

### ❌ NO-GO if:
- You want absolute zero tracking
- You need user-level tracking (privacy concern)
- You can't afford $9/month
- You don't have time to implement
- You prefer direct user feedback only

---

## 🆘 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Events not showing | Wait 5-10 min, check ad blocker, verify script loaded |
| Script not loading | Check domain in Plausible settings |
| Events fire multiple times | Add empty deps array to useEffect: `[]` |
| Dev events go to Plausible | Check `import.meta.env.DEV` logic |
| Privacy concerns | Review data policy: plausible.io/data-policy |

---

## 📞 Quick Links

- **Plausible:** https://plausible.io
- **Sentry:** https://sentry.io
- **Full Documentation:** `/docs/README.md`
- **Implementation Guide:** `/docs/analytics-implementation-guide.md`
- **Privacy Template:** `/docs/privacy-policy-with-analytics.md`

---

## 🎬 Next Steps

1. **Review** this card (you just did ✅)
2. **Decide** if you want analytics
3. **If YES:** Follow implementation guide
4. **If NO:** Keep privacy-pure (valid choice!)

---

## 💡 Remember

> "The best analytics solution respects user privacy while providing valuable insights."

**For RabbitMiles:** Plausible strikes the perfect balance.

---

**Version:** 1.0  
**Last Updated:** February 23, 2026  
**Quick Reference for:** Analytics implementation decision
