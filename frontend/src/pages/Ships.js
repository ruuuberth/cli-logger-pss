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

const Ships = () => {
  const [ships, setShips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  useEffect(() => {
    const fetchShips = async () => {
      try {
        setLoading(true);
        const response = await pssApi.getShips();
        setShips(response.data.data || []);
        setError(null);
      } catch (err) {
        setError('Error al cargar las naves');
        console.error('Ships error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchShips();
  }, []);

  const deferredSearch = useDeferredValue(searchTerm);
  const debouncedSearch = useDebouncedValue(deferredSearch, 250);

  const filteredShips = useMemo(() => {
    const term = debouncedSearch.trim().toLowerCase();
    if (!term) {
      return ships;
    }

    return ships.filter((ship) =>
      `${ship.name || ''} ${ship.class_type || ''}`.toLowerCase().includes(term)
    );
  }, [ships, debouncedSearch]);

  const paginatedShips = useMemo(() => {
    const start = page * rowsPerPage;
    return filteredShips.slice(start, start + rowsPerPage);
  }, [filteredShips, page, rowsPerPage]);

  useEffect(() => {
    setPage(0);
  }, [debouncedSearch]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="400px">
        <Typography>Cargando naves...</Typography>
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Ships - PixelStarships
      </Typography>
      
      <Box sx={{ mb: 3 }}>
        <TextField
          fullWidth
          label="Buscar naves..."
          variant="outlined"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Mostrando {filteredShips.length} resultados
      </Typography>

      <Paper>
        <TableContainer sx={{ maxHeight: 620 }}>
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Nombre</TableCell>
                <TableCell>Clase</TableCell>
                <TableCell>Estadisticas</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedShips.map((ship) => (
                <TableRow key={ship.id} hover>
                  <TableCell>{ship.id}</TableCell>
                  <TableCell>{ship.name}</TableCell>
                  <TableCell>
                    <Chip label={ship.class_type} color="primary" size="small" />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {compactStats(ship.stats).map((entry) => (
                        <Chip key={`${ship.id}-${entry}`} label={entry} size="small" variant="outlined" />
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
          count={filteredShips.length}
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

export default Ships;
