import { useState, useEffect } from 'react';
import { fetchMe, fetchAllUsers, fetchUserActivities } from '../utils/api';
import { useNavigate } from 'react-router-dom';

function Admin() {
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [activities, setActivities] = useState([]);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [error, setError] = useState(null);
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

    const result = await fetchUserActivities(user.athlete_id);
    if (result.success) {
      setActivities(result.data.activities || []);
    } else {
      setError(result.error || 'Failed to load activities');
      setActivities([]);
    }
    setActivitiesLoading(false);
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

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Users List */}
        <div className="bg-white shadow-md rounded-lg overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">
              All Users ({users.length})
            </h2>
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
                  className={`w-full text-left px-6 py-4 hover:bg-gray-50 transition-colors ${
                    selectedUser?.athlete_id === user.athlete_id ? 'bg-orange-50' : ''
                  }`}
                >
                  <div className="flex items-center">
                    {user.profile_picture ? (
                      <img
                        src={user.profile_picture}
                        alt={user.display_name}
                        className="h-10 w-10 rounded-full"
                      />
                    ) : (
                      <div className="h-10 w-10 rounded-full bg-gray-200 flex items-center justify-center">
                        <span className="text-gray-500 font-medium">
                          {user.display_name.charAt(0).toUpperCase()}
                        </span>
                      </div>
                    )}
                    <div className="ml-4 flex-1">
                      <p className="font-medium text-gray-900">{user.display_name}</p>
                      <p className="text-sm text-gray-500">ID: {user.athlete_id}</p>
                    </div>
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
                </button>
              ))
            )}
          </div>
        </div>

        {/* Selected User's Activities */}
        <div className="bg-white shadow-md rounded-lg overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">
              {selectedUser ? `${selectedUser.display_name}'s Activities` : 'Select a User'}
            </h2>
          </div>
          <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
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
              activities.map((activity) => (
                <div key={activity.id} className="px-6 py-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="font-medium text-gray-900">{activity.name}</h3>
                      <div className="mt-1 text-sm text-gray-500 space-y-1">
                        <p>Type: {activity.type}</p>
                        <p>Distance: {formatDistance(activity.distance)}</p>
                        <p>Duration: {formatDuration(activity.moving_time)}</p>
                        <p>Date: {formatDate(activity.start_date_local)}</p>
                      </div>
                    </div>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      {activity.strava_activity_id}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Admin;
