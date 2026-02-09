import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

export const pssApi = {
  // Items
  getItems: () => api.get('/api/v1/items/designs'),
  getItem: (id) => api.get(`/api/v1/items/designs/${id}`),
  
  // Ships
  getShips: () => api.get('/api/v1/ships/designs'),
  getShip: (id) => api.get(`/api/v1/ships/designs/${id}`),
  
  // Crews
  getCrews: () => api.get('/api/v1/crews/designs'),
  getCrew: (id) => api.get(`/api/v1/crews/designs/${id}`),
};

export default api;