import { useEffect, useState } from 'react';
import { fetchMe, resetTrailMatching } from '../utils/api';

function Settings() {
  const [authState, setAuthState] = useState({
    loading: true,
    isConnected: false,
  });
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    // Check if user is connected via /me endpoint
    const checkConnection = async () => {
      const result = await fetchMe();
      setAuthState({
        loading: false,
        isConnected: result.success,
      });
    };
    
    checkConnection();
  }, []);

  const handleDisconnect = () => {
    if (window.confirm('Are you sure you want to disconnect your Strava account?')) {
      // TODO: Call disconnect API endpoint when it becomes available
      // For now, just show a message
      alert('Disconnect functionality will be available soon. Please contact support to disconnect your account.');
    }
  };

  const handleResetTrailMatching = async () => {
    if (!window.confirm('Are you sure you want to reset trail matching for all activities? This will mark all activities as unprocessed for trail matching.')) {
      return;
    }

    setResetting(true);
    try {
      const result = await resetTrailMatching();
      if (result.success) {
        alert(`Success! ${result.data.activities_reset} activities have been reset for trail matching.`);
      } else {
        alert(`Failed to reset trail matching: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error resetting trail matching:', error);
      alert('An unexpected error occurred. Please try again.');
    } finally {
      setResetting(false);
    }
  };

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

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">
          Settings
        </h1>

        <div className="bg-white rounded-lg shadow">
          {/* Strava Connection Section */}
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Strava Connection
            </h2>
            
            {authState.isConnected ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <div className="w-12 h-12 bg-orange-500 rounded-full flex items-center justify-center mr-4">
                    <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169"></path>
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      Connected to Strava
                    </p>
                    <p className="text-sm text-gray-500">
                      Your Strava data is synced with RabbitMiles
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleDisconnect}
                  className="px-4 py-2 border border-red-300 text-red-700 rounded-md hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                >
                  Disconnect
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Not Connected
                  </p>
                  <p className="text-sm text-gray-500">
                    Connect your Strava account to start tracking your miles
                  </p>
                </div>
                <a
                  href="/connect"
                  className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500"
                >
                  Connect Strava
                </a>
              </div>
            )}
          </div>

          {/* Units Section */}
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Units
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Distance Unit
                </label>
                <select
                  className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-orange-500 focus:border-orange-500 sm:text-sm rounded-md"
                  defaultValue="miles"
                >
                  <option value="miles">Miles</option>
                  <option value="kilometers">Kilometers</option>
                </select>
              </div>
            </div>
          </div>

          {/* Trail Matching Section */}
          {authState.isConnected && (
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Trail Matching
              </h2>
              <div>
                <p className="text-sm text-gray-600 mb-4">
                  Reset trail matching to re-process all activities. This will mark all activities as unprocessed for the trail matcher.
                </p>
                <button
                  onClick={handleResetTrailMatching}
                  disabled={resetting}
                  className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {resetting ? 'Resetting...' : 'Reset Trail Matching'}
                </button>
              </div>
            </div>
          )}

          {/* About Section */}
          <div className="p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              About
            </h2>
            <div className="text-sm text-gray-600">
              <p className="mb-2">
                <strong>RabbitMiles</strong> - Version 1.0.0
              </p>
              <p>
                Track your running miles with Strava integration.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Settings;
