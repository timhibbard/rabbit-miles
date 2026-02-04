import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { MapContainer, TileLayer, Polyline, useMap } from 'react-leaflet';
import { fetchActivityDetail } from '../utils/api';
import { decodePolyline } from '../utils/polyline';
import { loadTrailData, calculateTrailSegments } from '../utils/trailMatching';
import Footer from '../components/Footer';
import 'leaflet/dist/leaflet.css';

const METERS_TO_MILES = 1609.34;

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

  useEffect(() => {
    const loadActivity = async () => {
      setLoading(true);
      setError(null);

      const result = await fetchActivityDetail(id);

      if (result.success) {
        setActivity(result.data);
        
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
  }, [id, navigate]);

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
                  <p><strong>Total Points:</strong> {debugInfo.totalPoints}</p>
                  <p><strong>Points On Trail:</strong> {debugInfo.pointsOnTrail} ({((debugInfo.pointsOnTrail / debugInfo.totalPoints) * 100).toFixed(1)}%)</p>
                  <p><strong>Points Off Trail:</strong> {debugInfo.pointsOffTrail} ({((debugInfo.pointsOffTrail / debugInfo.totalPoints) * 100).toFixed(1)}%)</p>
                  <p><strong>Trail Segments Loaded:</strong> {debugInfo.numTrailSegments}</p>
                  <p><strong>Tolerance:</strong> {debugInfo.tolerance} meters</p>
                </div>
                <details className="mt-3">
                  <summary className="cursor-pointer text-orange-600 hover:text-orange-700 font-medium">
                    View point-by-point analysis (first 50 points)
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
                        {debugInfo.points.slice(0, 50).map((point, idx) => (
                          <tr key={idx} className={point.isOnTrail ? 'bg-green-50' : 'bg-blue-50'}>
                            <td className="px-2 py-1">{point.pointIndex}</td>
                            <td className="px-2 py-1">{point.lat.toFixed(6)}</td>
                            <td className="px-2 py-1">{point.lon.toFixed(6)}</td>
                            <td className="px-2 py-1">{point.isOnTrail ? '✓' : '✗'}</td>
                            <td className="px-2 py-1">{point.minDistance}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
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
