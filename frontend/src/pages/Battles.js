import React, { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';

import { pssApi } from '../services/api';

const normalizeResultLabel = (value) => {
  if (value === null || value === undefined || value === '') {
    return 'N/A';
  }
  if (typeof value === 'boolean') {
    return value ? 'Win' : 'Loss';
  }
  if (typeof value === 'number') {
    return value > 0 ? 'Win' : value < 0 ? 'Loss' : 'Draw';
  }
  return String(value);
};

const resultChipColor = (value) => {
  const label = normalizeResultLabel(value).toLowerCase();
  if (label.includes('win') || label.includes('victory') || label.includes('gan')) {
    return 'success';
  }
  if (label.includes('loss') || label.includes('defeat') || label.includes('perd')) {
    return 'error';
  }
  if (label.includes('draw') || label.includes('tie') || label.includes('empat')) {
    return 'warning';
  }
  return 'default';
};

const formatDate = (value) => {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
};

const Battles = () => {
  const [username, setUsername] = useState('');
  const [limit, setLimit] = useState(10);
  const [battles, setBattles] = useState([]);
  const [resolvedUsername, setResolvedUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const canSearch = useMemo(() => username.trim().length > 0, [username]);

  const handleSearch = async (event) => {
    event.preventDefault();
    if (!canSearch) {
      return;
    }

    try {
      setLoading(true);
      const response = await pssApi.getUserBattles(username.trim(), Number(limit) || 10);
      setBattles(response.data.data || []);
      setResolvedUsername(response.data.username || username.trim());
      setError(null);
    } catch (err) {
      setBattles([]);
      setResolvedUsername('');
      setError('Error al cargar las batallas del usuario');
      console.error('Battles error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Batallas Recientes
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Box component="form" onSubmit={handleSearch}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              label="Usuario"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Limite"
              type="number"
              value={limit}
              onChange={(event) => setLimit(event.target.value)}
              inputProps={{ min: 1, max: 50 }}
              sx={{ width: { xs: '100%', sm: 140 } }}
            />
            <Button type="submit" variant="contained" disabled={!canSearch || loading}>
              {loading ? 'Consultando...' : 'Consultar'}
            </Button>
          </Stack>
        </Box>
      </Paper>

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}

      {resolvedUsername ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Mostrando {battles.length} batallas para: {resolvedUsername}
        </Typography>
      ) : (
        <Alert severity="info" sx={{ mb: 2 }}>
          Ingresa un usuario y presiona "Consultar".
        </Alert>
      )}

      <Paper>
        <TableContainer sx={{ maxHeight: 620 }}>
          <Table stickyHeader sx={{ minWidth: 800 }}>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Fecha</TableCell>
                <TableCell>Resultado</TableCell>
                <TableCell>Oponente</TableCell>
                <TableCell>Tipo</TableCell>
                <TableCell>Cambio trofeos</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {battles.map((battle, index) => (
                <TableRow key={battle.id || `${battle.created_at || 'n/a'}-${index}`} hover>
                  <TableCell>{battle.id || '-'}</TableCell>
                  <TableCell>{formatDate(battle.created_at)}</TableCell>
                  <TableCell>
                    <Chip
                      label={normalizeResultLabel(battle.result)}
                      color={resultChipColor(battle.result)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>{battle.opponent_name || '-'}</TableCell>
                  <TableCell>{battle.battle_type || '-'}</TableCell>
                  <TableCell>{battle.trophy_change ?? '-'}</TableCell>
                </TableRow>
              ))}
              {battles.length === 0 && resolvedUsername ? (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Typography variant="body2" color="text.secondary">
                      No se encontraron batallas para el usuario consultado.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Box>
  );
};

export default Battles;
