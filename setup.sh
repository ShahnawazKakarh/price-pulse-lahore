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
echo -e "${BLUE}[1/6] Checking Python version...${NC}"
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
echo -e "${BLUE}[2/6] Setting up virtual environment...${NC}"
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
echo -e "${BLUE}[3/6] Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Dependencies installed${NC}"

# ── Step 4: Environment file ──────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[4/6] Setting up .env...${NC}"
if [ -f ".env" ]; then
  echo -e "${YELLOW}  .env already exists — skipping${NC}"
else
  cp .env.example .env
  echo -e "${GREEN}✓ .env created from .env.example${NC}"
fi

# ── Step 5: Data directories ──────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[5/6] Creating data directories...${NC}"
mkdir -p data/images data/daily
echo -e "${GREEN}✓ data/images and data/daily ready${NC}"

# ── Step 6: Database check ────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[6/6] Checking database...${NC}"
if python3 -c "from db.database import check_connection; exit(0 if check_connection() else 1)" 2>/dev/null; then
  echo -e "${GREEN}✓ Database connected${NC}"
  echo -e "  Running migrations..."
  python3 -c "from db.database import init_db; init_db()" 2>/dev/null && echo -e "${GREEN}✓ Database initialised${NC}"
else
  echo -e "${YELLOW}  Database not reachable — pipeline will use JSON fallback${NC}"
  echo -e "  Set DATABASE_URL in .env to enable full DB support"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${YELLOW}Keys needed in .env:${NC}"
echo ""
echo -e "  ${YELLOW}GEMINI_API_KEY${NC}      → aistudio.google.com → Get API Key (free)"
echo -e "  ${YELLOW}DATABASE_URL${NC}        → PostgreSQL connection string"
echo -e "  ${YELLOW}TELEGRAM_BOT_TOKEN${NC}  → @BotFather on Telegram (optional)"
echo -e "  ${YELLOW}TELEGRAM_CHAT_ID${NC}    → @userinfobot on Telegram (optional)"
echo ""
echo -e "  ${YELLOW}Commands:${NC}"
echo ""
echo -e "  Activate venv:       ${GREEN}source venv/bin/activate${NC}"
echo -e "  Run pipeline:        ${GREEN}python scraper/pipeline.py${NC}"
echo -e "  Init DB manually:    ${GREEN}python db/database.py${NC}"
echo -e "  Test OCR on image:   ${GREEN}python scraper/ocr.py path/to/image.jpg vegetables${NC}"
echo -e "  Test alerts:         ${GREEN}python alerts/telegram.py${NC}"
echo ""
