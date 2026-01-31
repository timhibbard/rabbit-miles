# RabbitMiles 🐰

A React SPA for tracking running miles with Strava integration.

## Features

- 📊 Dashboard for viewing running statistics
- 🔗 Connect with Strava via OAuth
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

For setup instructions, see [LAMBDA_DEPLOYMENT.md](LAMBDA_DEPLOYMENT.md).

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
│   └── api.js      # Axios configuration
├── App.jsx         # Main app component with routing
└── main.jsx        # Entry point
```

## OAuth Flow

1. User clicks "Connect with Strava" button
2. User is redirected to backend OAuth endpoint: `{API_BASE_URL}/auth/start`
3. Backend handles OAuth with Strava and sets httpOnly cookies
4. App calls `/me` endpoint to check authentication status
5. Dashboard displays user information from `/me` response

## License

MIT
