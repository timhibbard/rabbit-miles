import { useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import debug from '../utils/debug';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

/**
 * OAuthCallback page - handles Strava OAuth redirect
 * 
 * Flow:
 * 1. Strava redirects here with code and state params
 * 2. We forward to backend /auth/callback with same params
 * 3. Backend validates, sets session cookie, and redirects to /connect
 */
function OAuthCallback() {
  const navigate = useNavigate();
  
  // Parse URL params once when component mounts
  const params = useMemo(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return {
      code: urlParams.get('code'),
      state: urlParams.get('state'),
      error: urlParams.get('error'),
    };
  }, []);

  // Determine error message (if any) outside of effect
  const errorMsg = useMemo(() => {
    if (params.error) {
      return `OAuth error: ${params.error}`;
    }
    if (!params.code || !params.state) {
      return 'Invalid OAuth callback - missing code or state';
    }
    return null;
  }, [params]);

  useEffect(() => {
    debug.log('OAuthCallback: Processing OAuth callback');
    debug.log('OAuthCallback: params=', params);

    // If there's an error, redirect to connect page after delay
    if (errorMsg) {
      debug.log('OAuthCallback: Error detected:', errorMsg);
      const timer = setTimeout(() => navigate('/connect'), 3000);
      return () => clearTimeout(timer);
    }

    // Forward to backend callback endpoint
    // The backend will validate state, exchange code for tokens, 
    // create session cookie, and redirect back to /connect
    const backendCallbackUrl = `${API_BASE_URL}/auth/callback?code=${encodeURIComponent(params.code)}&state=${encodeURIComponent(params.state)}`;
    debug.log('OAuthCallback: Redirecting to backend:', backendCallbackUrl);
    
    // Redirect to backend - it will set cookies and redirect back
    window.location.href = backendCallbackUrl;
  }, [params, errorMsg, navigate]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-gray-50 flex items-center justify-center">
      <div className="text-center">
        {errorMsg ? (
          <>
            <div className="text-red-600 mb-4">
              <svg className="w-16 h-16 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
              <p className="text-xl font-semibold">{errorMsg}</p>
            </div>
            <p className="text-gray-600">Redirecting to connect page...</p>
          </>
        ) : (
          <>
            <div className="inline-block animate-spin rounded-full h-16 w-16 border-b-2 border-orange-600 mb-4"></div>
            <p className="text-xl text-gray-900 mb-2">Completing authentication...</p>
            <p className="text-gray-600">Please wait while we connect your Strava account.</p>
          </>
        )}
      </div>
    </div>
  );
}

export default OAuthCallback;
