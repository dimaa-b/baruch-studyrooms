// Use relative path for API in production, allow override via environment variable
const API_BASE_URL = import.meta.env.VITE_API_URL || (
  import.meta.env.PROD ? '' : 'http://localhost:5001'
);

export { API_BASE_URL };
