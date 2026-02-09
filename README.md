# RabbitMiles 🐰

A React SPA for tracking running miles with Strava integration.

## Features

- 📊 Dashboard for viewing running statistics
- 🔗 Connect with Strava via OAuth
- 🔔 Real-time activity updates via Strava webhooks
- ⚙️ Settings page for managing preferences
- 📱 Responsive design with Tailwind CSS
- 🚀 Static site deployed to GitHub Pages

## Tech Stack

- **React** - UI library
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **Tailwind CSS** - Styling
- **Axios** - HTTP client for API calls

## Getting Started

### Prerequisites

- Node.js 20.x or higher
- npm

### Installation

1. Clone the repository:
```bash
git clone https://github.com/timhibbard/rabbit-miles.git
cd rabbit-miles
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

4. Update the `.env` file with your backend API URL:
```env
VITE_API_BASE_URL=https://api.rabbitmiles.com
```

### Development

Start the development server:
```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Building

Build for production:
```bash
npm run build
```

Preview the production build:
```bash
npm run preview
```

## Deployment

### Frontend Deployment

The app automatically deploys to GitHub Pages when changes are pushed to the `main` branch via GitHub Actions.

#### Setup GitHub Pages Deployment

1. Go to your repository Settings → Pages
2. Set Source to "GitHub Actions"
3. Add your backend URL as a repository secret:
   - Go to Settings → Secrets and variables → Actions
   - Add a new secret named `VITE_API_BASE_URL`
   - Set the value to your AWS backend endpoint

### Backend Deployment

AWS Lambda functions automatically deploy when changes are pushed to the `backend/` directory on the `main` branch.

For setup instructions, see:
- [LAMBDA_DEPLOYMENT.md](LAMBDA_DEPLOYMENT.md) - General Lambda deployment
- [WEBHOOK_SETUP.md](WEBHOOK_SETUP.md) - Strava webhook configuration
- [ENV_VARS.md](ENV_VARS.md) - Complete environment variables reference

## Troubleshooting

If you're experiencing issues with authentication or user login:

- **Quick Reference:** [QUICK_TROUBLESHOOT.md](QUICK_TROUBLESHOOT.md) - 5-minute diagnosis checklist
- **Detailed Guide:** [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md) - Comprehensive debugging strategies
- **Environment Setup:** [ENV_VARS.md](ENV_VARS.md) - Complete list of required environment variables
- **Existing Issues:** [TROUBLESHOOTING_AUTH.md](TROUBLESHOOTING_AUTH.md) - Known authentication issues

### Verification Script

Run the environment verification script to check Lambda configuration:

```bash
./scripts/verify-lambda-env.sh
```

This script automatically checks:
- All required environment variables are set
- APP_SECRET is consistent across Lambdas
- FRONTEND_URL and API_BASE_URL are correctly formatted
- Database ARNs are configured
- Common configuration errors

## Environment Variables

- `VITE_API_BASE_URL` - Base URL for the backend API (required)

**Important:** No secrets or API keys should be stored in the frontend. All authentication is handled by the backend using secure httpOnly cookies.

## Admin Features

RabbitMiles includes admin endpoints for managing and viewing user data. Admin access is controlled by an allowlist of athlete IDs.

### Admin Endpoints

The following admin-only endpoints are available:

- **GET /admin/users** - List all users in the system
  - Returns: Array of user objects (excluding sensitive tokens)
  - Response includes: athlete_id, display_name, profile_picture, created_at, updated_at

- **GET /admin/activities** - List recent activities from ALL users
  - Query parameters: `limit` (default: 50, max: 100), `offset` (default: 0)
  - Returns: Array of activity objects from all users, sorted by most recent
  - Each activity includes `athlete_name` field showing which user created it
  - **Note**: Requires Lambda deployment and API Gateway route configuration (see `ADMIN_ALL_ACTIVITIES_DEPLOYMENT.md`)

- **GET /admin/users/{athlete_id}/activities** - List activities for a specific user
  - Path parameter: `athlete_id` - The Strava athlete ID
  - Query parameters: `limit` (default: 50, max: 100), `offset` (default: 0)
  - Returns: Array of activity objects for the specified user

### Admin Access Control

Admin access is controlled via the `ADMIN_ATHLETE_IDS` environment variable in the backend Lambda functions:

