# Quality Profiles

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-11-28
- **Status**: Draft
- **Reference**: [Lidarr Quality Profiles](https://github.com/Lidarr/Lidarr)

---

## Overview

Quality Profiles define which audio formats are acceptable and preferred for downloads. Each artist is assigned a quality profile that controls:

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
| 13 | APE | Variable | Yes | 580 |
| 14 | WavPack | Variable | Yes | 590 |

### Quality Weight Explanation

The **weight** determines preference order:
- Higher weight = more preferred
- Used when multiple qualities are allowed
- Affects upgrade decisions

---

## Quality Profile Structure

### TypeScript Interface (Reference)

```typescript
interface QualityProfile {
  id: number;
  name: string;
  upgradeAllowed: boolean;
  cutoff: number;              // Quality ID where searching stops
  items: QualityProfileItem[];
  minFormatScore: number;
  cutoffFormatScore: number;
  formatItems: CustomFormatItem[];
}

interface QualityProfileItem {
  id: number;                   // Unique item ID in profile
  name: string | null;          // Group name (for quality groups)
  quality: Quality | null;      // Single quality (null if group)
  items: QualityProfileItem[];  // Nested qualities (for groups)
  allowed: boolean;
}

interface Quality {
  id: number;
  name: string;
}

interface CustomFormatItem {
  format: CustomFormat;
  score: number;
}
```

### Python SQLAlchemy Model

```python
from sqlalchemy import Column, Integer, String, Boolean, JSON
from sqlalchemy.orm import relationship
from src.soulspot.models.base import Base


class QualityProfile(Base):
    """
    # Hey future me – this profile system is borrowed from Lidarr.
    # The 'items' JSON can be nested (quality groups), so watch out
    # when parsing. The cutoff is a quality ID, not a weight!
    """
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

    def is_quality_allowed(self, quality_id: int) -> bool:
        """Check if a quality is allowed in this profile."""
        return self._check_items(self.items, quality_id)

    def _check_items(self, items: list, quality_id: int) -> bool:
        for item in items:
            if not item.get("allowed"):
                continue
            if item.get("quality") and item["quality"]["id"] == quality_id:
                return True
            if item.get("items"):
                if self._check_items(item["items"], quality_id):
                    return True
        return False

    def get_quality_weight(self, quality_id: int) -> int:
        """Get the weight/rank of a quality in this profile."""
        return self._get_weight(self.items, quality_id, 0)

    def _get_weight(self, items: list, quality_id: int, base: int) -> int:
        for idx, item in enumerate(items):
            weight = base + idx
            if item.get("quality") and item["quality"]["id"] == quality_id:
                return weight
            if item.get("items"):
                result = self._get_weight(item["items"], quality_id, weight * 100)
                if result >= 0:
                    return result
        return -1

    def is_cutoff_met(self, current_quality_id: int) -> bool:
        """Check if current quality meets or exceeds cutoff."""
        current_weight = self.get_quality_weight(current_quality_id)
        cutoff_weight = self.get_quality_weight(self.cutoff)
        return current_weight >= cutoff_weight

    def should_upgrade(self, current_quality_id: int, new_quality_id: int) -> bool:
        """Determine if new quality is an upgrade worth taking."""
        if not self.upgrade_allowed:
            return False
        if not self.is_quality_allowed(new_quality_id):
            return False

        current_weight = self.get_quality_weight(current_quality_id)
        new_weight = self.get_quality_weight(new_quality_id)

        return new_weight > current_weight
```

---

## Preset Quality Profiles

### 1. Lossless (FLAC Preferred)

**Purpose**: Best quality, lossless audio only

```json
{
  "name": "Lossless",
  "upgradeAllowed": true,
  "cutoff": 6,
  "items": [
    {
      "id": 1000,
      "name": "Lossless",
      "quality": null,
      "items": [
        { "quality": { "id": 7, "name": "FLAC 24-bit" }, "allowed": true },
        { "quality": { "id": 6, "name": "FLAC" }, "allowed": true },
        { "quality": { "id": 9, "name": "ALAC 24-bit" }, "allowed": true },
        { "quality": { "id": 8, "name": "ALAC" }, "allowed": true },
        { "quality": { "id": 14, "name": "WavPack" }, "allowed": true },
        { "quality": { "id": 13, "name": "APE" }, "allowed": true }
      ],
      "allowed": true
    }
  ]
}
```

### 2. High Quality (320 kbps minimum)

**Purpose**: High quality lossy, no lossless

```json
{
  "name": "High Quality",
  "upgradeAllowed": true,
  "cutoff": 4,
  "items": [
    { "quality": { "id": 4, "name": "MP3-320" }, "allowed": true },
    { "quality": { "id": 5, "name": "AAC-256" }, "allowed": true },
    { "quality": { "id": 12, "name": "Opus 256" }, "allowed": true },
    { "quality": { "id": 11, "name": "OGG Vorbis Q10" }, "allowed": true },
    { "quality": { "id": 3, "name": "MP3-256" }, "allowed": false },
    { "quality": { "id": 2, "name": "MP3-192" }, "allowed": false }
  ]
}
```

### 3. Standard (Any quality)

**Purpose**: Accept any quality, prefer better

```json
{
  "name": "Standard",
  "upgradeAllowed": true,
  "cutoff": 4,
  "items": [
    {
      "id": 1000,
      "name": "Lossless",
      "quality": null,
      "items": [
        { "quality": { "id": 7, "name": "FLAC 24-bit" }, "allowed": true },
        { "quality": { "id": 6, "name": "FLAC" }, "allowed": true }
      ],
      "allowed": true
    },
    { "quality": { "id": 4, "name": "MP3-320" }, "allowed": true },
    { "quality": { "id": 3, "name": "MP3-256" }, "allowed": true },
    { "quality": { "id": 2, "name": "MP3-192" }, "allowed": true },
    { "quality": { "id": 1, "name": "MP3-VBR" }, "allowed": true }
  ]
}
```

### 4. Portable (Space efficient)

**Purpose**: Smaller files for mobile devices

```json
{
  "name": "Portable",
  "upgradeAllowed": false,
  "cutoff": 3,
  "items": [
    { "quality": { "id": 12, "name": "Opus 256" }, "allowed": true },
    { "quality": { "id": 5, "name": "AAC-256" }, "allowed": true },
    { "quality": { "id": 3, "name": "MP3-256" }, "allowed": true },
    { "quality": { "id": 2, "name": "MP3-192" }, "allowed": true }
  ]
}
```

---

## Upgrade Logic

### Decision Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    UPGRADE DECISION FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  New Release Found                                              │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Is quality      │──No──► Skip (not allowed)                  │
│  │ allowed?        │                                            │
│  └───────┬─────────┘                                            │
│          │Yes                                                   │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Have existing   │──No──► Download (no file yet)              │
│  │ file?           │                                            │
│  └───────┬─────────┘                                            │
│          │Yes                                                   │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Is upgrade      │──No──► Skip (upgrades disabled)            │
│  │ allowed?        │                                            │
│  └───────┬─────────┘                                            │
│          │Yes                                                   │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Is cutoff       │──Yes──► Skip (already satisfied)           │
│  │ already met?    │                                            │
│  └───────┬─────────┘                                            │
│          │No                                                    │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Is new quality  │──No──► Skip (not an upgrade)               │
│  │ better?         │                                            │
│  └───────┬─────────┘                                            │
│          │Yes                                                   │
│          ▼                                                      │
│     Download & Replace                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Python Implementation

```python
class UpgradeDecisionService:
    """
    # Hey future me – this is the core upgrade logic. It's based on
    # Lidarr's approach but simplified. The tricky part is handling
    # quality groups (nested items). Make sure cutoff comparisons
    # use the same weight calculation as allowed checks!
    """

    def should_download(
        self,
        profile: QualityProfile,
        new_quality_id: int,
        existing_quality_id: int | None = None,
    ) -> UpgradeDecision:
        """
        Determine if a release should be downloaded.

        Args:
            profile: The quality profile to use
            new_quality_id: Quality ID of the new release
            existing_quality_id: Quality ID of existing file (None if no file)

        Returns:
            UpgradeDecision with result and reason
        """
        # Check if quality is allowed
        if not profile.is_quality_allowed(new_quality_id):
            return UpgradeDecision(
                should_download=False,
                reason="Quality not allowed in profile",
            )

        # No existing file - always download if allowed
        if existing_quality_id is None:
            return UpgradeDecision(
                should_download=True,
                reason="No existing file",
            )

        # Check if upgrades are enabled
        if not profile.upgrade_allowed:
            return UpgradeDecision(
                should_download=False,
                reason="Upgrades disabled in profile",
            )

        # Check if cutoff is already met
        if profile.is_cutoff_met(existing_quality_id):
            return UpgradeDecision(
                should_download=False,
                reason="Cutoff quality already met",
            )

        # Check if new quality is better
        if profile.should_upgrade(existing_quality_id, new_quality_id):
            return UpgradeDecision(
                should_download=True,
                reason="Quality upgrade available",
                is_upgrade=True,
            )

        return UpgradeDecision(
            should_download=False,
            reason="New quality is not an improvement",
        )


@dataclass
class UpgradeDecision:
    should_download: bool
    reason: str
    is_upgrade: bool = False
```

---

## Quality Detection

### From File Extension

```python
EXTENSION_TO_QUALITY = {
    ".flac": 6,
    ".mp3": None,  # Needs bitrate detection
    ".m4a": None,  # Could be AAC or ALAC
    ".ogg": 11,
    ".opus": 12,
    ".wav": 10,
    ".ape": 13,
    ".wv": 14,
}

def detect_quality_from_extension(path: str) -> int | None:
    """Quick quality detection from file extension."""
    ext = Path(path).suffix.lower()
    return EXTENSION_TO_QUALITY.get(ext)
```

### From Media Info

```python
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4


def detect_quality(path: str) -> Quality:
    """
    # Hey future me – mutagen is the key here for reading audio metadata.
    # MP3 bitrate detection is approximate (VBR vs CBR).
    # ALAC detection requires checking the codec in M4A containers.
    """
    audio = MutagenFile(path)

    if isinstance(audio, FLAC):
        bits = audio.info.bits_per_sample
        return Quality(id=7 if bits > 16 else 6, name=f"FLAC {'24-bit' if bits > 16 else ''}")

    if isinstance(audio, MP3):
        bitrate = audio.info.bitrate // 1000
        if bitrate >= 310:
            return Quality(id=4, name="MP3-320")
        elif bitrate >= 245:
            return Quality(id=3, name="MP3-256")
        elif bitrate >= 180:
            return Quality(id=2, name="MP3-192")
        else:
            return Quality(id=1, name="MP3-VBR")

    if isinstance(audio, MP4):
        # Check if ALAC or AAC
        if audio.info.codec and "alac" in audio.info.codec.lower():
            bits = audio.info.bits_per_sample
            return Quality(id=9 if bits > 16 else 8, name=f"ALAC {'24-bit' if bits > 16 else ''}")
        else:
            bitrate = audio.info.bitrate // 1000
            return Quality(id=5, name=f"AAC-{bitrate}")

    return Quality(id=0, name="Unknown")
```

---

## API Endpoints

### List Quality Profiles

```http
GET /api/v1/qualityprofile
```

### Create Quality Profile

```http
POST /api/v1/qualityprofile
Content-Type: application/json

{
  "name": "My Custom Profile",
  "upgradeAllowed": true,
  "cutoff": 6,
  "items": [
    { "quality": { "id": 6, "name": "FLAC" }, "allowed": true },
    { "quality": { "id": 4, "name": "MP3-320" }, "allowed": true }
  ]
}
```

### Update Quality Profile

```http
PUT /api/v1/qualityprofile/{id}
```

### Delete Quality Profile

```http
DELETE /api/v1/qualityprofile/{id}
```

**Note**: Cannot delete profiles assigned to artists.

### Get Quality Definitions

```http
GET /api/v1/qualitydefinition
```

Returns all available qualities with their properties.

---

## UI Components

### Quality Profile Selector

```tsx
function QualityProfileSelector({
  value,
  onChange,
  profiles,
}: QualityProfileSelectorProps) {
  return (
    <Select
      label="Quality Profile"
      value={value}
      onChange={onChange}
      options={profiles.map((p) => ({
        value: p.id,
        label: p.name,
        description: getProfileDescription(p),
      }))}
    />
  );
}

function getProfileDescription(profile: QualityProfile): string {
  const allowed = profile.items
    .filter((i) => i.allowed)
    .map((i) => i.quality?.name || i.name)
    .slice(0, 3);

  return `${allowed.join(", ")}${profile.items.length > 3 ? "..." : ""}`;
}
```

### Quality Profile Editor

```tsx
function QualityProfileEditor({ profile, onSave }: QualityProfileEditorProps) {
  const [items, setItems] = useState(profile?.items || []);
  const [name, setName] = useState(profile?.name || "");
  const [cutoff, setCutoff] = useState(profile?.cutoff || 6);
  const [upgradeAllowed, setUpgradeAllowed] = useState(profile?.upgradeAllowed ?? true);

  return (
    <div className="quality-profile-editor">
      <Input
        label="Profile Name"
        value={name}
        onChange={setName}
        required
      />

      <Toggle
        label="Allow Upgrades"
        checked={upgradeAllowed}
        onChange={setUpgradeAllowed}
      />

      <Select
        label="Cutoff"
        value={cutoff}
        onChange={setCutoff}
        options={items
          .filter((i) => i.allowed)
          .map((i) => ({
            value: i.quality?.id || i.id,
            label: i.quality?.name || i.name,
          }))}
        helperText="Stop searching when this quality is reached"
      />

      <h4>Quality Rankings</h4>
      <p className="text-muted">Drag to reorder. Higher = more preferred.</p>

      <DraggableList
        items={items}
        onReorder={setItems}
        renderItem={(item, index) => (
          <QualityItem
            item={item}
            onToggle={(allowed) => updateItemAllowed(index, allowed)}
          />
        )}
      />

      <div className="quality-profile-editor__actions">
        <Button variant="primary" onClick={() => onSave({ name, items, cutoff, upgradeAllowed })}>
          Save Profile
        </Button>
      </div>
    </div>
  );
}
```

### Quality Badge

```tsx
function QualityBadge({ quality }: { quality: Quality }) {
  const colorMap: Record<number, string> = {
    7: "purple",   // FLAC 24-bit
    6: "blue",     // FLAC
    4: "green",    // MP3-320
    3: "yellow",   // MP3-256
    2: "orange",   // MP3-192
    1: "red",      // MP3-VBR
    0: "gray",     // Unknown
  };

  return (
    <Badge color={colorMap[quality.id] || "gray"}>
      {quality.name}
    </Badge>
  );
}
```

---

## Database Schema

### Migration

```python
"""Add quality_profiles table

Revision ID: qp001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


def upgrade():
    op.create_table(
        "quality_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("upgrade_allowed", sa.Boolean(), default=True),
        sa.Column("cutoff", sa.Integer(), nullable=False),
        sa.Column("items", JSONB(), nullable=False),
        sa.Column("min_format_score", sa.Integer(), default=0),
        sa.Column("cutoff_format_score", sa.Integer(), default=0),
        sa.Column("format_items", JSONB(), default=[]),
    )

    # Insert default profiles
    op.execute("""
        INSERT INTO quality_profiles (name, upgrade_allowed, cutoff, items)
        VALUES
        ('Lossless', true, 6, '[{"id":1000,"name":"Lossless","quality":null,"items":[{"quality":{"id":7,"name":"FLAC 24-bit"},"allowed":true},{"quality":{"id":6,"name":"FLAC"},"allowed":true}],"allowed":true}]'),
        ('High Quality', true, 4, '[{"quality":{"id":4,"name":"MP3-320"},"allowed":true},{"quality":{"id":5,"name":"AAC-256"},"allowed":true}]'),
        ('Standard', true, 4, '[{"quality":{"id":6,"name":"FLAC"},"allowed":true},{"quality":{"id":4,"name":"MP3-320"},"allowed":true},{"quality":{"id":3,"name":"MP3-256"},"allowed":true}]')
    """)


def downgrade():
    op.drop_table("quality_profiles")
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-28  
**Status**: Draft
