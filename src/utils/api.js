import axios from 'axios';
import debug from './debug';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// Validate API_BASE_URL at module load time
if (!API_BASE_URL) {
  console.error('VITE_API_BASE_URL environment variable is not set!');
} else {
  debug.log('API_BASE_URL configured as:', API_BASE_URL);
}

// Create axios instance with base configuration
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Include cookies in all requests
});

// Add request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    // Log full request details in debug mode
    if (debug.enabled()) {
      debug.group('API Request');
      debug.log('Method:', config.method?.toUpperCase());
      debug.log('URL:', config.url);
      debug.log('Base URL:', config.baseURL);
      debug.log('Full URL:', `${config.baseURL}${config.url}`);
      // Filter sensitive headers before logging
      const safeHeaders = { ...config.headers };
      if (safeHeaders.Cookie) safeHeaders.Cookie = '[REDACTED]';
      debug.log('Headers:', safeHeaders);
      debug.log('With Credentials:', config.withCredentials);
      if (config.params) debug.log('Params:', config.params);
      if (config.data) debug.log('Data:', config.data);
      debug.groupEnd();
    }
    
    return config;
  },
  (error) => {
    console.error('Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for debugging
api.interceptors.response.use(
  (response) => {
    if (debug.enabled()) {
      debug.group('API Response');
      debug.log('Status:', response.status);
      debug.log('Status Text:', response.statusText);
      debug.log('Headers:', response.headers);
      debug.log('Data:', response.data);
      debug.groupEnd();
    }
    return response;
  },
  (error) => {
    if (debug.enabled()) {
      debug.group('API Response Error');
      if (error.response) {
        debug.log('Status:', error.response.status);
        debug.log('Status Text:', error.response.statusText);
        debug.log('Headers:', error.response.headers);
        debug.log('Data:', error.response.data);
      } else if (error.request) {
        debug.log('Request made but no response received');
        debug.log('Request:', error.request);
      } else {
        debug.log('Error setting up request:', error.message);
      }
      debug.log('Error config:', error.config);
      debug.groupEnd();
    }
    return Promise.reject(error);
  }
);

// Fetch current user from /me endpoint
export const fetchMe = async () => {
  try {
    debug.log('Calling /me endpoint...');
    const response = await api.get('/me');
    debug.log('/me response received successfully');
    debug.log('/me user data:', response.data);
    return { success: true, user: response.data };
  } catch (error) {
    console.error('/me endpoint error:', error.message);
    if (error.response) {
      console.error('/me response status:', error.response.status);
      debug.error('/me response data:', error.response.data);
      debug.error('/me response headers:', error.response.headers);
    }
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    return { success: false, error: error.message };
  }
};

// Fetch activities for the authenticated user
export const fetchActivities = async (limit = 10, offset = 0) => {
  try {
    debug.log(`Calling /activities endpoint (limit=${limit}, offset=${offset})...`);
    const response = await api.get('/activities', {
      params: { limit, offset },
    });
    debug.log('/activities response received:', response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('/activities endpoint error:', error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    return { success: false, error: error.message };
  }
};

// Refresh activities from Strava
export const refreshActivities = async () => {
  try {
    debug.log('Calling /activities/fetch endpoint...');
    const response = await api.post('/activities/fetch');
    debug.log('/activities/fetch response:', response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('/activities/fetch endpoint error:', error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    return { success: false, error: error.message };
  }
};

// Reset trail matching for all activities
export const resetTrailMatching = async () => {
  try {
    debug.log('Calling /activities/reset-matching endpoint...');
    const response = await api.post('/activities/reset-matching');
    debug.log('/activities/reset-matching response:', response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('/activities/reset-matching endpoint error:', error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    return { success: false, error: error.message };
  }
};

// Reset trail matching for a single activity
export const resetActivityTrailMatching = async (activityId) => {
  try {
    debug.log(`Calling /activities/${activityId}/reset-matching endpoint...`);
    const response = await api.post(`/activities/${activityId}/reset-matching`);
    debug.log(`/activities/${activityId}/reset-matching response:`, response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error(`/activities/${activityId}/reset-matching endpoint error:`, error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    if (error.response?.status === 404) {
      return { success: false, error: 'Activity not found or access denied' };
    }
    return { success: false, error: error.message };
  }
};

// Fetch a single activity detail with polyline
export const fetchActivityDetail = async (activityId) => {
  try {
    debug.log(`Calling /activities/${activityId} endpoint...`);
    const response = await api.get(`/activities/${activityId}`);
    debug.log(`/activities/${activityId} response received`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error(`/activities/${activityId} endpoint error:`, error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    if (error.response?.status === 404) {
      return { success: false, error: 'Activity not found' };
    }
    return { success: false, error: error.message };
  }
};

// Admin endpoints - only accessible to users with admin privileges

// Fetch all users (admin only)
export const fetchAllUsers = async () => {
  try {
    debug.log('Calling /admin/users endpoint...');
    const response = await api.get('/admin/users');
    debug.log('/admin/users response received:', response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('/admin/users endpoint error:', error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    if (error.response?.status === 403) {
      debug.log('User not authorized for admin access (403)');
      return { success: false, error: 'Access denied - admin privileges required' };
    }
    return { success: false, error: error.message };
  }
};

// Fetch activities for all users (admin only)
export const fetchAllActivities = async (limit = 50, offset = 0) => {
  try {
    debug.log(`Calling /admin/activities endpoint (limit=${limit}, offset=${offset})...`);
    const response = await api.get('/admin/activities', {
      params: { limit, offset },
    });
    debug.log('/admin/activities response received:', response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('/admin/activities endpoint error:', error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    if (error.response?.status === 403) {
      debug.log('User not authorized for admin access (403)');
      return { success: false, error: 'Access denied - admin privileges required' };
    }
    return { success: false, error: error.message };
  }
};

// Fetch activities for a specific user (admin only)
export const fetchUserActivities = async (athleteId, limit = 50, offset = 0) => {
  try {
    debug.log(`Calling /admin/users/${athleteId}/activities endpoint (limit=${limit}, offset=${offset})...`);
    const response = await api.get(`/admin/users/${athleteId}/activities`, {
      params: { limit, offset },
    });
    debug.log(`/admin/users/${athleteId}/activities response received:`, response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error(`/admin/users/${athleteId}/activities endpoint error:`, error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    if (error.response?.status === 403) {
      debug.log('User not authorized for admin access (403)');
      return { success: false, error: 'Access denied - admin privileges required' };
    }
    return { success: false, error: error.message };
  }
};

// Delete a user and all their data (admin only)
export const deleteUser = async (athleteId) => {
  try {
    debug.log(`Calling DELETE /admin/users/${athleteId} endpoint...`);
    const response = await api.delete(`/admin/users/${athleteId}`);
    debug.log(`DELETE /admin/users/${athleteId} response received:`, response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error(`DELETE /admin/users/${athleteId} endpoint error:`, error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    if (error.response?.status === 403) {
      debug.log('User not authorized for admin access (403)');
      return { success: false, error: 'Access denied - admin privileges required' };
    }
    if (error.response?.status === 404) {
      return { success: false, error: 'User not found' };
    }
    return { success: false, error: error.message };
  }
};

// Backfill activities for a user (admin only)
export const backfillUserActivities = async (athleteId) => {
  try {
    debug.log(`Calling POST /admin/users/${athleteId}/backfill-activities endpoint...`);
    const response = await api.post(`/admin/users/${athleteId}/backfill-activities`);
    debug.log(`POST /admin/users/${athleteId}/backfill-activities response received:`, response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error(`POST /admin/users/${athleteId}/backfill-activities endpoint error:`, error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    if (error.response?.status === 403) {
      debug.log('User not authorized for admin access (403)');
      return { success: false, error: 'Access denied - admin privileges required' };
    }
    if (error.response?.status === 404) {
      return { success: false, error: 'User not found' };
    }
    return { success: false, error: error.response?.data?.message || error.message };
  }
};

// Update activities for current user (user endpoint)
export const updateActivities = async () => {
  try {
    debug.log('Calling POST /activities/update endpoint...');
    const response = await api.post('/activities/update');
    debug.log('POST /activities/update response received:', response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('POST /activities/update endpoint error:', error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    return { success: false, error: error.response?.data?.error || error.message };
  }
};

// Update activities for a specific user (admin only)
export const updateUserActivities = async (athleteId) => {
  try {
    debug.log(`Calling POST /admin/users/${athleteId}/update-activities endpoint...`);
    const response = await api.post(`/admin/users/${athleteId}/update-activities`);
    debug.log(`POST /admin/users/${athleteId}/update-activities response received:`, response.data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error(`POST /admin/users/${athleteId}/update-activities endpoint error:`, error.message);
    if (error.response?.status === 401) {
      debug.log('User not authenticated (401)');
      return { success: false, notConnected: true };
    }
    if (error.response?.status === 403) {
      debug.log('User not authorized for admin access (403)');
      return { success: false, error: 'Access denied - admin privileges required' };
    }
    if (error.response?.status === 404) {
      return { success: false, error: 'User not found' };
    }
    return { success: false, error: error.response?.data?.error || error.message };
  }
};

export default api;
