import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// Create axios instance with base configuration
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Include cookies in all requests
});

// Fetch current user from /me endpoint
export const fetchMe = async () => {
  try {
    console.log('Calling /me endpoint...');
    const response = await api.get('/me');
    console.log('/me response:', response.data);
    return { success: true, user: response.data };
  } catch (error) {
    console.error('/me endpoint error:', error);
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
    console.error('Error calling /activities/fetch:', error.message, error.response?.data);
    return { success: false, error: error.message };
  }
};

export default api;
