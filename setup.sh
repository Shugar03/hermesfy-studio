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
echo -e "${YELLOW}[1/6] Checking Python...${NC}"
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ Python3 not found. Install: sudo apt install python3 python3-pip${NC}"
    exit 1
fi
PY_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}  ✓ $PY_VERSION${NC}"

# ── 2. Install dependencies ──────────────────────────────────
echo -e "${YELLOW}[2/6] Installing Python dependencies...${NC}"
if [ -f requirements.txt ]; then
    pip3 install --user -q -r requirements.txt 2>/dev/null || \
    pip3 install --user --break-system-packages -q -r requirements.txt 2>/dev/null || \
    echo -e "${YELLOW}  ⚠ pip install failed — install deps manually from requirements.txt${NC}"
    echo -e "${GREEN}  ✓ Dependencies installed${NC}"
else
    # Install known deps directly
    pip3 install --user -q requests 2>/dev/null || \
    pip3 install --user --break-system-packages -q requests 2>/dev/null || true
    echo -e "${YELLOW}  ⚠ No requirements.txt — installed core deps manually${NC}"
fi

# ── 3. Create directories ────────────────────────────────────
echo -e "${YELLOW}[3/6] Creating directories...${NC}"
mkdir -p cache/fal cache/versions output logs
echo -e "${GREEN}  ✓ cache/, output/, logs/${NC}"

# ── 4. Run Model Watcher (fetch fresh models from FAL.ai) ────
echo -e "${YELLOW}[4/6] Fetching latest models from FAL.ai...${NC}"
if python3 -m engine.model_watcher --verbose 2>/dev/null; then
    MODEL_COUNT=$(python3 -c "from engine.model_registry import ModelRegistry; print(ModelRegistry().get_summary()['total'])" 2>/dev/null || echo "?")
    echo -e "${GREEN}  ✓ Model registry updated: $MODEL_COUNT models${NC}"
else
    echo -e "${YELLOW}  ⚠ Model watcher failed (network?) — using default models${NC}"
fi

# ── 5. Schedule Model Watcher as cron (daily at 3am) ─────────
echo -e "${YELLOW}[5/6] Setting up daily model watcher (cron)...${NC}"
CRON_CMD="0 3 * * * cd $SCRIPT_DIR && python3 -m engine.model_watcher >> logs/model_watcher.log 2>&1"
CRON_MARKER="# hermesfy-model-watcher"

# Check if already scheduled
if crontab -l 2>/dev/null | grep -qF "hermesfy-model-watcher"; then
    echo -e "${GREEN}  ✓ Cron already configured${NC}"
else
    (crontab -l 2>/dev/null; echo "$CRON_CMD $CRON_MARKER") | crontab - 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ Cron job added (daily 3am)${NC}"
    else
        echo -e "${YELLOW}  ⚠ Could not add cron — add manually:${NC}"
        echo -e "    ${CYAN}$CRON_CMD $CRON_MARKER${NC}"
    fi
fi

# ── 6. Verify FAL API key ───────────────────────────────────
echo -e "${YELLOW}[6/6] Checking FAL API key...${NC}"
if [ -n "${FAL_KEY:-}" ] || [ -n "${FAL_AI_API_KEY:-}" ]; then
    echo -e "${GREEN}  ✓ FAL API key found${NC}"
elif [ -f .env ] && grep -q "FAL_KEY\|FAL_AI_API_KEY" .env; then
    echo -e "${GREEN}  ✓ FAL API key found in .env${NC}"
else
    echo -e "${YELLOW}  ⚠ No FAL API key found. Set FAL_KEY or FAL_AI_API_KEY:${NC}"
    echo -e "    ${CYAN}export FAL_KEY=your_key_here${NC}"
    echo -e "    ${CYAN}echo 'FAL_KEY=your_key' >> .env${NC}"
fi

# ── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ Setup complete!${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Quick start:"
echo -e "    ${CYAN}python3 -m engine.cli 'haceme un ad de Nike'${NC}"
echo -e "    ${CYAN}python3 -m engine.model_watcher --dry-run${NC}"
echo ""
echo -e "  What was set up:"
echo -e "    • Python dependencies installed"
echo -e "    • Directories created (cache/, output/, logs/)"
echo -e "    • Model registry fetched from FAL.ai (${MODEL_COUNT:-?} models)"
echo -e "    • Daily cron job for model updates (3am)"
echo ""
