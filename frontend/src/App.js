import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box, Container } from '@mui/material';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Items from './pages/Items';
import Ships from './pages/Ships';
import Crews from './pages/Crews';

function App() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Navbar />
      <Container maxWidth="lg" sx={{ flex: 1, py: 3 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/items" element={<Items />} />
          <Route path="/ships" element={<Ships />} />
          <Route path="/crews" element={<Crews />} />
        </Routes>
      </Container>
    </Box>
  );
}

export default App;