import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';

import { pssApi } from '../services/api';

const STORAGE_KEYS = {
  accessToken: 'pss_auth_access_token',
  refreshToken: 'pss_auth_refresh_token',
  deviceKey: 'pss_auth_device_key',
  email: 'pss_auth_email',
};

const Auth = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [refreshToken, setRefreshToken] = useState('');
  const [deviceKey, setDeviceKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    setEmail(localStorage.getItem(STORAGE_KEYS.email) || '');
    setAccessToken(localStorage.getItem(STORAGE_KEYS.accessToken) || '');
    setRefreshToken(localStorage.getItem(STORAGE_KEYS.refreshToken) || '');
    setDeviceKey(localStorage.getItem(STORAGE_KEYS.deviceKey) || '');
  }, []);

  const persistTokens = ({ nextEmail, nextAccessToken, nextRefreshToken, nextDeviceKey }) => {
    if (nextEmail !== undefined) {
      localStorage.setItem(STORAGE_KEYS.email, nextEmail || '');
      setEmail(nextEmail || '');
    }
    if (nextAccessToken !== undefined) {
      localStorage.setItem(STORAGE_KEYS.accessToken, nextAccessToken || '');
      setAccessToken(nextAccessToken || '');
    }
    if (nextRefreshToken !== undefined) {
      localStorage.setItem(STORAGE_KEYS.refreshToken, nextRefreshToken || '');
      setRefreshToken(nextRefreshToken || '');
    }
    if (nextDeviceKey !== undefined) {
      localStorage.setItem(STORAGE_KEYS.deviceKey, nextDeviceKey || '');
      setDeviceKey(nextDeviceKey || '');
    }
  };

  const handleEmailLogin = async () => {
    if (!email.trim() || !password) {
      setError('Ingresa email y contrasena.');
      return;
    }

    try {
      setLoading(true);
      const response = await pssApi.loginWithEmail(email.trim(), password, deviceKey.trim() || null);
      const tokenData = response?.data?.data || {};
      const nextAccessToken = tokenData.access_token || '';
      const nextRefreshToken = tokenData.refresh_token || '';
      const nextDeviceKey = tokenData.device_key || deviceKey;

      if (!nextAccessToken) {
        setError('No se obtuvo access token.');
        return;
      }

      persistTokens({
        nextEmail: email.trim(),
        nextAccessToken,
        nextRefreshToken,
        nextDeviceKey,
      });
      setSuccess('Sesion actualizada correctamente.');
      setError(null);
      setPassword('');
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'Error al autenticar por email/password.');
      setSuccess(null);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshExchange = async () => {
    if (!refreshToken.trim()) {
      setError('Ingresa refresh token.');
      return;
    }

    try {
      setLoading(true);
      const response = await pssApi.loginWithRefreshToken(refreshToken.trim(), deviceKey.trim() || null);
      const tokenData = response?.data?.data || {};
      const nextAccessToken = tokenData.access_token || '';
      const nextDeviceKey = tokenData.device_key || deviceKey;

      if (!nextAccessToken) {
        setError('No se pudo convertir refresh token en access token.');
        return;
      }

      persistTokens({
        nextAccessToken,
        nextRefreshToken: refreshToken.trim(),
        nextDeviceKey,
      });
      setSuccess('Access token renovado correctamente.');
      setError(null);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'Error al convertir refresh token.');
      setSuccess(null);
    } finally {
      setLoading(false);
    }
  };

  const handleClearSession = () => {
    persistTokens({
      nextAccessToken: '',
      nextRefreshToken: '',
      nextDeviceKey: '',
    });
    setPassword('');
    setError(null);
    setSuccess('Sesion local limpiada.');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Autenticacion
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 2 }}>
          <Chip
            label={accessToken ? 'Access token: disponible' : 'Access token: no disponible'}
            color={accessToken ? 'success' : 'default'}
          />
          <Chip
            label={refreshToken ? 'Refresh token: disponible' : 'Refresh token: no disponible'}
            color={refreshToken ? 'info' : 'default'}
          />
        </Stack>

        <Stack spacing={2}>
          <Typography variant="h6">Login por email/password</Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              label="Email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              fullWidth
            />
            <TextField
              label="Contrasena"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              fullWidth
            />
          </Stack>

          <TextField
            label="Device key (opcional)"
            value={deviceKey}
            onChange={(event) => setDeviceKey(event.target.value)}
            fullWidth
          />

          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <Button variant="contained" onClick={handleEmailLogin} disabled={loading}>
              {loading ? 'Procesando...' : 'Login por email'}
            </Button>
            <Button variant="outlined" onClick={handleRefreshExchange} disabled={loading}>
              {loading ? 'Procesando...' : 'Usar refresh token'}
            </Button>
            <Button color="error" variant="text" onClick={handleClearSession}>
              Limpiar sesion local
            </Button>
          </Stack>
        </Stack>

        <Divider sx={{ my: 2 }} />

        <Typography variant="body2" color="text.secondary">
          Tokens guardados localmente en el navegador para reutilizarlos en futuras features.
        </Typography>
      </Paper>

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {success ? <Alert severity="success">{success}</Alert> : null}
    </Box>
  );
};

export default Auth;
