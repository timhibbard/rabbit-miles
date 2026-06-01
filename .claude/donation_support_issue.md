# Add Donation/Support Options to Fund Strava API Costs

## Background

Strava is now charging for API access. To keep RabbitMiles free for users, we need to explore funding options. This issue covers implementing donation/support mechanisms to help cover ongoing API costs without charging users directly.

## Donation Platform Options

### Recommended: GitHub Sponsors (Primary)

**URL:** https://github.com/sponsors

**Why GitHub Sponsors:**
- ✅ **Zero fees** (GitHub pays processing fees)
- ✅ Integrated with project GitHub profile
- ✅ Recurring or one-time donations
- ✅ Professional and trustworthy
- ✅ Shows sponsor badges on GitHub
- ✅ Tax forms handled automatically
- ✅ Perfect for open source projects

**Setup Steps:**
1. Apply at github.com/sponsors
2. Set suggested tiers:
   - $3/month - Coffee Supporter
   - $5/month - Trail Sponsor
   - $10/month - Leaderboard Champion
   - One-time options: $5, $10, $25
3. Add sponsor button to repository

**Cons:**
- Requires GitHub account for donors
- Need approval (usually 1-2 days)

---

### Recommended: Ko-fi (Secondary)

**URL:** https://ko-fi.com

**Why Ko-fi:**
- ✅ Super simple setup (5 minutes)
- ✅ **Zero platform fees** on one-time donations
- ✅ No approval needed
- ✅ "Buy me a coffee" is friendly/casual
- ✅ Lower barrier for non-GitHub users
- ✅ PayPal or Stripe

**Setup Steps:**
1. Create account at ko-fi.com
2. Choose username: `rabbitmiles`
3. Connect PayPal or Stripe
4. Set coffee price ($3-5)
5. Enable monthly memberships (optional)

**Cons:**
- 5% fee on monthly memberships (not one-time)
- Less developer-focused

---

### Alternative Options

| Platform | Fees | Best For | Pros | Cons |
|----------|------|----------|------|------|
| **Buy Me a Coffee** | 5% (or 0% premium) | Simple one-time | Similar to Ko-fi, good UI | 5% fee |
| **Patreon** | 5-12% | Recurring community | Multiple tiers, community features | Higher fees, more complex |
| **Open Collective** | 10% + processing | Transparent finances | Public finances, fiscal hosting | High fees |
| **PayPal Donate** | ~3% + $0.30 | Direct donations | Simple, direct | Less modern, no analytics |
| **Stripe Payment Links** | 2.9% + $0.30 | Custom solution | Full control | Technical setup required |
| **Liberapay** | ~5% | Europe/recurring | Non-profit, ethical | Less known in US |

---

## Implementation Plan

### Phase 1: Set Up Donation Platforms

#### 1.1 GitHub Sponsors
- [ ] Apply for GitHub Sponsors at github.com/sponsors
- [ ] Configure tiers:
  ```
  $3/month - ☕ Coffee Supporter
  $5/month - 🏃 Trail Sponsor  
  $10/month - 🏆 Leaderboard Champion
  $25/month - 🐰 RabbitMiles Hero
  
  One-time: $5, $10, $25, $50
  ```
- [ ] Write sponsor profile describing project and costs
- [ ] Wait for approval (1-2 business days)

#### 1.2 Ko-fi
- [ ] Create Ko-fi account: ko-fi.com/rabbitmiles
- [ ] Connect payment processor (PayPal or Stripe)
- [ ] Set default coffee amount: $3
- [ ] Optionally enable monthly memberships
- [ ] Customize page with RabbitMiles branding

#### 1.3 Add GitHub Sponsor Button
Add `.github/FUNDING.yml` to repository:
```yaml
# .github/FUNDING.yml
github: timhibbard
ko_fi: rabbitmiles
custom: []
```

This adds a "Sponsor" button to the GitHub repository.

---

### Phase 2: Update Repository README

Add sponsor badges and information to `README.md`:

