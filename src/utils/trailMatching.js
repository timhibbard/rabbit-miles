/**
 * Trail matching utilities for calculating which segments of an activity
 * are on the trail vs off the trail
 */

const TRAIL_TOLERANCE_METERS = 50; // 50 meters on each side of trail (matches backend algorithm)

/**
 * Calculate the great circle distance in meters between two points
 * on the earth (specified in decimal degrees).
 */
function haversineDistance(lat1, lon1, lat2, lon2) {
  const toRadians = (degrees) => degrees * (Math.PI / 180);
  
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const earthRadiusMeters = 6371000;
  
  return earthRadiusMeters * c;
}

/**
 * Calculate the distance from a point to a line segment
 */
function pointToSegmentDistance(px, py, x1, y1, x2, y2) {
  const A = px - x1;
  const B = py - y1;
  const C = x2 - x1;
  const D = y2 - y1;
  
  const dot = A * C + B * D;
  const lenSq = C * C + D * D;
  
  let param = -1;
  if (lenSq !== 0) {
    param = dot / lenSq;
  }
  
  let xx, yy;
  
  if (param < 0) {
    xx = x1;
    yy = y1;
  } else if (param > 1) {
    xx = x2;
    yy = y2;
  } else {
    xx = x1 + param * C;
    yy = y1 + param * D;
  }
  
  return haversineDistance(py, px, yy, xx);
}

/**
 * Load trail data from GeoJSON files
 * Returns an array of trail segments, where each segment is an array of [lat, lon] coordinates
 */
export async function loadTrailData() {
  try {
    const [mainResponse, spursResponse] = await Promise.all([
      fetch('/rabbit-miles/main.geojson'),
      fetch('/rabbit-miles/spurs.geojson')
    ]);
    
    if (!mainResponse.ok || !spursResponse.ok) {
      throw new Error('Failed to load trail data');
    }
    
    const mainData = await mainResponse.json();
    const spursData = await spursResponse.json();
    
    // Extract trail segments from GeoJSON
    // Each segment is kept separate to avoid creating spurious connections
    const trailSegments = [];
    
    // Process main trail
    if (mainData.features) {
      mainData.features.forEach(feature => {
        if (feature.geometry && feature.geometry.type === 'LineString') {
          // GeoJSON uses [lon, lat] format, convert to [lat, lon]
          const segment = feature.geometry.coordinates.map(coord => [coord[1], coord[0]]);
          trailSegments.push(segment);
        }
      });
    }
    
    // Process spurs
    if (spursData.features) {
      spursData.features.forEach(feature => {
        if (feature.geometry && feature.geometry.type === 'LineString') {
          // GeoJSON uses [lon, lat] format, convert to [lat, lon]
          const segment = feature.geometry.coordinates.map(coord => [coord[1], coord[0]]);
          trailSegments.push(segment);
        }
      });
    }
    
    return trailSegments;
  } catch (error) {
    console.error('Error loading trail data:', error);
    return [];
  }
}

/**
 * Calculate which segments of an activity are on the trail
 * Returns an array of segments, each with {coordinates, isOnTrail}
 * @param {Array<[number, number]>} activityCoords - Array of [lat, lon] coordinates
 * @param {Array<Array<[number, number]>>} trailSegments - Array of trail segments
 * @param {boolean} includeDebugInfo - Whether to include debug information
 */
export function calculateTrailSegments(activityCoords, trailSegments, includeDebugInfo = false) {
  if (!activityCoords || activityCoords.length < 2) {
    return includeDebugInfo ? { segments: [], debugInfo: null } : [];
  }
  
  if (!trailSegments || trailSegments.length === 0) {
    // No trail data, mark all as off-trail
    const segments = [{
      coordinates: activityCoords,
      isOnTrail: false
    }];
    return includeDebugInfo ? { segments, debugInfo: null } : segments;
  }
  
  // Calculate which points are on the trail
  const pointsOnTrail = [];
  const debugData = includeDebugInfo ? [] : null;
  
  for (let i = 0; i < activityCoords.length; i++) {
    const [lat, lon] = activityCoords[i];
    let isOnTrail = false;
    let minDistance = Infinity;
    let closestTrailSegmentIdx = -1;
    
    // Check if this point is within tolerance of any trail segment
    // Now we iterate over separate trail segments to avoid spurious connections
    for (let segmentIdx = 0; segmentIdx < trailSegments.length; segmentIdx++) {
      const segment = trailSegments[segmentIdx];
      
      // Check each line segment within this trail segment
      for (let j = 0; j < segment.length - 1; j++) {
        const [trailLat1, trailLon1] = segment[j];
        const [trailLat2, trailLon2] = segment[j + 1];
        
        const distance = pointToSegmentDistance(
          lon, lat,
          trailLon1, trailLat1,
          trailLon2, trailLat2
        );
        
        if (distance < minDistance) {
          minDistance = distance;
          closestTrailSegmentIdx = segmentIdx;
        }
        
        if (distance <= TRAIL_TOLERANCE_METERS) {
          isOnTrail = true;
          break;
        }
      }
      
      if (isOnTrail) break;
    }
    
    pointsOnTrail.push(isOnTrail);
    
    if (includeDebugInfo) {
      debugData.push({
        pointIndex: i,
        lat,
        lon,
        isOnTrail,
        minDistance: Math.round(minDistance),
        closestTrailSegmentIdx,
        tolerance: TRAIL_TOLERANCE_METERS
      });
    }
  }
  
  // Group consecutive points with the same on/off trail status into segments
  const segments = [];
  let currentSegment = {
    coordinates: [activityCoords[0]],
    isOnTrail: pointsOnTrail[0]
  };
  
  for (let i = 1; i < activityCoords.length; i++) {
    if (pointsOnTrail[i] === currentSegment.isOnTrail) {
      // Continue current segment
      currentSegment.coordinates.push(activityCoords[i]);
    } else {
      // Start new segment
      // Add the transition point to both segments for continuity
      currentSegment.coordinates.push(activityCoords[i]);
      segments.push(currentSegment);
      
      currentSegment = {
        coordinates: [activityCoords[i]],
        isOnTrail: pointsOnTrail[i]
      };
    }
  }
  
  // Add the last segment
  if (currentSegment.coordinates.length > 0) {
    segments.push(currentSegment);
  }
  
  if (includeDebugInfo) {
    const debugInfo = {
      totalPoints: activityCoords.length,
      pointsOnTrail: pointsOnTrail.filter(x => x).length,
      pointsOffTrail: pointsOnTrail.filter(x => !x).length,
      numTrailSegments: trailSegments.length,
      tolerance: TRAIL_TOLERANCE_METERS,
      points: debugData
    };
    return { segments, debugInfo };
  }
  
  return segments;
}
