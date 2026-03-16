/**
 * OmniCompanion — Electron Main Process
 *
 * Creates the PiP (Picture-in-Picture) overlay window
 * and manages IPC bridge to the Python backend.
 */

import { app, BrowserWindow, ipcMain, screen } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

/**
 * Create the always-on-top PiP window.
 */
function createPiPWindow(): void {
  const display = screen.getPrimaryDisplay();
  const { width: screenWidth, height: screenHeight } = display.workAreaSize;

  // PiP window: bottom-right corner, 320x400
  const pipWidth = 320;
  const pipHeight = 400;

  mainWindow = new BrowserWindow({
    width: pipWidth,
    height: pipHeight,
    x: screenWidth - pipWidth - 20,
    y: screenHeight - pipHeight - 20,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: true,
    minimizable: false,
    skipTaskbar: true,
    hasShadow: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // Load the React app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // Handle window close
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * Start the Python orchestrator backend.
 */
function startPythonBackend(): void {
  pythonProcess = spawn('python', ['-m', 'src.orchestrator.main'], {
    cwd: path.join(__dirname, '../../..'),
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  if (pythonProcess.stdout) {
    pythonProcess.stdout.on('data', (data: Buffer) => {
      const message = data.toString().trim();
      console.log(`[Python] ${message}`);

      // Forward to renderer
      if (mainWindow) {
        mainWindow.webContents.send('backend-log', message);
      }
    });
  }

  if (pythonProcess.stderr) {
    pythonProcess.stderr.on('data', (data: Buffer) => {
      console.error(`[Python Error] ${data.toString()}`);
    });
  }

  pythonProcess.on('close', (code: number | null) => {
    console.log(`Python process exited with code ${code}`);
  });
}

/**
 * Set up IPC handlers for renderer communication.
 */
function setupIPC(): void {
  // Forward goals from UI to Python backend
  ipcMain.handle('submit-goal', async (_event, goal: string) => {
    if (pythonProcess && pythonProcess.stdin) {
      const message = JSON.stringify({ type: 'goal', data: goal }) + '\n';
      pythonProcess.stdin.write(message);
      return { accepted: true };
    }
    return { accepted: false, error: 'Backend not running' };
  });

  // Get current task status
  ipcMain.handle('get-status', async () => {
    return { status: 'ready' };
  });

  // Action confirmation from user
  ipcMain.handle('confirm-action', async (_event, actionId: string, approved: boolean) => {
    if (pythonProcess && pythonProcess.stdin) {
      const message = JSON.stringify({
        type: 'confirmation',
        data: { actionId, approved },
      }) + '\n';
      pythonProcess.stdin.write(message);
    }
    return { acknowledged: true };
  });
}

// App lifecycle
app.whenReady().then(() => {
  createPiPWindow();
  setupIPC();
  // startPythonBackend(); // Uncomment when backend is ready
});

app.on('window-all-closed', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createPiPWindow();
  }
});
