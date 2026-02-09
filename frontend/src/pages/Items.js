import React, { useState, useEffect } from 'react';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableContainer, 
  TableHead, 
  TableRow, 
  Paper, 
  Typography, 
  Box, 
  Alert,
  TextField,
  Chip
} from '@mui/material';
import { pssApi } from '../services/api';

const Items = () => {
  const [items, setItems] = useState([]);
  const [filteredItems, setFilteredItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

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

  useEffect(() => {
    const filtered = items.filter(item =>
      item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.rarity.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.item_type.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredItems(filtered);
  }, [items, searchTerm]);

  const getRarityColor = (rarity) => {
    const colors = {
      'Common': 'default',
      'Uncommon': 'success',
      'Rare': 'info',
      'Epic': 'warning',
      'Legendary': 'error'
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

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Nombre</TableCell>
              <TableCell>Rareza</TableCell>
              <TableCell>Tipo</TableCell>
              <TableCell>Estadísticas</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredItems.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.id}</TableCell>
                <TableCell>{item.name}</TableCell>
                <TableCell>
                  <Chip 
                    label={item.rarity} 
                    color={getRarityColor(item.rarity)}
                    size="small"
                  />
                </TableCell>
                <TableCell>{item.item_type}</TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {Object.entries(item.stats || {}).map(([stat, value]) => (
                      <Chip
                        key={stat}
                        label={`${stat}: ${value}`}
                        size="small"
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default Items;