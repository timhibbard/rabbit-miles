import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMe, fetchActivities } from '../utils/api';

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
  const navigate = useNavigate();

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
        loadActivities();
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
  }, [navigate]);

  // Load activities for the authenticated user
  const loadActivities = async () => {
    setActivitiesState({ loading: true, activities: [], error: null });
    
    const result = await fetchActivities(10, 0);
    
    if (result.success) {
      setActivitiesState({
        loading: false,
        activities: result.data.activities || [],
        error: null,
      });
    } else {
      setActivitiesState({
        loading: false,
        activities: [],
        error: result.error || 'Failed to load activities',
      });
    }
  };

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
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Recent Activities
          </h2>
          
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
                const distanceMiles = (activity.distance / 1609.34).toFixed(2);
                const durationMinutes = Math.floor(activity.moving_time / 60);
                const durationSeconds = activity.moving_time % 60;
                const pace = activity.distance > 0 
                  ? (activity.moving_time / 60) / (activity.distance / 1609.34)
                  : 0;
                const paceMin = Math.floor(pace);
                const paceSec = Math.floor((pace - paceMin) * 60);
                
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
                          {paceMin}:{paceSec.toString().padStart(2, '0')}/mi
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
