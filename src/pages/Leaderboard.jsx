import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMe, fetchLeaderboard } from '../utils/api';

// Number of top athletes to display in current rankings
const TOP_ATHLETES_COUNT = 5;

function Leaderboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [selectedWindow, setSelectedWindow] = useState('week');
  const [selectedBike, setSelectedBike] = useState(false);
  const [selectedFoot, setSelectedFoot] = useState(true); // Default to Foot only
  const [leaderboardData, setLeaderboardData] = useState(null);
  const [error, setError] = useState(null);

  // Check authentication (optional - leaderboard is public but we show user's rank if logged in)
  useEffect(() => {
    const checkAuth = async () => {
      const meResult = await fetchMe();
      
      if (meResult.success && meResult.user) {
        setCurrentUserId(meResult.user.athlete_id);
      }
      
      setLoading(false);
    };
    
    checkAuth();
  }, [navigate]);

  // Fetch leaderboard data when window or activity type changes
  useEffect(() => {
    // Compute activity_type based on selected filters
    const getActivityType = () => {
      if (selectedBike && selectedFoot) return 'all';
      if (selectedBike) return 'bike';
      if (selectedFoot) return 'foot';
      return 'all'; // If neither selected, show all
    };
    
    const loadLeaderboard = async () => {
      setError(null);
      try {
        const result = await fetchLeaderboard(selectedWindow, {
          user_id: currentUserId,
          activity_type: getActivityType(),
        });
        
        if (result.success) {
          setLeaderboardData(result.data);
          console.log('TELEMETRY - leaderboard_page_view', {
            window: selectedWindow,
            window_key: result.data.window_key,
            activity_type: getActivityType(),
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
  }, [selectedWindow, selectedBike, selectedFoot, currentUserId]);

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
      setSelectedBike(!selectedBike);
    } else if (type === 'foot') {
      setSelectedFoot(!selectedFoot);
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

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-2 sm:px-4 lg:px-8 py-4 sm:py-8">
        {/* Header */}
        <div className="mb-4 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-2">
            🏆 Leaderboard
          </h1>
          <p className="text-sm sm:text-base text-gray-600">
            View athlete rankings by time period.
          </p>
        </div>


        {/* Error Message */}
        {error && (
          <div className="mb-4 sm:mb-6 bg-red-50 border border-red-200 rounded-lg p-3 sm:p-4">
            <p className="text-red-800 text-sm sm:text-base">{error}</p>
          </div>
        )}

        {/* Previous Period Top 3 */}
        {leaderboardData && leaderboardData.previous_top3 && leaderboardData.previous_top3.length > 0 && (
          <div className="mb-6 sm:mb-8">
            <h2 className="text-lg sm:text-xl font-semibold text-gray-900 mb-3 sm:mb-4">
              🥇 Last {selectedWindow === 'week' ? 'Week' : selectedWindow === 'month' ? 'Month' : 'Year'}'s Top 3
            </h2>
            {/* Compact Top 3: Single line display */}
            <div className="bg-white rounded-lg shadow-md p-3 sm:p-4">
              <div className="flex flex-wrap items-center justify-around gap-2 sm:gap-4">
                {leaderboardData.previous_top3.map((entry, idx) => (
                  <div key={entry.user.id} className="flex items-center gap-2 sm:gap-3">
                    <div className="text-2xl sm:text-3xl">
                      {idx === 0 ? '🥇' : idx === 1 ? '🥈' : '🥉'}
                    </div>
                    {entry.user.avatar_url ? (
                      <img
                        src={entry.user.avatar_url}
                        alt={entry.user.display_name}
                        className="w-8 h-8 sm:w-10 sm:h-10 rounded-full"
                      />
                    ) : (
                      <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-gray-200 flex items-center justify-center">
                        <span className="text-sm sm:text-base text-gray-500">👤</span>
                      </div>
                    )}
                    <div className="text-left">
                      <p className="font-semibold text-gray-900 text-xs sm:text-sm">{entry.user.display_name}</p>
                      <p className="text-sm sm:text-base font-bold text-orange-600">{formatDistance(entry.value)} mi</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Current Leaderboard */}
        {leaderboardData && (
          <div>
            <h2 className="text-lg sm:text-xl font-semibold text-gray-900 mb-3 sm:mb-4">
              Current Rankings ({leaderboardData.window_key})
            </h2>
            
            {/* My Rank (Sticky) */}
            {leaderboardData.my_rank && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 sm:p-4 mb-3 sm:mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs sm:text-sm text-blue-600 font-medium">Your Rank</p>
                    <p className="text-xl sm:text-2xl font-bold text-blue-900">#{leaderboardData.my_rank.rank}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs sm:text-sm text-blue-600 font-medium">Your Total</p>
                    <p className="text-xl sm:text-2xl font-bold text-blue-900">{formatDistance(leaderboardData.my_rank.value)} mi</p>
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
                      <th className="px-2 sm:px-6 py-2 sm:py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Rank
                      </th>
                      <th className="px-2 sm:px-6 py-2 sm:py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Athlete
                      </th>
                      <th className="px-2 sm:px-6 py-2 sm:py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Distance (miles)
                      </th>
                      <th className="px-2 sm:px-6 py-2 sm:py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Last Updated
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {leaderboardData.rows.slice(0, TOP_ATHLETES_COUNT).map((entry) => (
                      <tr
                        key={entry.user.id}
                        className={entry.user.id === currentUserId ? 'bg-blue-50' : 'hover:bg-gray-50'}
                      >
                        <td className="px-2 sm:px-6 py-2 sm:py-4 whitespace-nowrap">
                          <div className="text-sm font-bold text-gray-900">
                            #{entry.rank}
                            {entry.rank === 1 && ' 🥇'}
                            {entry.rank === 2 && ' 🥈'}
                            {entry.rank === 3 && ' 🥉'}
                          </div>
                        </td>
                        <td className="px-2 sm:px-6 py-2 sm:py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            {entry.user.avatar_url ? (
                              <img
                                src={entry.user.avatar_url}
                                alt={entry.user.display_name}
                                className="w-8 h-8 sm:w-10 sm:h-10 rounded-full mr-2 sm:mr-3"
                              />
                            ) : (
                              <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-gray-200 flex items-center justify-center mr-2 sm:mr-3">
                                <span className="text-gray-500">👤</span>
                              </div>
                            )}
                            <div>
                              <div className="text-sm font-medium text-gray-900">
                                {entry.user.display_name}
                              </div>
                              <div className="text-xs sm:text-sm text-gray-500">
                                ID: {entry.user.id}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="px-2 sm:px-6 py-2 sm:py-4 whitespace-nowrap text-right">
                          <div className="text-base sm:text-lg font-bold text-orange-600">
                            {formatDistance(entry.value)}
                          </div>
                        </td>
                        <td className="px-2 sm:px-6 py-2 sm:py-4 whitespace-nowrap text-right text-xs sm:text-sm text-gray-500">
                          {formatDate(entry.last_updated)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="p-6 sm:p-8 text-center text-gray-500 text-sm sm:text-base">
                  No leaderboard data available for this period yet.
                </div>
              )}
            </div>

            {/* Stats Summary */}
            <div className="mt-3 sm:mt-4 text-xs sm:text-sm text-gray-600 text-center">
              Showing top {Math.min(TOP_ATHLETES_COUNT, leaderboardData.rows?.length || 0)} athletes
              {leaderboardData.cursor && ' • More results available'}
            </div>
          </div>
        )}

        {/* Inline Filters */}
        {leaderboardData && (
          <div className="mt-4 sm:mt-6">
            <div className="bg-white rounded-lg shadow p-3 sm:p-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
                {/* Time Period */}
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-600 mb-1.5">
                    Time Period
                  </label>
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => setSelectedWindow('week')}
                      className={`flex-1 px-2.5 py-1.5 rounded text-xs font-medium ${
                        selectedWindow === 'week'
                          ? 'bg-orange-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      Week
                    </button>
                    <button
                      onClick={() => setSelectedWindow('month')}
                      className={`flex-1 px-2.5 py-1.5 rounded text-xs font-medium ${
                        selectedWindow === 'month'
                          ? 'bg-orange-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      Month
                    </button>
                    <button
                      onClick={() => setSelectedWindow('year')}
                      className={`flex-1 px-2.5 py-1.5 rounded text-xs font-medium ${
                        selectedWindow === 'year'
                          ? 'bg-orange-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      Year
                    </button>
                  </div>
                </div>
                
                {/* Divider */}
                <div className="hidden sm:block h-12 w-px bg-gray-200"></div>
                
                {/* Activity Type */}
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-600 mb-1.5">
                    Activity Type
                  </label>
                  <div className="inline-flex rounded border border-gray-300 bg-white">
                    <button
                      onClick={() => toggleActivityType('bike')}
                      className={`px-2.5 sm:px-3 py-1.5 text-xs font-medium rounded-l transition-colors ${
                        selectedBike
                          ? 'bg-orange-600 text-white'
                          : 'bg-white text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      Bike
                    </button>
                    <button
                      onClick={() => toggleActivityType('foot')}
                      className={`px-2.5 sm:px-3 py-1.5 text-xs font-medium rounded-r border-l transition-colors ${
                        selectedFoot
                          ? 'bg-orange-600 text-white border-orange-600'
                          : 'bg-white text-gray-700 hover:bg-gray-50 border-gray-300'
                      }`}
                    >
                      Foot
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Leaderboard;
