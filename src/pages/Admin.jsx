import { useState, useEffect } from 'react';
import { fetchMe, fetchAllUsers, fetchUserActivities, deleteUser, backfillUserActivities } from '../utils/api';
import { useNavigate } from 'react-router-dom';

function Admin() {
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [activities, setActivities] = useState([]);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [loadingMoreActivities, setLoadingMoreActivities] = useState(false);
  const [activitiesOffset, setActivitiesOffset] = useState(0);
  const [totalActivitiesCount, setTotalActivitiesCount] = useState(0);
  const [hasMoreActivities, setHasMoreActivities] = useState(false);
  const [error, setError] = useState(null);
  const [refreshingUsers, setRefreshingUsers] = useState(false);
  const [refreshingActivities, setRefreshingActivities] = useState(false);
  const [backfillingActivities, setBackfillingActivities] = useState(false);
  const [deleteConfirmUser, setDeleteConfirmUser] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [successMessage, setSuccessMessage] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const loadAdminData = async () => {
      setLoading(true);
      setError(null);

      // Check if user is authenticated and is an admin
      const meResult = await fetchMe();
      if (!meResult.success || meResult.notConnected) {
        navigate('/connect');
        return;
      }

      setCurrentUser(meResult.user);

      // If user is not an admin, show error
      if (!meResult.user.is_admin) {
        setError('Access denied - admin privileges required');
        setLoading(false);
        return;
      }

      // Fetch all users
      const usersResult = await fetchAllUsers();
      if (!usersResult.success) {
        setError(usersResult.error || 'Failed to load users');
        setLoading(false);
        return;
      }

      setUsers(usersResult.data.users || []);
      setLoading(false);
    };

    loadAdminData();
  }, [navigate]);

  const handleUserSelect = async (user) => {
    setSelectedUser(user);
    setActivitiesLoading(true);
    setError(null);
    setActivitiesOffset(0);
    setActivities([]);

    const result = await fetchUserActivities(user.athlete_id, 50, 0);
    if (result.success) {
      setActivities(result.data.activities || []);
      setTotalActivitiesCount(result.data.total_count || 0);
      setHasMoreActivities((result.data.activities || []).length < (result.data.total_count || 0));
      setActivitiesOffset(50);
    } else {
      setError(result.error || 'Failed to load activities');
      setActivities([]);
      setTotalActivitiesCount(0);
      setHasMoreActivities(false);
    }
    setActivitiesLoading(false);
  };

  const handleRefreshUsers = async () => {
    setRefreshingUsers(true);
    setError(null);

    const usersResult = await fetchAllUsers();
    if (usersResult.success) {
      setUsers(usersResult.data.users || []);
    } else {
      setError(usersResult.error || 'Failed to refresh users');
    }
    setRefreshingUsers(false);
  };

  const handleRefreshActivities = async () => {
    if (!selectedUser) return;
    
    setRefreshingActivities(true);
    setError(null);
    setActivitiesOffset(0);

    const result = await fetchUserActivities(selectedUser.athlete_id, 50, 0);
    if (result.success) {
      setActivities(result.data.activities || []);
      setTotalActivitiesCount(result.data.total_count || 0);
      setHasMoreActivities((result.data.activities || []).length < (result.data.total_count || 0));
      setActivitiesOffset(50);
    } else {
      setError(result.error || 'Failed to refresh activities');
    }
    setRefreshingActivities(false);
  };

  const handleDeleteUserClick = (user, event) => {
    // Stop propagation to prevent user selection
    event.stopPropagation();
    setDeleteConfirmUser(user);
    setError(null);
    setSuccessMessage(null);
  };

  const handleDeleteUserConfirm = async () => {
    if (!deleteConfirmUser) return;

    setDeleting(true);
    setError(null);
    setSuccessMessage(null);

    const result = await deleteUser(deleteConfirmUser.athlete_id);
    
    if (result.success) {
      setSuccessMessage(`User ${deleteConfirmUser.display_name} and all their data have been deleted successfully.`);
      
      // Clear selection if the deleted user was selected
      if (selectedUser?.athlete_id === deleteConfirmUser.athlete_id) {
        setSelectedUser(null);
        setActivities([]);
      }
      
      // Refresh the users list
      const usersResult = await fetchAllUsers();
      if (usersResult.success) {
        setUsers(usersResult.data.users || []);
      }
      
      setDeleteConfirmUser(null);
    } else {
      setError(result.error || 'Failed to delete user');
    }
    
    setDeleting(false);
  };

  const handleDeleteUserCancel = () => {
    setDeleteConfirmUser(null);
  };

  const handleBackfillActivities = async () => {
    if (!selectedUser) return;
    
    setBackfillingActivities(true);
    setError(null);
    setSuccessMessage(null);

    const result = await backfillUserActivities(selectedUser.athlete_id);
    if (result.success) {
      setSuccessMessage(`Successfully backfilled ${result.data.activities_stored} activities for ${selectedUser.display_name}`);
      // Refresh activities list to show newly backfilled activities
      setActivitiesOffset(0);
      const activitiesResult = await fetchUserActivities(selectedUser.athlete_id, 50, 0);
      if (activitiesResult.success) {
        setActivities(activitiesResult.data.activities || []);
        setTotalActivitiesCount(activitiesResult.data.total_count || 0);
        setHasMoreActivities((activitiesResult.data.activities || []).length < (activitiesResult.data.total_count || 0));
        setActivitiesOffset(50);
      }
    } else {
      setError(result.error || 'Failed to backfill activities');
    }
    setBackfillingActivities(false);
  };

  const loadMoreActivities = async () => {
    if (!selectedUser || loadingMoreActivities || !hasMoreActivities) return;
    
    setLoadingMoreActivities(true);
    setError(null);

    const result = await fetchUserActivities(selectedUser.athlete_id, 50, activitiesOffset);
    if (result.success) {
      const newActivities = result.data.activities || [];
      setActivities([...activities, ...newActivities]);
      const newOffset = activitiesOffset + 50;
      setActivitiesOffset(newOffset);
      setHasMoreActivities(newOffset < (result.data.total_count || 0));
    } else {
      setError(result.error || 'Failed to load more activities');
    }
    setLoadingMoreActivities(false);
  };

  const handleScroll = (e) => {
    const bottom = e.target.scrollHeight - e.target.scrollTop <= e.target.clientHeight + 50;
    if (bottom && hasMoreActivities && !loadingMoreActivities) {
      loadMoreActivities();
    }
  };

  const getActivityCountText = () => {
    if (!selectedUser) return 'Select a User';
    
    const baseText = `${selectedUser.display_name}'s Activities`;
    if (totalActivitiesCount > activities.length) {
      return `${baseText} (${activities.length} of ${totalActivitiesCount})`;
    }
    return `${baseText} (${activities.length})`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDistance = (meters) => {
    if (!meters) return 'N/A';
    const miles = meters / 1609.34;
    return `${miles.toFixed(2)} mi`;
  };

  // Format duration for activity list (returns N/A for missing data)
  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  // Format distance for trail statistics (returns 0 mi for zero values)
  const formatTrailDistance = (meters) => {
    if (!meters || meters === 0) return '0 mi';
    const miles = meters / 1609.34;
    return `${miles.toFixed(2)} mi`;
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
          <p className="mt-2 text-gray-600">Loading admin panel...</p>
        </div>
      </div>
    );
  }

  if (error && !currentUser?.is_admin) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-center">
            <svg className="h-6 w-6 text-red-600 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <h3 className="text-lg font-medium text-red-900">Access Denied</h3>
              <p className="mt-1 text-red-700">{error}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Admin Panel</h1>
        <p className="mt-2 text-gray-600">
          Viewing as admin: {currentUser?.display_name} (ID: {currentUser?.athlete_id})
        </p>
      </div>

      {error && (
        <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <p className="text-yellow-800">{error}</p>
        </div>
      )}

      {successMessage && (
        <div className="mb-6 bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-green-800">{successMessage}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Users List */}
        <div className="bg-white shadow-md rounded-lg overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-900">
              All Users ({users.length})
            </h2>
            <button
              onClick={handleRefreshUsers}
              disabled={refreshingUsers}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {refreshingUsers ? (
                <>
                  <svg className="animate-spin -ml-0.5 mr-2 h-4 w-4 text-gray-700" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Refreshing...
                </>
              ) : (
                <>
                  <svg className="-ml-0.5 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Refresh
                </>
              )}
            </button>
          </div>
          <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
            {users.length === 0 ? (
              <div className="px-6 py-8 text-center text-gray-500">
                No users found
              </div>
            ) : (
              users.map((user) => (
                <button
                  key={user.athlete_id}
                  onClick={() => handleUserSelect(user)}
                  className={`w-full text-left px-6 py-2 hover:bg-gray-50 transition-colors ${
                    selectedUser?.athlete_id === user.athlete_id ? 'bg-orange-50' : ''
                  }`}
                >
                  <div className="flex items-start">
                    {user.profile_picture ? (
                      <img
                        src={user.profile_picture}
                        alt={user.display_name}
                        className="h-10 w-10 rounded-full flex-shrink-0"
                      />
                    ) : (
                      <div className="h-10 w-10 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                        <span className="text-gray-500 font-medium">
                          {user.display_name ? user.display_name.charAt(0).toUpperCase() : '?'}
                        </span>
                      </div>
                    )}
                    <div className="ml-4 flex-1 min-w-0">
                      <p className="font-medium text-gray-900" title={`ID: ${user.athlete_id}`}>
                        {user.display_name}
                        <span className="sr-only"> (ID: {user.athlete_id})</span>
                      </p>
                      
                      {user.stats && (
                        <p className="mt-1 text-xs text-gray-600" aria-label={`This week: ${formatTrailDistance(user.stats.week_distance)}, This month: ${formatTrailDistance(user.stats.month_distance)}, This year: ${formatTrailDistance(user.stats.year_distance)}, Total: ${formatTrailDistance(user.stats.total_distance)}`}>
                          {formatTrailDistance(user.stats.week_distance)} | {formatTrailDistance(user.stats.month_distance)} | {formatTrailDistance(user.stats.year_distance)} | {formatTrailDistance(user.stats.total_distance)}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                      <button
                        onClick={(e) => handleDeleteUserClick(user, e)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-md transition-colors"
                        title="Delete user"
                      >
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                      <svg
                        className="h-5 w-5 text-gray-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M9 5l7 7-7 7"
                        />
                      </svg>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Selected User's Activities */}
        <div className="bg-white shadow-md rounded-lg overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-900">
              {getActivityCountText()}
            </h2>
            {selectedUser && (
              <div className="flex gap-2">
                <button
                  onClick={handleBackfillActivities}
                  disabled={backfillingActivities}
                  className="inline-flex items-center px-3 py-2 border border-orange-300 shadow-sm text-sm leading-4 font-medium rounded-md text-orange-700 bg-white hover:bg-orange-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Download all activities from Strava since Jan 1, 2026"
                >
                  {backfillingActivities ? (
                    <>
                      <svg className="animate-spin -ml-0.5 mr-2 h-4 w-4 text-orange-700" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Backfilling...
                    </>
                  ) : (
                    <>
                      <svg className="-ml-0.5 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      Backfill
                    </>
                  )}
                </button>
                <button
                  onClick={handleRefreshActivities}
                  disabled={refreshingActivities}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {refreshingActivities ? (
                    <>
                      <svg className="animate-spin -ml-0.5 mr-2 h-4 w-4 text-gray-700" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Refreshing...
                    </>
                  ) : (
                    <>
                      <svg className="-ml-0.5 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      Refresh
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
          <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto" onScroll={handleScroll}>
            {!selectedUser ? (
              <div className="px-6 py-8 text-center text-gray-500">
                Select a user from the list to view their activities
              </div>
            ) : activitiesLoading ? (
              <div className="px-6 py-8 text-center">
                <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-orange-600"></div>
                <p className="mt-2 text-gray-600">Loading activities...</p>
              </div>
            ) : activities.length === 0 ? (
              <div className="px-6 py-8 text-center text-gray-500">
                No activities found for this user
              </div>
            ) : (
              <>
                {activities.map((activity) => (
                  <a
                    key={activity.id}
                    href={`/activity/${activity.id}?debug=1`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block px-6 py-4 hover:bg-gray-50 transition-colors cursor-pointer"
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <h3 className="font-medium text-gray-900">{activity.name}</h3>
                        <div className="mt-1 text-sm text-gray-500 space-y-1">
                          <p>Type: {activity.type}</p>
                          <p>Distance: {formatDistance(activity.distance)}</p>
                          <p>Duration: {formatDuration(activity.moving_time)}</p>
                          <p>Date: {formatDate(activity.start_date_local)}</p>
                          {activity.distance_on_trail !== null && activity.distance_on_trail !== undefined && 
                           activity.time_on_trail !== null && activity.time_on_trail !== undefined && (
                            <p className="text-orange-600 font-medium">
                              Trail: {formatDistance(activity.distance_on_trail)} / {formatDuration(activity.time_on_trail)}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {activity.strava_activity_id}
                        </span>
                        <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    </div>
                  </a>
                ))}
                {loadingMoreActivities && (
                  <div className="px-6 py-4 text-center">
                    <div className="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-orange-600"></div>
                    <p className="mt-2 text-sm text-gray-600">Loading more activities...</p>
                  </div>
                )}
                {!hasMoreActivities && activities.length > 0 && (
                  <div className="px-6 py-4 text-center text-sm text-gray-500">
                    All activities loaded
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      {deleteConfirmUser && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
          <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <div className="flex items-center mb-4">
                <div className="flex-shrink-0 w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                  <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div className="ml-4">
                  <h3 className="text-lg font-medium text-gray-900">Delete User</h3>
                </div>
              </div>
              
              <div className="mb-6">
                <p className="text-gray-600 mb-3">
                  Are you sure you want to delete <strong>{deleteConfirmUser.display_name}</strong> (ID: {deleteConfirmUser.athlete_id})?
                </p>
                <div className="bg-red-50 border border-red-200 rounded-md p-3">
                  <p className="text-sm text-red-800">
                    <strong>Warning:</strong> This action cannot be undone. This will permanently delete:
                  </p>
                  <ul className="mt-2 ml-4 text-sm text-red-700 list-disc">
                    <li>User account and profile</li>
                    <li>All activity records</li>
                    <li>All associated data</li>
                  </ul>
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button
                  onClick={handleDeleteUserCancel}
                  disabled={deleting}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteUserConfirm}
                  disabled={deleting}
                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center"
                >
                  {deleting ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Deleting...
                    </>
                  ) : (
                    'Delete User'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Admin;
