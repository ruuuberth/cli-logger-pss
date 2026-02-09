import React, { useState, useEffect } from 'react';
import { Grid, Card, CardContent, Typography, Box, Alert } from '@mui/material';
import { pssApi } from '../services/api';

const Dashboard = () => {
  const [data, setData] = useState({
    items: [],
    ships: [],
    crews: []
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [itemsRes, shipsRes, crewsRes] = await Promise.all([
          pssApi.getItems(),
          pssApi.getShips(),
          pssApi.getCrews()
        ]);

        setData({
          items: itemsRes.data.data || [],
          ships: shipsRes.data.data || [],
          crews: crewsRes.data.data || []
        });
        setError(null);
      } catch (err) {
        setError('Error al cargar datos de PixelStarships');
        console.error('Dashboard error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="400px">
        <Typography>Cargando datos...</Typography>
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard - PixelStarships Logger
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" color="primary" gutterBottom>
                Items
              </Typography>
              <Typography variant="h3">
                {data.items.length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Diseños de items cargados
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" color="primary" gutterBottom>
                Ships
              </Typography>
              <Typography variant="h3">
                {data.ships.length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Diseños de naves cargados
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" color="primary" gutterBottom>
                Crews
              </Typography>
              <Typography variant="h3">
                {data.crews.length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Diseños de tripulación cargados
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Items Recientes
              </Typography>
              <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
                {data.items.slice(0, 5).map((item) => (
                  <Box key={item.id} sx={{ py: 1, borderBottom: '1px solid #333' }}>
                    <Typography variant="body1">
                      {item.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {item.rarity} • {item.item_type}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;