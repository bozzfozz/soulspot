# Library Scanner Services - Naming Clarification

**Last Updated:** December 2025

---

## ❓ Warum 2 "Scanner" Services?

### **Problem (vor Rename):**
```
library_scanner.py          ← LOW-LEVEL file discovery
library_scanner_service.py  ← HIGH-LEVEL DB import
```
**Verwirrung:** Beide heißen fast gleich!

---

## ✅ Lösung (nach Rename):

| Service | Purpose | Complexity |
|---------|---------|------------|
| **file_discovery_service.py** | File discovery + metadata | LOW (340 lines) |
| **library_import_service.py** | Full DB import pipeline | HIGH (1765 lines) |

---

## 📋 Verwendung:

### **FileDiscoveryService** (LOW-LEVEL)
```python
from soulspot.application.services.file_discovery_service import FileDiscoveryService

service = FileDiscoveryService()
files = service.discover_audio_files(Path("/music"))
for file in files:
    info = service.scan_file(file)  # Gets hash, metadata, validates
```

**Use Cases:**
- Duplicate detection (by hash)
- File integrity check
- Quick metadata extraction
- NO database operations

---

### **LibraryImportService** (HIGH-LEVEL)
```python
from soulspot.application.services.library_scanner_service import LibraryScannerService

service = LibraryScannerService(session, settings)
result = await service.scan_and_import()  # Full DB import
```

**Use Cases:**
- Import entire music library to DB
- Lidarr folder structure parsing
- Artist/Album/Track creation
- Incremental scans (only new files)
- Job Queue integration

---

## 🔄 Migration Path:

**Old Code (DEPRECATED - library_scanner.py removed in Dec 2025):**
```python
from soulspot.application.services.library_scanner import LibraryScannerService
```

**New Code:**
```python
from soulspot.application.services.file_discovery_service import FileDiscoveryService
```

**Note:** The backwards compatibility alias in `library_scanner.py` has been removed. Update all imports to use the new path.

---

## 📊 Comparison:

| Feature | FileDiscoveryService | LibraryImportService |
|---------|---------------------|---------------------|
| **DB Operations** | ❌ NO | ✅ YES |
| **Folder Parsing** | ❌ NO | ✅ Lidarr structure |
| **Use Case** | File analysis | Library import |
| **Complexity** | Simple | Complex |
| **Async** | ❌ Sync | ✅ Async |
| **Dependencies** | Mutagen only | DB + Repositories |

---

## 🎯 Wann welchen Service?

**FileDiscoveryService:**
- Duplicate detection
- File health check
- Quick scans ohne DB
- Use cases / utilities

**LibraryImportService:**
- Initial library import
- Incremental sync
- Background jobs
- Full metadata pipeline

---

**Rename Reason:** Clarity! Names now reflect actual purpose.
