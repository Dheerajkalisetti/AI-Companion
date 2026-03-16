#!/bin/bash
# ═══════════════════════════════════════════════════
# OmniCompanion v2 — Native Desktop App Launcher
# ═══════════════════════════════════════════════════
# Starts the Vite dev server, then launches Electron.
# The Electron app auto-starts the Python companion backend.
#
# Usage:
#   chmod +x start_v2.sh
#   ./start_v2.sh
# ═══════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  🤖 OmniCompanion v2 — Native Desktop App"
echo "═══════════════════════════════════════════════════"
echo ""

# ─── Check Python venv ────────────────────────────
if [ ! -d ".venv" ]; then
    echo "⚠️  No .venv found. Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate 2>/dev/null || true

# ─── Install Python deps if needed ────────────────
echo "📦 Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt >/dev/null 2>&1 || pip3 install -r requirements.txt >/dev/null 2>&1

# ─── Check for GEMINI_API_KEY ─────────────────────
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ GEMINI_API_KEY not set. Add it to .env file."
    exit 1
fi

# ─── Check UI node_modules ───────────────────────
if [ ! -d "src/ui/node_modules" ]; then
    echo "📦 Installing UI dependencies..."
    cd src/ui && npm install && cd ../..
fi

echo ""
echo "🚀 Starting OmniCompanion v2..."
echo ""

# ─── Start Vite dev server in background ──────────
echo "  📡 Starting UI dev server..."
cd src/ui
npx vite --config vite.config.v2.ts &
VITE_PID=$!
cd ../..

# Wait for Vite to be ready
echo "  ⏳ Waiting for Vite dev server..."
for i in $(seq 1 20); do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo "  ✅ Vite dev server ready"
        break
    fi
    sleep 0.5
done

# ─── Launch Electron ──────────────────────────────
echo "  🖥️  Launching Electron app..."
echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ OmniCompanion v2 launching!"
echo "  🎤 Voice mode is default — just start talking"
echo "  💬 Chat available via button in bottom-right"
echo "  Press Ctrl+C to stop all services"
echo "═══════════════════════════════════════════════════"
echo ""

cd src/ui
NODE_ENV=development npx electron ./electron/main_v2.js
ELECTRON_EXIT=$?
cd ../..

# ─── Cleanup ──────────────────────────────────────
echo ""
echo "  🛑 Shutting down..."
kill $VITE_PID 2>/dev/null
wait $VITE_PID 2>/dev/null

echo "  👋 OmniCompanion v2 stopped."
exit $ELECTRON_EXIT
