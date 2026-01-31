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

export default api;
