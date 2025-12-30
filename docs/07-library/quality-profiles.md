# Quality Profiles

**Category:** Library Management  
**Status:** 🚧 Draft  
**Last Updated:** 2025-11-28  
**Related Docs:** [Lidarr Integration](./lidarr-integration.md) | [Download Manager Roadmap](../06-features/download-manager-roadmap.md)

---

## Overview

Quality Profiles define which audio formats are acceptable and preferred for downloads. Each artist is assigned a quality profile controlling:

1. **Allowed Qualities** — Which formats will be downloaded
2. **Quality Ranking** — Order of preference
3. **Cutoff** — Minimum acceptable quality (stop searching once reached)
4. **Upgrade Allowed** — Whether to replace existing files with better quality

---

## Audio Quality Definitions

### Quality Tiers

| ID | Name | Bitrate | Lossless | Weight |
|----|------|---------|----------|--------|
| 0 | Unknown | Variable | No | 1 |
| 1 | MP3-VBR | Variable | No | 200 |
| 2 | MP3-192 | 192 kbps | No | 300 |
| 3 | MP3-256 | 256 kbps | No | 400 |
| 4 | MP3-320 | 320 kbps | No | 500 |
| 5 | AAC-256 | 256 kbps | No | 450 |
| 6 | FLAC | Variable | Yes | 600 |
| 7 | FLAC 24-bit | Variable | Yes | 700 |
| 8 | ALAC | Variable | Yes | 600 |
| 9 | ALAC 24-bit | Variable | Yes | 700 |
| 10 | WAV | Uncompressed | Yes | 650 |
| 11 | OGG Vorbis Q10 | ~500 kbps | No | 550 |
| 12 | Opus 256 | 256 kbps | No | 475 |

### Quality Weight

The **weight** determines preference order:
- Higher weight = more preferred
- Used when multiple qualities allowed
- Affects upgrade decisions

---

## Quality Profile Structure

### Database Model

```python
class QualityProfile(Base):
    """Quality profile system borrowed from Lidarr."""
    __tablename__ = "quality_profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    upgrade_allowed = Column(Boolean, default=True)
    cutoff = Column(Integer, nullable=False)  # Quality ID
    items = Column(JSON, nullable=False)  # Nested quality items
    min_format_score = Column(Integer, default=0)
    cutoff_format_score = Column(Integer, default=0)
    format_items = Column(JSON, default=list)

    # Relationships
    artists = relationship("Artist", back_populates="quality_profile")
```

---

### Methods

```python
def is_quality_allowed(self, quality_id: int) -> bool:
    """Check if a quality is allowed in this profile."""
    return self._check_items(self.items, quality_id)

def get_quality_weight(self, quality_id: int) -> int:
    """Get the weight/rank of a quality in this profile."""
    return self._get_weight(self.items, quality_id, 0)

def is_cutoff_met(self, current_quality_id: int) -> bool:
    """Check if current quality meets or exceeds cutoff."""
    current_weight = self.get_quality_weight(current_quality_id)
    cutoff_weight = self.get_quality_weight(self.cutoff)
    return current_weight >= cutoff_weight
```

---

## Example Profiles

### Audiophile

```yaml
name: "Audiophile"
upgrade_allowed: true
cutoff: 6  # FLAC
items:
  - quality: {id: 7, name: "FLAC 24-bit"}
    allowed: true
  - quality: {id: 6, name: "FLAC"}
    allowed: true
  - quality: {id: 10, name: "WAV"}
    allowed: true
  - quality: {id: 8, name: "ALAC"}
    allowed: true
  - quality: {id: 4, name: "MP3-320"}
    allowed: false
```

**Behavior:**
- Downloads only lossless formats
- Prefers FLAC 24-bit over standard FLAC
- Stops searching once FLAC (cutoff) found
- Won't download MP3-320 even if only option

---

### Balanced

```yaml
name: "Balanced"
upgrade_allowed: true
cutoff: 4  # MP3-320
items:
  - quality: {id: 6, name: "FLAC"}
    allowed: true
  - quality: {id: 4, name: "MP3-320"}
    allowed: true
  - quality: {id: 3, name: "MP3-256"}
    allowed: true
  - quality: {id: 2, name: "MP3-192"}
    allowed: false
```

**Behavior:**
- Accepts 256kbps and higher
- Prefers FLAC if available
- Stops searching at MP3-320 (cutoff)
- Will upgrade 256kbps → 320kbps → FLAC

---

### Any Quality

```yaml
name: "Any Quality"
upgrade_allowed: false
cutoff: 0  # Unknown (accepts anything)
items:
  - quality: {id: 6, name: "FLAC"}
    allowed: true
  - quality: {id: 4, name: "MP3-320"}
    allowed: true
  - quality: {id: 3, name: "MP3-256"}
    allowed: true
  - quality: {id: 2, name: "MP3-192"}
    allowed: true
  - quality: {id: 1, name: "MP3-VBR"}
    allowed: true
```

**Behavior:**
- Downloads any quality
- No upgrades (upgrade_allowed = false)
- Useful for rare/hard-to-find releases

---

## Usage Workflow

### Assign Profile to Artist

```python
# Assign quality profile to artist
artist.quality_profile_id = 1  # Audiophile profile

# Or via relationship
artist.quality_profile = audiophile_profile
```

---

### Check if Download Allowed

```python
# Before downloading
if quality_profile.is_quality_allowed(quality_id):
    # Download allowed
    download_track()
else:
    # Quality not acceptable
    skip()
```

---

### Check if Upgrade Needed

```python
# Check existing file quality
current_quality_id = track.quality_id

if quality_profile.upgrade_allowed:
    if not quality_profile.is_cutoff_met(current_quality_id):
        # Upgrade available
        search_for_better_quality()
```

---

## Related Documentation

- **[Lidarr Integration](./lidarr-integration.md)** - Lidarr compatibility
- **[Download Manager Roadmap](../06-features/download-manager-roadmap.md)** - Future quality features

---

**Last Validated:** 2025-11-28  
**Implementation Status:** 🚧 Draft
