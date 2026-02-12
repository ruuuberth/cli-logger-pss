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

const Items = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  useEffect(() => {
    const fetchItems = async () => {
      try {
        setLoading(true);
        const response = await pssApi.getItems();
        setItems(response.data.data || []);
        setError(null);
      } catch (err) {
        setError('Error al cargar los items');
        console.error('Items error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchItems();
  }, []);

  const deferredSearch = useDeferredValue(searchTerm);
  const debouncedSearch = useDebouncedValue(deferredSearch, 250);

  const filteredItems = useMemo(() => {
    const term = debouncedSearch.trim().toLowerCase();
    if (!term) {
      return items;
    }

    return items.filter((item) =>
      `${item.name || ''} ${item.rarity || ''} ${item.item_type || ''}`
        .toLowerCase()
        .includes(term)
    );
  }, [items, debouncedSearch]);

  const paginatedItems = useMemo(() => {
    const start = page * rowsPerPage;
    return filteredItems.slice(start, start + rowsPerPage);
  }, [filteredItems, page, rowsPerPage]);

  useEffect(() => {
    setPage(0);
  }, [debouncedSearch]);

  const getRarityColor = (rarity) => {
    const colors = {
      Common: 'default',
      Uncommon: 'success',
      Rare: 'info',
      Epic: 'warning',
      Legendary: 'error',
    };
    return colors[rarity] || 'default';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="400px">
        <Typography>Cargando items...</Typography>
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Items - PixelStarships
      </Typography>
      
      <Box sx={{ mb: 3 }}>
        <TextField
          fullWidth
          label="Buscar items..."
          variant="outlined"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Mostrando {filteredItems.length} resultados
      </Typography>

      <Paper>
        <TableContainer sx={{ maxHeight: 620 }}>
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Nombre</TableCell>
                <TableCell>Rareza</TableCell>
                <TableCell>Tipo</TableCell>
                <TableCell>Estadisticas</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedItems.map((item) => (
                <TableRow key={item.id} hover>
                  <TableCell>{item.id}</TableCell>
                  <TableCell>{item.name}</TableCell>
                  <TableCell>
                    <Chip label={item.rarity} color={getRarityColor(item.rarity)} size="small" />
                  </TableCell>
                  <TableCell>{item.item_type}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {compactStats(item.stats).map((entry) => (
                        <Chip key={`${item.id}-${entry}`} label={entry} size="small" variant="outlined" />
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
          count={filteredItems.length}
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

export default Items;
