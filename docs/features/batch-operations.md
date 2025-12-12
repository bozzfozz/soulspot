# Batch Operations

> **Version:** 1.0  
> **Status:** ✅ Active  
> **Last Updated:** 2025-12-12  
> **Service:** `src/soulspot/application/services/batch_processor.py`

---

## Overview

Der Batch Processor ist ein generisches Utility für effizientes Batching von API-Aufrufen an externe Services (Spotify, MusicBrainz, etc.). Reduziert die Anzahl der API-Requests drastisch und respektiert Rate-Limits besser.

**Beispiel:**
- **Ohne Batching:** 100 Tracks = 100 Spotify API Calls
- **Mit Batching:** 100 Tracks = 2 Spotify API Calls (50 pro Batch)

---

## Key Features

- **Generic Design**: Funktioniert mit beliebigen API-Funktionen (Spotify, MusicBrainz, etc.)
- **Automatic Batching**: Sammelt Items und verarbeitet bei `batch_size` automatisch
- **Manual Flush**: Erzwungene Verarbeitung vor Shutdown oder auf Timer
- **Time-Based Auto-Flush**: Automatische Verarbeitung nach `max_wait_time` (Items nicht endlos warten)
- **Error Handling**: Partial Failure Support - einzelne Items können fehlschlagen
- **Thread-Safe**: AsyncIO Lock verhindert Race-Conditions
- **Metrics**: Success Rate, Failed Items mit Exception Details

---

## Core Concepts

### Batch Result

```python
@dataclass
class BatchResult[R]:
    successful: list[R]              # Erfolgreich verarbeitete Items
    failed: list[tuple[Any, Exception]]  # Fehlgeschlagene Items mit Exception
    
    # Computed Properties
    @property
    def total_items(self) -> int:     # successful + failed count
    def success_count(self) -> int:   # Anzahl erfolgreicher Items
    def failure_count(self) -> int:   # Anzahl fehlgeschlagener Items
    def success_rate(self) -> float:  # Success rate in % (0-100)
```

**Example Usage:**
```python
result = await processor.flush()
print(f"Processed {result.total_items} items")
print(f"Success: {result.success_count}, Failed: {result.failure_count}")
print(f"Success Rate: {result.success_rate:.1f}%")

# Handle failures
for item, exception in result.failed:
    logger.error(f"Failed to process {item}: {exception}")
```

---

## Basic Usage

### Simple Batch Processing

```python
from soulspot.application.services.batch_processor import BatchProcessor

# Define your batch processor function
async def fetch_tracks_from_spotify(track_ids: list[str]) -> list[Track]:
    """Fetch multiple tracks in one API call."""
    response = await spotify_api.get_tracks(track_ids)
    return [Track.from_spotify(t) for t in response['tracks']]

# Create batch processor
processor = BatchProcessor[str, Track](
    batch_size=50,                      # Process 50 tracks at a time
    processor_func=fetch_tracks_from_spotify,
    max_wait_time=5.0,                  # Auto-flush after 5 seconds
    auto_flush=True                     # Auto-process when batch is full
)

# Add items one by one (auto-flushes at 50 items)
for track_id in track_ids:
    result = await processor.add(track_id)
    if result:  # Returns BatchResult if auto-flushed
        print(f"Auto-flushed: {result.success_count} tracks processed")

# Flush remaining items (< 50)
final_result = await processor.flush()
print(f"Final flush: {final_result.success_count} tracks processed")
```

---

## Advanced Patterns

### 1. Batch Add (Multiple Items at Once)

```python
# Add multiple items and get all batch results
track_ids = [f"track_{i}" for i in range(150)]
results = await processor.add_batch(track_ids)

# Results is list of BatchResults (one per batch)
total_success = sum(r.success_count for r in results)
total_failed = sum(r.failure_count for r in results)
print(f"Total: {total_success} success, {total_failed} failed")
```

### 2. Manual Flush Control

```python
# Disable auto-flush for full manual control
processor = BatchProcessor(
    batch_size=50,
    processor_func=fetch_tracks,
    auto_flush=False  # No automatic processing
)

# Add items without processing
for track_id in track_ids:
    await processor.add(track_id)  # Always returns None (no auto-flush)

# Check pending count
print(f"{processor.get_pending_count()} items pending")

# Manually trigger processing when ready
result = await processor.flush()
```

### 3. Time-Based Flush

