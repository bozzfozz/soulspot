# Library UI Patterns

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-11-28
- **Status**: Draft
- **Reference**: [Lidarr UI](https://github.com/Lidarr/Lidarr) React/Redux Frontend

---

## Overview

This document defines the UI patterns for SoulSpot's library management views. Inspired by Lidarr's powerful browsing and filtering capabilities.

---

## View Modes

### Artist Index View Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **Table** | Dense list with sortable columns | Large collections, quick scanning |
| **Poster** | Grid of artist images | Visual browsing |
| **Banner** | Wide banners with artist info | Featured/highlighted artists |
| **Overview** | Cards with descriptions | Discovering new artists |

### Album View Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **Table** | Detailed album listing | Managing releases |
| **Album Studio** | Compact monitoring grid | Bulk monitoring changes |

---

## Table View Pattern

### Artist Table Columns

```tsx
interface ColumnDefinition {
  id: string;
  label: string;
  sortable: boolean;
  defaultVisible: boolean;
  width?: string;
}

const artistColumns: ColumnDefinition[] = [
  { id: "status", label: "", sortable: false, defaultVisible: true, width: "40px" },
  { id: "artistName", label: "Artist", sortable: true, defaultVisible: true },
  { id: "artistType", label: "Type", sortable: true, defaultVisible: true },
  { id: "qualityProfile", label: "Quality", sortable: true, defaultVisible: true },
  { id: "metadataProfile", label: "Metadata", sortable: true, defaultVisible: false },
  { id: "path", label: "Path", sortable: true, defaultVisible: false },
  { id: "sizeOnDisk", label: "Size", sortable: true, defaultVisible: true },
  { id: "genres", label: "Genres", sortable: false, defaultVisible: false },
  { id: "ratings", label: "Rating", sortable: true, defaultVisible: false },
  { id: "tags", label: "Tags", sortable: false, defaultVisible: false },
  { id: "added", label: "Added", sortable: true, defaultVisible: true },
  { id: "albumCount", label: "Albums", sortable: true, defaultVisible: true },
  { id: "trackFileCount", label: "Tracks", sortable: true, defaultVisible: true },
  { id: "actions", label: "", sortable: false, defaultVisible: true, width: "80px" },
];
```

### Album Table Columns

```tsx
const albumColumns: ColumnDefinition[] = [
  { id: "monitored", label: "", sortable: false, defaultVisible: true, width: "40px" },
  { id: "title", label: "Album", sortable: true, defaultVisible: true },
  { id: "artist", label: "Artist", sortable: true, defaultVisible: true },
  { id: "albumType", label: "Type", sortable: true, defaultVisible: true },
  { id: "releaseDate", label: "Release", sortable: true, defaultVisible: true },
  { id: "trackCount", label: "Tracks", sortable: true, defaultVisible: true },
  { id: "sizeOnDisk", label: "Size", sortable: true, defaultVisible: true },
  { id: "percentOfTracks", label: "Progress", sortable: true, defaultVisible: true },
  { id: "duration", label: "Duration", sortable: true, defaultVisible: false },
  { id: "ratings", label: "Rating", sortable: true, defaultVisible: false },
  { id: "actions", label: "", sortable: false, defaultVisible: true, width: "80px" },
];
```

### Table Component Structure

```tsx
// React Component Pattern
interface TableViewProps<T> {
  items: T[];
  columns: ColumnDefinition[];
  visibleColumns: string[];
  sortKey: string;
  sortDirection: "asc" | "desc";
  onSort: (key: string) => void;
  onColumnToggle: (columnId: string) => void;
  isLoading: boolean;
  selectedIds: Set<number>;
  onSelect: (id: number) => void;
  onSelectAll: () => void;
}

function LibraryTable<T extends { id: number }>({
  items,
  columns,
  visibleColumns,
  sortKey,
  sortDirection,
  onSort,
  selectedIds,
  onSelect,
  onSelectAll,
}: TableViewProps<T>) {
  return (
    <table className="library-table">
      <thead>
        <tr>
          <th className="select-cell">
            <Checkbox
              checked={selectedIds.size === items.length}
              indeterminate={selectedIds.size > 0 && selectedIds.size < items.length}
              onChange={onSelectAll}
            />
          </th>
          {columns
            .filter((col) => visibleColumns.includes(col.id))
            .map((col) => (
              <th
                key={col.id}
                onClick={col.sortable ? () => onSort(col.id) : undefined}
                className={col.sortable ? "sortable" : ""}
                style={{ width: col.width }}
              >
                {col.label}
                {sortKey === col.id && (
                  <SortIcon direction={sortDirection} />
                )}
              </th>
            ))}
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id} className={selectedIds.has(item.id) ? "selected" : ""}>
            <td>
              <Checkbox
                checked={selectedIds.has(item.id)}
                onChange={() => onSelect(item.id)}
              />
            </td>
            {/* Render cells based on visible columns */}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

---

## Filter System

### Filter Types

```tsx
enum FilterType {
  BOOLEAN = "boolean",
  SELECT = "select",
  MULTI_SELECT = "multiSelect",
  DATE_RANGE = "dateRange",
  NUMBER_RANGE = "numberRange",
  TEXT = "text",
}

interface FilterDefinition {
  id: string;
  label: string;
  type: FilterType;
  options?: { value: string; label: string }[];
  default?: any;
}
```

### Artist Filters

```tsx
const artistFilters: FilterDefinition[] = [
  {
    id: "monitored",
    label: "Monitored",
    type: FilterType.SELECT,
    options: [
      { value: "all", label: "All" },
      { value: "monitored", label: "Monitored Only" },
      { value: "unmonitored", label: "Unmonitored Only" },
    ],
    default: "all",
  },
  {
    id: "status",
    label: "Status",
    type: FilterType.MULTI_SELECT,
    options: [
      { value: "continuing", label: "Continuing" },
      { value: "ended", label: "Ended" },
    ],
    default: [],
  },
  {
    id: "qualityProfileId",
    label: "Quality Profile",
    type: FilterType.SELECT,
    options: [], // Populated dynamically
    default: "all",
  },
  {
    id: "metadataProfileId",
    label: "Metadata Profile",
    type: FilterType.SELECT,
    options: [], // Populated dynamically
    default: "all",
  },
  {
    id: "tags",
    label: "Tags",
    type: FilterType.MULTI_SELECT,
    options: [], // Populated dynamically
    default: [],
  },
  {
    id: "missing",
    label: "Missing Albums",
    type: FilterType.BOOLEAN,
    default: false,
  },
  {
    id: "artistType",
    label: "Artist Type",
    type: FilterType.MULTI_SELECT,
    options: [
      { value: "Person", label: "Person" },
      { value: "Group", label: "Group" },
      { value: "Orchestra", label: "Orchestra" },
      { value: "Choir", label: "Choir" },
    ],
    default: [],
  },
];
```

### Album Filters

```tsx
const albumFilters: FilterDefinition[] = [
  {
    id: "monitored",
    label: "Monitored",
    type: FilterType.SELECT,
    options: [
      { value: "all", label: "All" },
      { value: "monitored", label: "Monitored Only" },
      { value: "unmonitored", label: "Unmonitored Only" },
    ],
  },
  {
    id: "albumType",
    label: "Album Type",
    type: FilterType.MULTI_SELECT,
    options: [
      { value: "Album", label: "Album" },
      { value: "EP", label: "EP" },
      { value: "Single", label: "Single" },
      { value: "Broadcast", label: "Broadcast" },
      { value: "Other", label: "Other" },
    ],
  },
  {
    id: "releaseStatus",
    label: "Release Status",
    type: FilterType.SELECT,
    options: [
      { value: "all", label: "All" },
      { value: "released", label: "Released" },
      { value: "unreleased", label: "Unreleased" },
    ],
  },
  {
    id: "progress",
    label: "Progress",
    type: FilterType.SELECT,
    options: [
      { value: "all", label: "All" },
      { value: "complete", label: "Complete" },
      { value: "incomplete", label: "Incomplete" },
      { value: "missing", label: "Missing" },
    ],
  },
  {
    id: "releaseDate",
    label: "Release Date",
    type: FilterType.DATE_RANGE,
  },
];
```

### Filter Bar Component

```tsx
interface FilterBarProps {
  filters: FilterDefinition[];
  activeFilters: Record<string, any>;
  onFilterChange: (filterId: string, value: any) => void;
  onClearFilters: () => void;
  savedFilters: SavedFilter[];
  onSaveFilter: (name: string) => void;
  onLoadFilter: (filter: SavedFilter) => void;
}

function FilterBar({
  filters,
  activeFilters,
  onFilterChange,
  onClearFilters,
  savedFilters,
  onSaveFilter,
  onLoadFilter,
}: FilterBarProps) {
  const activeCount = Object.values(activeFilters).filter(Boolean).length;

  return (
    <div className="filter-bar">
      <div className="filter-bar__controls">
        {filters.map((filter) => (
          <FilterControl
            key={filter.id}
            definition={filter}
            value={activeFilters[filter.id]}
            onChange={(value) => onFilterChange(filter.id, value)}
          />
        ))}
      </div>

      <div className="filter-bar__actions">
        {activeCount > 0 && (
          <Button variant="ghost" onClick={onClearFilters}>
            Clear Filters ({activeCount})
          </Button>
        )}

        <Dropdown
          trigger={<Button variant="secondary">Saved Filters</Button>}
        >
          {savedFilters.map((saved) => (
            <DropdownItem key={saved.id} onClick={() => onLoadFilter(saved)}>
              {saved.name}
            </DropdownItem>
          ))}
          <DropdownDivider />
          <DropdownItem onClick={() => setShowSaveModal(true)}>
            Save Current Filters...
          </DropdownItem>
        </Dropdown>
      </div>
    </div>
  );
}
```

---

## Poster/Grid View Pattern

### Poster Card Component

```tsx
interface PosterCardProps {
  artist: Artist;
  showTitle: boolean;
  showMonitored: boolean;
  showQualityProfile: boolean;
  posterSize: "small" | "medium" | "large";
  onClick: () => void;
  onEdit: () => void;
}

function ArtistPosterCard({
  artist,
  showTitle,
  showMonitored,
  showQualityProfile,
  posterSize,
  onClick,
  onEdit,
}: PosterCardProps) {
  const posterSizes = {
    small: { width: 138, height: 162 },
    medium: { width: 170, height: 200 },
    large: { width: 238, height: 280 },
  };

  const size = posterSizes[posterSize];

  return (
    <div
      className={`poster-card poster-card--${posterSize}`}
      style={{ width: size.width }}
      onClick={onClick}
    >
      <div className="poster-card__image-container" style={{ height: size.height }}>
        <LazyImage
          src={artist.images.find((i) => i.coverType === "poster")?.url}
          alt={artist.artistName}
          fallback="/images/artist-placeholder.png"
        />

        {/* Status Overlay */}
        <div className="poster-card__status">
          <StatusIndicator status={artist.status} />
          {showMonitored && (
            <MonitorIcon monitored={artist.monitored} />
          )}
        </div>

        {/* Progress Bar */}
        <div className="poster-card__progress">
          <ProgressBar
            value={artist.statistics.trackFileCount}
            max={artist.statistics.trackCount}
            color={getProgressColor(artist.statistics)}
          />
        </div>

        {/* Hover Overlay */}
        <div className="poster-card__overlay">
          <Button icon="edit" onClick={(e) => { e.stopPropagation(); onEdit(); }} />
          <Button icon="refresh" onClick={(e) => { e.stopPropagation(); refreshArtist(artist.id); }} />
        </div>
      </div>

      {showTitle && (
        <div className="poster-card__title">
          <span className="poster-card__name">{artist.artistName}</span>
          {showQualityProfile && (
            <span className="poster-card__quality">{artist.qualityProfile?.name}</span>
          )}
        </div>
      )}
    </div>
  );
}
```

### Grid Layout

```tsx
function PosterGrid({ artists, posterSize, ...cardProps }: PosterGridProps) {
  return (
    <div
      className="poster-grid"
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(auto-fill, minmax(${posterSizes[posterSize].width}px, 1fr))`,
        gap: "16px",
      }}
    >
      {artists.map((artist) => (
        <ArtistPosterCard
          key={artist.id}
          artist={artist}
          posterSize={posterSize}
          {...cardProps}
        />
      ))}
    </div>
  );
}
```

---

## Banner View Pattern

```tsx
function ArtistBanner({ artist }: { artist: Artist }) {
  return (
    <div className="artist-banner">
      <div
        className="artist-banner__background"
        style={{
          backgroundImage: `url(${artist.images.find((i) => i.coverType === "fanart")?.url})`,
        }}
      />
      <div className="artist-banner__overlay" />

      <div className="artist-banner__content">
        <div className="artist-banner__poster">
          <img src={artist.images.find((i) => i.coverType === "poster")?.url} alt="" />
        </div>

        <div className="artist-banner__info">
          <h2 className="artist-banner__name">{artist.artistName}</h2>
          <div className="artist-banner__meta">
            <span>{artist.artistType}</span>
            <span>{artist.genres.slice(0, 3).join(", ")}</span>
            <span>{artist.status === "continuing" ? "Active" : "Inactive"}</span>
          </div>
          <div className="artist-banner__stats">
            <Stat label="Albums" value={artist.statistics.albumCount} />
            <Stat label="Tracks" value={artist.statistics.trackFileCount} />
            <Stat label="Size" value={formatBytes(artist.statistics.sizeOnDisk)} />
          </div>
        </div>

        <div className="artist-banner__actions">
          <MonitorToggle monitored={artist.monitored} artistId={artist.id} />
          <Button variant="primary">Search</Button>
          <DropdownMenu>
            <DropdownItem>Edit</DropdownItem>
            <DropdownItem>Refresh</DropdownItem>
            <DropdownItem danger>Delete</DropdownItem>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
}
```

---

## Overview/Card View Pattern

```tsx
function ArtistOverviewCard({ artist }: { artist: Artist }) {
  return (
    <div className="overview-card">
      <div className="overview-card__poster">
        <img src={artist.images.find((i) => i.coverType === "poster")?.url} alt="" />
        <StatusBadge status={artist.status} />
      </div>

      <div className="overview-card__body">
        <div className="overview-card__header">
          <h3>{artist.artistName}</h3>
          <MonitorIcon monitored={artist.monitored} />
        </div>

        <p className="overview-card__overview">
          {truncate(artist.overview, 200)}
        </p>

        <div className="overview-card__tags">
          {artist.genres.slice(0, 3).map((genre) => (
            <Tag key={genre}>{genre}</Tag>
          ))}
        </div>

        <div className="overview-card__footer">
          <div className="overview-card__stats">
            <span>{artist.statistics.albumCount} Albums</span>
            <span>{artist.statistics.trackFileCount}/{artist.statistics.trackCount} Tracks</span>
          </div>
          <QualityProfileBadge profile={artist.qualityProfile} />
        </div>
      </div>
    </div>
  );
}
```

---

## Sorting Controls

### Sort Options

```tsx
const artistSortOptions = [
  { value: "sortName", label: "Sort Name" },
  { value: "artistName", label: "Artist Name" },
  { value: "added", label: "Date Added" },
  { value: "albumCount", label: "Album Count" },
  { value: "trackCount", label: "Track Count" },
  { value: "sizeOnDisk", label: "Size on Disk" },
  { value: "ratings.value", label: "Rating" },
  { value: "path", label: "Path" },
];

const albumSortOptions = [
  { value: "title", label: "Title" },
  { value: "releaseDate", label: "Release Date" },
  { value: "trackCount", label: "Track Count" },
  { value: "sizeOnDisk", label: "Size on Disk" },
  { value: "ratings.value", label: "Rating" },
  { value: "artistName", label: "Artist Name" },
];
```

### Sort Control Component

```tsx
function SortControl({ options, value, direction, onChange, onDirectionChange }) {
  return (
    <div className="sort-control">
      <Select
        value={value}
        onChange={onChange}
        options={options}
        label="Sort by"
      />
      <IconButton
        icon={direction === "asc" ? "sort-asc" : "sort-desc"}
        onClick={() => onDirectionChange(direction === "asc" ? "desc" : "asc")}
        aria-label={`Sort ${direction === "asc" ? "ascending" : "descending"}`}
      />
    </div>
  );
}
```

---

## Album Studio View

The Album Studio is a specialized view for bulk-editing album monitoring.

```tsx
interface AlbumStudioArtist {
  id: number;
  artistName: string;
  albums: AlbumStudioAlbum[];
}

interface AlbumStudioAlbum {
  id: number;
  title: string;
  albumType: string;
  releaseDate: string;
  monitored: boolean;
  statistics: AlbumStatistics;
}

function AlbumStudio({ artists }: { artists: AlbumStudioArtist[] }) {
  const [changes, setChanges] = useState<Map<number, boolean>>(new Map());

  const handleToggle = (albumId: number, monitored: boolean) => {
    setChanges((prev) => new Map(prev).set(albumId, monitored));
  };

  const handleSave = async () => {
    const updates = Array.from(changes.entries()).map(([id, monitored]) => ({
      id,
      monitored,
    }));
    await updateAlbums(updates);
    setChanges(new Map());
  };

  return (
    <div className="album-studio">
      <div className="album-studio__header">
        <h2>Album Studio</h2>
        <div className="album-studio__actions">
          <Button
            variant="primary"
            disabled={changes.size === 0}
            onClick={handleSave}
          >
            Save Changes ({changes.size})
          </Button>
        </div>
      </div>

      <div className="album-studio__grid">
        {artists.map((artist) => (
          <div key={artist.id} className="album-studio__artist">
            <div className="album-studio__artist-header">
              <h3>{artist.artistName}</h3>
              <div className="album-studio__artist-actions">
                <Button size="small" onClick={() => monitorAll(artist, true)}>
                  Monitor All
                </Button>
                <Button size="small" onClick={() => monitorAll(artist, false)}>
                  Unmonitor All
                </Button>
              </div>
            </div>

            <div className="album-studio__albums">
              {artist.albums.map((album) => {
                const isMonitored = changes.has(album.id)
                  ? changes.get(album.id)
                  : album.monitored;

                return (
                  <div
                    key={album.id}
                    className={`album-studio__album ${isMonitored ? "monitored" : ""}`}
                    onClick={() => handleToggle(album.id, !isMonitored)}
                  >
                    <div className="album-studio__album-info">
                      <span className="album-studio__album-title">{album.title}</span>
                      <span className="album-studio__album-meta">
                        {album.albumType} • {formatDate(album.releaseDate)}
                      </span>
                    </div>
                    <div className="album-studio__album-progress">
                      <ProgressBar
                        value={album.statistics.trackFileCount}
                        max={album.statistics.trackCount}
                        size="small"
                      />
                    </div>
                    <MonitorIcon monitored={isMonitored} size="small" />
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## Bulk Selection & Actions

### Selection State Management

```tsx
interface SelectionState<T> {
  selectedIds: Set<number>;
  selectItem: (id: number) => void;
  deselectItem: (id: number) => void;
  toggleItem: (id: number) => void;
  selectAll: (items: T[]) => void;
  deselectAll: () => void;
  isSelected: (id: number) => boolean;
  selectedCount: number;
}

function useSelection<T extends { id: number }>(): SelectionState<T> {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const selectItem = (id: number) => {
    setSelectedIds((prev) => new Set(prev).add(id));
  };

  const deselectItem = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const toggleItem = (id: number) => {
    selectedIds.has(id) ? deselectItem(id) : selectItem(id);
  };

  const selectAll = (items: T[]) => {
    setSelectedIds(new Set(items.map((i) => i.id)));
  };

  const deselectAll = () => {
    setSelectedIds(new Set());
  };

  return {
    selectedIds,
    selectItem,
    deselectItem,
    toggleItem,
    selectAll,
    deselectAll,
    isSelected: (id) => selectedIds.has(id),
    selectedCount: selectedIds.size,
  };
}
```

### Bulk Action Bar

```tsx
function BulkActionBar({
  selectedCount,
  onEdit,
  onDelete,
  onUpdateMonitored,
  onUpdateTags,
  onDeselectAll,
}: BulkActionBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="bulk-action-bar">
      <span className="bulk-action-bar__count">
        {selectedCount} selected
      </span>

      <div className="bulk-action-bar__actions">
        <Button variant="ghost" onClick={onDeselectAll}>
          Deselect All
        </Button>
        <Button onClick={() => onUpdateMonitored(true)}>
          Monitor
        </Button>
        <Button onClick={() => onUpdateMonitored(false)}>
          Unmonitor
        </Button>
        <Button onClick={onEdit}>
          Edit
        </Button>
        <Button onClick={onUpdateTags}>
          Tags
        </Button>
        <Button variant="danger" onClick={onDelete}>
          Delete
        </Button>
      </div>
    </div>
  );
}
```

---

## View Options Panel

```tsx
interface ViewOptions {
  viewMode: "table" | "poster" | "banner" | "overview";
  posterSize: "small" | "medium" | "large";
  showTitle: boolean;
  showMonitored: boolean;
  showQualityProfile: boolean;
  sortKey: string;
  sortDirection: "asc" | "desc";
  visibleColumns: string[];
}

function ViewOptionsPanel({ options, onChange }: ViewOptionsPanelProps) {
  return (
    <Popover
      trigger={<IconButton icon="settings" aria-label="View Options" />}
    >
      <div className="view-options">
        <section>
          <h4>View Mode</h4>
          <SegmentedControl
            value={options.viewMode}
            onChange={(viewMode) => onChange({ ...options, viewMode })}
            options={[
              { value: "table", icon: "list" },
              { value: "poster", icon: "grid" },
              { value: "banner", icon: "rows" },
              { value: "overview", icon: "cards" },
            ]}
          />
        </section>

        {options.viewMode === "poster" && (
          <section>
            <h4>Poster Size</h4>
            <SegmentedControl
              value={options.posterSize}
              onChange={(posterSize) => onChange({ ...options, posterSize })}
              options={[
                { value: "small", label: "S" },
                { value: "medium", label: "M" },
                { value: "large", label: "L" },
              ]}
            />
          </section>
        )}

        {options.viewMode !== "table" && (
          <section>
            <h4>Display Options</h4>
            <Checkbox
              label="Show Title"
              checked={options.showTitle}
              onChange={(showTitle) => onChange({ ...options, showTitle })}
            />
            <Checkbox
              label="Show Monitored Status"
              checked={options.showMonitored}
              onChange={(showMonitored) => onChange({ ...options, showMonitored })}
            />
            <Checkbox
              label="Show Quality Profile"
              checked={options.showQualityProfile}
              onChange={(showQualityProfile) => onChange({ ...options, showQualityProfile })}
            />
          </section>
        )}

        {options.viewMode === "table" && (
          <section>
            <h4>Columns</h4>
            {allColumns.map((col) => (
              <Checkbox
                key={col.id}
                label={col.label}
                checked={options.visibleColumns.includes(col.id)}
                onChange={() => toggleColumn(col.id)}
              />
            ))}
          </section>
        )}
      </div>
    </Popover>
  );
}
```

---

## CSS Patterns

### Table Styles (Light Mode)

```css
.library-table {
  width: 100%;
  border-collapse: collapse;
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  overflow: hidden;
}

.library-table th {
  background: #f8f9fa;
  color: #374151;
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #e5e5e5;
}

.library-table th.sortable {
  cursor: pointer;
  user-select: none;
}

.library-table th.sortable:hover {
  background: #f0f1f3;
}

.library-table td {
  padding: 12px 16px;
  border-bottom: 1px solid #e5e5e5;
  color: #1f2937;
}

.library-table tr:hover {
  background: #f8f9fa;
}

.library-table tr.selected {
  background: #eff6ff;
}
```

### Poster Grid Styles

```css
.poster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 20px;
  padding: 20px;
}

.poster-card {
  position: relative;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.poster-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

.poster-card__image-container {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  background: #e5e5e5;
}

.poster-card__image-container img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.poster-card__overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.poster-card:hover .poster-card__overlay {
  opacity: 1;
}

.poster-card__progress {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 4px;
}

.poster-card__title {
  padding: 8px 4px;
  text-align: center;
}

.poster-card__name {
  display: block;
  font-weight: 500;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.poster-card__quality {
  display: block;
  font-size: 0.75rem;
  color: #6b7280;
}
```

### Filter Bar Styles

```css
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #ffffff;
  border-bottom: 1px solid #e5e5e5;
  gap: 16px;
}

.filter-bar__controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-bar__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-28  
**Status**: Draft
