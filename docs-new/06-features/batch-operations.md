# Batch Operations

**Category:** Features  
**Status:** ✅ Active  
**Last Updated:** 2025-12-12  
**Related Docs:** [API Reference](../03-api-reference/) | [Metadata Enrichment](./metadata-enrichment.md)

---

## Overview

Batch Processor is a generic utility for efficient batching of API calls to external services (Spotify, MusicBrainz, etc.). Dramatically reduces API request count and respects rate limits better.

**Example:**
- **Without Batching:** 100 tracks = 100 Spotify API calls
- **With Batching:** 100 tracks = 2 Spotify API calls (50 per batch)

---

## Features

- **Generic Design:** Works with arbitrary API functions (Spotify, MusicBrainz, etc.)
- **Automatic Batching:** Collects items and processes at `batch_size` automatically
- **Manual Flush:** Force processing before shutdown or on timer
- **Time-Based Auto-Flush:** Automatic processing after `max_wait_time` (items don't wait forever)
- **Error Handling:** Partial failure support - individual items can fail
- **Thread-Safe:** AsyncIO lock prevents race conditions
- **Metrics:** Success rate, failed items with exception details

---

## Core Concepts

### Batch Result

```python
@dataclass
class BatchResult[R]:
    successful: list[R]              # Successfully processed items
    failed: list[tuple[Any, Exception]]  # Failed items with exception
    
    # Computed Properties
    @property
    def total_items(self) -> int:     # successful + failed count
    def success_count(self) -> int:   # Successful items count
    def failure_count(self) -> int:   # Failed items count
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

# Define batch processor function
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

### Batch Add (Multiple Items at Once)

```python
# Add multiple items and get all batch results
track_ids = [f"track_{i}" for i in range(150)]
results = await processor.add_batch(track_ids)

# Results is list of BatchResults (one per batch)
total_success = sum(r.success_count for r in results)
total_failed = sum(r.failure_count for r in results)
print(f"Total: {total_success} success, {total_failed} failed")
```

---

### Manual Flush Control

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

---

### Time-Based Flush

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
```

---

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `batch_size` | int | Required | Items per batch |
| `processor_func` | Callable | Required | Function to process batch |
| `max_wait_time` | float | None | Max wait time before flush (seconds) |
| `auto_flush` | bool | True | Auto-process at batch_size |

---

## Error Handling

```python
# Partial failure handling
result = await processor.flush()

# Check for failures
if result.failure_count > 0:
    logger.warning(f"{result.failure_count} items failed")
    
    # Log each failure
    for item, exception in result.failed:
        logger.error(f"Failed: {item} - {exception}")
        
    # Retry failed items
    retry_items = [item for item, _ in result.failed]
    retry_results = await processor.add_batch(retry_items)
```

---

## Performance Metrics

```python
# Track performance
total_processed = 0
total_time = 0

for i in range(10):
    start = time.time()
    result = await processor.flush()
    elapsed = time.time() - start
    
    total_processed += result.total_items
    total_time += elapsed
    
    print(f"Batch {i}: {result.success_count} items in {elapsed:.2f}s")

avg_time_per_batch = total_time / 10
throughput = total_processed / total_time
print(f"Avg: {avg_time_per_batch:.2f}s per batch, {throughput:.1f} items/sec")
```

---

## Related Documentation

- **[Metadata Enrichment](./metadata-enrichment.md)** - Uses batch processing
- **[API Reference](../03-api-reference/)** - API endpoint documentation

---

**Last Validated:** 2025-12-12  
**Implementation Status:** ✅ Production-ready
