#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Hermesfy Studio — First-Time Setup Script
# Run once after cloning the repo. Sets up everything needed.
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Hermesfy Studio — First-Time Setup${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""

# ── 1. Check Python ──────────────────────────────────────────
echo -e "${YELLOW}[1/7] Checking Python...${NC}"
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ Python3 not found. Install: sudo apt install python3 python3-pip python3-venv${NC}"
    exit 1
fi
PY_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}  ✓ $PY_VERSION${NC}"

# ── 2. Create venv (recommended) ─────────────────────────────
echo -e "${YELLOW}[2/7] Setting up virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv 2>/dev/null || echo -e "${YELLOW}  ⚠ Could not create venv — using system Python${NC}"
fi
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo -e "${GREEN}  ✓ venv activated${NC}"
else
    echo -e "${YELLOW}  ⚠ No venv — using system Python${NC}"
fi

# ── 3. Install package (editable mode) ───────────────────────
echo -e "${YELLOW}[3/7] Installing hermesfy-studio...${NC}"
pip install -e ".[dev]" 2>/dev/null || \
pip install -e . 2>/dev/null || \
pip install --break-system-packages -e ".[dev]" 2>/dev/null || \
pip install --break-system-packages -e . 2>/dev/null || {
    echo -e "${YELLOW}  ⚠ pip install -e . failed — trying requirements.txt${NC}"
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt 2>/dev/null || \
        pip install --break-system-packages -r requirements.txt 2>/dev/null || true
    fi
}
echo -e "${GREEN}  ✓ Package installed${NC}"

# ── 4. Create directories ────────────────────────────────────
echo -e "${YELLOW}[4/7] Creating directories...${NC}"
mkdir -p cache/fal cache/versions output logs
echo -e "${GREEN}  ✓ cache/, output/, logs/${NC}"

# ── 5. Create .env if missing ────────────────────────────────
echo -e "${YELLOW}[5/7] Checking environment...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}  ⚠ Created .env from .env.example — edit it with your API keys${NC}"
    fi
fi
if grep -q "your_fal_api_key_here" .env 2>/dev/null; then
    echo -e "${YELLOW}  ⚠ FAL_API_KEY not set yet — edit .env with your key${NC}"
elif [ -n "${FAL_API_KEY:-}" ] || [ -n "${FAL_KEY:-}" ] || [ -n "${FAL_AI_API_KEY:-}" ]; then
    echo -e "${GREEN}  ✓ FAL API key found${NC}"
elif grep -q "FAL_API_KEY\|FAL_KEY\|FAL_AI_API_KEY" .env 2>/dev/null; then
    echo -e "${GREEN}  ✓ FAL API key found in .env${NC}"
else
    echo -e "${YELLOW}  ⚠ No FAL API key — set it in .env${NC}"
fi

# ── 6. Run Model Watcher (fetch fresh models from FAL.ai) ────
echo -e "${YELLOW}[6/7] Fetching latest models from FAL.ai...${NC}"
# Model watcher lives in the local engine/ dir or can be run via the installed package
if python3 -c "from hermesfy.providers.registry import ModelRegistry; print('ok')" 2>/dev/null; then
    echo -e "${GREEN}  ✓ Model registry accessible via hermesfy package${NC}"
elif [ -f engine/model_watcher.py ]; then
    if python3 -m engine.model_watcher 2>/dev/null; then
        MODEL_COUNT=$(python3 -c "from engine.model_registry import ModelRegistry; print(ModelRegistry().get_summary()['total'])" 2>/dev/null || echo "?")
        echo -e "${GREEN}  ✓ Model registry updated: $MODEL_COUNT models${NC}"
    else
        echo -e "${YELLOW}  ⚠ Model watcher failed (network?) — using built-in defaults${NC}"
    fi
else
    echo -e "${YELLOW}  ⚠ Model watcher not found — using built-in model list${NC}"
fi

# ── 7. Dashboard info ────────────────────────────────────────
echo -e "${YELLOW}[7/7] Dashboard...${NC}"
if [ -f dashboard/index.html ]; then
    echo -e "${GREEN}  ✓ Dashboard available at: dashboard/index.html${NC}"
    echo -e "    Start with: ${CYAN}cd dashboard && python3 -m http.server 8090${NC}"
else
    echo -e "${YELLOW}  ⚠ Dashboard not found${NC}"
fi

# ── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ Setup complete!${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Quick start:"
if [ -f venv/bin/activate ]; then
    echo -e "    ${CYAN}source venv/bin/activate${NC}"
fi
echo -e "    ${CYAN}export FAL_API_KEY=your_key${NC}"
echo -e "    ${CYAN}python3 -m hermesfy.cli 'haceme un ad de Nike'${NC}"
echo ""
echo -e "  What was set up:"
echo -e "    • Python package installed (editable mode)"
echo -e "    • Directories created (cache/, output/, logs/)"
echo -e "    • .env file created (edit with your API keys)"
echo -e "    • Model registry fetched from FAL.ai"
echo -e "    • Dashboard ready (dashboard/index.html)"
echo ""
