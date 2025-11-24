# Testing Guide

Comprehensive guide for testing SoulSpot, including unit tests, integration tests, and test-driven development practices.

## Table of Contents

- [Testing Overview](#testing-overview)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Test Structure](#test-structure)
- [Testing Best Practices](#testing-best-practices)
- [Mocking and Fixtures](#mocking-and-fixtures)
- [Coverage](#coverage)
- [Continuous Integration](#continuous-integration)

---

## Testing Overview

SoulSpot uses a comprehensive testing strategy to ensure code quality and reliability.

### Testing Framework

- **Test Runner:** pytest 8.3+
- **Async Support:** pytest-asyncio
- **Mocking:** pytest-mock, unittest.mock
- **HTTP Mocking:** pytest-httpx
- **Coverage:** pytest-cov
- **Fixtures:** pytest fixtures + factory-boy

### Test Types

1. **Unit Tests** - Test individual components in isolation
2. **Integration Tests** - Test components working together
3. **End-to-End Tests** - Test complete user workflows (planned)

### Current Test Coverage

```
Total Tests: 228
Unit Tests: 221
Integration Tests: 7
Success Rate: 100%
```

---

## Running Tests

### Basic Test Commands

**Run all tests:**
```bash
make test
```

**Run with verbose output:**
```bash
pytest tests/ -v
```

**Run specific test file:**
```bash
pytest tests/unit/domain/test_entities.py -v
```

**Run specific test class:**
```bash
pytest tests/unit/domain/test_entities.py::TestArtist -v
```

**Run specific test:**
```bash
pytest tests/unit/domain/test_entities.py::TestArtist::test_create_artist -v
```

### Advanced Test Commands

**Run only unit tests:**
```bash
make test-unit
# or
pytest tests/unit/ -v
```

**Run only integration tests:**
```bash
pytest tests/integration/ -v
```

**Run tests matching a pattern:**
```bash
pytest tests/ -k "spotify" -v
```

**Run tests with coverage:**
```bash
make test-cov
# or
pytest tests/ --cov=src/soulspot --cov-report=html --cov-report=term
```

**Run tests in parallel:**
```bash
pytest tests/ -n auto  # Requires pytest-xdist
```

**Stop on first failure:**
```bash
pytest tests/ -x
```

**Show local variables on failure:**
```bash
pytest tests/ -l
```

---

## Writing Tests

### Test File Structure

**Naming Convention:**
- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

**Example Structure:**
```python
"""Tests for artist entity."""

import pytest
from soulspot.domain.entities import Artist
from soulspot.domain.exceptions import ValidationException


class TestArtist:
    """Test suite for Artist entity."""
    
    def test_create_artist(self):
        """Test creating a new artist."""
        # Arrange
        artist_id = "artist-123"
        name = "The Beatles"
        
        # Act
        artist = Artist(id=artist_id, name=name)
        
        # Assert
        assert artist.id == artist_id
        assert artist.name == name
    
    def test_create_artist_invalid_name(self):
        """Test creating artist with invalid name raises error."""
        with pytest.raises(ValidationException):
            Artist(id="artist-123", name="")
```

### Arrange-Act-Assert Pattern

Follow the AAA pattern for clear, maintainable tests:

```python
def test_example():
    # Arrange - Set up test data and preconditions
    user = User(name="John")
    
    # Act - Execute the functionality being tested
    result = user.get_greeting()
    
    # Assert - Verify the results
    assert result == "Hello, John"
```

---

## Test Structure

### Project Test Directory

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── unit/                       # Unit tests
│   ├── domain/
│   │   ├── test_entities.py
│   │   └── test_value_objects.py
│   ├── application/
│   │   ├── use_cases/
│   │   ├── services/
│   │   ├── workers/
│   │   └── cache/
│   └── infrastructure/
│       ├── persistence/
│       └── integrations/
└── integration/                # Integration tests
    └── api/
        └── test_main.py
```

### Test Categories

#### 1. Domain Layer Tests (`tests/unit/domain/`)

Test pure business logic without external dependencies.

**Example:**
```python
def test_playlist_add_track():
    """Test adding a track to a playlist."""
    playlist = Playlist(id="pl-1", name="My Playlist")
    track_id = TrackId("track-1")
    
    playlist.add_track(track_id)
    
    assert track_id in playlist.track_ids
    assert playlist.track_count() == 1
```

#### 2. Application Layer Tests (`tests/unit/application/`)

Test use cases, services, and business logic orchestration with mocked dependencies.

**Example:**
```python
@pytest.mark.asyncio
async def test_import_playlist_use_case():
    """Test importing a Spotify playlist."""
    # Arrange
    mock_spotify = AsyncMock()
    mock_spotify.get_playlist.return_value = {...}
    
    use_case = ImportSpotifyPlaylistUseCase(
        spotify_client=mock_spotify,
        playlist_repo=mock_playlist_repo,
        track_repo=mock_track_repo
    )
    
    request = ImportSpotifyPlaylistRequest(
        playlist_id="spotify:playlist:123",
        access_token="token"
    )
    
    # Act
    response = await use_case.execute(request)
    
    # Assert
    assert response.tracks_imported > 0
    mock_spotify.get_playlist.assert_called_once()
```

#### 3. Infrastructure Tests (`tests/unit/infrastructure/`)

Test external integrations with mocked HTTP calls.

**Example:**
```python
@pytest.mark.asyncio
async def test_spotify_client_get_playlist(httpx_mock):
    """Test Spotify client playlist retrieval."""
    # Arrange
    httpx_mock.add_response(
        url="https://api.spotify.com/v1/playlists/123",
        json={"id": "123", "name": "Test Playlist"}
    )
    
    client = SpotifyClient(...)
    
    # Act
    playlist = await client.get_playlist("123", "token")
    
    # Assert
    assert playlist["name"] == "Test Playlist"
```

#### 4. API Integration Tests (`tests/integration/api/`)

Test API endpoints with test client.

**Example:**
```python
def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

---

## Testing Best Practices

### 1. Test Isolation

**Each test should be independent:**
```python
# Good - Independent tests
class TestPlaylist:
    def test_add_track(self):
        playlist = Playlist(id="pl-1", name="Test")
        playlist.add_track(TrackId("track-1"))
        assert playlist.track_count() == 1
    
    def test_remove_track(self):
        playlist = Playlist(id="pl-2", name="Test")
        track_id = TrackId("track-1")
        playlist.add_track(track_id)
        playlist.remove_track(track_id)
        assert playlist.track_count() == 0

# Bad - Tests depend on each other
class TestPlaylist:
    playlist = None
    
    def test_1_create_playlist(self):
        self.playlist = Playlist(id="pl-1", name="Test")
    
    def test_2_add_track(self):
        # Depends on test_1_create_playlist
        self.playlist.add_track(TrackId("track-1"))
```

### 2. Use Descriptive Test Names

```python
# Good
def test_import_playlist_with_invalid_token_raises_authentication_error():
    ...

# Bad
def test_playlist():
    ...
```

### 3. Test One Thing at a Time

```python
# Good - Tests one specific behavior
def test_track_is_downloaded_returns_true_when_file_path_set():
    track = Track(id="t-1", title="Song", file_path="/path/to/song.mp3")
    assert track.is_downloaded() is True

def test_track_is_downloaded_returns_false_when_file_path_not_set():
    track = Track(id="t-1", title="Song", file_path=None)
    assert track.is_downloaded() is False

# Bad - Tests multiple things
def test_track_download_status():
    track1 = Track(id="t-1", title="Song1", file_path="/path")
    track2 = Track(id="t-2", title="Song2", file_path=None)
    assert track1.is_downloaded() is True
    assert track2.is_downloaded() is False
```

### 4. Test Both Success and Failure Paths

```python
class TestDownload:
    def test_complete_download_success(self):
        """Test successful download completion."""
        download = Download(id="d-1", track_id="t-1", status=DownloadStatus.DOWNLOADING)
        download.complete("/path/to/file.mp3")
        assert download.status == DownloadStatus.COMPLETED
    
    def test_complete_download_invalid_state_raises_error(self):
        """Test completing already completed download raises error."""
        download = Download(id="d-1", track_id="t-1", status=DownloadStatus.COMPLETED)
        with pytest.raises(InvalidStateException):
            download.complete("/path/to/file.mp3")
```

---

## Mocking and Fixtures

### Using pytest Fixtures

**Define fixtures in `conftest.py`:**
```python
import pytest
from soulspot.domain.entities import Artist


@pytest.fixture
def sample_artist():
    """Provide a sample artist for testing."""
    return Artist(
        id="artist-1",
        name="The Beatles",
        spotify_uri="spotify:artist:3WrFJ7ztbogyGnTHbHJFl2"
    )


@pytest.fixture
def artist_repository():
    """Provide a mock artist repository."""
    repo = AsyncMock()
    repo.get_by_id.return_value = None
    repo.save.return_value = None
    return repo
```

**Use fixtures in tests:**
```python
def test_artist_update_name(sample_artist):
    """Test updating artist name."""
    sample_artist.update_name("Beatles, The")
    assert sample_artist.name == "Beatles, The"


@pytest.mark.asyncio
async def test_save_artist(artist_repository, sample_artist):
    """Test saving an artist."""
    await artist_repository.save(sample_artist)
    artist_repository.save.assert_called_once_with(sample_artist)
```

### Mocking with pytest-mock

```python
def test_with_mock(mocker):
    """Test using pytest-mock."""
    mock_client = mocker.Mock()
    mock_client.fetch_data.return_value = {"data": "value"}
    
    result = mock_client.fetch_data()
    
    assert result["data"] == "value"
    mock_client.fetch_data.assert_called_once()
```

### Mocking HTTP Calls with pytest-httpx

```python
@pytest.mark.asyncio
async def test_api_call(httpx_mock):
    """Test external API call."""
    httpx_mock.add_response(
        url="https://api.example.com/data",
        json={"result": "success"},
        status_code=200
    )
    
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        data = response.json()
    
    assert data["result"] == "success"
```

---

## Coverage

### Viewing Coverage Reports

**Generate HTML coverage report:**
```bash
make test-cov
```

**View the report:**
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Coverage Goals

- **Overall:** >80% coverage
- **Critical paths:** 100% coverage
- **New code:** >90% coverage

### Coverage Configuration

Coverage settings in `pyproject.toml`:
```toml
[tool.coverage.run]
source = ["src"]
branch = true
omit = [
    "tests/*",
    "**/__init__.py",
]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if TYPE_CHECKING:",
    "raise AssertionError",
    "raise NotImplementedError",
]
```

---

## Continuous Integration

Tests run automatically on:
- **Pull Requests** - All tests must pass
- **Commits to main** - Ensures stability
- **Scheduled runs** - Daily checks

### CI Configuration

See `.github/workflows/` for GitHub Actions configuration (coming in Phase 6).

### Pre-commit Hooks

Install pre-commit hooks to run tests before commits:
```bash
pre-commit install
```

Hooks run:
- Code formatting (ruff)
- Linting (ruff)
- Type checking (mypy)
- Security checks (bandit)

---

## Debugging Tests

### Running Tests with PDB

```bash
pytest tests/ --pdb  # Drop into debugger on failure
```

### Print Debugging

```python
def test_something():
    result = calculate()
    print(f"Result: {result}")  # Will show in pytest output with -s
    assert result == expected
```

**Run with stdout:**
```bash
pytest tests/test_file.py -s  # Show print statements
```

---

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)

---

**Happy Testing! 🧪✅**
