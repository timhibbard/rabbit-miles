import axios from 'axios';

const BACKEND_BASE_URL = import.meta.env.VITE_BACKEND_BASE_URL;

// Create axios instance with base configuration
const api = axios.create({
  baseURL: BACKEND_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token if available
// Note: The authToken should be set by the backend OAuth callback handler
// which will store it in localStorage after successful Strava authentication
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      localStorage.removeItem('authToken');
      localStorage.removeItem('stravaConnected');
      // Redirect to connect page with proper base path
      window.location.href = '/rabbit-miles/connect';
    }
    return Promise.reject(error);
  }
);

export default api;
