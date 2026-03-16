/**
 * OmniCompanion v2 — Electron Main Process
 *
 * Full-screen native desktop app for the voice-first AI companion.
 * Auto-starts the Python backend and loads the v2 UI.
 *
 * Key differences from v1:
 * - Full application window (not PiP overlay)
 * - Auto-starts Python companion backend
 * - Grants microphone/screen permissions for voice
 * - Frameless with custom title bar region
 */

const { app, BrowserWindow, ipcMain, screen, session } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let pythonProcess = null;

const isDev = process.env.NODE_ENV === 'development' ||
    !app.isPackaged;

/**
 * Create the main application window.
 */
function createMainWindow() {
    const display = screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight } = display.workAreaSize;

    // Full-ish size window, centered
    const winWidth = Math.min(1200, screenWidth - 100);
    const winHeight = Math.min(800, screenHeight - 100);

    mainWindow = new BrowserWindow({
        width: winWidth,
        height: winHeight,
        minWidth: 800,
        minHeight: 600,
        center: true,
        frame: false,
        titleBarStyle: 'hiddenInset',
        vibrancy: 'dark',
        visualEffectState: 'active',
        transparent: false,
        backgroundColor: '#0a0a1a',
        hasShadow: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload_v2.js'),
        },
    });

    // Load the v2 UI
    if (isDev) {
        // In dev mode, load from Vite dev server
        mainWindow.loadURL('http://localhost:5173/index_v2.html').catch(() => {
            // Fallback: try without the v2 path
            mainWindow.loadURL('http://localhost:5173').catch((err) => {
                console.error('Cannot connect to Vite dev server:', err.message);
                mainWindow.loadURL(`data:text/html,
                    <html><body style="background:#0a0a1a;color:#fff;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh">
                    <div style="text-align:center">
                        <h2>🤖 OmniCompanion v2</h2>
                        <p style="color:#888">Start the Vite dev server first:</p>
                        <code style="color:#00d4aa">cd src/ui && npx vite --config vite.config.v2.ts</code>
                    </div>
                    </body></html>
                `);
            });
        });
    } else {
        // In production, load the built files
        const distPath = path.join(__dirname, '../dist/index_v2.html');
        mainWindow.loadFile(distPath).catch(() => {
            const fallbackPath = path.join(__dirname, '../dist/index.html');
            mainWindow.loadFile(fallbackPath).catch((err) => {
                console.error('Failed to load app:', err);
            });
        });
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // Open DevTools in development
    if (isDev && process.env.OPEN_DEVTOOLS) {
        mainWindow.webContents.openDevTools({ mode: 'detach' });
    }
}

/**
 * Start the Python companion backend.
 */
function startPythonBackend() {
    const projectRoot = path.join(__dirname, '../../..');
    const venvPython = path.join(projectRoot, '.venv', 'bin', 'python3');
    const fallbackPython = 'python3';

    // Try venv first, fallback to system python
    const fs = require('fs');
    const pythonBin = fs.existsSync(venvPython) ? venvPython : fallbackPython;

    console.log(`[Backend] Starting Python companion with: ${pythonBin}`);

    pythonProcess = spawn(pythonBin, ['run_companion.py'], {
        cwd: projectRoot,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
    });

    if (pythonProcess.stdout) {
        pythonProcess.stdout.on('data', (data) => {
            const msg = data.toString().trim();
            if (msg) {
                console.log(`[Companion] ${msg}`);
                if (mainWindow) {
                    mainWindow.webContents.send('backend-log', msg);
                }
            }
        });
    }

    if (pythonProcess.stderr) {
        pythonProcess.stderr.on('data', (data) => {
            const msg = data.toString().trim();
            if (msg) {
                console.error(`[Companion Err] ${msg}`);
            }
        });
    }

    pythonProcess.on('close', (code) => {
        console.log(`[Backend] Python companion exited with code ${code}`);
        pythonProcess = null;
    });

    pythonProcess.on('error', (err) => {
        console.error(`[Backend] Failed to start Python companion:`, err.message);
        pythonProcess = null;
    });
}

/**
 * Set up IPC handlers.
 */
function setupIPC() {
    ipcMain.handle('submit-goal', async (_event, goal) => {
        console.log(`[IPC] Goal: ${goal}`);
        return { accepted: true };
    });

    ipcMain.handle('get-status', async () => {
        return {
            status: 'ready',
            backendRunning: pythonProcess !== null,
        };
    });

    ipcMain.handle('confirm-action', async (_event, actionId, approved) => {
        console.log(`[IPC] Action ${actionId}: ${approved ? 'approved' : 'denied'}`);
        return { acknowledged: true };
    });

    ipcMain.handle('restart-backend', async () => {
        if (pythonProcess) {
            pythonProcess.kill();
            pythonProcess = null;
        }
        startPythonBackend();
        return { restarted: true };
    });
}

/**
 * Grant microphone permission automatically (needed for Web Speech API).
 */
function setupPermissions() {
    session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
        const allowedPermissions = ['media', 'microphone', 'audioCapture'];
        if (allowedPermissions.includes(permission)) {
            callback(true);
        } else {
            callback(false);
        }
    });

    // Also handle permission checks
    session.defaultSession.setPermissionCheckHandler((webContents, permission) => {
        const allowedPermissions = ['media', 'microphone', 'audioCapture'];
        return allowedPermissions.includes(permission);
    });
}

// ─── App Lifecycle ──────────────────────────────

app.whenReady().then(() => {
    setupPermissions();
    createMainWindow();
    setupIPC();
    startPythonBackend();
    console.log('OmniCompanion v2 ready');
});

app.on('window-all-closed', () => {
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
    }
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createMainWindow();
    }
});

app.on('before-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
    }
});
