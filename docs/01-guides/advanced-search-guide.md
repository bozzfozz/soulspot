# Advanced Search Guide

**Category:** User Guide  
**Version:** 1.0  
**Last Updated:** 2025-01  
**Audience:** Users

---

## Overview

Advanced Search provides powerful filtering, autocomplete, bulk actions, and search history management.

**Access:** Navigate to **Search** or visit `/ui/search`

---

## Features

### 1. Search Bar with Autocomplete

**Basic Search:**
- Type track/artist/album name → Press Enter or click Search

**Search Tips:**
- Track name: "Bohemian Rhapsody"
- Artist: "Queen"
- Album: "A Night at the Opera"
- Combined: "Queen Bohemian Rhapsody"

**Autocomplete:**
- Type 2+ characters → Wait 300ms for suggestions
- Shows up to 5 Spotify suggestions
- Click suggestion or use arrow keys

**Keyboard Navigation:**
- `↓` / `↑` = Navigate suggestions
- `Enter` = Select highlighted
- `Esc` = Close dropdown

---

### 2. Advanced Filters Panel

Located on left sidebar for refining results.

**Quality Filter:**
- **FLAC (Lossless)** - Highest quality
- **320kbps MP3** - High quality
- **256kbps+** - Good quality
- **Any Quality** - No restrictions (default)

**Artist Filter:** Enter artist name → Real-time filtering

**Album Filter:** Enter album name → Partial matches

**Duration Filter:**
- **Short** - Less than 3 minutes
- **Medium** - 3 to 5 minutes
- **Long** - More than 5 minutes

**Clear All Filters:** Reset all to default

---

### 3. Search Results

**Result Cards show:**
- Track name, artist(s), album, duration
- Checkbox for bulk selection
- Action buttons (Download, Spotify link)

**Expand Details:** Click ▼ to see:
- Track ID, Spotify URI
- Full duration, complete album info

**Individual Actions:**
- **Download** button - Download track immediately
- **Spotify** button - Open in Spotify
- **Checkbox** - Add to bulk selection

---

### 4. Bulk Actions

Select multiple tracks for batch operations.

**How to Select:**
1. **Individual:** Click checkbox on track card
2. **Select All:** Check "Select All" in bulk actions bar
3. **Clear:** Click "Clear Selection"

**Bulk Actions Bar (when tracks selected):**
- Number selected
- Select All checkbox
- Download Selected button
- Clear Selection button

**Bulk Download:**
- Click "Download Selected"
- System queues all downloads
- Shows progress toasts
- Displays success/failure count
- Clears selection automatically

---

### 5. Search History

Recent searches saved for quick access.

**Features:**
- **Auto-Save:** Every search saved automatically
- **Max 10 Searches:** Most recent only
- **No Duplicates:** Repeated searches don't duplicate
- **Click to Search:** Click history item to repeat
- **Persistent:** Saved in browser localStorage

**Clear History:** Click "Clear" button

---

## Keyboard Shortcuts

**Global:**
- `Tab` = Navigate between elements
- `Enter` = Activate buttons, submit search
- `Esc` = Close autocomplete dropdown

**Search Bar:**
- `Ctrl/Cmd + K` = Focus search input
- `↓` / `↑` = Navigate suggestions
- `Enter` = Submit or select suggestion

**Results:**
- `Tab` = Navigate track cards
- `Space` = Toggle checkbox on focused track
- `Enter` = Expand/collapse details

---

## Tips & Best Practices

### Effective Searching
- **Be Specific:** Include artist + track name
- **Use Filters:** Narrow results with quality/duration
- **Check History:** Reuse previous searches
- **Bulk Download:** Select multiple to save time

### Quality Selection
- **Archival:** FLAC for lossless
- **Most Uses:** 320kbps MP3 excellent quality
- **Compatibility:** "Any Quality" finds more results

### Managing Results
- Use filters AFTER searching
- Expand details to verify correct version
- Check Spotify link if unsure
- Use bulk download for albums/playlists

---

## Troubleshooting

### No Autocomplete Suggestions

**Solutions:**
- Ensure authenticated with Spotify (`/ui/auth`)
- Type at least 2 characters
- Wait 300ms after stopping typing
- Check browser console for errors

### Search Returns No Results

**Solutions:**
- Try different query
- Remove some filters
- Check spelling
- Use more general terms

### Download Fails

**Solutions:**
- Ensure authenticated with Spotify
- Check track availability in your region
- Verify Soulseek connection
- Try different quality

### Filters Not Working

**Solutions:**
- Perform search first (filters work on results)
- Clear filters and retry
- Refresh page
- Check browser console

---

## Examples

**Example 1: Find Specific Track**
```
1. Type "Bohemian Rhapsody Queen"
2. Select from autocomplete or Enter
3. Use Quality filter for FLAC
4. Click Download
```

**Example 2: Bulk Download Album**
```
1. Search "Dark Side of the Moon"
2. Apply Artist filter: "Pink Floyd"
3. Click "Select All"
4. Click "Download Selected"
```

**Example 3: Filter by Duration**
```
1. Search "Metallica"
2. Apply Duration: "Long (> 5 min)"
3. Results show only songs longer than 5 minutes
```

---

## FAQs

**Q: Search without Spotify authentication?**  
A: No, search uses Spotify API (requires auth). Visit `/ui/auth` to connect.

**Q: How many tracks for bulk download?**  
A: No hard limit, but recommend batches of 20-30 for performance.

**Q: Search history sync across devices?**  
A: No, stored locally in browser. Each device maintains own history.

**Q: Export search results?**  
A: Not currently, but can select + download all using bulk actions.

**Q: What if download fails?**  
A: System shows error message. Retry individual tracks or check Downloads page.

---

## Technical Details

**Browser Storage:** localStorage saves search history (max 10 entries)

**Data Privacy:**
- Searches go directly to Spotify API
- History stays in browser
- No search data sent to external servers
- Clear browser data to remove history

**Browser Compatibility:**
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Requires JavaScript enabled

---

## Related Documentation

- [User Guide](./user-guide.md) - Feature documentation
- [Keyboard Navigation Guide](../../guides/developer/keyboard-navigation.md) - Full shortcuts

---

**Version:** 1.0  
**Last Updated:** 2025-01