```python
import asyncio

processor = BatchProcessor(
    batch_size=100,
    processor_func=fetch_tracks,
    max_wait_time=10.0,  # Flush after 10 seconds
    auto_flush=True
)

# Background task for time-based flushing
async def periodic_flush():
    while True:
        await asyncio.sleep(1)  # Check every second
        result = await processor.flush_if_needed()
        if result:
            print(f"Time-based flush: {result.success_count} items")

# Start background task
asyncio.create_task(periodic_flush())

# Add items slowly (< batch_size)
for track_id in track_ids:
    await processor.add(track_id)
    await asyncio.sleep(0.5)  # Simulate slow input
    # → Auto-flushes after 10s even if batch not full
```

### 4. Graceful Shutdown

```python
async def shutdown():
    """Flush remaining items before exit."""
    try:
        final_result = await processor.close()
        print(f"Shutdown: {final_result.success_count} items processed")
    except Exception as e:
        logger.error(f"Shutdown flush failed: {e}")
```

---

## Configuration Strategies

### Batch Size Tuning

```python
# Small batches (faster feedback, more API calls)
processor = BatchProcessor(batch_size=10)
# Pros: Low latency, quick failures
# Cons: More API calls, rate-limit risk

# Medium batches (balanced - RECOMMENDED)
processor = BatchProcessor(batch_size=50)
# Pros: Good balance, most APIs support 50-100 items
# Cons: None

# Large batches (fewer API calls, slower feedback)
processor = BatchProcessor(batch_size=100)
# Pros: Fewer API calls, better for rate-limits
# Cons: Higher latency, larger failure scope
```

### Wait Time Tuning

```python
# Short wait (responsive, more flushes)
processor = BatchProcessor(max_wait_time=2.0)
# Use: Real-time UI updates, interactive features

# Medium wait (balanced - RECOMMENDED)
processor = BatchProcessor(max_wait_time=5.0)
# Use: Background tasks, async operations

# Long wait (efficient, batch-focused)
processor = BatchProcessor(max_wait_time=30.0)
# Use: Scheduled jobs, bulk imports
```

---

## API-Specific Examples

### Spotify API Batching

```python
# Spotify allows 50 tracks per /tracks endpoint
async def fetch_spotify_tracks(track_ids: list[str]) -> list[Track]:
    # Spotify API: GET /v1/tracks?ids=id1,id2,...,id50
    response = await spotify_client.get_tracks(track_ids)
    return [Track.from_dict(t) for t in response['tracks']]

processor = BatchProcessor[str, Track](
    batch_size=50,  # Spotify limit
    processor_func=fetch_spotify_tracks,
    max_wait_time=3.0
)

# Usage: Fetch 200 tracks with 4 API calls
track_ids = ["spotify:track:xxx" for _ in range(200)]
results = await processor.add_batch(track_ids)
# → 4 batches (50+50+50+50), 4 API calls
```

### MusicBrainz API Batching

```python
# MusicBrainz rate-limit: 1 request/second
async def fetch_musicbrainz_releases(mbids: list[str]) -> list[Album]:
    results = []
    for mbid in mbids:  # No native batch endpoint
        album = await musicbrainz_client.get_release(mbid)
        results.append(album)
        await asyncio.sleep(1.0)  # Respect rate-limit
    return results

processor = BatchProcessor[str, Album](
    batch_size=5,  # Small batches (rate-limited API)
    processor_func=fetch_musicbrainz_releases,
    max_wait_time=10.0
)

# Usage: 20 MBIDs = 4 batches, 20 seconds total (1 req/sec)
mbids = ["mbid-xxx" for _ in range(20)]
results = await processor.add_batch(mbids)
```

---

## Error Handling Patterns

### Partial Failure Handling

```python
result = await processor.flush()

# Process successful items
for track in result.successful:
    await save_to_database(track)
    logger.info(f"Saved track: {track.title}")

# Retry failed items individually
for item, exception in result.failed:
    logger.error(f"Failed to process {item}: {exception}")
    # Option 1: Retry immediately
    try:
        track = await fetch_single_track(item)
        await save_to_database(track)
    except Exception as e:
        # Option 2: Queue for later retry
        await retry_queue.add(item)
```

### Complete Batch Failure

```python
# If processor_func raises exception, ALL items marked as failed
result = await processor.flush()

if result.failure_count == result.total_items:
    logger.critical("Complete batch failure - API down?")
    # Exponential backoff retry
    for attempt in range(3):
        await asyncio.sleep(2 ** attempt)
        retry_result = await processor.add_batch([item for item, _ in result.failed])
        if retry_result[0].success_count > 0:
            break
```

---

## Performance Considerations

### Memory Usage

