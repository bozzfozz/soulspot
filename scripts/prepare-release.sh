#!/usr/bin/env bash
# Release helper script for SoulSpot Bridge
# This script helps maintainers prepare releases locally

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print colored output
print_error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_error "Must be run from the project root directory"
    exit 1
fi

# Check if git working directory is clean
if ! git diff-index --quiet HEAD --; then
    print_error "Working directory is not clean. Commit or stash changes first."
    exit 1
fi

# Get current version
CURRENT_VERSION=$(poetry version -s)
print_info "Current version: $CURRENT_VERSION"

# Ask for version bump type
echo ""
echo "Select version bump type:"
echo "  1) patch (bug fixes)         - $CURRENT_VERSION → $(poetry version patch -s && git checkout pyproject.toml)"
echo "  2) minor (new features)      - $CURRENT_VERSION → $(poetry version minor -s && git checkout pyproject.toml)"
echo "  3) major (breaking changes)  - $CURRENT_VERSION → $(poetry version major -s && git checkout pyproject.toml)"
echo "  4) custom version"
echo ""
read -p "Enter choice [1-4]: " CHOICE

case $CHOICE in
    1)
        BUMP_TYPE="patch"
        poetry version patch
        ;;
    2)
        BUMP_TYPE="minor"
        poetry version minor
        ;;
    3)
        BUMP_TYPE="major"
        poetry version major
        ;;
    4)
        read -p "Enter custom version (e.g., 1.2.3): " CUSTOM_VERSION
        poetry version "$CUSTOM_VERSION"
        BUMP_TYPE="custom"
        ;;
    *)
        print_error "Invalid choice"
        exit 1
        ;;
esac

NEW_VERSION=$(poetry version -s)
print_success "Version bumped to: $NEW_VERSION"

# Update package.json
print_info "Updating package.json..."
sed -i.bak "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" package.json
rm package.json.bak 2>/dev/null || true
print_success "package.json updated"

# Update CHANGELOG.md
print_info "Updating CHANGELOG.md..."
DATE=$(date +%Y-%m-%d)

# Create temporary file with new section
cat > /tmp/new_changelog_section.md << EOF

## [$NEW_VERSION] - $DATE

### Added
- 

### Changed
- 

### Fixed
- 

EOF

# Insert after [Unreleased] section
awk '/## \[Unreleased\]/{print; system("cat /tmp/new_changelog_section.md"); next}1' CHANGELOG.md > /tmp/CHANGELOG.md.new
mv /tmp/CHANGELOG.md.new CHANGELOG.md

# Add comparison link at the bottom
if ! grep -q "^\[$NEW_VERSION\]:" CHANGELOG.md; then
    echo "" >> CHANGELOG.md
    echo "[$NEW_VERSION]: https://github.com/bozzfozz/soulspot-bridge/releases/tag/v$NEW_VERSION" >> CHANGELOG.md
fi

print_success "CHANGELOG.md updated with new section"

# Show changes
print_info "Changes to be committed:"
git diff pyproject.toml package.json CHANGELOG.md

echo ""
read -p "Do you want to commit these changes? [y/N]: " CONFIRM

if [[ $CONFIRM =~ ^[Yy]$ ]]; then
    # Create release branch
    BRANCH_NAME="release/v$NEW_VERSION"
    git checkout -b "$BRANCH_NAME"
    
    # Commit changes
    git add pyproject.toml package.json CHANGELOG.md
    git commit -m "chore: bump version to $NEW_VERSION"
    
    print_success "Changes committed to branch: $BRANCH_NAME"
    
    echo ""
    print_info "Next steps:"
    echo "  1. Edit CHANGELOG.md and fill in the changes for this release"
    echo "  2. Run tests: poetry run pytest"
    echo "  3. Review the changes: git diff main"
    echo "  4. Push the branch: git push origin $BRANCH_NAME"
    echo "  5. Create a Pull Request on GitHub"
    echo "  6. After PR is merged, create and push the tag:"
    echo "     git tag v$NEW_VERSION"
    echo "     git push origin v$NEW_VERSION"
    echo ""
    print_success "Release preparation complete!"
else
    # Revert changes
    git checkout pyproject.toml package.json CHANGELOG.md
    print_info "Changes reverted"
fi