```markdown
# RabbitMiles 🐰

[![GitHub Sponsors](https://img.shields.io/github/sponsors/timhibbard?style=social)](https://github.com/sponsors/timhibbard)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Development-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/rabbitmiles)

A React SPA for tracking running miles with Strava integration.

## 💖 Support RabbitMiles

RabbitMiles is free and built by one person. Strava now charges for API access, and your support helps keep this project running and free for everyone.

**Ways to support:**
- ⭐ Star this repository
- 💰 [Sponsor on GitHub](https://github.com/sponsors/timhibbard) (recurring or one-time)
- ☕ [Buy me a coffee](https://ko-fi.com/rabbitmiles) (one-time)
- 🐛 Report bugs and contribute code
- 📢 Share with other runners

Your support is appreciated! 🙏

---

[Rest of README...]
```

---

### Phase 3: Add Support Section to Web App

#### 3.1 Create Support/Donate Page

**New route:** `/support`

**File:** `src/pages/Support.jsx`

```jsx
import React from 'react';
import { Link } from 'react-router-dom';

function Support() {
  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Support RabbitMiles 💖</h1>
      
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
        <h2 className="text-xl font-semibold mb-3">Why donations help</h2>
        <p className="text-gray-700 mb-3">
          RabbitMiles is a free, open-source project built and maintained by one person. 
          Strava recently started charging for API access, which means there are ongoing 
          costs to keep this service running.
        </p>
        <p className="text-gray-700">
          <strong>Current monthly costs:</strong> ~$XX for Strava API + AWS hosting
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-4 mb-8">
        <div className="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition">
          <h3 className="text-lg font-semibold mb-2 flex items-center">
            <svg className="w-5 h-5 mr-2" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
            </svg>
            GitHub Sponsors
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            Monthly or one-time sponsorship. Zero fees - 100% goes to development.
          </p>
          <a 
            href="https://github.com/sponsors/timhibbard"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-pink-600 text-white px-4 py-2 rounded hover:bg-pink-700 transition"
          >
            Sponsor on GitHub
          </a>
        </div>

        <div className="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition">
          <h3 className="text-lg font-semibold mb-2 flex items-center">
            ☕ Ko-fi
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            Buy me a coffee (one-time donation). Quick and easy with PayPal or card.
          </p>
          <a 
            href="https://ko-fi.com/rabbitmiles"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600 transition"
          >
            Buy Me a Coffee
          </a>
        </div>
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 mb-6">
        <h3 className="text-lg font-semibold mb-3">Other ways to help</h3>
        <ul className="space-y-2 text-gray-700">
          <li>⭐ <a href="https://github.com/timhibbard/rabbit-miles" target="_blank" rel="noopener noreferrer" className="underline">Star the repository on GitHub</a></li>
          <li>🐛 Report bugs and issues you encounter</li>
          <li>💻 Contribute code or documentation</li>
          <li>📢 Tell other runners about RabbitMiles</li>
          <li>🎨 Share feedback and feature ideas</li>
        </ul>
      </div>

      <div className="text-center">
        <p className="text-gray-600 mb-4">
          Thank you for using RabbitMiles! Your support means everything. 🙏
        </p>
        <Link to="/" className="text-blue-600 hover:underline">
          ← Back to Dashboard
        </Link>
      </div>
    </div>
  );
}

export default Support;
```

#### 3.2 Add Route to App.jsx

```jsx
import Support from './pages/Support';

// In your Routes:
<Route path="/support" element={<Support />} />
```

#### 3.3 Add Link to Navigation (Layout.jsx)

```jsx
<nav>
  {/* ... existing nav items ... */}
  <Link 
    to="/support" 
    className="nav-link text-pink-600 hover:text-pink-700"
  >
    💖 Support
  </Link>
</nav>
```

---

### Phase 4: Add Non-Intrusive In-App Prompts

#### Option A: Dismissible Banner (Subtle)

**File:** `src/components/SupportBanner.jsx`

```jsx
import React, { useState, useEffect } from 'react';

function SupportBanner() {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Check if user has already dismissed
    const isDismissed = localStorage.getItem('supportBannerDismissed');
    if (isDismissed) {
      setDismissed(true);
    }
  }, []);

  const handleDismiss = () => {
    localStorage.setItem('supportBannerDismissed', 'true');
    setDismissed(true);
  };

  if (dismissed) return null;

  return (
    <div className="bg-yellow-50 border-b border-yellow-200 p-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <span className="text-sm text-yellow-800">
          ☕ Enjoying RabbitMiles? 
          <a 
            href="https://github.com/sponsors/timhibbard" 
            target="_blank"
            rel="noopener noreferrer"
            className="underline ml-1 font-medium hover:text-yellow-900"
          >
            Support development
          </a>
          {' '}to help cover Strava API costs.
        </span>
        <button
          onClick={handleDismiss}
          className="text-yellow-600 hover:text-yellow-800 ml-4"
          aria-label="Dismiss"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

export default SupportBanner;
```