```python
# Monitor pending items to prevent memory bloat
if processor.get_pending_count() > 1000:
    logger.warning("Too many pending items - forcing flush")
    await processor.flush()
```

### Rate Limit Integration

```python
from datetime import datetime, timedelta

class RateLimitedBatchProcessor(BatchProcessor):
    def __init__(self, *args, rate_limit_per_minute=60, **kwargs):
        super().__init__(*args, **kwargs)
        self.rate_limit = rate_limit_per_minute
        self.request_times = []
    
    async def _flush_internal(self):
        # Check rate-limit before flushing
        now = datetime.now()
        self.request_times = [t for t in self.request_times 
                              if now - t < timedelta(minutes=1)]
        
        if len(self.request_times) >= self.rate_limit:
            wait_time = (self.request_times[0] + timedelta(minutes=1) - now).total_seconds()
            logger.info(f"Rate-limited: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        
        result = await super()._flush_internal()
        self.request_times.append(now)
        return result
```

---

## Monitoring & Metrics

### Success Rate Tracking

```python
class MetricsBatchProcessor(BatchProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_processed = 0
        self.total_failed = 0
    
    async def _flush_internal(self):
        result = await super()._flush_internal()
        self.total_processed += result.success_count
        self.total_failed += result.failure_count
        return result
    
    def get_stats(self):
        total = self.total_processed + self.total_failed
        success_rate = (self.total_processed / total * 100) if total > 0 else 0
        return {
            "total_processed": self.total_processed,
            "total_failed": self.total_failed,
            "success_rate": f"{success_rate:.1f}%"
        }
```

### Logging Integration

```python
import logging

logger = logging.getLogger(__name__)

async def logged_processor_func(items):
    logger.info(f"[BATCH] Processing {len(items)} items")
    try:
        results = await actual_processor(items)
        logger.info(f"[BATCH] Success: {len(results)} items")
        return results
    except Exception as e:
        logger.error(f"[BATCH] Failed: {e}")
        raise
```

---

## Testing Strategies

### Unit Tests

```python
import pytest

@pytest.mark.asyncio
async def test_batch_processing():
    # Mock processor function
    async def mock_processor(items):
        return [f"processed_{item}" for item in items]
    
    processor = BatchProcessor(
        batch_size=3,
        processor_func=mock_processor,
        auto_flush=True
    )
    
    # Add 5 items (triggers auto-flush at 3)
    result1 = await processor.add("item1")
    result2 = await processor.add("item2")
    result3 = await processor.add("item3")  # Triggers flush
    
    assert result3 is not None
    assert result3.success_count == 3
    
    # Remaining 2 items
    await processor.add("item4")
    await processor.add("item5")
    result_final = await processor.flush()
    
    assert result_final.success_count == 2
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_spotify_batch_integration():
    # Real Spotify client (test credentials)
    processor = BatchProcessor(
        batch_size=50,
        processor_func=spotify_client.get_tracks,
        max_wait_time=5.0
    )
    
    # Add 100 real track IDs
    track_ids = await get_test_track_ids(100)
    results = await processor.add_batch(track_ids)
    
    # Verify 2 batches (50+50)
    assert len(results) == 2
    assert all(r.success_count == 50 for r in results)
```

---

## Related Features

- **[Spotify Sync](./spotify-sync.md)** - Bulk playlist/artist sync
- **[Download Management](./download-management.md)** - Batch download operations
- **[Metadata Enrichment](./metadata-enrichment.md)** - Batch metadata fetching
- **[Library Management](./library-management.md)** - Bulk library operations

---

## Troubleshooting

### Memory Leak (Too Many Pending Items)
**Symptom:** `get_pending_count()` keeps growing  
**Cause:** Items added faster than processed  
**Solution:**
```python
# Force flush when pending exceeds threshold
if processor.get_pending_count() > 500:
    await processor.flush()
```

### Deadlock (Lock Never Released)
**Symptom:** `add()` hangs forever  
**Cause:** Exception in `_flush_internal()` without cleanup  
**Solution:** Always use `try/finally` for lock cleanup (built-in)

### Rate-Limit Exceeded
**Symptom:** 429 Too Many Requests from API  
**Cause:** `batch_size` too aggressive  
**Solution:** Reduce `batch_size` and increase `max_wait_time`

### Items Lost on Shutdown
**Symptom:** Last batch not processed  
**Cause:** Missing `close()` call  
**Solution:**
```python
try:
    # ... processing ...
finally:
    await processor.close()  # Flush remaining items
```

---

**Version:** 1.0 · **Status:** Active · **Service:** `batch_processor.py`
