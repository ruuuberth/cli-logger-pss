const { contextBridge, ipcRenderer } = require('electron');
const backendPort = process.env.PSS_DESKTOP_BACKEND_PORT || '8877';
const apiBaseUrl = `http://127.0.0.1:${backendPort}`;

contextBridge.exposeInMainWorld('pssDesktop', {
  isDesktop: true,
  apiBaseUrl,
  getApiBaseUrl: () => ipcRenderer.invoke('desktop:get-api-base-url'),
  detectGameDirectory: () => ipcRenderer.invoke('desktop:detect-game-directory'),
  pickGameDirectory: () => ipcRenderer.invoke('desktop:pick-game-directory'),
  scanGameFiles: (sourceDir) => ipcRenderer.invoke('desktop:scan-game-files', sourceDir),
});