**Add to Layout.jsx:**
```jsx
import SupportBanner from './SupportBanner';

<Layout>
  <SupportBanner />
  {/* rest of layout */}
</Layout>
```

#### Option B: Settings Page Section

**In `src/pages/Settings.jsx`:**

```jsx
{/* Add after existing settings sections */}

<div className="mt-8 border-t pt-8">
  <h2 className="text-2xl font-bold mb-4">Support RabbitMiles 💖</h2>
  
  <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-6 border border-blue-200">
    <p className="text-gray-700 mb-4">
      RabbitMiles is <strong>free and ad-free</strong>. If you find it useful, 
      consider supporting development to help cover Strava API costs (~$XX/month).
    </p>
    
    <div className="flex flex-wrap gap-3 mb-4">
      <a 
        href="https://github.com/sponsors/timhibbard" 
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center px-4 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700 transition"
      >
        <svg className="w-5 h-5 mr-2" viewBox="0 0 16 16" fill="currentColor">
          <path d="M4.25 2.5c-1.336 0-2.75 1.164-2.75 3 0 2.15 1.58 4.144 3.365 5.682A20.565 20.565 0 008 13.393a20.561 20.561 0 003.135-2.211C12.92 9.644 14.5 7.65 14.5 5.5c0-1.836-1.414-3-2.75-3-1.373 0-2.609.986-3.029 2.456a.75.75 0 01-1.442 0C6.859 3.486 5.623 2.5 4.25 2.5z"/>
        </svg>
        Sponsor on GitHub
      </a>
      
      <a 
        href="https://ko-fi.com/rabbitmiles" 
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition"
      >
        ☕ Buy Me a Coffee
      </a>
    </div>
    
    <p className="text-sm text-gray-600">
      <strong>Current status:</strong> XX supporters helping cover $XX/month in costs. Thank you! 🙏
    </p>
  </div>
</div>
```

#### Option C: Footer Link (Always Visible)

**In `src/components/Layout.jsx` or footer component:**

```jsx
<footer className="mt-auto border-t border-gray-200 bg-gray-50">
  <div className="max-w-7xl mx-auto px-4 py-6">
    <div className="flex flex-wrap justify-between items-center text-sm text-gray-600">
      <div>
        Made with 🐰 by <a href="https://github.com/timhibbard" className="underline">Tim</a>
      </div>
      <div className="flex gap-4">
        <Link to="/support" className="underline hover:text-gray-900">
          💖 Support this project
        </Link>
        <a 
          href="https://github.com/timhibbard/rabbit-miles" 
          target="_blank" 
          rel="noopener noreferrer"
          className="underline hover:text-gray-900"
        >
          GitHub
        </a>
      </div>
    </div>
  </div>
</footer>
```

---

### Phase 5: Track and Display Support Status

#### 5.1 Create Support Stats Component (Optional)

Show transparency about funding status on support page:

```jsx
function SupportStats() {
  // These could be fetched from GitHub Sponsors API or manually updated
  const monthlyCosts = 45; // Update manually
  const currentSupport = 23; // From GitHub Sponsors
  const supporters = 8; // Number of active sponsors
  
  const percentage = Math.min((currentSupport / monthlyCosts) * 100, 100);
  
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
      <h3 className="text-lg font-semibold mb-4">Monthly Funding Status</h3>
      
      <div className="mb-4">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-gray-600">
            ${currentSupport} / ${monthlyCosts} per month
          </span>
          <span className="text-gray-600">
            {percentage.toFixed(0)}% funded
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div 
            className="bg-green-500 h-3 rounded-full transition-all"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
      
      <p className="text-sm text-gray-600">
        <strong>{supporters} amazing supporters</strong> are helping keep RabbitMiles free!
      </p>
    </div>
  );
}
```

---

## Expected Results

### Realistic Donation Rates

Based on typical open source/free service donation patterns:

