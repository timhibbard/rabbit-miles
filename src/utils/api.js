import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// Validate API_BASE_URL at module load time
if (!API_BASE_URL) {
  console.error('VITE_API_BASE_URL environment variable is not set!');
} else {
  console.log('API_BASE_URL configured as:', API_BASE_URL);
}

// Create axios instance with base configuration
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Include cookies in all requests
});

// Add request interceptor to include session token from sessionStorage
// This provides Mobile Safari compatibility where cookies may be blocked.
// Note: This adds Authorization header even when cookies work, creating
// intentional redundancy. Both methods are supported by the backend, and
// the redundancy is acceptable for simplicity and Mobile Safari compatibility.
api.interceptors.request.use(
  (config) => {
    // Check if we have a session token in sessionStorage (Mobile Safari fallback)
    const sessionToken = sessionStorage.getItem('rm_session');
    if (sessionToken) {
      console.log('Adding Authorization header with session token:', sessionToken.substring(0, 20) + '...');
      config.headers.Authorization = `Bearer ${sessionToken}`;
    } else {
      console.log('No session token found in sessionStorage for this request');
    }
    return config;
  },
  (error) => {
    console.error('Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Fetch current user from /me endpoint
export const fetchMe = async () => {
  try {
    console.log('Calling /me endpoint...');
    console.log('API_BASE_URL:', API_BASE_URL);
    console.log('Session token in storage:', sessionStorage.getItem('rm_session') ? 'present' : 'missing');
    const response = await api.get('/me');
    console.log('/me response:', response.data);
    console.log('/me response status:', response.status);
    return { success: true, user: response.data };
  } catch (error) {
    console.error('/me endpoint error:', error);
    if (error.response) {
      console.error('/me response status:', error.response.status);
      console.error('/me response data:', error.response.data);
      console.error('/me response headers:', error.response.headers);
    }
    if (error.response?.status === 401) {
      console.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    console.error('Error calling /me:', error.message, error.response?.data);
    return { success: false, error: error.message };
  }
};

// Fetch activities for the authenticated user
export const fetchActivities = async (limit = 10, offset = 0) => {
  try {
    console.log(`Calling /activities endpoint (limit=${limit}, offset=${offset})...`);
    const response = await api.get('/activities', {
      params: { limit, offset },
    });
    console.log('/activities response:', response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('/activities endpoint error:', error);
    if (error.response?.status === 401) {
      console.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    console.error('Error calling /activities:', error.message, error.response?.data);
    return { success: false, error: error.message };
  }
};

// Refresh activities from Strava
export const refreshActivities = async () => {
  try {
    console.log('Calling /activities/fetch endpoint...');
    const response = await api.post('/activities/fetch');
    console.log('/activities/fetch response:', response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('/activities/fetch endpoint error:', error);
    if (error.response?.status === 401) {
      console.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    return { success: false, error: error.message };
  }
};

// Reset trail matching for all activities
export const resetTrailMatching = async () => {
  try {
    console.log('Calling /activities/reset-matching endpoint...');
    const response = await api.post('/activities/reset-matching');
    console.log('/activities/reset-matching response:', response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('/activities/reset-matching endpoint error:', error);
    if (error.response?.status === 401) {
      console.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    return { success: false, error: error.message };
  }
};

// Fetch a single activity detail with polyline
export const fetchActivityDetail = async (activityId) => {
  try {
    console.log(`Calling /activities/${activityId} endpoint...`);
    const response = await api.get(`/activities/${activityId}`);
    console.log(`/activities/${activityId} response:`, response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error(`/activities/${activityId} endpoint error:`, error);
    if (error.response?.status === 401) {
      console.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    if (error.response?.status === 404) {
      return { success: false, error: 'Activity not found' };
    }
    return { success: false, error: error.message };
  }
};

export default api;
