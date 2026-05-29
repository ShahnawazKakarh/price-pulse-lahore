#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Price Pulse Lahore — Project Setup
# QA Pulse by SK · skakarh.com
# ─────────────────────────────────────────────────────────────────────────────
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Price Pulse Lahore — Setup${NC}"
echo -e "${BLUE}  QA Pulse by SK · skakarh.com${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── Step 1: Python version check ──────────────────────────────────────────────
echo -e "${BLUE}[1/5] Checking Python version...${NC}"
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
  echo -e "${RED}✗ Python not found. Install Python 3.11+ from python.org${NC}"
  exit 1
fi

PYTHON_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MINOR" -lt 11 ]; then
  echo -e "${RED}✗ Python 3.11+ required. Found: $PYTHON_VERSION${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# ── Step 2: Virtual environment ───────────────────────────────────────────────
echo ""
echo -e "${BLUE}[2/5] Setting up virtual environment...${NC}"
if [ -d "venv" ]; then
  echo -e "${YELLOW}  venv already exists — skipping${NC}"
else
  $PYTHON -m venv venv
  echo -e "${GREEN}✓ Virtual environment created${NC}"
fi
source venv/bin/activate
echo -e "${GREEN}✓ venv activated${NC}"

# ── Step 3: Install dependencies ─────────────────────────────────────────────
echo ""
echo -e "${BLUE}[3/5] Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Dependencies installed${NC}"

# ── Step 4: Environment file ──────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[4/5] Setting up .env...${NC}"
if [ -f ".env" ]; then
  echo -e "${YELLOW}  .env already exists — skipping${NC}"
else
  cp .env.example .env
  echo -e "${GREEN}✓ .env created from .env.example${NC}"
fi

# ── Step 5: Data directories ──────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[5/5] Creating data directories...${NC}"
mkdir -p data/images data/daily
echo -e "${GREEN}✓ data/images and data/daily ready${NC}"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo ""
echo -e "  1. Open ${YELLOW}.env${NC} and add your keys:"
echo ""
echo -e "     ${YELLOW}GEMINI_API_KEY${NC}  → aistudio.google.com → Get API Key"
echo -e "                     Key format: ${GREEN}AQ.Ab8RN6...${NC} (new Google format)"
echo -e "                     Model used: ${GREEN}gemini-1.5-flash${NC} (free, 1500 req/day)"
echo -e "                     Key stays local — ${RED}never committed to GitHub${NC}"
echo ""
echo -e "     ${YELLOW}TELEGRAM_BOT_TOKEN${NC} → talk to @BotFather on Telegram"
echo -e "     ${YELLOW}TELEGRAM_CHAT_ID${NC}   → get from @userinfobot on Telegram"
echo -e "                     Both optional — alerts just skip if not set"
echo ""
echo -e "  2. Activate venv in every new terminal:"
echo -e "     ${GREEN}source venv/bin/activate${NC}"
echo ""
echo -e "  3. Run the full pipeline:"
echo -e "     ${GREEN}python scraper/pipeline.py${NC}"
echo ""
echo -e "  4. Test Telegram alerts:"
echo -e "     ${GREEN}python alerts/telegram.py${NC}"
echo ""
echo -e "  5. Test OCR on a local image:"
echo -e "     ${GREEN}python scraper/ocr.py path/to/image.jpg vegetables${NC}"
echo ""
