import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMe } from '../utils/api';

function Dashboard() {
  const [stats] = useState({
    totalMiles: 0,
    thisWeek: 0,
    thisMonth: 0,
  });
  const [authState, setAuthState] = useState({
    loading: true,
    user: null,
    error: null,
  });
  const navigate = useNavigate();

  useEffect(() => {
    // Check authentication status via /me endpoint
    const checkAuth = async () => {
      const result = await fetchMe();
      
      if (result.success) {
        // User is authenticated
        setAuthState({
          loading: false,
          user: result.user,
          error: null,
        });
      } else if (result.notConnected) {
        // User is not connected (401 response)
        navigate('/connect');
      } else {
        // API error or unreachable
        setAuthState({
          loading: false,
          user: null,
          error: result.error || 'Unable to reach the API',
        });
      }
    };

    checkAuth();
  }, [navigate]);

  // Loading state
  if (authState.loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-orange-600 mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (authState.error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <svg
              className="w-12 h-12 text-red-600 mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              ></path>
            </svg>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Unable to Connect
            </h2>
            <p className="text-gray-600 mb-4">
              {authState.error}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Dashboard
          </h1>
          {authState.user && (
            <p className="text-gray-600 mt-2">
              Welcome back, {authState.user.display_name}!
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              Total Miles
            </h3>
            <p className="text-3xl font-bold text-gray-900">
              {stats.totalMiles.toFixed(1)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              This Week
            </h3>
            <p className="text-3xl font-bold text-gray-900">
              {stats.thisWeek.toFixed(1)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              This Month
            </h3>
            <p className="text-3xl font-bold text-gray-900">
              {stats.thisMonth.toFixed(1)}
            </p>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Recent Activities
          </h2>
          <p className="text-gray-500">
            No activities yet. Connect your Strava account to see your running data.
          </p>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
