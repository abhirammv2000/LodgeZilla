// Base URL of the LodgeZilla API. Set REACT_APP_API_BASE_URL at build time to
// point the UI at a deployed backend; the default suits local development.
export const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000/api';
