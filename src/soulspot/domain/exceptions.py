"""
⚠️ DEPRECATED - DO NOT IMPORT FROM THIS FILE ⚠️

This file is NEVER imported because Python resolves `soulspot.domain.exceptions`
to the `exceptions/` PACKAGE (directory), not this MODULE (file).

All exceptions are defined in: soulspot/domain/exceptions/__init__.py

This file exists only for historical reference and will be removed in a future version.
Do NOT add new exceptions here - they will never be importable!

Correct import:
    from soulspot.domain.exceptions import EntityNotFoundError  # Works!

This file was superseded by the exceptions/ package to support:
- TokenRefreshException with extra attributes (error_code, http_status)
- Structured metadata on exceptions (entity_type, entity_id)
- Better organization of related exceptions

DELETE THIS FILE when migration is complete (Dec 2025).
"""

# This module is never imported - see exceptions/__init__.py instead
raise ImportError(
    "This module is DEPRECATED. "
    "Import from soulspot.domain.exceptions (the package) instead."
)
