# Google Analytics 4 Setup Guide

This guide will walk you through setting up Google Analytics 4 (GA4) for RabbitMiles.

## Prerequisites

- Google account
- Access to [Google Analytics](https://analytics.google.com/)
- Access to GitHub repository settings (for adding secrets)

## Step 1: Create GA4 Property

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

## Step 2: Set Up Data Stream

1. Select platform: **Web**
2. Fill in website details:
   - **Website URL:** https://rabbitmiles.com
   - **Stream name:** RabbitMiles Production
3. Click **Create stream**
4. **Copy the Measurement ID** (format: `G-XXXXXXXXXX`)
   - You'll need this for the next steps!
5. Toggle on **Enhanced measurement** (automatic event tracking)

## Step 3: Configure Local Development

1. Create a `.env` file in the project root (if it doesn't exist):
   ```bash
   cp .env.example .env
   ```

2. Add your Measurement ID to `.env`:
   ```bash
   # Backend API Base URL
   VITE_API_BASE_URL=https://api.rabbitmiles.com
   
   # Google Analytics 4 Measurement ID
   VITE_GA_MEASUREMENT_ID=G-XXXXXXXXXX
   ```

3. Replace `G-XXXXXXXXXX` with your actual Measurement ID from Step 2

## Step 4: Add GitHub Secret

For production deployment, add the Measurement ID as a GitHub secret:

1. Go to your repository on GitHub
2. Navigate to **Settings → Secrets and variables → Actions**
3. Click **New repository secret**
4. Name: `VITE_GA_MEASUREMENT_ID`
5. Value: `G-XXXXXXXXXX` (your measurement ID)
6. Click **Add secret**

## Step 5: Test in Development

1. Start the development server:
   ```bash
   npm run dev
   ```

2. Open the app in your browser: http://localhost:5173

3. Open the browser console (F12)

4. You should see: `GA4 disabled in development mode`
   - This is expected! GA4 only runs in production by default

5. To test GA4 in development, temporarily edit `src/utils/analytics.js`:
   ```javascript
   // Change this line:
   const IS_PRODUCTION = import.meta.env.PROD;
   
   // To this (temporarily):
   const IS_PRODUCTION = true; // Force enable for testing
   ```

6. After testing, **revert this change** before committing!

## Step 6: Deploy to Production

1. Commit your changes:
   ```bash
   git add .
   git commit -m "Add Google Analytics 4 tracking"
   git push origin main
   ```

2. GitHub Actions will automatically build and deploy

3. The `VITE_GA_MEASUREMENT_ID` secret will be used during the build

## Step 7: Verify Events in GA4

1. Go to [Google Analytics](https://analytics.google.com/)

2. Navigate to **Reports → Realtime**

3. Visit your production site: https://rabbitmiles.com

4. Perform actions:
   - Navigate between pages
   - Connect with Strava
   - View leaderboard
   - Update settings

5. Within 30 seconds, you should see:
   - Active users count increase
   - Events appearing in Realtime report
   - Page views tracked

## What's Being Tracked

### Automatic Events (Enhanced Measurement)
- ✅ Page views
- ✅ Scroll depth (90%)
- ✅ Outbound link clicks
- ✅ Site search
- ✅ File downloads

### Custom Events
- **Authentication:**
  - `login` - User successfully connects Strava
  - `logout` - User disconnects Strava

- **Activities:**
  - `refresh` - User manually refreshes activities
  - `view` - User views activity list
  - `view_detail` - User views activity detail page

- **Leaderboard:**
  - `view` - User views leaderboard (with window and activity type)
  - `filter` - User changes leaderboard filters

- **Settings:**
  - `update` - User updates settings (which setting changed)

- **Admin:**
  - `access` - Admin user accesses admin page

- **Static Pages:**
  - `page_view` - User views About, Privacy, or Terms page

## Key Metrics to Review

### Daily (First 2 Weeks)

Check **Reports → Realtime** to verify:
- Events are being tracked correctly
- Users are showing up
- No errors in browser console

### Weekly

Review **Reports → Life cycle → Engagement → Overview**:
- Daily Active Users (DAU)
- Weekly Active Users (WAU)
- Monthly Active Users (MAU)
- Top events

### Monthly (After 4 Weeks)

Analyze **Reports → Life cycle → Retention**:
- User retention rates
- Repeat user percentage
- User engagement time

Create custom explorations:
- Leaderboard engagement rate
- Feature usage patterns
- User journey analysis

## Privacy Considerations

The implementation follows privacy best practices:

- ✅ Analytics only runs in production
- ✅ No personally identifiable information (PII) tracked
- ✅ User IDs are not sent to GA4
- ✅ Activity data is not sent to GA4
- ✅ Only aggregate behavior is tracked

### Next Steps for Privacy (Optional)

Consider adding:

1. **Privacy Policy Update:** Mention GA4 usage
2. **Cookie Consent Banner:** For GDPR compliance (if you have EU users)
3. **Opt-out Option:** Link to [Google Analytics Opt-out](https://tools.google.com/dlpage/gaoptout)

## Troubleshooting

### Events Not Showing Up

1. **Check Measurement ID:** Verify `VITE_GA_MEASUREMENT_ID` is correct in GitHub Secrets
2. **Check Browser Console:** Look for GA4 errors
3. **Check Network Tab:** Look for requests to `google-analytics.com`
4. **Wait:** Events can take 1-2 minutes to appear in Realtime

### "GA4 disabled in development mode" in Production

1. **Check Build Logs:** Verify `VITE_GA_MEASUREMENT_ID` is being used
2. **Check GitHub Secret:** Ensure secret name matches exactly
3. **Redeploy:** Sometimes a fresh deployment fixes the issue

### No Measurement ID Found

1. **Local Development:** Check `.env` file exists and has `VITE_GA_MEASUREMENT_ID`
2. **Production:** Check GitHub Secret is set correctly
3. **Restart Dev Server:** After changing `.env`, restart `npm run dev`

## Resources

- [Google Analytics 4 Documentation](https://support.google.com/analytics/answer/10089681)
- [react-ga4 Documentation](https://github.com/codler/react-ga4)
- [GA4 Event Reference](https://support.google.com/analytics/answer/9267735)
- [GA4 Best Practices](https://support.google.com/analytics/answer/9267744)

## Support

If you need help:
1. Check the [GA4 Help Center](https://support.google.com/analytics)
2. Review browser console for errors
3. Test in development mode (temporarily enable GA4)
4. Check GitHub Actions logs for build errors

## Next Steps After Setup

Once GA4 is collecting data (wait 2-4 weeks):

1. Review **Monthly Active Users (MAU)** to understand your user base
2. Analyze **engagement metrics** to see which features are most used
3. Check **retention rates** to see if users return
4. Make informed decision about funding strategy:
   - < 50 MAU: Likely can absorb costs yourself
   - 50-200 MAU: Donations could work
   - 200+ MAU: Consider freemium or paid tier

Good luck! 🐰📊
