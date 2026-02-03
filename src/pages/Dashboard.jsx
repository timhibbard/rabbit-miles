import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMe, fetchActivities, refreshActivities } from '../utils/api';

// Constants
const METERS_TO_MILES = 1609.34;
const ACTIVITY_POLL_INTERVAL = 30000; // Poll every 30 seconds

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
  const [activitiesState, setActivitiesState] = useState({
    loading: false,
    activities: [],
    error: null,
  });
  const [refreshState, setRefreshState] = useState({
    refreshing: false,
    message: null,
    error: null,
  });
  const [isPolling, setIsPolling] = useState(false);
  const pollingIntervalRef = useRef(null);
  const isLoadingRef = useRef(false);
  const navigate = useNavigate();

  // Load activities for the authenticated user
  const loadActivities = useCallback(async (silent = false) => {
    // Prevent overlapping requests
    if (isLoadingRef.current) {
      if (silent) {
        console.log('Skipping silent refresh - request already in progress');
      }
      return;
    }
    
    isLoadingRef.current = true;
    
    // If not silent, show loading state
    if (!silent) {
      setActivitiesState({ loading: true, activities: [], error: null });
    }
    
    const result = await fetchActivities(10, 0);
    
    isLoadingRef.current = false;
    
    if (result.success) {
      setActivitiesState({
        loading: false,
        activities: result.data.activities || [],
        error: null,
      });
    } else {
      // For silent refresh, don't update error state to avoid disrupting UI
      if (!silent) {
        setActivitiesState({
          loading: false,
          activities: [],
          error: result.error || 'Failed to load activities',
        });
      } else {
        // For silent refresh, just log the error
        console.warn('Silent activity refresh failed:', result.error);
      }
    }
  }, []);

  // Refresh activities from Strava
  const handleRefreshActivities = async () => {
    setRefreshState({ refreshing: true, message: null, error: null });
    
    const result = await refreshActivities();
    
    if (result.success) {
      const message = result.data.message || 'Activities refreshed successfully';
      const totalStored = result.data.total_activities_stored || 0;
      
      // Show the message from backend (includes helpful hint for 0 activities)
      const detailMessage = totalStored > 0 
        ? `${message} (${totalStored} activities synced)`
        : message; // Use backend message as-is when 0 activities
      
      setRefreshState({
        refreshing: false,
        message: detailMessage,
        error: null,
      });
      // Reload activities after successful refresh
      loadActivities(false);
      // Clear success message after 8 seconds (longer for hint message)
      setTimeout(() => {
        setRefreshState(prev => ({ ...prev, message: null }));
      }, 8000);
    } else {
      setRefreshState({
        refreshing: false,
        message: null,
        error: result.error || 'Failed to refresh activities',
      });
      // Clear error message after 10 seconds
      setTimeout(() => {
        setRefreshState(prev => ({ ...prev, error: null }));
      }, 10000);
    }
  };

  // Start automatic polling for activity updates
  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) return; // Already polling
    
    setIsPolling(true);
    pollingIntervalRef.current = setInterval(() => {
      // Silent refresh - don't show loading spinner
      loadActivities(true);
    }, ACTIVITY_POLL_INTERVAL);
  }, [loadActivities]);

  // Stop automatic polling
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  useEffect(() => {
    // Check authentication status via /me endpoint
    const checkAuth = async () => {
      console.log('Dashboard: Checking authentication...');
      const result = await fetchMe();
      console.log('Dashboard: fetchMe result:', result);
      
      if (result.success) {
        // User is authenticated
        console.log('Dashboard: User authenticated:', result.user);
        setAuthState({
          loading: false,
          user: result.user,
          error: null,
        });
        // Fetch activities after successful authentication
        loadActivities(false);
        // Start automatic polling
        startPolling();
      } else if (result.notConnected) {
        // User is not connected (401 response)
        console.log('Dashboard: User not connected, redirecting to /connect');
        navigate('/connect');
      } else {
        // API error or unreachable
        console.error('Dashboard: API error:', result.error);
        setAuthState({
          loading: false,
          user: null,
          error: result.error || 'Unable to reach the API',
        });
      }
    };

    checkAuth();

    // Cleanup polling on unmount
    return () => {
      stopPolling();
    };
  }, [navigate, loadActivities, startPolling, stopPolling]);

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
          <div className="flex items-center gap-4">
            {authState.user && authState.user.profile_picture && (
              <img 
                src={authState.user.profile_picture} 
                alt={authState.user.display_name || "User profile picture"}
                referrerPolicy="no-referrer"
                onError={(e) => { e.target.style.display = 'none'; }}
                className="w-16 h-16 rounded-full border-2 border-orange-500"
              />
            )}
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Dashboard
              </h1>
              {authState.user && (
                <p className="text-gray-600 mt-2">
                  Welcome back, {authState.user.display_name}!
                </p>
              )}
            </div>
          </div>
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
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-gray-900">
              Recent Activities
            </h2>
          </div>
          
          {refreshState.message && (
            <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-4">
              <p className="text-green-800">{refreshState.message}</p>
            </div>
          )}
          
          {refreshState.error && (
            <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800">{refreshState.error}</p>
            </div>
          )}
          
          {activitiesState.loading && (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600 mb-2"></div>
              <p className="text-gray-500">Loading activities...</p>
            </div>
          )}
          
          {activitiesState.error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-600">{activitiesState.error}</p>
            </div>
          )}
          
          {!activitiesState.loading && !activitiesState.error && activitiesState.activities.length === 0 && (
            <p className="text-gray-500">
              No activities yet. Your Strava activities will appear here once they are synced.
            </p>
          )}
          
          {!activitiesState.loading && !activitiesState.error && activitiesState.activities.length > 0 && (
            <div className="space-y-4">
              {activitiesState.activities.map((activity) => {
                const distanceMiles = (activity.distance / METERS_TO_MILES).toFixed(2);
                const durationMinutes = Math.floor(activity.elapsed_time / 60);
                const durationSeconds = activity.elapsed_time % 60;
                
                // Calculate pace with proper zero handling
                // Pace = elapsed_time (minutes) / distance (miles)
                let paceMin = 0;
                let paceSec = 0;
                if (activity.distance > 0 && activity.elapsed_time > 0) {
                  const pace = (activity.elapsed_time / 60) / (activity.distance / METERS_TO_MILES);
                  paceMin = Math.floor(pace);
                  paceSec = Math.floor((pace - paceMin) * 60);
                }
                
                // Format date
                const activityDate = activity.start_date_local 
                  ? new Date(activity.start_date_local).toLocaleDateString('en-US', {
                      weekday: 'short',
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                    })
                  : '';
                
                return (
                  <div 
                    key={activity.id}
                    className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h3 className="font-semibold text-gray-900">{activity.name}</h3>
                        <p className="text-sm text-gray-500">{activityDate}</p>
                      </div>
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                        {activity.type}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500">Distance</p>
                        <p className="font-semibold text-gray-900">{distanceMiles} mi</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Duration</p>
                        <p className="font-semibold text-gray-900">
                          {durationMinutes}:{durationSeconds.toString().padStart(2, '0')}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Pace</p>
                        <p className="font-semibold text-gray-900">
                          {activity.distance > 0 && activity.elapsed_time > 0 
                            ? `${paceMin}:${paceSec.toString().padStart(2, '0')}/mi`
                            : 'N/A'
                          }
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          
          {/* Controls at bottom */}
          <div className="mt-6 pt-6 border-t border-gray-200 flex justify-between items-center" aria-label="Activity controls">
            <div className="flex items-center gap-3">
              {isPolling && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                  Auto-updating
                </span>
              )}
            </div>
            <button
              onClick={handleRefreshActivities}
              disabled={refreshState.refreshing}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-white font-medium focus:outline-none focus:ring-2 focus:ring-orange-500 ${
                refreshState.refreshing
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-orange-600 hover:bg-orange-700'
              }`}
            >
              {refreshState.refreshing ? (
                <>
                  <div className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  <span>Refreshing...</span>
                </>
              ) : (
                <>
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    ></path>
                  </svg>
                  <span>Refresh Activities</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
