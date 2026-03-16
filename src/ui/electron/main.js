/**
 * OmniCompanion — Electron Main Process
 *
 * Creates the PiP overlay window and manages IPC bridge.
 */

const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');

let mainWindow = null;

function createPiPWindow() {
    const display = screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight } = display.workAreaSize;

    const pipWidth = 380;
    const pipHeight = 520;

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

    // Load the built React app
    const distPath = path.join(__dirname, '../dist/index.html');
    mainWindow.loadFile(distPath).catch((err) => {
        console.error('Failed to load app. Run "npm run build" first.', err);
        mainWindow.loadURL(`data:text/html,
      <html><body style="background:#1a1a2e;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh">
        <div style="text-align:center">
          <h2>🤖 OmniCompanion</h2>
          <p>Run <code>npm run build</code> first, then <code>npm run electron:dev</code></p>
        </div>
      </body></html>
    `);
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function setupIPC() {
    ipcMain.handle('submit-goal', async (_event, goal) => {
        console.log(`[IPC] Goal received: ${goal}`);
        return { accepted: true };
    });

    ipcMain.handle('get-status', async () => {
        return { status: 'ready' };
    });

    ipcMain.handle('confirm-action', async (_event, actionId, approved) => {
        console.log(`[IPC] Action ${actionId}: ${approved ? 'approved' : 'denied'}`);
        return { acknowledged: true };
    });
}

app.whenReady().then(() => {
    createPiPWindow();
    setupIPC();
    console.log('OmniCompanion UI ready');
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createPiPWindow();
    }
});
