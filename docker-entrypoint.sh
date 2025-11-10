#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "  SoulSpot Bridge - Docker Container Startup"
echo "================================================"

# Set default values
PUID=${PUID:-1000}
PGID=${PGID:-1000}
UMASK=${UMASK:-002}
TZ=${TZ:-UTC}

echo "Configuration:"
echo "  PUID: $PUID"
echo "  PGID: $PGID"
echo "  UMASK: $UMASK"
echo "  TZ: $TZ"
echo ""

# Set timezone
if [ ! -z "$TZ" ]; then
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
    echo -e "${GREEN}✓${NC} Timezone set to: $TZ"
fi

# Set umask
umask $UMASK
echo -e "${GREEN}✓${NC} Umask set to: $UMASK"

# Update user and group IDs if they differ from defaults
if [ "$PUID" != "1000" ] || [ "$PGID" != "1000" ]; then
    echo ""
    echo "Updating user and group IDs..."
    
    # Update group ID
    groupmod -o -g "$PGID" soulspot
    echo -e "${GREEN}✓${NC} Group ID updated to: $PGID"
    
    # Update user ID
    usermod -o -u "$PUID" soulspot
    echo -e "${GREEN}✓${NC} User ID updated to: $PUID"
fi

echo ""
echo "Validating directory structure..."

# Validate that /downloads exists (must be provided as bind mount)
if [ ! -d "/downloads" ]; then
    echo -e "${RED}✗ ERROR: /downloads directory does not exist!${NC}"
    echo "  The /downloads directory must be mounted from the host."
    echo "  Please ensure the bind mount './mnt/downloads:/downloads' is configured"
    echo "  and that the directory exists on the host system."
    exit 1
fi
echo -e "${GREEN}✓${NC} /downloads directory exists"

# Validate that /music exists (must be provided as bind mount)
if [ ! -d "/music" ]; then
    echo -e "${RED}✗ ERROR: /music directory does not exist!${NC}"
    echo "  The /music directory must be mounted from the host."
    echo "  Please ensure the bind mount './mnt/music:/music' is configured"
    echo "  and that the directory exists on the host system."
    exit 1
fi
echo -e "${GREEN}✓${NC} /music directory exists"

# Auto-create /config directory if it doesn't exist
if [ ! -d "/config" ]; then
    echo -e "${YELLOW}!${NC} /config directory does not exist, creating..."
    mkdir -p /config
    echo -e "${GREEN}✓${NC} /config directory created"
else
    echo -e "${GREEN}✓${NC} /config directory exists"
fi

# Set ownership of /config directory to the configured PUID/PGID
echo ""
echo "Setting file permissions..."
chown -R $PUID:$PGID /config
echo -e "${GREEN}✓${NC} /config ownership set to $PUID:$PGID"

# Set ownership of app directory
chown -R $PUID:$PGID /app
echo -e "${GREEN}✓${NC} /app ownership set to $PUID:$PGID"

# Verify required environment variables for Spotify and slskd
echo ""
echo "Validating configuration..."

MISSING_VARS=()

if [ -z "$SPOTIFY_CLIENT_ID" ]; then
    MISSING_VARS+=("SPOTIFY_CLIENT_ID")
fi

if [ -z "$SPOTIFY_CLIENT_SECRET" ]; then
    MISSING_VARS+=("SPOTIFY_CLIENT_SECRET")
fi

if [ -z "$SLSKD_BASE_URL" ] && [ -z "$SLSKD_URL" ]; then
    MISSING_VARS+=("SLSKD_BASE_URL or SLSKD_URL")
fi

if [ -z "$SLSKD_API_KEY" ] && [ -z "$SLSKD_PASSWORD" ]; then
    MISSING_VARS+=("SLSKD_API_KEY or SLSKD_PASSWORD")
fi

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo -e "${YELLOW}!${NC} Warning: The following environment variables are not set:"
    for var in "${MISSING_VARS[@]}"; do
        echo "    - $var"
    done
    echo "  The application may not function correctly without these variables."
    echo ""
fi

# Update DATABASE_URL to use /config directory
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///config/soulspot.db}"
echo -e "${GREEN}✓${NC} Database: $DATABASE_URL"

# Update storage paths to use container paths
export STORAGE__DOWNLOAD_PATH="${STORAGE__DOWNLOAD_PATH:-/downloads}"
export STORAGE__MUSIC_PATH="${STORAGE__MUSIC_PATH:-/music}"
export STORAGE__ARTWORK_PATH="${STORAGE__ARTWORK_PATH:-/config/artwork}"
export STORAGE__TEMP_PATH="${STORAGE__TEMP_PATH:-/config/tmp}"

# Ensure additional config directories exist
mkdir -p /config/artwork /config/tmp
chown -R $PUID:$PGID /config/artwork /config/tmp

echo ""
echo "================================================"
echo "  Starting SoulSpot Bridge Application"
echo "================================================"
echo ""

# Switch to app user and execute command
exec gosu $PUID:$PGID "$@"