- **1-5% of active users** will donate
- **Average one-time donation:** $5-10
- **Average monthly sponsorship:** $3-5/month
- **Conversion timing:** Users more likely to donate after 2-4 weeks of use

**Example projections:**

| Active Users | Donors (3%) | Avg Donation | Monthly Revenue |
|--------------|-------------|--------------|-----------------|
| 50 users | 1-2 donors | $5/month | $5-10/month |
| 100 users | 3-5 donors | $5/month | $15-25/month |
| 200 users | 6-10 donors | $5/month | $30-50/month |
| 500 users | 15-25 donors | $5/month | $75-125/month |

---

## Best Practices for Maximizing Support

### 1. Transparency
- ✅ Show actual monthly costs (Strava API + AWS)
- ✅ Display funding progress (X% funded)
- ✅ Thank supporters publicly (with permission)
- ✅ Share what donations enable (new features, faster updates)

### 2. Timing
- ✅ Ask after positive experiences (milestone reached, feature used)
- ✅ Don't show on first visit
- ✅ Make dismissible/non-annoying
- ✅ Periodic gentle reminders (not every page)

### 3. Messaging
- ✅ Be genuine and personal
- ✅ Explain the "why" (Strava API costs)
- ✅ Make it optional and guilt-free
- ✅ Emphasize community benefit (keeps it free for everyone)

### 4. Options
- ✅ Multiple platforms (GitHub + Ko-fi covers most users)
- ✅ Both one-time and recurring options
- ✅ Various price points ($3, $5, $10, $25)
- ✅ Non-monetary ways to help (stars, contributions)

---

## Maintenance Tasks

### Regular Updates
- [ ] Monthly: Update support stats on Support page
- [ ] Quarterly: Thank sponsors in release notes
- [ ] Annually: Review and adjust donation tiers

### Sponsor Recognition
- [ ] Create SPONSORS.md file listing supporters (with permission)
- [ ] Add sponsor section to README
- [ ] Thank new sponsors on social media/updates

---

## Alternative/Future Considerations

If donations don't cover costs, consider:

1. **Optimize API usage** (reduce calls, cache more aggressively)
2. **Freemium model** (basic free, premium $3-5/month)
3. **Limit features** (cap activities per month on free tier)
4. **Community hosting** (users can self-host)
5. **Seek sponsorship** (local running stores, gear brands)

---

## Success Metrics

Track these to measure effectiveness:

- [ ] Number of monthly sponsors (GitHub)
- [ ] Number of one-time donations (Ko-fi)
- [ ] Total monthly revenue
- [ ] % of costs covered by donations
- [ ] Donation conversion rate (donors / active users)
- [ ] Average time to first donation (days after signup)

---

## Implementation Checklist

### Setup (Week 1)
- [ ] Apply for GitHub Sponsors
- [ ] Create Ko-fi account
- [ ] Add `.github/FUNDING.yml`
- [ ] Update README with sponsor badges
- [ ] Wait for GitHub Sponsors approval

### Development (Week 2)
- [ ] Create `/support` page
- [ ] Add Support route to App.jsx
- [ ] Add "Support" link to navigation
- [ ] Implement SupportBanner component
- [ ] Add support section to Settings page
- [ ] Add support link to footer

### Testing (Week 2)
- [ ] Test donation links work correctly
- [ ] Test banner dismiss functionality
- [ ] Mobile responsive check
- [ ] Verify external links open in new tabs

### Launch (Week 3)
- [ ] Deploy support page
- [ ] Announce on social media / to users
- [ ] Monitor donation analytics
- [ ] Thank early supporters

### Ongoing
- [ ] Monthly: Update support stats
- [ ] Quarterly: Thank sponsors publicly
- [ ] Respond to sponsor messages/questions

---

## Additional Resources

- [GitHub Sponsors Documentation](https://docs.github.com/en/sponsors)
- [Ko-fi Help Center](https://help.ko-fi.com/)
- [Open Source Funding Best Practices](https://opensource.guide/getting-paid/)
- [Sustainable Open Source](https://sfosc.org/)

---

## Questions to Consider

- How much are monthly Strava API costs actually running?
- What's the current active user count?
- Would users be open to a small monthly subscription if donations aren't sufficient?
- Are there any local running organizations that might sponsor the project?
