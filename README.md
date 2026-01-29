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
VITE_BACKEND_BASE_URL=https://your-api-endpoint.amazonaws.com
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

The app automatically deploys to GitHub Pages when changes are pushed to the `main` branch via GitHub Actions.

### Setup GitHub Pages Deployment

1. Go to your repository Settings → Pages
2. Set Source to "GitHub Actions"
3. Add your backend URL as a repository secret:
   - Go to Settings → Secrets and variables → Actions
   - Add a new secret named `VITE_BACKEND_BASE_URL`
   - Set the value to your AWS backend endpoint

## Environment Variables

- `VITE_BACKEND_BASE_URL` - Base URL for the backend API (required)

**Important:** No secrets or API keys should be stored in the frontend. All authentication is handled by the backend.

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
2. User is redirected to backend OAuth endpoint: `{BACKEND_BASE_URL}/auth/strava`
3. Backend handles OAuth with Strava and redirects back to the app
4. App stores connection status in localStorage

## License

MIT
