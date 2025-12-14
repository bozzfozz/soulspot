#!/bin/bash
# scripts/validate-startup.sh
# Quick validation script for checking if code changes break app startup

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 STARTUP VALIDATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Find the correct source path (virtual GitHub environment)
SOURCE_PATH=$(find / -path "*/soulspot/src/soulspot" -type d 2>/dev/null | head -1)

if [ -z "$SOURCE_PATH" ]; then
    echo "❌ ERROR: Could not find soulspot source directory"
    exit 1
fi

BASE_PATH=$(dirname "$SOURCE_PATH")
echo "📂 Using source path: $SOURCE_PATH"
echo ""

# Add to Python path
export PYTHONPATH="$BASE_PATH:$PYTHONPATH"

# Track results
PASSED=0
FAILED=0

# 1. Import Check
echo "1️⃣  Import Check"
echo "─────────────────────────────────────────────────────────"

# Main app
if python3 -c "import sys; sys.path.insert(0, '$BASE_PATH'); from soulspot.main import create_app" 2>/dev/null; then
    echo "✅ soulspot.main imports successfully"
    ((PASSED++))
else
    echo "❌ soulspot.main FAILED to import"
    ((FAILED++))
fi

# Lifecycle
if python3 -c "import sys; sys.path.insert(0, '$BASE_PATH'); from soulspot.infrastructure.lifecycle import lifespan" 2>/dev/null; then
    echo "✅ soulspot.infrastructure.lifecycle imports successfully"
    ((PASSED++))
else
    echo "❌ soulspot.infrastructure.lifecycle FAILED to import"
    ((FAILED++))
fi

# AutoImportService (recently modified)
if python3 -c "import sys; sys.path.insert(0, '$BASE_PATH'); from soulspot.application.services.auto_import import AutoImportService" 2>/dev/null; then
    echo "✅ soulspot.application.services.auto_import imports successfully"
    ((PASSED++))
else
    echo "❌ soulspot.application.services.auto_import FAILED to import"
    ((FAILED++))
fi

echo ""

# 2. Syntax Check
echo "2️⃣  Syntax Check"
echo "─────────────────────────────────────────────────────────"

SYNTAX_ERRORS=0
for file in "$SOURCE_PATH"/**/*.py; do
    if [ -f "$file" ]; then
        if ! python3 -m py_compile "$file" 2>/dev/null; then
            echo "❌ Syntax error in: $file"
            ((SYNTAX_ERRORS++))
            ((FAILED++))
        fi
    fi
done

if [ $SYNTAX_ERRORS -eq 0 ]; then
    echo "✅ No syntax errors found"
    ((PASSED++))
else
    echo "❌ Found $SYNTAX_ERRORS syntax error(s)"
fi

echo ""

# 3. Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 VALIDATION SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Passed: $PASSED"
echo "❌ Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ STARTUP VALIDATION PASSED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 0
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "❌ STARTUP VALIDATION FAILED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "💡 TIP: Run with verbose error output:"
    echo "   python3 -c \"import sys; sys.path.insert(0, '$BASE_PATH'); from soulspot.main import create_app\""
    echo ""
    exit 1
fi
