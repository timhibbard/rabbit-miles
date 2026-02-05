import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import ConnectStrava from './pages/ConnectStrava';
import OAuthCallback from './pages/OAuthCallback';
import Settings from './pages/Settings';
import Privacy from './pages/Privacy';
import Terms from './pages/Terms';
import ActivityDetail from './pages/ActivityDetail';

function App() {
  return (
    <BrowserRouter basename="/rabbit-miles">
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="connect" element={<ConnectStrava />} />
          <Route path="callback" element={<OAuthCallback />} />
          <Route path="activity/:id" element={<ActivityDetail />} />
          <Route path="settings" element={<Settings />} />
          <Route path="privacy" element={<Privacy />} />
          <Route path="terms" element={<Terms />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
