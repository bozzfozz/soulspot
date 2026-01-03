"""Quality profile value object for audio quality standards.

Hey future me - this is THE SINGLE SOURCE OF TRUTH for quality profiles!

BEFORE (duplicated in 3+ files):
    quality_upgrade_service.py:  QUALITY_PROFILES = {"low": {...}, ...}
    automation_workflow_service.py:  quality_profile: str = "high"
    watchlist_service.py:  quality_profile: str = "high"

AFTER (centralized here):
    from soulspot.domain.value_objects import QualityProfile
    profile = QualityProfile.HIGH
    config = profile.config  # {"min_bitrate": 320, ...}

Benefits:
- Type safety: Can't pass invalid quality profile strings
- Single source of truth for bitrates/formats
- Easy to add new profiles or modify existing ones
- IDE autocomplete for valid values
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class QualityConfig:
    """Configuration for a quality profile.
    
    Attributes:
        min_bitrate: Minimum acceptable bitrate in kbps
        formats: Acceptable audio formats for this quality level
        description: Human-readable description
    """
    min_bitrate: int
    formats: tuple[str, ...]
    description: str

    def accepts_format(self, format_str: str) -> bool:
        """Check if format is acceptable for this quality level."""
        return format_str.lower() in self.formats

    def accepts_bitrate(self, bitrate: int) -> bool:
        """Check if bitrate meets minimum requirement."""
        return bitrate >= self.min_bitrate


class QualityProfile(Enum):
    """Audio quality profile definitions.
    
    Usage:
        profile = QualityProfile.HIGH
        if profile.config.accepts_bitrate(320):
            print("Bitrate OK!")
        
        # String conversion (for DB storage)
        profile_str = profile.value  # "high"
        profile = QualityProfile.from_string("high")
        
        # Get all valid profile names
        valid_names = QualityProfile.valid_names()  # ["low", "medium", "high", "lossless"]
    """
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    LOSSLESS = "lossless"
    
    @property
    def config(self) -> QualityConfig:
        """Get configuration for this quality profile."""
        return _QUALITY_CONFIGS[self]
    
    @classmethod
    def from_string(cls, value: str) -> "QualityProfile":
        """Parse quality profile from string.
        
        Args:
            value: Profile name (case-insensitive)
            
        Returns:
            QualityProfile enum value
            
        Raises:
            ValueError: If value is not a valid profile name
        """
        normalized = value.lower().strip()
        try:
            return cls(normalized)
        except ValueError:
            valid = ", ".join(cls.valid_names())
            raise ValueError(
                f"Invalid quality profile: '{value}'. Valid options: {valid}"
            ) from None
    
    @classmethod
    def valid_names(cls) -> list[str]:
        """Get list of valid profile names."""
        return [p.value for p in cls]
    
    @classmethod
    def default(cls) -> "QualityProfile":
        """Get default quality profile."""
        return cls.HIGH
    
    def __str__(self) -> str:
        return self.value


# Hey future me - these are the OFFICIAL quality configs!
# Modify here to change bitrate/format requirements project-wide.
# 
# Bitrate reference:
#   - 128 kbps: Typical streaming low quality
#   - 192 kbps: Standard quality MP3
#   - 320 kbps: High quality MP3 (max for lossy)
#   - 1411 kbps: CD quality (16-bit/44.1kHz)
#   - Higher: Hi-res audio (24-bit/96kHz+)
_QUALITY_CONFIGS: dict[QualityProfile, QualityConfig] = {
    QualityProfile.LOW: QualityConfig(
        min_bitrate=128,
        formats=("mp3", "m4a", "ogg", "aac"),
        description="Low quality - streaming equivalent",
    ),
    QualityProfile.MEDIUM: QualityConfig(
        min_bitrate=192,
        formats=("mp3", "m4a", "ogg", "aac"),
        description="Medium quality - standard streaming",
    ),
    QualityProfile.HIGH: QualityConfig(
        min_bitrate=320,
        formats=("mp3", "m4a", "flac", "alac", "ogg"),
        description="High quality - max lossy or lossless",
    ),
    QualityProfile.LOSSLESS: QualityConfig(
        min_bitrate=1411,
        formats=("flac", "alac", "wav", "aiff"),
        description="Lossless - CD quality or higher",
    ),
}


# Legacy compatibility: dict format for existing code
# Hey future me - use QualityProfile enum in new code!
# This dict is here for gradual migration only.
QUALITY_PROFILES_DICT: dict[str, dict[str, Any]] = {
    profile.value: {
        "min_bitrate": profile.config.min_bitrate,
        "formats": list(profile.config.formats),
    }
    for profile in QualityProfile
}
