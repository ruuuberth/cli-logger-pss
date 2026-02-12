import React, { useDeferredValue, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { pssApi } from '../services/api';

const useDebouncedValue = (value, delay = 250) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
};

const compactStats = (stats = {}) => {
  const entries = Object.entries(stats);
  if (entries.length === 0) {
    return [];
  }

  const visible = entries.slice(0, 3).map(([stat, value]) => `${stat}: ${value}`);
  if (entries.length > 3) {
    visible.push(`+${entries.length - 3} mas`);
  }
  return visible;
};

const Crews = () => {
  const [crews, setCrews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  useEffect(() => {
    const fetchCrews = async () => {
      try {
        setLoading(true);
        const response = await pssApi.getCrews();
        setCrews(response.data.data || []);
        setError(null);
      } catch (err) {
        setError('Error al cargar la tripulación');
        console.error('Crews error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchCrews();
  }, []);

  const deferredSearch = useDeferredValue(searchTerm);
  const debouncedSearch = useDebouncedValue(deferredSearch, 250);

  const filteredCrews = useMemo(() => {
    const term = debouncedSearch.trim().toLowerCase();
    if (!term) {
      return crews;
    }

    return crews.filter((crew) =>
      `${crew.name || ''} ${crew.race || ''} ${crew.role || ''}`
        .toLowerCase()
        .includes(term)
    );
  }, [crews, debouncedSearch]);

  const paginatedCrews = useMemo(() => {
    const start = page * rowsPerPage;
    return filteredCrews.slice(start, start + rowsPerPage);
  }, [filteredCrews, page, rowsPerPage]);

  useEffect(() => {
    setPage(0);
  }, [debouncedSearch]);

  const getRoleColor = (role) => {
    const colors = {
      Captain: 'error',
      Pilot: 'primary',
      Engineer: 'success',
      Scientist: 'info',
      Medic: 'warning',
      Gunner: 'secondary',
    };
    return colors[role] || 'default';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="400px">
        <Typography>Cargando tripulación...</Typography>
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Crews - PixelStarships
      </Typography>

      <Box sx={{ mb: 2 }}>
        <TextField
          fullWidth
          label="Buscar tripulacion..."
          variant="outlined"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Mostrando {filteredCrews.length} resultados
      </Typography>

      <Paper>
        <TableContainer sx={{ maxHeight: 620 }}>
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Nombre</TableCell>
                <TableCell>Raza</TableCell>
                <TableCell>Rol</TableCell>
                <TableCell>Estadisticas</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedCrews.map((crew) => (
                <TableRow key={crew.id} hover>
                  <TableCell>{crew.id}</TableCell>
                  <TableCell>{crew.name}</TableCell>
                  <TableCell>{crew.race}</TableCell>
                  <TableCell>
                    <Chip label={crew.role} color={getRoleColor(crew.role)} size="small" />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {compactStats(crew.stats).map((entry) => (
                        <Chip key={`${crew.id}-${entry}`} label={entry} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        <TablePagination
          component="div"
          count={filteredCrews.length}
          page={page}
          onPageChange={(_, nextPage) => setPage(nextPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(event) => {
            setRowsPerPage(parseInt(event.target.value, 10));
            setPage(0);
          }}
          rowsPerPageOptions={[10, 25, 50, 100]}
        />
      </Paper>
    </Box>
  );
};

export default Crews;
