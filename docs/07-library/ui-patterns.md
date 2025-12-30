# Library UI Patterns

**Category:** Library Management  
**Status:** ✅ Active  
**Last Updated:** 2025-12-30  
**Related:** [Component Library](../08-ui-components/component-library.md), [Workflows](./workflows.md), [Data Models](./data-models.md)

---

## Overview

UI patterns for SoulSpot's library management views, inspired by Lidarr's powerful browsing and filtering capabilities. Supports multiple view modes, advanced filtering, and bulk operations.

## View Modes

### Artist Index View Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **Table** | Dense list with sortable columns | Large collections, quick scanning, power users |
| **Poster** | Grid of artist images | Visual browsing, discovery |
| **Banner** | Wide banners with artist info | Featured/highlighted artists |
| **Overview** | Cards with descriptions | Discovering new artists |

### Album View Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **Table** | Detailed album listing with columns | Managing releases, sorting |
| **Album Studio** | Compact monitoring grid | Bulk monitoring changes |

## Table View Pattern

### Artist Table Columns

**Available Columns:**

| Column | Sortable | Default Visible | Description |
|--------|----------|-----------------|-------------|
| Status | No | Yes | Monitoring/ended indicator |
| Artist | Yes | Yes | Artist name (clickable) |
| Type | Yes | Yes | Person, Group, Orchestra, etc. |
| Quality | Yes | Yes | Quality profile name |
| Path | Yes | No | Folder path on disk |
| Size | Yes | Yes | Total library size (GB) |
| Genres | No | No | Genre tags |
| Rating | Yes | No | User/community rating |
| Added | Yes | Yes | Date added to library |
| Albums | Yes | Yes | Album count |
| Tracks | Yes | Yes | Track file count |
| Actions | No | Yes | Quick action buttons |

**Component Structure:**

```tsx
// React/TypeScript pattern
interface TableViewProps<T> {
  items: T[];
  columns: ColumnDefinition[];
  visibleColumns: string[];
  sortKey: string;
  sortDirection: "asc" | "desc";
  onSort: (key: string) => void;
  selectedIds: Set<number>;
  onSelect: (id: number) => void;
  onSelectAll: () => void;
}

// Column definition
interface ColumnDefinition {
  id: string;
  label: string;
  sortable: boolean;
  defaultVisible: boolean;
  width?: string;
}
```

### Album Table Columns

| Column | Sortable | Default Visible | Description |
|--------|----------|-----------------|-------------|
| Monitored | No | Yes | Checkbox toggle |
| Album | Yes | Yes | Album title (clickable) |
| Artist | Yes | Yes | Artist name |
| Type | Yes | Yes | Studio, EP, Single, etc. |
| Release | Yes | Yes | Release date |
| Tracks | Yes | Yes | Track count |
| Size | Yes | Yes | Disk space used |
| Progress | Yes | Yes | Completion percentage |
| Duration | Yes | No | Total runtime |
| Actions | No | Yes | Quick actions |

## Poster View Pattern

### Artist Poster Grid

```html
<div class="poster-grid">
  <div class="poster-card" data-artist-id="1">
    <div class="poster-image">
      <img src="/images/artists/1/poster.jpg" alt="Michael Jackson" loading="lazy">
      <div class="poster-overlay">
        <button class="btn-edit">Edit</button>
        <button class="btn-search">Search</button>
      </div>
    </div>
    <div class="poster-info">
      <h3 class="artist-name">Michael Jackson</h3>
      <div class="statistics">
        <span class="album-count">12 albums</span>
        <span class="track-count">147 tracks</span>
      </div>
      <div class="status-icons">
        <span class="monitored">👁️</span>
        <span class="quality">FLAC</span>
      </div>
    </div>
  </div>
</div>
```

**CSS Grid Layout:**

```css
.poster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
  padding: 20px;
}

.poster-card {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  transition: transform 0.2s;
}

.poster-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.2);
}

.poster-image {
  aspect-ratio: 1;
  overflow: hidden;
}

.poster-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.7);
  opacity: 0;
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s;
}

.poster-card:hover .poster-overlay {
  opacity: 1;
}
```

## Filtering Pattern

### Filter Bar

