#!/bin/bash
# Quick Testing Script for SoulSpot UI Enhancements
# Run this after deploying Phase 1 & 2 features
#
# ⚠️ DEPRECATED - ONE-TIME CHECKLIST: This script was used for manual UI testing after
# Phase 1 & 2 deployment (Nov 2025). All features tested and deployed.
#
# Historical manual testing checklist. For current testing, use pytest (tests/integration/).

set -e

echo "🚀 SoulSpot UI Testing - Quick Start"
echo "===================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}1. Starting Development Server...${NC}"
cd "$(dirname "$0")/.."

# Check if poetry is available
if command -v poetry &> /dev/null; then
    echo "Using Poetry..."
    poetry run uvicorn soulspot.main:app --reload --host 0.0.0.0 --port 8000 &
elif command -v python3 &> /dev/null; then
    echo "Using Python3..."
    python3 -m uvicorn soulspot.main:app --reload --host 0.0.0.0 --port 8000 &
else
    echo "ERROR: Neither poetry nor python3 found"
    exit 1
fi

SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for server to start
echo "Waiting for server to be ready..."
sleep 5

# Check if server is responding
if curl -s http://localhost:8000 > /dev/null; then
    echo -e "${GREEN}✅ Server is running!${NC}"
else
    echo "ERROR: Server failed to start"
    kill $SERVER_PID
    exit 1
fi

echo ""
echo "🧪 Testing Checklist"
echo "==================="
echo ""

echo "📱 Open these URLs in your browser:"
echo ""
echo "1. UI Demo Page (all features):"
echo "   http://localhost:8000/ui-demo"
echo ""
echo "2. Downloads Page (filtering):"
echo "   http://localhost:8000/downloads"
echo ""
echo "3. Playlists Page (lazy loading):"
echo "   http://localhost:8000/playlists"
echo ""

echo "🔍 Manual Tests to Perform:"
echo ""
echo "Phase 1 - Quick Wins:"
echo "  [ ] Ripple effects on button clicks"
echo "  [ ] Circular progress indicators on downloads"
echo "  [ ] Keyboard navigation (Tab, Enter, Esc)"
echo "  [ ] Lazy image loading (scroll playlists)"
echo "  [ ] Stagger animations on page load"
echo "  [ ] Skip to content link (Tab on first load)"
echo ""
echo "Phase 2 - Advanced Features:"
echo "  [ ] Fuzzy search (try typos like 'bettls' for 'Beatles')"
echo "  [ ] Download filters (status, priority, progress)"
echo "  [ ] Native notifications (check browser permission)"
echo "  [ ] PWA install (mobile browsers or Chrome desktop)"
echo "  [ ] Service worker (offline mode - disconnect network)"
echo "  [ ] Mobile gestures (swipe on touch device)"
echo ""

echo "🔧 Browser DevTools Checks:"
echo ""
echo "1. Console (F12 → Console):"
echo "   [ ] No JavaScript errors"
echo "   [ ] Service worker registered message"
echo ""
echo "2. Network Tab (F12 → Network):"
echo "   [ ] Static assets cached (second page load)"
echo "   [ ] SSE connection established"
echo ""
echo "3. Application Tab (F12 → Application):"
echo "   [ ] Service Worker: Activated and running"
echo "   [ ] Manifest: Valid with no warnings"
echo "   [ ] Cache Storage: Static assets present"
echo ""
echo "4. Lighthouse (F12 → Lighthouse):"
echo "   [ ] PWA score: 90+ recommended"
echo "   [ ] Installability: Pass"
echo ""

echo "📊 Performance Checks:"
echo ""
echo "  [ ] Fuzzy search responds in <300ms (large playlist)"
echo "  [ ] Filter apply <100ms (500+ downloads)"
echo "  [ ] Page load <2s (desktop, good 3G)"
echo "  [ ] Service worker cache hit <50ms"
echo ""

echo "🌐 Browser Compatibility:"
echo ""
echo "  [ ] Chrome 90+ (desktop & mobile)"
echo "  [ ] Firefox 88+ (desktop & Android)"
echo "  [ ] Safari 14+ (iOS 14+)"
echo "  [ ] Edge 90+"
echo ""

echo "📱 PWA Installation Test:"
echo ""
echo "Android Chrome:"
echo "  1. Open http://localhost:8000 on mobile"
echo "  2. Wait for 'Add to Home Screen' banner"
echo "  3. Tap 'Install'"
echo "  4. Verify icon on home screen"
echo "  5. Open app from home screen"
echo "  6. Check for standalone display (no browser UI)"
echo ""
echo "iOS Safari:"
echo "  1. Open http://localhost:8000 on iPhone/iPad"
echo "  2. Tap Share button"
echo "  3. Select 'Add to Home Screen'"
echo "  4. Tap 'Add'"
echo "  5. Open app from home screen"
echo ""
echo "Desktop Chrome:"
echo "  1. Look for install icon in address bar (⊕)"
echo "  2. Click 'Install'"
echo "  3. App opens in standalone window"
echo ""

echo "🔔 Notification Test:"
echo ""
echo "  1. Allow notifications when prompted"
echo "  2. Complete a download (or simulate SSE event)"
echo "  3. Check native notification appears"
echo "  4. Click notification → should navigate to /downloads"
echo ""

echo "📴 Offline Mode Test:"
echo ""
echo "  1. Visit http://localhost:8000 (ensure cached)"
echo "  2. Open DevTools → Network tab"
echo "  3. Toggle 'Offline' checkbox"
echo "  4. Reload page"
echo "  5. Verify offline.html displays"
echo "  6. Click 'Retry Connection' button"
echo ""

echo "🎨 Visual Regression (Manual):"
echo ""
echo "  [ ] Glassmorphism effects render correctly"
echo "  [ ] Animations are smooth (60fps)"
echo "  [ ] No layout shift on load"
echo "  [ ] Responsive design (320px - 1920px)"
echo ""

echo ""
echo -e "${GREEN}🎉 Ready for Testing!${NC}"
echo ""
echo "Press Ctrl+C to stop the server when done."
echo "Server PID: $SERVER_PID"
echo ""

# Keep script running
wait $SERVER_PID