```bash
# Example: Multiple admin athlete IDs (comma-separated)
ADMIN_ATHLETE_IDS="3519964,12345,67890"
```

**Security Features:**
- Authentication derived from session cookie only (no client-provided athlete_id accepted)
- Admin endpoints return 403 Forbidden if user is not in allowlist
- All admin responses include `Cache-Control: no-store` header
- Access/refresh tokens are never exposed in API responses
- All admin actions are audit logged to CloudWatch

**Frontend Access:**
- Admin navigation link only appears for authorized users
- Admin page checks authorization and redirects if not authenticated
- Non-admin users cannot discover or access admin endpoints

### Setting Up Admin Access

1. Add the `ADMIN_ATHLETE_IDS` environment variable to your admin Lambda functions:
   - `admin_list_users`
   - `admin_all_activities`
   - `admin_user_activities`
   - `admin_delete_user`
   - `admin_backfill_activities`
   - `me` (for is_admin flag)

2. Set the value to a comma-separated list of Strava athlete IDs that should have admin access

3. Deploy the Lambda functions with the updated environment variables

4. Admin users will see the "Admin" link in the navigation after logging in

## Project Structure

```
src/
├── components/      # Reusable React components
│   └── Layout.jsx   # Main layout with navigation
├── pages/          # Page components
│   ├── Dashboard.jsx
│   ├── ConnectStrava.jsx
│   ├── OAuthCallback.jsx  # OAuth callback handler
│   └── Settings.jsx
├── utils/          # Utility functions
│   ├── api.js      # Axios configuration
│   └── debug.js    # Debug logging utility
├── App.jsx         # Main app component with routing
└── main.jsx        # Entry point
```

## Debug Mode

The app includes a comprehensive debug logging system that can be enabled by adding `?debug=1` to any URL:

```
https://timhibbard.github.io/rabbit-miles/?debug=1
https://timhibbard.github.io/rabbit-miles/connect?debug=1
```

When debug mode is enabled:
- 🐛 A yellow banner appears at the top of the page
- Detailed logs are written to the browser console including:
  - URL parsing and session token detection
  - Token format validation (without exposing token content)
  - Token storage operations success/failure
  - API request/response details with sanitized headers
  - Error details with full stack traces
  
**Security Note:** Token content is never logged - only presence, format validation, and storage status are shown.

**Usage Tips:**
- Use debug mode to troubleshoot authentication issues
- Check the browser console (F12) for detailed logs
- Debug mode persists across page navigation in the same tab
- To disable, remove `?debug=1` from the URL

## Domain

The application is hosted at:
- **Frontend:** https://rabbitmiles.com
- **API:** https://api.rabbitmiles.com

**Example Debugging Session:**
```bash
# Enable debug mode
1. Navigate to: https://rabbitmiles.com/connect?debug=1
2. Click "Connect with Strava"
3. Complete OAuth flow
4. Check browser console for detailed authentication logs
5. Look for "[DEBUG]" prefixed messages
```

## OAuth Flow

The app uses cookie-based authentication with Strava OAuth:

1. User clicks "Connect with Strava" button
2. Frontend redirects to backend OAuth endpoint: `{API_BASE_URL}/auth/start`
3. Backend redirects to Strava OAuth authorization page
4. After authorization, Strava redirects to: `{API_BASE_URL}/auth/callback` (API Gateway)
5. Backend validates state, exchanges code for tokens, and sets httpOnly session cookie
6. Backend redirects to `/connect?connected=1`
7. App calls `/me` endpoint to verify authentication and get user info
8. Dashboard displays user information

**Important:** The Strava application's "Authorization Callback Domain" must be set to `api.rabbitmiles.com`.

## Webhook Flow

When configured, Strava sends real-time updates when activities are created, updated, or deleted:

1. User creates/updates/deletes an activity in Strava
2. Strava sends webhook event to `{API_BASE_URL}/strava/webhook`
3. Webhook handler queues event to SQS (<2 seconds)
4. Webhook processor fetches activity details from Strava API
5. Activity is automatically updated in database
6. Frontend sees updates on next data refresh

For setup instructions, see [WEBHOOK_SETUP.md](WEBHOOK_SETUP.md).

## License

MIT
