import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';

import { pssApi } from '../services/api';

const STORAGE_KEYS = {
  accessToken: 'pss_auth_access_token',
  refreshToken: 'pss_auth_refresh_token',
  deviceKey: 'pss_auth_device_key',
};

const Battles = () => {
  const [username, setUsername] = useState('');
  const [limit, setLimit] = useState(10);
  const [battleId, setBattleId] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [refreshToken, setRefreshToken] = useState('');
  const [deviceKey, setDeviceKey] = useState('');
  const [forceRefresh, setForceRefresh] = useState(false);
  const [ttlSeconds, setTtlSeconds] = useState('');
  const [loadingBattles, setLoadingBattles] = useState(false);
  const [loadingReport, setLoadingReport] = useState(false);
  const [battles, setBattles] = useState([]);
  const [storedBattles, setStoredBattles] = useState([]);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loadingStored, setLoadingStored] = useState(false);

  useEffect(() => {
    setAccessToken(localStorage.getItem(STORAGE_KEYS.accessToken) || '');
    setRefreshToken(localStorage.getItem(STORAGE_KEYS.refreshToken) || '');
    setDeviceKey(localStorage.getItem(STORAGE_KEYS.deviceKey) || '');
  }, []);

  const loadStoredBattles = async () => {
    try {
      setLoadingStored(true);
      const response = await pssApi.getStoredBattles(300, 0);
      setStoredBattles(response?.data?.data || []);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'No se pudo cargar el indice de batallas almacenadas.');
      setStoredBattles([]);
    } finally {
      setLoadingStored(false);
    }
  };

  useEffect(() => {
    loadStoredBattles();
  }, []);

  const resolvedBattleId = useMemo(() => {
    const value = String(battleId || '').trim();
    return value;
  }, [battleId]);

  const handleFetchBattles = async () => {
    if (!username.trim()) {
      setError('Ingresa un username.');
      return;
    }

    try {
      setError(null);
      setLoadingBattles(true);
      const response = await pssApi.getUserBattles(
        username.trim(),
        Number(limit) || 10,
        accessToken.trim() || null,
        refreshToken.trim() || null,
        deviceKey.trim() || null
      );
      const rows = response?.data?.data || [];
      setBattles(rows);
      loadStoredBattles();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'No se pudieron cargar batallas recientes.');
      setBattles([]);
    } finally {
      setLoadingBattles(false);
    }
  };

  const handleFetchReport = async () => {
    if (!resolvedBattleId) {
      setError('Ingresa battle id.');
      return;
    }

    try {
      setError(null);
      setLoadingReport(true);
      const response = await pssApi.getBattleReport(
        resolvedBattleId,
        accessToken.trim() || null,
        refreshToken.trim() || null,
        deviceKey.trim() || null,
        forceRefresh,
        ttlSeconds === '' ? null : ttlSeconds
      );
      setReport(response?.data?.data || null);
      loadStoredBattles();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'No se pudo obtener el reporte de batalla.');
      setReport(null);
    } finally {
      setLoadingReport(false);
    }
  };

  const handleUseBattleId = (id) => {
    if (id === null || id === undefined) {
      return;
    }
    setBattleId(String(id));
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Batallas
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Token y parametros
        </Typography>

        <Stack spacing={2}>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <TextField
              label="Access token"
              value={accessToken}
              onChange={(event) => setAccessToken(event.target.value)}
              fullWidth
            />
            <TextField
              label="Refresh token"
              value={refreshToken}
              onChange={(event) => setRefreshToken(event.target.value)}
              fullWidth
            />
          </Stack>
          <TextField
            label="Device key (opcional)"
            value={deviceKey}
            onChange={(event) => setDeviceKey(event.target.value)}
            fullWidth
          />
        </Stack>
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 2 }} alignItems={{ md: 'center' }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            IDs almacenados (persistentes)
          </Typography>
          <Button variant="outlined" onClick={loadStoredBattles} disabled={loadingStored}>
            {loadingStored ? 'Actualizando...' : 'Actualizar indice'}
          </Button>
        </Stack>

        {storedBattles.length > 0 ? (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Battle ID</TableCell>
                <TableCell>Jugador</TableCell>
                <TableCell>Oponente</TableCell>
                <TableCell>Resultado</TableCell>
                <TableCell>Tipo</TableCell>
                <TableCell>Reporte XML</TableCell>
                <TableCell align="right">Accion</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {storedBattles.map((row) => (
                <TableRow key={row.battle_id}>
                  <TableCell>{row.battle_id}</TableCell>
                  <TableCell>{row.player_name || '-'}</TableCell>
                  <TableCell>{row.opponent_name || '-'}</TableCell>
                  <TableCell>{row.result || '-'}</TableCell>
                  <TableCell>{row.battle_type || '-'}</TableCell>
                  <TableCell>{row.has_report ? 'Si' : 'No'}</TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => handleUseBattleId(row.battle_id)}>
                      usar
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <Typography variant="body2" color="text.secondary">
            Aun no hay IDs almacenados.
          </Typography>
        )}
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Batallas recientes
        </Typography>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 2 }}>
          <TextField
            label="Username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            fullWidth
          />
          <TextField
            label="Limit"
            type="number"
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
            inputProps={{ min: 1, max: 50 }}
            sx={{ minWidth: 120 }}
          />
          <Button variant="contained" onClick={handleFetchBattles} disabled={loadingBattles}>
            {loadingBattles ? 'Cargando...' : 'Cargar batallas'}
          </Button>
        </Stack>

        {battles.length > 0 ? (
          <Stack spacing={1}>
            {battles.map((battle, index) => (
              <Paper key={`${battle.id || 'battle'}-${index}`} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} alignItems={{ md: 'center' }}>
                  <Typography variant="body2" sx={{ flexGrow: 1 }}>
                    #{battle.id || '-'} | {battle.player_name || '-'} vs {battle.opponent_name || '-'} | {battle.result || '-'}
                  </Typography>
                  <Button size="small" onClick={() => handleUseBattleId(battle.id)}>
                    usar battle id
                  </Button>
                </Stack>
              </Paper>
            ))}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary">
            Sin resultados cargados.
          </Typography>
        )}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Reporte XML (GetBattle3)
        </Typography>

        <Stack spacing={2}>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <TextField
              label="Battle ID"
              value={battleId}
              onChange={(event) => setBattleId(event.target.value)}
              fullWidth
            />
            <TextField
              label="TTL cache memoria (segundos)"
              type="number"
              value={ttlSeconds}
              onChange={(event) => setTtlSeconds(event.target.value)}
              inputProps={{ min: 0 }}
              sx={{ minWidth: 220 }}
            />
          </Stack>

          <FormControlLabel
            control={
              <Checkbox
                checked={forceRefresh}
                onChange={(event) => setForceRefresh(event.target.checked)}
              />
            }
            label="Force refresh (ignorar cache frontend/backend cuando aplique)"
          />

          <Button variant="contained" onClick={handleFetchReport} disabled={loadingReport}>
            {loadingReport ? 'Cargando...' : 'Descargar reporte'}
          </Button>

          {report ? (
            <Stack spacing={1}>
              <Typography variant="body2">
                battle_id: {report.battle_id || '-'} | source: {report.source || '-'} | endpoint: {report.source_endpoint || '-'}
              </Typography>
              <Typography variant="body2">
                player: {report.player_name || '-'} | opponent: {report.opponent_name || '-'} | result: {report.result || '-'}
              </Typography>
              <TextField
                label="XML report"
                value={report.xml_report || ''}
                multiline
                minRows={10}
                maxRows={20}
                fullWidth
              />
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Sin reporte cargado.
            </Typography>
          )}
        </Stack>
      </Paper>

      {error ? <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert> : null}
    </Box>
  );
};

export default Battles;
