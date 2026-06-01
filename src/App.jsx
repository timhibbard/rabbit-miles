import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import ConnectStrava from './pages/ConnectStrava';
import OAuthCallback from './pages/OAuthCallback';
import Settings from './pages/Settings';
import Privacy from './pages/Privacy';
import Terms from './pages/Terms';
import ActivityDetail from './pages/ActivityDetail';
import About from './pages/About';
import Admin from './pages/Admin';
import Leaderboard from './pages/Leaderboard';
import { initGA, trackPageView } from './utils/analytics';

function AnalyticsWrapper() {
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
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="connect" element={<ConnectStrava />} />
        <Route path="callback" element={<OAuthCallback />} />
        <Route path="activity/:id" element={<ActivityDetail />} />
        <Route path="settings" element={<Settings />} />
        <Route path="admin" element={<Admin />} />
        <Route path="leaderboard" element={<Leaderboard />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="terms" element={<Terms />} />
        <Route path="about" element={<About />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AnalyticsWrapper />
    </BrowserRouter>
  );
}

export default App;
