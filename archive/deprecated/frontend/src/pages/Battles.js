import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';

import { pssApi } from '../services/api';

const STORAGE_KEYS = {
  accessToken: 'pss_auth_access_token',
  lastBattleAccessToken: 'pss_battles_last_access_token',
};

const Battles = () => {
  const [battleId, setBattleId] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [forceRefresh, setForceRefresh] = useState(false);
  const [ttlSeconds, setTtlSeconds] = useState('');
  const [loadingReport, setLoadingReport] = useState(false);
  const [storedBattles, setStoredBattles] = useState([]);
  const [storedTotal, setStoredTotal] = useState(0);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loadingStored, setLoadingStored] = useState(false);
  const [storedPage, setStoredPage] = useState(0);
  const [storedRowsPerPage, setStoredRowsPerPage] = useState(25);
  const [storedSearchInput, setStoredSearchInput] = useState('');
  const [storedSearchApplied, setStoredSearchApplied] = useState('');
  const [storedHasReportInput, setStoredHasReportInput] = useState('all');
  const [storedHasReportApplied, setStoredHasReportApplied] = useState('all');

  useEffect(() => {
    const lastBattleToken = localStorage.getItem(STORAGE_KEYS.lastBattleAccessToken) || '';
    const authToken = localStorage.getItem(STORAGE_KEYS.accessToken) || '';
    setAccessToken(lastBattleToken || authToken);
  }, []);

  const persistLastAccessToken = (token) => {
    const normalized = String(token || '').trim();
    if (!normalized) {
      return;
    }
    localStorage.setItem(STORAGE_KEYS.lastBattleAccessToken, normalized);
    localStorage.setItem(STORAGE_KEYS.accessToken, normalized);
  };

  const loadStoredBattles = async (opts = {}) => {
    const nextPage = Number.isInteger(opts.page) ? opts.page : storedPage;
    const nextRowsPerPage = Number.isInteger(opts.rowsPerPage) ? opts.rowsPerPage : storedRowsPerPage;
    const nextSearchApplied = opts.searchApplied !== undefined ? opts.searchApplied : storedSearchApplied;
    const nextHasReportApplied = opts.hasReportApplied !== undefined ? opts.hasReportApplied : storedHasReportApplied;
    const nextOffset = nextPage * nextRowsPerPage;
    const nextHasReport =
      nextHasReportApplied === 'with'
        ? true
        : nextHasReportApplied === 'without'
          ? false
          : null;

    try {
      setLoadingStored(true);
      const response = await pssApi.getStoredBattles(
        nextRowsPerPage,
        nextOffset,
        nextSearchApplied,
        nextHasReport
      );
      setStoredBattles(response?.data?.data || []);
      setStoredTotal(Number(response?.data?.total) || 0);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'No se pudo cargar el indice de batallas almacenadas.');
      setStoredBattles([]);
      setStoredTotal(0);
    } finally {
      setLoadingStored(false);
    }
  };

  useEffect(() => {
    loadStoredBattles({
      page: storedPage,
      rowsPerPage: storedRowsPerPage,
      searchApplied: storedSearchApplied,
      hasReportApplied: storedHasReportApplied,
    });
  }, []);

  const resolvedBattleId = useMemo(() => {
    const value = String(battleId || '').trim();
    return value;
  }, [battleId]);

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
        forceRefresh,
        ttlSeconds === '' ? null : ttlSeconds
      );
      persistLastAccessToken(accessToken);
      setReport(response?.data?.data || null);
      loadStoredBattles({
        page: storedPage,
        rowsPerPage: storedRowsPerPage,
        searchApplied: storedSearchApplied,
        hasReportApplied: storedHasReportApplied,
      });
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

  const handleApplyStoredFilters = async () => {
    setStoredPage(0);
    setStoredSearchApplied(storedSearchInput.trim());
    setStoredHasReportApplied(storedHasReportInput);
    await loadStoredBattles({
      page: 0,
      rowsPerPage: storedRowsPerPage,
      searchApplied: storedSearchInput.trim(),
      hasReportApplied: storedHasReportInput,
    });
  };

  const handleStoredPageChange = async (_, nextPage) => {
    setStoredPage(nextPage);
    await loadStoredBattles({
      page: nextPage,
      rowsPerPage: storedRowsPerPage,
      searchApplied: storedSearchApplied,
      hasReportApplied: storedHasReportApplied,
    });
  };

  const handleStoredRowsPerPageChange = async (event) => {
    const nextRows = parseInt(event.target.value, 10) || 25;
    setStoredRowsPerPage(nextRows);
    setStoredPage(0);
    await loadStoredBattles({
      page: 0,
      rowsPerPage: nextRows,
      searchApplied: storedSearchApplied,
      hasReportApplied: storedHasReportApplied,
    });
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Batallas
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 2 }} alignItems={{ md: 'center' }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            IDs almacenados (persistentes)
          </Typography>
          <Button
            variant="outlined"
            onClick={() =>
              loadStoredBattles({
                page: storedPage,
                rowsPerPage: storedRowsPerPage,
                searchApplied: storedSearchApplied,
                hasReportApplied: storedHasReportApplied,
              })
            }
            disabled={loadingStored}
          >
            {loadingStored ? 'Actualizando...' : 'Actualizar indice'}
          </Button>
        </Stack>

        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 2 }}>
          <TextField
            label="Filtro (battle id / jugador / oponente)"
            value={storedSearchInput}
            onChange={(event) => setStoredSearchInput(event.target.value)}
            fullWidth
          />
          <TextField
            select
            label="Reporte XML"
            value={storedHasReportInput}
            onChange={(event) => setStoredHasReportInput(event.target.value)}
            sx={{ minWidth: 180 }}
          >
            <MenuItem value="all">Todos</MenuItem>
            <MenuItem value="with">Con reporte</MenuItem>
            <MenuItem value="without">Sin reporte</MenuItem>
          </TextField>
          <Button variant="contained" onClick={handleApplyStoredFilters} disabled={loadingStored}>
            Aplicar filtros
          </Button>
        </Stack>

        {storedBattles.length > 0 ? (
          <>
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
            <TablePagination
              component="div"
              count={storedTotal}
              page={storedPage}
              onPageChange={handleStoredPageChange}
              rowsPerPage={storedRowsPerPage}
              onRowsPerPageChange={handleStoredRowsPerPageChange}
              rowsPerPageOptions={[10, 25, 50, 100]}
            />
          </>
        ) : (
          <Typography variant="body2" color="text.secondary">
            Aun no hay IDs almacenados.
          </Typography>
        )}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Obtener reporte de batalla
        </Typography>

        <Stack spacing={2}>
          <TextField
            label="Access token"
            value={accessToken}
            onChange={(event) => setAccessToken(event.target.value)}
            helperText="Solo es necesario si el reporte aun no existe en el indice. Se guarda automaticamente como ultimo token usado."
            fullWidth
          />

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