```html
<div class="filter-bar">
  <div class="filter-group">
    <label>Monitored</label>
    <select name="monitored">
      <option value="all">All</option>
      <option value="monitored">Monitored Only</option>
      <option value="unmonitored">Unmonitored Only</option>
    </select>
  </div>
  
  <div class="filter-group">
    <label>Status</label>
    <select name="status">
      <option value="all">All</option>
      <option value="continuing">Continuing</option>
      <option value="ended">Ended</option>
    </select>
  </div>
  
  <div class="filter-group">
    <label>Quality Profile</label>
    <select name="qualityProfile">
      <option value="">All Profiles</option>
      <option value="1">Lossless</option>
      <option value="2">High Quality</option>
      <option value="3">Any Quality</option>
    </select>
  </div>
  
  <div class="filter-group">
    <label>Search</label>
    <input type="search" name="search" placeholder="Filter by name...">
  </div>
  
  <button class="btn-reset-filters">Reset Filters</button>
</div>
```

### Filter State Management

```typescript
interface FilterState {
  monitored: "all" | "monitored" | "unmonitored";
  status: "all" | "continuing" | "ended";
  qualityProfileId: number | null;
  search: string;
  tags: number[];
}

function applyFilters(items: Artist[], filters: FilterState): Artist[] {
  return items.filter(artist => {
    if (filters.monitored !== "all" && artist.monitored !== (filters.monitored === "monitored")) {
      return false;
    }
    if (filters.status !== "all" && artist.status !== filters.status) {
      return false;
    }
    if (filters.qualityProfileId && artist.qualityProfileId !== filters.qualityProfileId) {
      return false;
    }
    if (filters.search && !artist.artistName.toLowerCase().includes(filters.search.toLowerCase())) {
      return false;
    }
    return true;
  });
}
```

## Bulk Operations Pattern

### Selection Mode

```html
<!-- Checkbox in table header -->
<th class="select-cell">
  <input type="checkbox" id="select-all" />
</th>

<!-- Checkbox in table row -->
<td class="select-cell">
  <input type="checkbox" class="select-item" data-id="1" />
</td>

<!-- Bulk action toolbar (appears when items selected) -->
<div class="bulk-actions" style="display: none;">
  <span class="selection-count">3 items selected</span>
  <button class="btn-bulk-edit">Edit</button>
  <button class="btn-bulk-monitor">Monitor</button>
  <button class="btn-bulk-delete">Delete</button>
  <button class="btn-clear-selection">Clear</button>
</div>
```

### Bulk Edit Modal

```html
<dialog id="bulk-edit-dialog">
  <h2>Edit 3 Artists</h2>
  <form>
    <div class="form-group">
      <label>
        <input type="checkbox" name="change_quality_profile" />
        Quality Profile
      </label>
      <select name="quality_profile_id" disabled>
        <option value="1">Lossless</option>
        <option value="2">High Quality</option>
      </select>
    </div>
    
    <div class="form-group">
      <label>
        <input type="checkbox" name="change_monitored" />
        Monitored
      </label>
      <select name="monitored" disabled>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    </div>
    
    <div class="form-group">
      <label>
        <input type="checkbox" name="change_tags" />
        Tags
      </label>
      <select name="tags" multiple disabled>
        <option value="1">Classical</option>
        <option value="2">Jazz</option>
      </select>
    </div>
    
    <div class="form-actions">
      <button type="button" class="btn-cancel">Cancel</button>
      <button type="submit" class="btn-apply">Apply Changes</button>
    </div>
  </form>
</dialog>
```

## Progress Indicators

### Album Completeness Bar

```html
<div class="progress-bar-container">
  <div class="progress-bar" style="width: 75%;">
    <span class="progress-label">75% (9/12 tracks)</span>
  </div>
</div>
```

**Color Coding:**
- 100%: Green (complete)
- 50-99%: Yellow (incomplete)
- 0-49%: Red (mostly missing)

### Loading States

```html
<!-- Skeleton loader for table rows -->
<tr class="skeleton-row">
  <td><div class="skeleton-box" style="width: 40px;"></div></td>
  <td><div class="skeleton-box" style="width: 200px;"></div></td>
  <td><div class="skeleton-box" style="width: 80px;"></div></td>
</tr>

<!-- Spinner for actions -->
<button class="btn-loading" disabled>
  <span class="spinner"></span>
  Searching...
</button>
```

## Related Documentation

- [Component Library](../08-ui-components/component-library.md) - Reusable UI components
- [Workflows](./workflows.md) - User workflows and processes
- [Data Models](./data-models.md) - Entity data structures
- [API Reference](./api-reference.md) - Backend endpoints
