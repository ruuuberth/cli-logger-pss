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

const Crews = () => {
  const [crews, setCrews] = useState([]);
  const [filteredCrews, setFilteredCrews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

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

  useEffect(() => {
    const filtered = crews.filter(crew =>
      (crew.name || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
      (crew.race || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
      (crew.role || "").toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredCrews(filtered);
  }, [crews, searchTerm]);

  const getRoleColor = (role) => {
    const colors = {
      'Captain': 'error',
      'Pilot': 'primary',
      'Engineer': 'success',
      'Scientist': 'info',
      'Medic': 'warning',
      'Gunner': 'secondary'
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
      
      <Box sx={{ mb: 3 }}>
        <TextField
          fullWidth
          label="Buscar tripulación..."
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
              <TableCell>Raza</TableCell>
              <TableCell>Rol</TableCell>
              <TableCell>Estadísticas</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredCrews.map((crew) => (
              <TableRow key={crew.id}>
                <TableCell>{crew.id}</TableCell>
                <TableCell>{crew.name}</TableCell>
                <TableCell>{crew.race}</TableCell>
                <TableCell>
                  <Chip 
                    label={crew.role} 
                    color={getRoleColor(crew.role)}
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {Object.entries(crew.stats || {}).map(([stat, value]) => (
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

export default Crews;