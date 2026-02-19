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

  // Auth
  loginWithEmail: (email, password, deviceKey = null) =>
    api.post('/api/v1/auth/login-email', {
      email,
      password,
      device_key: deviceKey,
    }),
  loginWithRefreshToken: (refreshToken, deviceKey = null) =>
    api.post('/api/v1/auth/login-refresh', {
      refresh_token: refreshToken,
      device_key: deviceKey,
    }),

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
  getBattleReport: (
    battleId,
    accessToken = null,
    forceRefresh = false,
    ttlSeconds = null
  ) => {
    const normalizedBattleId = Number(battleId);
    if (!Number.isInteger(normalizedBattleId) || normalizedBattleId <= 0) {
      return Promise.reject(new Error('battleId must be a positive integer'));
    }

    const tokenQuery = accessToken && accessToken.trim().length > 0
      ? `&access_token=${encodeURIComponent(accessToken.trim())}`
      : '';
    const forceRefreshQuery = forceRefresh ? '&force_refresh=true' : '';
    const ttlQuery = Number.isInteger(Number(ttlSeconds)) && Number(ttlSeconds) >= 0
      ? `&ttl_seconds=${Number(ttlSeconds)}`
      : '';

    const query = `/api/v1/battles/report?battle_id=${normalizedBattleId}${tokenQuery}${forceRefreshQuery}${ttlQuery}`;
    if (forceRefresh) {
      return api.get(query);
    }

    return requestWithCache(
      `battle-report-${normalizedBattleId}-${tokenQuery}-${ttlQuery}`,
      query
    );
  },

  getStoredBattles: (limit = 200, offset = 0, search = '', hasReport = null) => {
    const normalizedLimit = Math.min(1000, Math.max(1, Number(limit) || 200));
    const normalizedOffset = Math.max(0, Number(offset) || 0);
    const normalizedSearch = String(search || '').trim();
    const searchQuery = normalizedSearch.length > 0
      ? `&search=${encodeURIComponent(normalizedSearch)}`
      : '';
    const hasReportQuery = hasReport === true
      ? '&has_report=true'
      : hasReport === false
        ? '&has_report=false'
        : '';
    return requestWithCache(
      `stored-battles-${normalizedLimit}-${normalizedOffset}-${normalizedSearch}-${hasReportQuery}`,
      `/api/v1/battles/stored?limit=${normalizedLimit}&offset=${normalizedOffset}${searchQuery}${hasReportQuery}`
    );
  },
};

export default api;
