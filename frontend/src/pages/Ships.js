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

const Ships = () => {
  const [ships, setShips] = useState([]);
  const [filteredShips, setFilteredShips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

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

  useEffect(() => {
    const filtered = ships.filter(ship =>
      ship.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ship.class_type.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredShips(filtered);
  }, [ships, searchTerm]);

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

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Nombre</TableCell>
              <TableCell>Clase</TableCell>
              <TableCell>Estadísticas</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredShips.map((ship) => (
              <TableRow key={ship.id}>
                <TableCell>{ship.id}</TableCell>
                <TableCell>{ship.name}</TableCell>
                <TableCell>
                  <Chip 
                    label={ship.class_type} 
                    color="primary"
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {Object.entries(ship.stats || {}).map(([stat, value]) => (
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

export default Ships;