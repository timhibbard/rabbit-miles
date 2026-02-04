import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { fetchMe, fetchActivities, refreshActivities } from '../utils/api';
import debug from '../utils/debug';
import Footer from '../components/Footer';

// Constants
const METERS_TO_MILES = 1609.34;
const ACTIVITY_POLL_INTERVAL = 30000; // Poll every 30 seconds
const INITIAL_ACTIVITIES_TO_SHOW = 15; // Initial number of activities to display
const ACTIVITIES_INCREMENT = 15; // Number of activities to load when scrolling
const MAX_ACTIVITIES_FOR_STATS = 1000; // Maximum activities to fetch for stats calculation

function Dashboard() {
  // Activity type filter state - can select bike, foot, or both
  const [selectedTypes, setSelectedTypes] = useState(['Ride', 'Run', 'Walk']);
  
  // Remove the stats state since we'll calculate it with useMemo
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
  const [displayCount, setDisplayCount] = useState(INITIAL_ACTIVITIES_TO_SHOW);
  const pollingIntervalRef = useRef(null);
  const isLoadingRef = useRef(false);
  const loadMoreTriggerRef = useRef(null);
  const navigate = useNavigate();

  // Get current month and year for labels (memoized to avoid recreating on every render)
  const currentMonthName = useMemo(() => new Date().toLocaleString('en-US', { month: 'long' }), []);
  const currentYear = useMemo(() => new Date().getFullYear(), []);

  // Calculate statistics from activities based on selected types using useMemo
  const stats = useMemo(() => {
    const activities = activitiesState.activities;
    
    if (!activities || activities.length === 0) {
      return {
        totalMiles: 0,
        totalTime: 0,
        thisWeek: 0,
        thisWeekTime: 0,
        thisMonth: 0,
        thisMonthTime: 0,
        thisYear: 0,
        thisYearTime: 0,
      };
    }

    const now = new Date();
    const startOfWeek = new Date(now);
    // Start of week (Monday) - getDay() returns 0 for Sunday, 1 for Monday, etc.
    // For Monday-based week: if Sunday (0), go back 6 days; otherwise go back (day - 1) days
    const dayOfWeek = now.getDay();
    const daysToSubtract = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
    startOfWeek.setDate(now.getDate() - daysToSubtract);
    startOfWeek.setHours(0, 0, 0, 0);

    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    const startOfYear = new Date(now.getFullYear(), 0, 1);

    let totalMiles = 0;
    let totalTime = 0;
    let thisWeek = 0;
    let thisWeekTime = 0;
    let thisMonth = 0;
    let thisMonthTime = 0;
    let thisYear = 0;
    let thisYearTime = 0;

    activities.forEach((activity) => {
      // Filter by selected activity types
      if (!selectedTypes.includes(activity.type)) {
        return;
      }

      const activityDate = new Date(activity.start_date_local);
      const miles = activity.distance / METERS_TO_MILES;
      const time = activity.moving_time;

      // Total (all time)
      totalMiles += miles;
      totalTime += time;

      // This year
      if (activityDate >= startOfYear) {
        thisYear += miles;
        thisYearTime += time;
      }

      // This month
      if (activityDate >= startOfMonth) {
        thisMonth += miles;
        thisMonthTime += time;
      }

      // This week
      if (activityDate >= startOfWeek) {
        thisWeek += miles;
        thisWeekTime += time;
      }
    });

    return {
      totalMiles,
      totalTime,
      thisWeek,
      thisWeekTime,
      thisMonth,
      thisMonthTime,
      thisYear,
      thisYearTime,
    };
  }, [activitiesState.activities, selectedTypes]);

  // Calculate display data using useMemo
  const displayData = useMemo(() => {
    const filteredActivities = activitiesState.activities.filter(activity => selectedTypes.includes(activity.type));
    const totalFiltered = filteredActivities.length;
    const visibleActivities = filteredActivities.slice(0, displayCount);
    const hasMore = displayCount < totalFiltered;
    
    return {
      filteredActivities,
      totalFiltered,
      visibleActivities,
      hasMore,
    };
  }, [activitiesState.activities, selectedTypes, displayCount]);

  // Load activities for the authenticated user
  const loadActivities = useCallback(async (silent = false) => {
    // Prevent overlapping requests
    if (isLoadingRef.current) {
      if (silent) {
        debug.log('Skipping silent refresh - request already in progress');
      }
      return;
    }
    
    isLoadingRef.current = true;
    
    // If not silent, show loading state
    if (!silent) {
      setActivitiesState({ loading: true, activities: [], error: null });
    }
    
    // Fetch all activities (increase limit to get all for stats calculation)
    const result = await fetchActivities(MAX_ACTIVITIES_FOR_STATS, 0);
    
    isLoadingRef.current = false;
    
    if (result.success) {
      const activities = result.data.activities || [];
      setActivitiesState({
        loading: false,
        activities,
        error: null,
      });
      // Stats will be calculated automatically via useMemo
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
        debug.warn('Silent activity refresh failed:', result.error);
      }
    }
  }, []);

  // Toggle activity type filter (Bike or Foot)
  const toggleActivityType = useCallback((type) => {
    if (type === 'Bike') {
      if (selectedTypes.includes('Ride')) {
        // Remove bike
        setSelectedTypes(prev => prev.filter(t => t !== 'Ride'));
      } else {
        // Add bike
        setSelectedTypes(prev => [...prev, 'Ride']);
      }
    } else if (type === 'Foot') {
      if (selectedTypes.includes('Run') || selectedTypes.includes('Walk')) {
        // Remove foot activities
        setSelectedTypes(prev => prev.filter(t => t !== 'Run' && t !== 'Walk'));
      } else {
        // Add foot activities
        setSelectedTypes(prev => [...prev, 'Run', 'Walk']);
      }
    }
    
    // Reset to initial display count after filter changes
    setDisplayCount(INITIAL_ACTIVITIES_TO_SHOW);
  }, [selectedTypes]);

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
      debug.log('Dashboard: Checking authentication...');
      const result = await fetchMe();
      debug.log('Dashboard: fetchMe result:', result);
      
      if (result.success) {
        // User is authenticated
        debug.log('Dashboard: User authenticated:', result.user);
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
        debug.log('Dashboard: User not connected, redirecting to /connect');
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

  // Intersection observer for infinite scroll
  useEffect(() => {
    const trigger = loadMoreTriggerRef.current;
    if (!trigger) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting && displayData.hasMore) {
          setDisplayCount(prev => prev + ACTIVITIES_INCREMENT);
        }
      },
      {
        root: null,
        rootMargin: '100px',
        threshold: 0.1,
      }
    );

    observer.observe(trigger);

    return () => {
      observer.disconnect();
    };
  }, [displayData.hasMore]);

  // Format time in seconds to hours:minutes
  const formatTime = (seconds) => {
    if (!seconds || seconds === 0) return '0:00';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}:${minutes.toString().padStart(2, '0')}`;
  };

  // Loading state
  if (authState.loading) {
    return (
      <>
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-orange-600 mb-4"></div>
            <p className="text-gray-600">Loading...</p>
          </div>
        </div>
        <Footer />
      </>
    );
  }

  // Error state
  if (authState.error) {
    return (
      <>
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
        <Footer />
      </>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Debug mode indicator */}
      {debug.enabled() && (
        <div className="fixed top-0 left-0 right-0 bg-yellow-400 text-black text-center py-1 text-xs font-mono z-50">
          🐛 DEBUG MODE ENABLED - Check browser console for detailed logs
        </div>
      )}
      
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
          
          {/* Activity Type Filter */}
          <div className="mt-6 flex items-center gap-4">
            <span className="text-sm font-medium text-gray-700">Activity Type:</span>
            <div className="inline-flex rounded-lg border border-gray-300 bg-white">
              <button
                onClick={() => toggleActivityType('Bike')}
                className={`px-4 py-2 text-sm font-medium rounded-l-lg transition-colors ${
                  selectedTypes.includes('Ride')
                    ? 'bg-orange-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                Bike
              </button>
              <button
                onClick={() => toggleActivityType('Foot')}
                className={`px-4 py-2 text-sm font-medium rounded-r-lg border-l transition-colors ${
                  selectedTypes.includes('Run') || selectedTypes.includes('Walk')
                    ? 'bg-orange-600 text-white border-orange-600'
                    : 'bg-white text-gray-700 hover:bg-gray-50 border-gray-300'
                }`}
              >
                Foot
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              Total Miles
            </h3>
            <p className="text-3xl font-bold text-gray-900">
              {stats.totalMiles.toFixed(1)}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {formatTime(stats.totalTime)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              This Week
            </h3>
            <p className="text-3xl font-bold text-gray-900">
              {stats.thisWeek.toFixed(1)}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {formatTime(stats.thisWeekTime)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              {currentMonthName}
            </h3>
            <p className="text-3xl font-bold text-gray-900">
              {stats.thisMonth.toFixed(1)}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {formatTime(stats.thisMonthTime)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              {currentYear}
            </h3>
            <p className="text-3xl font-bold text-gray-900">
              {stats.thisYear.toFixed(1)}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {formatTime(stats.thisYearTime)}
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
          
          {!activitiesState.loading && !activitiesState.error && (
            activitiesState.activities.length === 0 ? (
              <p className="text-gray-500">
                No activities yet. Your Strava activities will appear here once they are synced.
              </p>
            ) : (
              activitiesState.activities.filter(activity => selectedTypes.includes(activity.type)).length === 0 ? (
                <p className="text-gray-500">
                  No activities match the selected filter. Try selecting a different activity type.
                </p>
              ) : null
            )
          )}
          
          {!activitiesState.loading && !activitiesState.error && displayData.totalFiltered > 0 && (
            <>
              <div className="space-y-4">
                {displayData.visibleActivities.map((activity) => {
                const distanceMiles = (activity.distance / METERS_TO_MILES).toFixed(2);
                const durationMinutes = Math.floor(activity.elapsed_time / 60);
                const durationSeconds = activity.elapsed_time % 60;
                
                // Calculate trail metrics if available
                const distanceOnTrailMiles = activity.distance_on_trail 
                  ? (activity.distance_on_trail / METERS_TO_MILES).toFixed(2)
                  : null;
                const timeOnTrailMinutes = activity.time_on_trail 
                  ? Math.floor(activity.time_on_trail / 60)
                  : null;
                
                // Calculate pace with proper zero handling
                // Pace = moving_time (minutes) / distance (miles) for Run
                // Speed = distance (miles) / moving_time (hours) for Ride and Walk
                let paceDisplay = 'N/A';
                if (activity.distance > 0 && activity.moving_time > 0) {
                  const distanceMi = activity.distance / METERS_TO_MILES;
                  const timeHours = activity.moving_time / 3600;
                  
                  if (activity.type === 'Ride' || activity.type === 'Walk') {
                    // Use mph for bike and walk
                    const mph = distanceMi / timeHours;
                    paceDisplay = `${mph.toFixed(1)} mph`;
                  } else {
                    // Use min/mi for running
                    const pace = (activity.moving_time / 60) / distanceMi;
                    const paceMin = Math.floor(pace);
                    const paceSec = Math.floor((pace - paceMin) * 60);
                    paceDisplay = `${paceMin}:${paceSec.toString().padStart(2, '0')}/mi`;
                  }
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
                  <Link
                    key={activity.id}
                    to={`/activity/${activity.id}`}
                    className="block border border-gray-200 rounded-lg p-4 hover:bg-gray-50 hover:border-orange-300 transition-colors"
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
                        {distanceOnTrailMiles && (
                          <p className="text-xs text-green-600 mt-0.5">
                            {distanceOnTrailMiles} mi on trail
                          </p>
                        )}
                      </div>
                      <div>
                        <p className="text-gray-500">Duration</p>
                        <p className="font-semibold text-gray-900">
                          {durationMinutes}:{durationSeconds.toString().padStart(2, '0')}
                        </p>
                        {timeOnTrailMinutes !== null && (
                          <p className="text-xs text-green-600 mt-0.5">
                            {timeOnTrailMinutes} min on trail
                          </p>
                        )}
                      </div>
                      <div>
                        <p className="text-gray-500">{activity.type === 'Ride' || activity.type === 'Walk' ? 'Speed' : 'Pace'}</p>
                        <p className="font-semibold text-gray-900">{paceDisplay}</p>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
            
            {/* Infinite scroll trigger and status */}
            {displayData.hasMore && (
              <div ref={loadMoreTriggerRef} className="mt-6 text-center py-4">
                <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-orange-600"></div>
                <p className="text-sm text-gray-500 mt-2">Loading more activities...</p>
              </div>
            )}
            
            {!displayData.hasMore && displayCount > INITIAL_ACTIVITIES_TO_SHOW && (
              <div className="mt-6 text-center py-4">
                <p className="text-sm text-gray-500">
                  You've reached the end. Showing all {displayData.totalFiltered} activities.
                </p>
              </div>
            )}
          </>
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
      
      {/* Footer */}
      <Footer />
    </div>
  );
}

export default Dashboard;
