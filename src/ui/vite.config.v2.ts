/**
 * OmniCompanion v2 — Vite Configuration
 *
 * Uses the new index_v2.html entry point for the
 * voice-first multimodal UI.
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
    plugins: [react()],
    base: './',
    build: {
        outDir: 'dist',
        rollupOptions: {
            input: path.resolve(__dirname, 'index_v2.html'),
        },
    },
    server: {
        port: 5173,
        // Don't auto-open browser — Electron loads this URL directly
    },
});
