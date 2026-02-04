# RabbitMiles 🐰

A React SPA for tracking running miles with Strava integration.

## Production URL

The application is deployed at: **https://rabbitmiles.com**

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
VITE_API_BASE_URL=https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod
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

## Environment Variables

- `VITE_API_BASE_URL` - Base URL for the backend API (required)

**Important:** No secrets or API keys should be stored in the frontend. All authentication is handled by the backend using secure httpOnly cookies.

## Project Structure

```
src/
├── components/      # Reusable React components
│   └── Layout.jsx   # Main layout with navigation
├── pages/          # Page components
│   ├── Dashboard.jsx
│   ├── ConnectStrava.jsx
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
https://rabbitmiles.com/?debug=1
https://rabbitmiles.com/connect?debug=1
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

1. User clicks "Connect with Strava" button
2. User is redirected to backend OAuth endpoint: `{API_BASE_URL}/auth/start`
3. Backend handles OAuth with Strava and sets httpOnly cookies
4. App calls `/me` endpoint to check authentication status
5. Dashboard displays user information from `/me` response

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
