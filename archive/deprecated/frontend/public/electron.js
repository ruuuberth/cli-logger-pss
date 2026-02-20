const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const isDev = require('electron-is-dev');

let mainWindow;
let backendProcess = null;

const BACKEND_PORT = Number(process.env.PSS_DESKTOP_BACKEND_PORT || 8877);
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const TEXT_EXTENSIONS = new Set(['.xml', '.json', '.txt', '.log', '.csv', '.ini', '.cfg', '.yaml', '.yml']);
const MAX_FILES_TO_SCAN = 300;
const MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024;

function getCandidateDirectories() {
  const home = os.homedir();
  if (process.platform === 'win32') {
    return [
      path.join(home, 'AppData', 'LocalLow', 'SavySoda', 'Pixel Starships'),
      path.join(home, 'AppData', 'Local', 'SavySoda', 'Pixel Starships'),
      path.join(home, 'Documents', 'SavySoda', 'Pixel Starships'),
    ];
  }

  if (process.platform === 'darwin') {
    return [
      path.join(home, 'Library', 'Application Support', 'SavySoda', 'Pixel Starships'),
      path.join(home, 'Library', 'Caches', 'SavySoda', 'Pixel Starships'),
    ];
  }

  return [
    path.join(home, '.config', 'unity3d', 'SavySoda', 'Pixel Starships'),
    path.join(home, '.local', 'share', 'SavySoda', 'Pixel Starships'),
    path.join(home, 'SavySoda', 'Pixel Starships'),
  ];
}

function shouldIncludeFile(fileName, size) {
  if (!Number.isFinite(size) || size <= 0 || size > MAX_FILE_SIZE_BYTES) {
    return false;
  }

  const ext = path.extname(fileName || '').toLowerCase();
  return TEXT_EXTENSIONS.has(ext);
}

async function detectGameDirectory() {
  for (const candidate of getCandidateDirectories()) {
    try {
      const stat = await fs.promises.stat(candidate);
      if (stat.isDirectory()) {
        return candidate;
      }
    } catch (_error) {
      // Ignore invalid candidates.
    }
  }
  return null;
}

async function scanGameFiles(sourceDir) {
  if (!sourceDir) {
    return [];
  }

  const collected = [];

  const walk = async (currentDir) => {
    if (collected.length >= MAX_FILES_TO_SCAN) {
      return;
    }

    const entries = await fs.promises.readdir(currentDir, { withFileTypes: true });
    for (const entry of entries) {
      if (collected.length >= MAX_FILES_TO_SCAN) {
        break;
      }

      const absolutePath = path.join(currentDir, entry.name);
      if (entry.isDirectory()) {
        await walk(absolutePath);
        continue;
      }

      if (!entry.isFile()) {
        continue;
      }

      const stat = await fs.promises.stat(absolutePath);
      if (!shouldIncludeFile(entry.name, stat.size)) {
        continue;
      }

      const content = await fs.promises.readFile(absolutePath, 'utf8');
      collected.push({
        name: entry.name,
        relativePath: path.relative(sourceDir, absolutePath),
        size: stat.size,
        content,
      });
    }
  };

  await walk(sourceDir);
  return collected;
}

function startBundledBackend() {
  if (backendProcess) {
    return;
  }

  const userDataDir = app.getPath('userData');
  const env = {
    ...process.env,
    PSS_DESKTOP_MODE: '1',
    PSS_DESKTOP_BACKEND_PORT: String(BACKEND_PORT),
    DATABASE_URL: `sqlite:///${path.join(userDataDir, 'pss_logger.db')}`,
    ALLOWED_HOSTS: '*',
  };

  if (isDev) {
    const pythonCmd = process.env.PSS_DESKTOP_PYTHON || 'python3';
    const backendRoot = path.resolve(__dirname, '../../backend');
    backendProcess = spawn(
      pythonCmd,
      ['-m', 'app.desktop_main'],
      { cwd: backendRoot, env, stdio: 'pipe' }
    );
  } else {
    const executableName = process.platform === 'win32' ? 'pss-backend.exe' : 'pss-backend';
    const executablePath = path.join(process.resourcesPath, 'backend', executableName);
    backendProcess = spawn(executablePath, [], { env, stdio: 'pipe' });
  }

  backendProcess.stdout.on('data', (chunk) => {
    process.stdout.write(`[backend] ${chunk}`);
  });
  backendProcess.stderr.on('data', (chunk) => {
    process.stderr.write(`[backend] ${chunk}`);
  });
  backendProcess.on('exit', (code) => {
    process.stdout.write(`[backend] exited with code ${code}\n`);
    backendProcess = null;
  });
}

function stopBundledBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
}

function registerIpcHandlers() {
  ipcMain.handle('desktop:get-api-base-url', async () => BACKEND_URL);
  ipcMain.handle('desktop:detect-game-directory', async () => detectGameDirectory());
  ipcMain.handle('desktop:pick-game-directory', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory'],
      title: 'Selecciona carpeta SavySoda/Pixel Starships',
    });
    if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths[0];
  });
  ipcMain.handle('desktop:scan-game-files', async (_event, sourceDir) => scanGameFiles(sourceDir));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    icon: path.join(__dirname, 'icon.png')
  });

  mainWindow.loadURL(
    isDev
      ? 'http://localhost:3000'
      : `file://${path.join(__dirname, '../build/index.html')}`
  );

  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  registerIpcHandlers();
  startBundledBackend();
  createWindow();
});

app.on('window-all-closed', () => {
  stopBundledBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

app.on('before-quit', () => {
  stopBundledBackend();
});
