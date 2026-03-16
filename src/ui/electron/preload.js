/**
 * OmniCompanion — Electron Preload Script
 * Exposes safe IPC methods to the renderer.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('omni', {
    submitGoal: (goal) => ipcRenderer.invoke('submit-goal', goal),
    getStatus: () => ipcRenderer.invoke('get-status'),
    confirmAction: (actionId, approved) =>
        ipcRenderer.invoke('confirm-action', actionId, approved),
    onBackendLog: (callback) =>
        ipcRenderer.on('backend-log', (_event, msg) => callback(msg)),
});
