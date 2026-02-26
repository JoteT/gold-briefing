#!/bin/bash
# setup_browser.sh — Install Playwright browser automation for AGI
# Run this once from your Terminal:  bash setup_browser.sh

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Africa Gold Intelligence — Browser Automation Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 1: Install Playwright Python package
echo "Step 1/2: Installing Playwright..."
pip install playwright --break-system-packages
if [ $? -ne 0 ]; then
  echo ""
  echo "pip failed — trying pip3..."
  pip3 install playwright --break-system-packages
fi

echo ""

# Step 2: Download Chromium browser
echo "Step 2/2: Downloading Chromium (~180MB, one-time download)..."
playwright install chromium
if [ $? -ne 0 ]; then
  echo ""
  echo "Trying with python3 -m playwright..."
  python3 -m playwright install chromium
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Open your .env file and fill in:"
echo "       BEEHIIV_EMAIL=your@email.com"
echo "       BEEHIIV_PASSWORD=your_beehiiv_password"
echo ""
echo "  2. Test the connection:"
echo "       python3 beehiiv_browser.py --test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
