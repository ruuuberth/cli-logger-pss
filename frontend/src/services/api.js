import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const CACHE_TTL_MS = 5 * 60 * 1000;

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

const responseCache = new Map();

const getCachedResponse = (key) => {
  const entry = responseCache.get(key);
  if (!entry) {
    return null;
  }

  if (entry.status === 'pending') {
    return entry.promise;
  }

  if (Date.now() - entry.timestamp < CACHE_TTL_MS) {
    return Promise.resolve(entry.response);
  }

  responseCache.delete(key);
  return null;
};

const requestWithCache = (key, url) => {
  const cached = getCachedResponse(key);
  if (cached) {
    return cached;
  }

  const requestPromise = api
    .get(url)
    .then((response) => {
      responseCache.set(key, {
        status: 'resolved',
        timestamp: Date.now(),
        response,
      });
      return response;
    })
    .catch((error) => {
      responseCache.delete(key);
      throw error;
    });

  responseCache.set(key, {
    status: 'pending',
    promise: requestPromise,
  });

  return requestPromise;
};

export const pssApi = {
  clearCache: () => responseCache.clear(),

  // Items
  getItems: () => requestWithCache('items-designs', '/api/v1/items/designs'),
  getItem: (id) => api.get(`/api/v1/items/designs/${id}`),

  // Ships
  getShips: () => requestWithCache('ships-designs', '/api/v1/ships/designs'),
  getShip: (id) => api.get(`/api/v1/ships/designs/${id}`),

  // Crews
  getCrews: () => requestWithCache('crews-designs', '/api/v1/crews/designs'),
  getCrew: (id) => api.get(`/api/v1/crews/designs/${id}`),

  // Battles
  getUserBattles: (username, limit = 10) => {
    const normalizedUsername = (username || '').trim();
    if (!normalizedUsername) {
      return Promise.reject(new Error('username is required'));
    }
    const normalizedLimit = Math.min(50, Math.max(1, Number(limit) || 10));
    const encodedUsername = encodeURIComponent(normalizedUsername);
    return requestWithCache(
      `battles-${encodedUsername}-${normalizedLimit}`,
      `/api/v1/battles/recent?username=${encodedUsername}&limit=${normalizedLimit}`
    );
  },
};

export default api;
