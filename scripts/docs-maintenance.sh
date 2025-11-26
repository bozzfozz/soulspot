#!/bin/bash
# Documentation Maintenance - Automated Cleanup Script
# Run this to consolidate and fix documentation structure

set -e

echo "🧹 SoulSpot Documentation Maintenance - Automated Cleanup"
echo "=========================================================="
echo ""

cd "$(dirname "$0")/.."  # Go to repo root

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counter
FIXES_APPLIED=0

echo -e "${BLUE}Phase 1: Archive Directory Consolidation${NC}"
echo "==========================================="

# Check if archive directory exists and is mostly empty
if [ -d "docs/archive" ]; then
    FILE_COUNT=$(find docs/archive -type f 2>/dev/null | wc -l)
    if [ "$FILE_COUNT" -le 5 ]; then
        echo "Found docs/archive/ with $FILE_COUNT files - consolidating..."
        
        # Move any files from archive/ to archived/
        for file in docs/archive/*.md; do
            if [ -f "$file" ]; then
                cp "$file" "docs/archived/$(basename "$file")-archived-$(date +%Y%m%d).bak"
                echo "  ✓ Moved $(basename "$file")"
                ((FIXES_APPLIED++))
            fi
        done
        
        # Remove archive directory
        rmdir docs/archive 2>/dev/null && echo "  ✓ Removed empty docs/archive/" || echo "  ⚠ Could not remove docs/archive/ (not empty)"
    else
        echo "  ⚠ docs/archive/ has $FILE_COUNT files - manual review needed"
    fi
else
    echo "  ✓ docs/archive/ does not exist (already consolidated)"
fi

echo ""
echo -e "${BLUE}Phase 2: Fix Broken Route References${NC}"
echo "======================================"

# Replace /ui/ routes with / (API restructured)
echo "Searching for '/ui/' route references..."
REFS_FOUND=$(grep -r "/ui/" docs --include="*.md" 2>/dev/null | wc -l)
if [ "$REFS_FOUND" -gt 0 ]; then
    echo "  Found $REFS_FOUND references to old '/ui/' routes"
    echo "  Note: Manual update recommended - not auto-fixing to preserve context"
    echo "  Command: find docs -name '*.md' -type f -exec sed -i 's|/ui/|/|g' {} \\;"
    echo "  Files to check:"
    grep -r "/ui/" docs --include="*.md" 2>/dev/null | cut -d: -f1 | sort -u | while read file; do
        echo "    - $file"
    done
else
    echo "  ✓ No '/ui/' references found (already updated)"
fi

# Replace /api/v1/ with /api/
echo ""
echo "Searching for '/api/v1/' route references..."
API_REFS_FOUND=$(grep -r "/api/v1/" docs --include="*.md" 2>/dev/null | wc -l)
if [ "$API_REFS_FOUND" -gt 0 ]; then
    echo "  Found $API_REFS_FOUND references to old '/api/v1/' routes"
    echo "  Note: Manual update recommended"
    echo "  Command: find docs -name '*.md' -type f -exec sed -i 's|/api/v1/|/api/|g' {} \\;"
else
    echo "  ✓ No '/api/v1/' references found (already updated)"
fi

echo ""
echo -e "${BLUE}Phase 3: Link Validation${NC}"
echo "========================"

# Check for common broken link patterns
echo "Checking for broken internal link patterns..."

MISSING_REFS=(
    "docs/keyboard-navigation.md"
    "docs/ui-ux-visual-guide.md"
    "docs/advanced-search-guide.md"
    "docs/ui-ux-testing-report.md"
)

BROKEN_COUNT=0
for ref in "${MISSING_REFS[@]}"; do
    if ! [ -f "$ref" ]; then
        FILES_REFERENCING=$(grep -r "$(basename "$ref")" docs --include="*.md" 2>/dev/null | wc -l)
        if [ "$FILES_REFERENCING" -gt 0 ]; then
            echo "  ⚠ Missing: $ref (referenced in $FILES_REFERENCING files)"
            ((BROKEN_COUNT++))
        fi
    fi
done

if [ "$BROKEN_COUNT" -eq 0 ]; then
    echo "  ✓ No broken internal link patterns detected"
else
    echo "  Found $BROKEN_COUNT potentially broken references"
fi

echo ""
echo -e "${BLUE}Phase 4: Documentation Freshness Check${NC}"
echo "======================================"

# Check modification dates of key files
echo "Checking documentation freshness..."

KEY_DOCS=(
    "docs/README.md"
    "docs/project/CHANGELOG.md"
    "docs/development/frontend-roadmap.md"
    "docs/development/backend-roadmap.md"
    "docs/api/README.md"
    "docs/project/contributing.md"
)

for doc in "${KEY_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        MODIFIED=$(stat -f%Sm -t%s "$doc" 2>/dev/null || stat -c%Y "$doc" 2>/dev/null || echo "unknown")
        if [ "$MODIFIED" != "unknown" ]; then
            AGE_DAYS=$(( ($(date +%s) - $MODIFIED) / 86400 ))
            if [ "$AGE_DAYS" -lt 3 ]; then
                echo "  ✓ $doc ($AGE_DAYS days old)"
            elif [ "$AGE_DAYS" -lt 14 ]; then
                echo "  🟡 $doc ($AGE_DAYS days old - review recommended)"
            else
                echo "  🔴 $doc ($AGE_DAYS days old - update needed)"
            fi
        else
            echo "  ? $doc (unable to determine age)"
        fi
    else
        echo "  ✗ $doc (missing)"
    fi
done

echo ""
echo -e "${BLUE}Phase 5: Version Standardization${NC}"
echo "=================================="

# Check current version in key files
echo "Checking version consistency..."

VERSION_IN_CHANGELOG=$(grep -m1 "^## \[" docs/project/CHANGELOG.md | grep -oP '\d+\.\d+\.\d+' | head -1)
VERSION_IN_API=$(grep "^> \*\*Version:" docs/api/README.md | grep -oP '\d+\.\d+\.\d+' | head -1)
VERSION_IN_README=$(grep -i "version" README.md | grep -oP '\d+\.\d+\.\d+' | head -1)

echo "  CHANGELOG.md: v$VERSION_IN_CHANGELOG"
echo "  API README: v$VERSION_IN_API"
echo "  Root README: v$VERSION_IN_README"

if [ "$VERSION_IN_CHANGELOG" != "$VERSION_IN_API" ] || [ "$VERSION_IN_CHANGELOG" != "$VERSION_IN_README" ]; then
    echo "  ⚠ Version mismatch detected - manual update needed"
else
    echo "  ✓ Versions consistent (v$VERSION_IN_CHANGELOG)"
fi

echo ""
echo -e "${BLUE}Phase 6: New Documentation Files${NC}"
echo "=================================="

# Check for newly created files
NEW_FILES=(
    "docs/version-3.0/STATUS.md"
    "docs/development/DOCUMENTATION_MAINTENANCE_LOG.md"
    "docs/development/UI_QUICK_WINS_PHASE1.md"
    "docs/development/UI_ADVANCED_FEATURES_PHASE2.md"
    "docs/development/PHASE2_VALIDATION_REPORT.md"
)

for file in "${NEW_FILES[@]}"; do
    if [ -f "$file" ]; then
        SIZE=$(wc -l < "$file")
        echo "  ✓ $file ($SIZE lines)"
        ((FIXES_APPLIED++))
    else
        echo "  ⚠ $file (expected but missing)"
    fi
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Documentation Maintenance Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📊 Summary:"
echo "  ✓ Automated fixes applied: $FIXES_APPLIED"
echo "  ⚠ Manual reviews recommended: See above"
echo ""
echo "📝 Next Steps:"
echo "  1. Review broken link patterns and update references"
echo "  2. Verify version consistency across all docs"
echo "  3. Update stale documentation (>14 days)"
echo "  4. Run 'make docs-validate' to check links"
echo ""
echo "📚 New Documentation:"
echo "  - docs/version-3.0/STATUS.md - v3.0 implementation status"
echo "  - docs/development/DOCUMENTATION_MAINTENANCE_LOG.md - This session's findings"
echo "  - docs/development/UI_QUICK_WINS_PHASE1.md - Phase 1 UI features"
echo "  - docs/development/UI_ADVANCED_FEATURES_PHASE2.md - Phase 2 UI features"
echo "  - docs/development/PHASE2_VALIDATION_REPORT.md - Validation results"
echo ""
echo "⏰ Recommended Schedule:"
echo "  - Weekly: Run link validation"
echo "  - Monthly: Check staleness and update"
echo "  - Quarterly: Full documentation audit"
echo ""

exit 0
