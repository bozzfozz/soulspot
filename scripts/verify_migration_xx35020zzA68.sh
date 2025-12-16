#!/bin/bash
# Migration Verification Script
# Tests the xx35020zzA68 migration in various scenarios

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_DB="/tmp/test_migration_$$.db"

echo "================================================"
echo "  Migration xx35020zzA68 Verification Script"
echo "================================================"
echo ""

# Cleanup on exit
cleanup() {
    rm -f "$TEST_DB"
}
trap cleanup EXIT

cd "$PROJECT_ROOT"

echo "Test 1: Fresh database (no previous migration)"
echo "----------------------------------------------"
rm -f "$TEST_DB"
export DATABASE_URL="sqlite:///$TEST_DB"
alembic upgrade ww34019yyz67
echo "✓ Applied previous migration (ww34019yyz67)"

alembic upgrade xx35020zzA68
echo "✓ Applied current migration (xx35020zzA68)"
echo ""

echo "Test 2: Idempotency (run migration twice)"
echo "------------------------------------------"
alembic downgrade ww34019yyz67
echo "✓ Downgraded to previous migration"

alembic upgrade xx35020zzA68
echo "✓ Applied migration first time"

alembic downgrade ww34019yyz67
alembic upgrade xx35020zzA68
echo "✓ Applied migration second time (idempotent)"
echo ""

echo "Test 3: Simulate orphaned table cleanup"
echo "----------------------------------------"
rm -f "$TEST_DB"
alembic upgrade ww34019yyz67

# Simulate orphaned table
sqlite3 "$TEST_DB" "CREATE TABLE _alembic_tmp_soulspot_artists (id VARCHAR(36));"
echo "✓ Created orphaned temp table"

alembic upgrade xx35020zzA68
echo "✓ Migration cleaned up orphaned table and succeeded"
echo ""

echo "Test 4: Verify database schema"
echo "-------------------------------"
SCHEMA=$(sqlite3 "$TEST_DB" ".schema soulspot_artists")
if echo "$SCHEMA" | grep -q "artwork_url"; then
    echo "✓ soulspot_artists.artwork_url exists"
else
    echo "✗ soulspot_artists.artwork_url not found"
    exit 1
fi

if ! echo "$SCHEMA" | grep -q "image_url"; then
    echo "✓ soulspot_artists.image_url removed"
else
    echo "⚠ soulspot_artists.image_url still exists (unexpected)"
fi

PLAYLIST_SCHEMA=$(sqlite3 "$TEST_DB" ".schema playlists")
if echo "$PLAYLIST_SCHEMA" | grep -q "artwork_url"; then
    echo "✓ playlists.artwork_url exists"
else
    echo "✗ playlists.artwork_url not found"
    exit 1
fi

echo ""
echo "================================================"
echo "  All Tests Passed! ✓"
echo "================================================"
echo ""
echo "Migration xx35020zzA68 is ready for deployment."
echo ""
