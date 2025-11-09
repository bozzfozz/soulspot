# Examples

This directory contains example scripts and validation tools for SoulSpot Bridge.

## Available Examples

### `example_phase4.py`
Example script demonstrating Phase 4 functionality including:
- Use cases (Import Spotify Playlist, Enrich Metadata)
- Worker system and job queue
- Caching layer
- Application services

**Usage:**
```bash
python examples/example_phase4.py
```

**Requirements:**
- Configured `.env` file with Spotify credentials
- Running slskd instance
- Database initialized

### `validate_phase4.py`
Validation script for Phase 4 implementation:
- Checks all Phase 4 components exist
- Verifies module structure
- Validates imports and dependencies
- Reports implementation status

**Usage:**
```bash
python examples/validate_phase4.py
```

## Creating New Examples

When adding new example scripts:

1. **Name clearly:** Use descriptive names like `example_<feature>.py`
2. **Add documentation:** Include docstrings and comments
3. **Handle errors:** Provide clear error messages
4. **Add to this README:** Document what the example does

## Testing Examples

Examples can be tested with:
```bash
pytest examples/ --doctest-modules
```

## See Also

- [Setup Guide](../docs/setup-guide.md) - For environment setup
- [Testing Guide](../docs/testing-guide.md) - For testing best practices
- [Contributing Guide](../docs/contributing.md) - For contribution guidelines
