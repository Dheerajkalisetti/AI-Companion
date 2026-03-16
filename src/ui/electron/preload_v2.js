/**
 * OmniCompanion v2 — Electron Preload Script
 * Exposes safe IPC methods and system info to the renderer.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('omni', {
    // Legacy IPC
    submitGoal: (goal) => ipcRenderer.invoke('submit-goal', goal),
    getStatus: () => ipcRenderer.invoke('get-status'),
    confirmAction: (actionId, approved) =>
        ipcRenderer.invoke('confirm-action', actionId, approved),

    // v2 additions
    restartBackend: () => ipcRenderer.invoke('restart-backend'),
    onBackendLog: (callback) =>
        ipcRenderer.on('backend-log', (_event, msg) => callback(msg)),

    // System info
    platform: process.platform,
    isElectron: true,
});
