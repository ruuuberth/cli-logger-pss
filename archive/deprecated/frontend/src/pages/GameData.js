import React, { useMemo, useRef, useState } from 'react';
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
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';

import { pssApi } from '../services/api';

const TEXT_EXTENSIONS = new Set([
  '.xml',
  '.json',
  '.txt',
  '.log',
  '.csv',
  '.ini',
  '.cfg',
  '.yaml',
  '.yml',
]);

const MAX_FILES_TO_SCAN = 300;
const MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024;

const isDesktop = typeof window !== 'undefined' && window.pssDesktop?.isDesktop;

const shouldIncludeFile = (file) => {
  if (!file || !Number.isFinite(file.size) || file.size <= 0 || file.size > MAX_FILE_SIZE_BYTES) {
    return false;
  }

  const lower = String(file.name || '').toLowerCase();
  for (const extension of TEXT_EXTENSIONS) {
    if (lower.endsWith(extension)) {
      return true;
    }
  }

  return false;
};

const GameData = () => {
  const fileInputRef = useRef(null);
  const [folderPath, setFolderPath] = useState('');
  const [files, setFiles] = useState([]);
  const [scanLoading, setScanLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const selectedTotalBytes = useMemo(
    () => files.reduce((acc, current) => acc + (current.file?.size || current.size || 0), 0),
    [files]
  );

  const openFolderPicker = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const mapWebSelection = (selectedFiles) => {
    const mapped = selectedFiles
      .map((file) => {
        const relativePath = file.webkitRelativePath || file.name;
        return {
          file,
          name: file.name,
          relativePath,
          size: file.size,
        };
      })
      .filter((entry) => shouldIncludeFile(entry.file))
      .slice(0, MAX_FILES_TO_SCAN);

    const firstRelative = mapped[0]?.relativePath || selectedFiles[0]?.webkitRelativePath || '';
    const slashIndex = firstRelative.indexOf('/');
    const rootFolder = slashIndex > 0 ? firstRelative.slice(0, slashIndex) : firstRelative;

    return { mapped, rootFolder };
  };

  const handleFolderSelected = (event) => {
    const selectedFiles = Array.from(event.target.files || []);
    if (selectedFiles.length === 0) {
      setFiles([]);
      setFolderPath('');
      setError('No se seleccionaron archivos.');
      setSuccess(null);
      return;
    }

    const { mapped, rootFolder } = mapWebSelection(selectedFiles);

    setFolderPath(rootFolder || 'Carpeta seleccionada por usuario');
    setFiles(mapped);
    setSuccess(null);

    if (mapped.length === 0) {
      setError('No se encontraron archivos exportables (xml/json/txt/log/csv/ini/cfg/yaml).');
      return;
    }

    setError(null);
  };

  const scanDesktopDirectory = async (targetPath) => {
    try {
      setScanLoading(true);
      setError(null);
      setSuccess(null);
      const scanned = await window.pssDesktop.scanGameFiles(targetPath);
      const mapped = (scanned || []).map((row) => ({
        name: row.name,
        relativePath: row.relativePath,
        size: row.size,
        content: row.content,
      }));
      setFolderPath(targetPath);
      setFiles(mapped);

      if (mapped.length === 0) {
        setError('No se encontraron archivos exportables en la carpeta detectada.');
      }
    } catch (err) {
      setError(err?.message || 'No se pudo escanear la carpeta detectada.');
      setFiles([]);
    } finally {
      setScanLoading(false);
    }
  };

  const handleAutoDetectDesktop = async () => {
    if (!isDesktop) {
      openFolderPicker();
      return;
    }

    try {
      setScanLoading(true);
      setError(null);
      setSuccess(null);
      const detected = await window.pssDesktop.detectGameDirectory();
      if (!detected) {
        setError('No se detecto automaticamente SavySoda/Pixel Starships. Usa seleccion manual.');
        return;
      }
      await scanDesktopDirectory(detected);
    } catch (err) {
      setError(err?.message || 'Error en deteccion automatica. Usa seleccion manual.');
    } finally {
      setScanLoading(false);
    }
  };

  const handlePickDesktopDirectory = async () => {
    if (!isDesktop) {
      openFolderPicker();
      return;
    }

    try {
      setError(null);
      const picked = await window.pssDesktop.pickGameDirectory();
      if (!picked) {
        return;
      }
      await scanDesktopDirectory(picked);
    } catch (err) {
      setError(err?.message || 'No se pudo seleccionar carpeta manualmente.');
    }
  };

  const exportToProject = async () => {
    if (files.length === 0) {
      setError('Primero selecciona o detecta la carpeta del juego.');
      return;
    }

    try {
      setExportLoading(true);
      setError(null);
      const response = await pssApi.importGameFiles({
        sourceDir: folderPath,
        files,
      });
      const data = response?.data?.data || {};
      setSuccess(
        `Importacion completada. Nuevos: ${data.imported || 0}, actualizados: ${data.updated || 0}, omitidos: ${data.skipped || 0}.`
      );
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'No se pudieron exportar los archivos al backend.');
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Importar datos locales del juego
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          webkitdirectory=""
          directory=""
          style={{ display: 'none' }}
          onChange={handleFolderSelected}
        />

        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 2 }}>
          <Button variant="outlined" onClick={handleAutoDetectDesktop} disabled={scanLoading || exportLoading}>
            {scanLoading ? 'Detectando...' : 'Detectar carpeta automaticamente'}
          </Button>
          <Button variant="outlined" onClick={handlePickDesktopDirectory} disabled={scanLoading || exportLoading}>
            Seleccionar carpeta manualmente
          </Button>
          <Button color="success" variant="contained" onClick={exportToProject} disabled={scanLoading || exportLoading}>
            {exportLoading ? 'Exportando...' : 'Exportar al proyecto'}
          </Button>
        </Stack>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Carpeta seleccionada:
        </Typography>
        <Typography variant="body1" sx={{ fontFamily: 'monospace', mb: 2 }}>
          {folderPath || '-'}
        </Typography>

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
          <Chip label={`Modo: ${isDesktop ? 'Desktop nativo' : 'Web'}`} variant="outlined" />
          <Chip label={`Archivos listos: ${files.length}`} color={files.length > 0 ? 'primary' : 'default'} />
          <Chip label={`Limite: ${MAX_FILES_TO_SCAN}`} variant="outlined" />
          <Chip label={`Total: ${selectedTotalBytes} bytes`} variant="outlined" />
          <Chip label={`Max por archivo: ${Math.floor(MAX_FILE_SIZE_BYTES / (1024 * 1024))} MB`} variant="outlined" />
        </Stack>
      </Paper>

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {success ? <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert> : null}

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Archivos detectados
        </Typography>

        {files.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Aun no hay archivos cargados para exportar.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Archivo</TableCell>
                <TableCell>Ruta relativa</TableCell>
                <TableCell align="right">Tamano (bytes)</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {files.map((file) => (
                <TableRow key={`${file.relativePath}-${file.size}`}>
                  <TableCell>{file.name}</TableCell>
                  <TableCell>{file.relativePath}</TableCell>
                  <TableCell align="right">{file.size}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>
    </Box>
  );
};

export default GameData;
