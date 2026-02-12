import React from 'react';
import { Alert, Box, Paper, Typography } from '@mui/material';

const Battles = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Batallas
      </Typography>

      <Paper sx={{ p: 2 }}>
        <Alert severity="info" sx={{ mb: 2 }}>
          Feature postergada temporalmente.
        </Alert>
        <Typography variant="body1" sx={{ mb: 1 }}>
          Esta pantalla se habilitara cuando se cierre el flujo completo de autenticacion para la API de Pixel Starships.
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Mientras tanto, usa la seccion Auth para gestionar access token / refresh token.
        </Typography>
      </Paper>
    </Box>
  );
};

export default Battles;
