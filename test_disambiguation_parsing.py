#!/usr/bin/env python3
"""Test script for artist folder parsing with disambiguation handling."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from soulspot.domain.value_objects.folder_parsing import (
    parse_artist_folder,
    parse_album_folder,
)


def test_parse_artist_folder():
    """Test parse_artist_folder() for disambiguation stripping."""
    test_cases = [
        ("The Beatles", "The Beatles", None),
        ("The Beatles (112944f7-8971-4b2b-b9d6-891e1dc2a7ff)", "The Beatles", "112944f7-8971-4b2b-b9d6-891e1dc2a7ff"),
        ("Various Artists", "Various Artists", None),
        ("Pink Floyd (4d3nxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)", "Pink Floyd", "4d3nxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"),
        ("The White Stripes (extra spaces)  (550e8400-e29b-41d4-a716-446655440000)", "The White Stripes (extra spaces)", "550e8400-e29b-41d4-a716-446655440000"),
    ]

    print("Testing parse_artist_folder():")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for input_name, expected_name, expected_uuid in test_cases:
        result = parse_artist_folder(input_name)
        name_match = result.name == expected_name
        uuid_match = result.uuid == expected_uuid
        matches = name_match and uuid_match
        
        status = "✓ PASS" if matches else "✗ FAIL"
        print(f"{status}: '{input_name}'")
        print(f"  Expected: name='{expected_name}', uuid={expected_uuid}")
        print(f"  Got:      name='{result.name}', uuid={result.uuid}")
        
        if matches:
            passed += 1
        else:
            failed += 1
            if not name_match:
                print(f"  NAME MISMATCH: '{expected_name}' != '{result.name}'")
            if not uuid_match:
                print(f"  UUID MISMATCH: {expected_uuid} != {result.uuid}")
        print()
    
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_parse_album_folder():
    """Test parse_album_folder() still works correctly."""
    test_cases = [
        ("Thriller (1982)", "Thriller", 1982, None),
        ("Bad (1987) (Deluxe Edition)", "Bad", 1987, "Deluxe Edition"),
        ("Abbey Road", "Abbey Road", None, None),
    ]
    
    print("\nTesting parse_album_folder():")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for input_name, expected_title, expected_year, expected_dis in test_cases:
        result = parse_album_folder(input_name)
        title_match = result.title == expected_title
        year_match = result.year == expected_year
        dis_match = result.disambiguation == expected_dis
        matches = title_match and year_match and dis_match
        
        status = "✓ PASS" if matches else "✗ FAIL"
        print(f"{status}: '{input_name}'")
        print(f"  Expected: title='{expected_title}', year={expected_year}, dis='{expected_dis}'")
        print(f"  Got:      title='{result.title}', year={result.year}, dis='{result.disambiguation}'")
        
        if matches:
            passed += 1
        else:
            failed += 1
        print()
    
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    artist_ok = test_parse_artist_folder()
    album_ok = test_parse_album_folder()
    
    if artist_ok and album_ok:
        print("\n✓ All tests PASSED!")
        sys.exit(0)
    else:
        print("\n✗ Some tests FAILED!")
        sys.exit(1)
