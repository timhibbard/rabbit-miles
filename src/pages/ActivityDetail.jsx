import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { MapContainer, TileLayer, Polyline, Marker, useMap } from 'react-leaflet';
import { fetchActivityDetail, resetActivityTrailMatching } from '../utils/api';
import { decodePolyline } from '../utils/polyline';
import { loadTrailData, calculateTrailSegments } from '../utils/trailMatching';
import Footer from '../components/Footer';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const METERS_TO_MILES = 1609.34;
const POINTS_PER_PAGE = 200;
const POLLING_INTERVAL_MS = 3000; // Poll every 3 seconds

// Custom icon for hover marker
const hoverIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Component to fit map bounds to polyline
function FitBounds({ bounds }) {
  const map = useMap();
  
  useEffect(() => {
    if (bounds && bounds.length > 0) {
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [bounds, map]);
  
  return null;
}

function ActivityDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const debugMode = searchParams.get('debug') === '1';
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activity, setActivity] = useState(null);
  const [coordinates, setCoordinates] = useState([]);
  const [trailSegments, setTrailSegments] = useState([]);
  const [debugInfo, setDebugInfo] = useState(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [resettingMatching, setResettingMatching] = useState(false);
  const [hoveredPointIndex, setHoveredPointIndex] = useState(null);
  const [lastMatchedTimestamp, setLastMatchedTimestamp] = useState(null);
  const [showRefreshNotification, setShowRefreshNotification] = useState(false);

  useEffect(() => {
    const loadActivity = async () => {
      setLoading(true);
      setError(null);

      const result = await fetchActivityDetail(id);

      if (result.success) {
        setActivity(result.data);
        
        // Track last_matched timestamp for polling
        setLastMatchedTimestamp(result.data.last_matched);
        
        // Decode polyline if available
        if (result.data.polyline) {
          const coords = decodePolyline(result.data.polyline);
          setCoordinates(coords);
          
          // Load trail data and calculate segments if trail matching has been performed
          // (distance_on_trail will be null if activity hasn't been trail-matched yet)
          if (result.data.distance_on_trail !== null) {
            const trailData = await loadTrailData();
            if (trailData.length > 0) {
              if (debugMode) {
                const { segments, debugInfo } = calculateTrailSegments(coords, trailData, true);
                setTrailSegments(segments);
                setDebugInfo(debugInfo);
              } else {
                const segments = calculateTrailSegments(coords, trailData);
                setTrailSegments(segments);
              }
            }
          }
        }
      } else if (result.notConnected) {
        navigate('/connect');
      } else {
        setError(result.error || 'Failed to load activity');
      }

      setLoading(false);
    };

    loadActivity();
  }, [id, navigate, debugMode]);

  // Polling effect to check for updated last_matched timestamp
  // This enables auto-refresh when database is updated
  useEffect(() => {
    if (!debugMode || loading || error) {
      return;
    }

    const pollForUpdates = async () => {
      try {
        const result = await fetchActivityDetail(id);
        if (result.success) {
          const newLastMatched = result.data.last_matched;
          
          // If last_matched changed from NULL to a value, or changed to a different value
          // then reload the page to show updated data
          if (newLastMatched && newLastMatched !== lastMatchedTimestamp) {
            console.log('Activity data updated, reloading...', {
              old: lastMatchedTimestamp,
              new: newLastMatched
            });
            setShowRefreshNotification(true);
            
            // Show notification for 2 seconds before reloading
            setTimeout(() => {
              window.location.reload();
            }, 2000);
          }
        }
      } catch (err) {
        console.error('Error polling for updates:', err);
      }
    };

    // Set up polling interval
    const intervalId = setInterval(pollForUpdates, POLLING_INTERVAL_MS);

    // Clean up on unmount
    return () => clearInterval(intervalId);
  }, [id, debugMode, loading, error, lastMatchedTimestamp]);

  const formatTime = (seconds) => {
    if (!seconds || seconds === 0) return '0:00';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const handleResetMatching = async () => {
    if (!window.confirm('Reset trail matching for this activity? This will clear the last_matched timestamp and allow it to be reprocessed.')) {
      return;
    }
    
    setResettingMatching(true);
    try {
      const result = await resetActivityTrailMatching(id);
      if (result.success) {
        alert('Trail matching reset successfully. The activity will be reprocessed.');
        // Reload the activity to show updated state
        window.location.reload();
      } else {
        alert(`Failed to reset trail matching: ${result.error || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setResettingMatching(false);
    }
  };

  if (loading) {
    return (
      <>
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-orange-600 mb-4"></div>
            <p className="text-gray-600">Loading activity...</p>
          </div>
        </div>
        <Footer />
      </>
    );
  }

  if (error) {
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
                Error Loading Activity
              </h2>
              <p className="text-gray-600 mb-4">{error}</p>
              <Link
                to="/"
                className="inline-block px-6 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
              >
                Back to Dashboard
              </Link>
            </div>
          </div>
        </div>
        <Footer />
      </>
    );
  }

  if (!activity) {
    return null;
  }

  const distanceMiles = (activity.distance / METERS_TO_MILES).toFixed(2);
  const distanceOnTrailMiles = activity.distance_on_trail
    ? (activity.distance_on_trail / METERS_TO_MILES).toFixed(2)
    : null;
  
  const hasTrailData = activity.distance_on_trail !== null && activity.distance_on_trail > 0;
  
  // Calculate pace using moving_time (excludes stopped time)
  let pace = 'N/A';
  let paceLabel = 'Pace';
  if (activity.distance > 0 && activity.moving_time > 0) {
    const distanceMi = activity.distance / METERS_TO_MILES;
    const timeHours = activity.moving_time / 3600;
    
    if (activity.type === 'Ride' || activity.type === 'Walk') {
      // Use mph for bike and walk
      const mph = distanceMi / timeHours;
      pace = `${mph.toFixed(1)} mph`;
      paceLabel = 'Speed';
    } else {
      // Use min/mi for running
      const paceValue = (activity.moving_time / 60) / distanceMi;
      const paceMin = Math.floor(paceValue);
      const paceSec = Math.floor((paceValue - paceMin) * 60);
      pace = `${paceMin}:${paceSec.toString().padStart(2, '0')}/mi`;
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Refresh notification */}
      {showRefreshNotification && (
        <div className="fixed top-4 right-4 z-50 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-3 animate-pulse">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span className="font-medium">Activity updated! Refreshing...</span>
        </div>
      )}
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Back button */}
        <div className="mb-6">
          <Link
            to="/"
            className="inline-flex items-center text-gray-600 hover:text-gray-900"
          >
            <svg
              className="w-5 h-5 mr-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M15 19l-7-7 7-7"
              ></path>
            </svg>
            Back to Dashboard
          </Link>
        </div>

        {/* Activity header */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                {activity.name}
              </h1>
              <p className="text-gray-600">{formatDate(activity.start_date_local)}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-orange-100 text-orange-800">
                {activity.type}
              </span>
              <a
                href={`https://www.strava.com/activities/${activity.strava_activity_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
              >
                <svg
                  className="w-5 h-5 mr-2"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169"></path>
                </svg>
                View on Strava
              </a>
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-6">
            <div>
              <p className="text-sm text-gray-500 mb-1">Distance</p>
              <p className="text-2xl font-bold text-gray-900">{distanceMiles} mi</p>
              {distanceOnTrailMiles && (
                <p className="text-sm text-green-600 mt-1">
                  {distanceOnTrailMiles} mi on trail
                </p>
              )}
            </div>
            <div>
              <p className="text-sm text-gray-500 mb-1">Moving Time</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatTime(activity.moving_time)}
              </p>
              {activity.time_on_trail !== null && (
                <p className="text-sm text-green-600 mt-1">
                  {formatTime(activity.time_on_trail)} on trail
                </p>
              )}
            </div>
            <div>
              <p className="text-sm text-gray-500 mb-1">{paceLabel}</p>
              <p className="text-2xl font-bold text-gray-900">{pace}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500 mb-1">Elevation Gain</p>
              <p className="text-2xl font-bold text-gray-900">
                {activity.total_elevation_gain.toFixed(0)} ft
              </p>
            </div>
          </div>
        </div>

        {/* Map */}
        {coordinates.length > 0 ? (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Route Map</h2>
            <div className="h-[500px] rounded-lg overflow-hidden">
              <MapContainer
                center={coordinates[0]}
                zoom={13}
                style={{ height: '100%', width: '100%' }}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {trailSegments.length > 0 ? (
                  // Render segments in different colors based on trail matching
                  trailSegments.map((segment, idx) => (
                    <Polyline
                      key={idx}
                      positions={segment.coordinates}
                      color={segment.isOnTrail ? '#10b981' : '#3b82f6'}
                      weight={4}
                      opacity={0.8}
                    />
                  ))
                ) : (
                  // Show single blue polyline when no trail data
                  <Polyline
                    positions={coordinates}
                    color="#3b82f6"
                    weight={4}
                    opacity={0.8}
                  />
                )}
                {/* Hover marker for point-by-point analysis */}
                {debugMode && hoveredPointIndex !== null && coordinates[hoveredPointIndex] && (
                  <Marker 
                    position={coordinates[hoveredPointIndex]} 
                    icon={hoverIcon}
                  />
                )}
                <FitBounds bounds={coordinates} />
              </MapContainer>
            </div>
            <div className="mt-4 flex items-center gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-8 h-1 bg-green-500 rounded"></div>
                <span className="text-gray-600">On trail</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-8 h-1 bg-blue-500 rounded"></div>
                <span className="text-gray-600">Off trail</span>
              </div>
              {trailSegments.length === 0 && hasTrailData && (
                <p className="text-gray-500 italic">
                  (Loading trail segments...)
                </p>
              )}
              {!hasTrailData && (
                <p className="text-gray-500 italic">
                  (Trail matching data not available for this activity)
                </p>
              )}
            </div>
            {debugMode && debugInfo && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg text-sm">
                <h3 className="font-semibold text-gray-900 mb-2">Debug Information</h3>
                <div className="space-y-1 text-gray-700">
                  <p><strong>Activity ID:</strong> {activity.id}</p>
                  <p><strong>Total Points:</strong> {debugInfo.totalPoints}</p>
                  <p><strong>Points On Trail:</strong> {debugInfo.pointsOnTrail} ({((debugInfo.pointsOnTrail / debugInfo.totalPoints) * 100).toFixed(1)}%) - {(() => {
                    // Calculate distance for points on trail
                    let distance = 0;
                    for (let i = 0; i < coordinates.length - 1; i++) {
                      if (debugInfo.points[i] && debugInfo.points[i].isOnTrail) {
                        const [lat1, lon1] = coordinates[i];
                        const [lat2, lon2] = coordinates[i + 1];
                        // Haversine distance calculation
                        const toRadians = (deg) => deg * (Math.PI / 180);
                        const dLat = toRadians(lat2 - lat1);
                        const dLon = toRadians(lon2 - lon1);
                        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                          Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) *
                          Math.sin(dLon / 2) * Math.sin(dLon / 2);
                        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
                        distance += 6371000 * c; // Earth radius in meters
                      }
                    }
                    return (distance / METERS_TO_MILES).toFixed(2);
                  })()} mi</p>
                  <p><strong>Points Off Trail:</strong> {debugInfo.pointsOffTrail} ({((debugInfo.pointsOffTrail / debugInfo.totalPoints) * 100).toFixed(1)}%)</p>
                  <p><strong>Trail Segments Loaded:</strong> {debugInfo.numTrailSegments}</p>
                  <p><strong>Tolerance:</strong> {debugInfo.tolerance} meters</p>
                  <p><strong>Last Matched:</strong> {activity.last_matched ? new Date(activity.last_matched).toLocaleString() : 'Never'}</p>
                </div>
                <div className="mt-3">
                  <button
                    onClick={handleResetMatching}
                    disabled={resettingMatching}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-red-500"
                  >
                    {resettingMatching ? 'Resetting...' : 'Reset last_matched to NULL'}
                  </button>
                  <p className="text-xs text-gray-600 mt-1">
                    This will clear the last_matched timestamp so the activity can be reprocessed
                  </p>
                </div>
                <details className="mt-3">
                  <summary className="cursor-pointer text-orange-600 hover:text-orange-700 font-medium">
                    View point-by-point analysis ({POINTS_PER_PAGE} points per page)
                  </summary>
                  <div className="mt-2 max-h-96 overflow-y-auto">
                    <table className="min-w-full text-xs">
                      <thead className="bg-gray-100 sticky top-0">
                        <tr>
                          <th className="px-2 py-1 text-left">#</th>
                          <th className="px-2 py-1 text-left">Lat</th>
                          <th className="px-2 py-1 text-left">Lon</th>
                          <th className="px-2 py-1 text-left">On Trail</th>
                          <th className="px-2 py-1 text-left">Distance (m)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {debugInfo.points.slice(currentPage * POINTS_PER_PAGE, (currentPage + 1) * POINTS_PER_PAGE).map((point) => (
                          <tr 
                            key={point.pointIndex} 
                            className={`${point.isOnTrail ? 'bg-green-50' : 'bg-blue-50'} hover:bg-orange-100 cursor-pointer transition-colors`}
                            onMouseEnter={() => setHoveredPointIndex(point.pointIndex)}
                            onMouseLeave={() => setHoveredPointIndex(null)}
                          >
                            <td className="px-2 py-1">{point.pointIndex}</td>
                            <td className="px-2 py-1">{point.lat.toFixed(6)}</td>
                            <td className="px-2 py-1">{point.lon.toFixed(6)}</td>
                            <td className="px-2 py-1">{point.isOnTrail ? '✓' : '✗'}</td>
                            <td className="px-2 py-1">{point.minDistance}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {debugInfo.points.length > POINTS_PER_PAGE && (
                      <div className="mt-3 flex items-center justify-between border-t border-gray-200 pt-3">
                        <button
                          onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                          disabled={currentPage === 0}
                          className="px-3 py-1 text-sm bg-orange-600 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-orange-700"
                        >
                          Previous
                        </button>
                        <span className="text-sm text-gray-600">
                          Page {currentPage + 1} of {Math.ceil(debugInfo.points.length / POINTS_PER_PAGE)} 
                          {' '}(showing {currentPage * POINTS_PER_PAGE + 1} - {Math.min((currentPage + 1) * POINTS_PER_PAGE, debugInfo.points.length)} of {debugInfo.points.length} points)
                        </span>
                        <button
                          onClick={() => setCurrentPage(Math.min(Math.ceil(debugInfo.points.length / POINTS_PER_PAGE) - 1, currentPage + 1))}
                          disabled={currentPage >= Math.ceil(debugInfo.points.length / POINTS_PER_PAGE) - 1}
                          className="px-3 py-1 text-sm bg-orange-600 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-orange-700"
                        >
                          Next
                        </button>
                      </div>
                    )}
                  </div>
                </details>
              </div>
            )}
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Route Map</h2>
            <div className="bg-gray-50 rounded-lg p-8 text-center">
              <svg
                className="w-12 h-12 text-gray-400 mx-auto mb-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                ></path>
              </svg>
              <p className="text-gray-600">No route data available for this activity</p>
            </div>
          </div>
        )}
      </div>

      <Footer />
    </div>
  );
}

export default ActivityDetail;
