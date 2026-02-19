import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMe, fetchLeaderboard } from '../utils/api';

function Leaderboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [selectedWindow, setSelectedWindow] = useState('week');
  const [selectedActivityType, setSelectedActivityType] = useState('foot'); // Default to Foot only
  const [leaderboardData, setLeaderboardData] = useState(null);
  const [error, setError] = useState(null);

  // Check admin status and authentication
  useEffect(() => {
    const checkAuth = async () => {
      const meResult = await fetchMe();
      
      if (!meResult.success || !meResult.user) {
        // Not authenticated, redirect to connect page
        navigate('/connect');
        return;
      }
      
      if (!meResult.user.is_admin) {
        // Not an admin, redirect to dashboard
        navigate('/');
        return;
      }
      
      setIsAdmin(true);
      setCurrentUserId(meResult.user.athlete_id);
      setLoading(false);
    };
    
    checkAuth();
  }, [navigate]);

  // Fetch leaderboard data when window or activity type changes
  useEffect(() => {
    if (!isAdmin) return;
    
    const loadLeaderboard = async () => {
      setError(null);
      try {
        const result = await fetchLeaderboard(selectedWindow, {
          user_id: currentUserId,
          activity_type: selectedActivityType,
        });
        
        if (result.success) {
          setLeaderboardData(result.data);
          console.log('TELEMETRY - leaderboard_page_view', {
            window: selectedWindow,
            window_key: result.data.window_key,
            activity_type: selectedActivityType,
          });
        } else {
          setError(result.error || 'Failed to load leaderboard');
        }
      } catch (err) {
        console.error('Error loading leaderboard:', err);
        setError('An unexpected error occurred');
      }
    };
    
    loadLeaderboard();
  }, [selectedWindow, selectedActivityType, isAdmin, currentUserId]);

  // Format distance in meters to miles
  const formatDistance = (meters) => {
    const miles = meters / 1609.34;
    return miles.toFixed(2);
  };

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString();
  };

  // Toggle activity type filter (Bike or Foot)
  const toggleActivityType = (type) => {
    if (type === 'bike') {
      setSelectedActivityType(selectedActivityType === 'bike' ? 'all' : 'bike');
    } else if (type === 'foot') {
      setSelectedActivityType(selectedActivityType === 'foot' ? 'all' : 'foot');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-orange-600 mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAdmin) {
    return null; // Will redirect in useEffect
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            🏆 Leaderboard (Admin Preview)
          </h1>
          <p className="text-gray-600">
            View runner rankings by time period. This feature is currently in admin-only testing mode.
          </p>
        </div>

        {/* Window Selector */}
        <div className="mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Time Period
            </label>
            <div className="flex space-x-2">
              <button
                onClick={() => setSelectedWindow('week')}
                className={`px-4 py-2 rounded-md font-medium ${
                  selectedWindow === 'week'
                    ? 'bg-orange-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                This Week
              </button>
              <button
                onClick={() => setSelectedWindow('month')}
                className={`px-4 py-2 rounded-md font-medium ${
                  selectedWindow === 'month'
                    ? 'bg-orange-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                This Month
              </button>
              <button
                onClick={() => setSelectedWindow('year')}
                className={`px-4 py-2 rounded-md font-medium ${
                  selectedWindow === 'year'
                    ? 'bg-orange-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                This Year
              </button>
            </div>
          </div>
        </div>

        {/* Activity Type Filter */}
        <div className="mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Activity Type
            </label>
            <div className="inline-flex rounded-lg border border-gray-300 bg-white">
              <button
                onClick={() => toggleActivityType('bike')}
                className={`px-4 py-2 text-sm font-medium rounded-l-lg transition-colors ${
                  selectedActivityType === 'bike' || selectedActivityType === 'all'
                    ? 'bg-orange-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                Bike
              </button>
              <button
                onClick={() => toggleActivityType('foot')}
                className={`px-4 py-2 text-sm font-medium rounded-r-lg border-l transition-colors ${
                  selectedActivityType === 'foot' || selectedActivityType === 'all'
                    ? 'bg-orange-600 text-white border-orange-600'
                    : 'bg-white text-gray-700 hover:bg-gray-50 border-gray-300'
                }`}
              >
                Foot
              </button>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Previous Period Top 3 */}
        {leaderboardData && leaderboardData.previous_top3 && leaderboardData.previous_top3.length > 0 && (
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              🥇 Last {selectedWindow === 'week' ? 'Week' : selectedWindow === 'month' ? 'Month' : 'Year'}'s Top 3
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {leaderboardData.previous_top3.map((entry, idx) => (
                <div key={entry.user.id} className="bg-white rounded-lg shadow-md p-6 text-center">
                  <div className="text-4xl mb-2">
                    {idx === 0 ? '🥇' : idx === 1 ? '🥈' : '🥉'}
                  </div>
                  <div className="flex items-center justify-center mb-2">
                    {entry.user.avatar_url ? (
                      <img
                        src={entry.user.avatar_url}
                        alt={entry.user.display_name}
                        className="w-16 h-16 rounded-full"
                      />
                    ) : (
                      <div className="w-16 h-16 rounded-full bg-gray-200 flex items-center justify-center">
                        <span className="text-2xl text-gray-500">👤</span>
                      </div>
                    )}
                  </div>
                  <p className="font-semibold text-gray-900">{entry.user.display_name}</p>
                  <p className="text-2xl font-bold text-orange-600">{formatDistance(entry.value)} mi</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Current Leaderboard */}
        {leaderboardData && (
          <div>
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Current Rankings ({leaderboardData.window_key})
            </h2>
            
            {/* My Rank (Sticky) */}
            {leaderboardData.my_rank && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-blue-600 font-medium">Your Rank</p>
                    <p className="text-2xl font-bold text-blue-900">#{leaderboardData.my_rank.rank}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-blue-600 font-medium">Your Total</p>
                    <p className="text-2xl font-bold text-blue-900">{formatDistance(leaderboardData.my_rank.value)} mi</p>
                  </div>
                </div>
              </div>
            )}

            {/* Leaderboard Table */}
            <div className="bg-white rounded-lg shadow overflow-hidden">
              {leaderboardData.rows && leaderboardData.rows.length > 0 ? (
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Rank
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Runner
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Distance (miles)
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Last Updated
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {leaderboardData.rows.map((entry) => (
                      <tr
                        key={entry.user.id}
                        className={entry.user.id === currentUserId ? 'bg-blue-50' : 'hover:bg-gray-50'}
                      >
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-bold text-gray-900">
                            #{entry.rank}
                            {entry.rank === 1 && ' 🥇'}
                            {entry.rank === 2 && ' 🥈'}
                            {entry.rank === 3 && ' 🥉'}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            {entry.user.avatar_url ? (
                              <img
                                src={entry.user.avatar_url}
                                alt={entry.user.display_name}
                                className="w-10 h-10 rounded-full mr-3"
                              />
                            ) : (
                              <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center mr-3">
                                <span className="text-gray-500">👤</span>
                              </div>
                            )}
                            <div>
                              <div className="text-sm font-medium text-gray-900">
                                {entry.user.display_name}
                              </div>
                              <div className="text-sm text-gray-500">
                                ID: {entry.user.id}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          <div className="text-lg font-bold text-orange-600">
                            {formatDistance(entry.value)}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                          {formatDate(entry.last_updated)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="p-8 text-center text-gray-500">
                  No leaderboard data available for this period yet.
                </div>
              )}
            </div>

            {/* Stats Summary */}
            <div className="mt-4 text-sm text-gray-600 text-center">
              Showing {leaderboardData.total_returned} runners
              {leaderboardData.cursor && ' • More results available'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Leaderboard;
