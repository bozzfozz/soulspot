# Archiv: Entfernte Remote/Multi-User Features

**Datum:** 2025-11-12  
**Grund:** SoulSpot wird als lokaler Dienst im privaten Netzwerk betrieben und soll nicht über das Internet erreichbar sein.

Dieses Dokument archiviert alle entfernten Dokumentationsabschnitte zu folgenden Features:
- Multi-User Support
- nginx (Reverse Proxy)
- PostgreSQL
- Redis Integration
- Jellyfin Integration
- Navidrome Integration
- Subsonic Integration
- External/Remote/Internet Access

Falls diese Features später wieder benötigt werden, können sie aus diesem Archiv wiederhergestellt oder als separate Roadmap-Items neu geplant werden.

---

## 1. docs/archive/development-roadmap-archived.md

### Zeile 35: Vision - Media-Server Integration
**Entfernt:**
```
- 🔄 **Mit Media-Servern synchronisiert** – Plex, Jellyfin, Navidrome, Subsonic Integration
```
**Grund:** SoulSpot ist lokal-only, keine externe Media-Server-Integration vorgesehen.

---

### Zeile 81: Note über PostgreSQL/Redis/nginx
**Entfernt:**
```
> **Note:** Advanced features originally planned for Phase 6 (v3.0 features such as Production Profile with PostgreSQL/Redis/nginx, Kubernetes, OWASP security hardening) have been moved to the dedicated [Version 3.0 section](#-version-30--production-hardening--enterprise-deployment-geplant) to keep Phase 6 focused and achievable.
```
**Grund:** PostgreSQL, Redis, nginx werden nicht benötigt für lokalen Betrieb.

---

### Zeilen 119-121: Media Server Integration Table
**Entfernt:**
```
| **Jellyfin** | Rescan Trigger, Ratings Sync, Path Mapping | 📋 Planned | Phase 8 |
| **Navidrome** | Rescan Trigger, Path Mapping | 📋 Planned | Phase 8 |
| **Subsonic** | API Integration | 📋 Planned | Phase 8 |
```
**Grund:** Keine Jellyfin, Navidrome, Subsonic Integration geplant.

---

### Zeile 196: Media Server Rescan
**Entfernt:**
```
8. Media Server Rescan (Plex, Jellyfin, Navidrome Trigger)
```
**Grund:** Keine Media-Server-Integration vorgesehen.

---

### Zeilen 288-289: Sync Features
**Entfernt:**
```
| **Jellyfin Sync** | Ratings ↔ ID3v2 POPM | 📋 Planned | Phase 7-8 |
| **Navidrome Sync** | Ratings ↔ ID3v2 POPM | 📋 Planned | Phase 8 |
```
**Grund:** Keine Media-Server Sync-Features geplant.

---

### Zeile 362: Advanced Deployment Features Note
**Entfernt:**
```
> **Note:** Advanced deployment features (Production Profile with PostgreSQL/Redis/nginx, Kubernetes Manifests) have been moved to v3.0 scope as they are not required for current production readiness. See [Version 3.0 section](#-version-30--production-hardening--enterprise-deployment-geplant) for details.
```
**Grund:** Keine erweiterten Deployment-Features mit PostgreSQL/Redis/nginx erforderlich.

---

### Zeile 381: PostgreSQL Connection Pool
**Entfernt:**
```
- Connection pool configuration for PostgreSQL with configurable pool_size and max_overflow
```
**Grund:** Keine PostgreSQL-Integration geplant.

---

### Zeile 389: Redis Integration Note
**Entfernt:**
```
> **Note:** Advanced performance features (Redis Integration for Distributed Cache) have been moved to v3.0 scope. See [Version 3.0 section](#-version-30--production-hardening--enterprise-deployment-geplant) for details.
```
**Grund:** Keine Redis-Integration erforderlich.

---

### Zeile 523: Cross-provider sync
**Entfernt:**
```
| - Cross-provider sync (Spotify↔Plex↔Navidrome) | HIGH | MEDIUM |
```
**Grund:** Keine Cross-provider Sync geplant.

---

### Zeilen 579-580: Ratings Sync
**Entfernt:**
```
| - Jellyfin ratings sync | MEDIUM | MEDIUM |
| - Navidrome ratings sync | MEDIUM | LOW |
```
**Grund:** Keine Media-Server Ratings-Sync vorgesehen.

---

### Zeile 613: Redis sessions
**Entfernt:**
```
| - Future: Redis or database-backed sessions | | | | |
```
**Grund:** Redis nicht benötigt für lokalen Betrieb.

---

### Zeile 618: Redis/KMS encryption
**Entfernt:**
```
| - Future: Encrypt tokens at rest (DB/Redis encryption or KMS) | | | | |
```
**Grund:** Redis-bezogene Features nicht vorgesehen.

---

### Zeile 621: Multi-User Support
**Entfernt:**
```
| **3. Multi-User Support** | HIGH | P2 | v2.2 | Medium (5-7 days) |
```
**Grund:** Kein Multi-User Support geplant (lokal-only, single-user).

---

### Zeile 640: Multi-user RBAC
**Entfernt:**
```
- Multi-user requires RBAC implementation (see Phase 9.1)
```
**Grund:** Kein Multi-User Support vorgesehen.

---

### Zeilen 669-671: Media Server Integration Features
**Entfernt:**
```
| - Jellyfin (rescan, ratings) | MEDIUM | MEDIUM |
| - Navidrome (rescan, mapping) | MEDIUM | LOW |
| - Subsonic API | MEDIUM | LOW |
```
**Grund:** Keine Media-Server-Integration geplant.

---

### Zeile 753: Phase 9.1 Multi-User & Security
**Entfernt:**
```
#### 9.1 Multi-User & Security 👥
```
**Grund:** Kein Multi-User Support vorgesehen.

---

### Zeile 758: Multi-user RBAC table entry
**Entfernt:**
```
| - Multi-user support (RBAC) | HIGH | LOW |
```
**Grund:** Kein Multi-User Support geplant.

---

### Zeile 867: Version 3.0 Description
**Entfernt:**
```
- 🚀 **Production-Ready:** PostgreSQL, Redis, nginx für skalierbaren Betrieb
```
**Grund:** PostgreSQL, Redis, nginx nicht erforderlich.

---

### Zeile 874-890: Production Profile Section
**Entfernt:**
```
#### 3.1 Production Profile (PostgreSQL, Redis, nginx) 🐘

| Feature | Description | Priority |
|---------|-------------|----------|
| **PostgreSQL Integration** | Production-ready relational database | HIGH |
| **Redis Integration** | Distributed caching & session storage | HIGH |
| **nginx Reverse Proxy** | Production web server | MEDIUM |
```
**Grund:** Komplette Production Profile Section mit PostgreSQL/Redis/nginx entfernt.

---

### Zeilen 911-916: Kubernetes Stateful Services
**Entfernt:**
```
| - Database StatefulSet | Persistent PostgreSQL | HIGH |
| - Redis StatefulSet | Distributed cache | MEDIUM |
| - Ingress configuration | External access & routing | MEDIUM |
```
**Grund:** Keine externen Services und External Access vorgesehen.

---

### Zeile 1012: Production Profile Checklist
**Entfernt:**
```
- [ ] **Production Profile:** PostgreSQL + Redis + nginx vollständig konfiguriert und getestet
```
**Grund:** Keine Production Profile Features erforderlich.

---

### Zeile 1023: Performance Metrics
**Entfernt:**
```
- [ ] **Performance:** PostgreSQL + Redis < 50ms p95 Latency
```
**Grund:** PostgreSQL + Redis nicht vorgesehen.

---

## 2. docs/docker-setup.md

### Zeilen 430-438: PostgreSQL Configuration
**Entfernt:**
```
### Using External PostgreSQL

To use PostgreSQL instead of SQLite, update your `.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/soulspot
```

And add a PostgreSQL service to your `docker-compose.yml`.
```
**Grund:** PostgreSQL-Integration nicht vorgesehen, nur SQLite für lokalen Betrieb.

---

## 3. docs/backend-development-roadmap.md

### Zeile 27: Data Management Description
**Entfernt (teilweise):**
```
- 🗄️ **Data Management** – SQLite/PostgreSQL database layer, Alembic migrations, robust data persistence
```
**Ersetzt durch:**
```
- 🗄️ **Data Management** – SQLite database layer, Alembic migrations, robust data persistence
```
**Grund:** PostgreSQL wird nicht unterstützt.

---

### Zeilen 330-331: Database & Cache Roadmap
**Entfernt:**
```
| **PostgreSQL Support** | Production database option | P1 | Large | v3.0 |
| **Redis Integration** | Distributed cache & sessions | P1 | Large | v3.0 |
```
**Grund:** PostgreSQL und Redis nicht geplant.

---

### Zeilen 342-344: Media Server Integrations
**Entfernt:**
```
| **Jellyfin** | Rescan trigger, ratings sync | P2 | Medium | Phase 8 |
| **Navidrome** | Rescan trigger, path mapping | P2 | Medium | Phase 8 |
| **Subsonic** | API integration | P3 | Medium | Phase 8 |
```
**Grund:** Keine Media-Server-Integrationen vorgesehen.

---

### Zeilen 352-355: Production Infrastructure
**Entfernt:**
```
| **PostgreSQL Integration** | Production-ready RDBMS | P1 | Large |
| **Redis Integration** | Distributed caching & session storage | P1 | Large |
```
**Grund:** Keine erweiterte Produktionsinfrastruktur erforderlich.

---

### Zeilen 400-401: Infrastructure Dependencies
**Entfernt:**
```
    ├─→ PostgreSQL Integration
    ├─→ Redis Integration
```
**Grund:** Diese Infrastruktur-Abhängigkeiten nicht vorgesehen.

---

## 4. docs/roadmap-crosscutting.md

### Zeilen 93-95: Production Infrastructure Stack
**Entfernt:**
```
| **Database (prod)** | PostgreSQL | 📋 v3.0 |
| **Cache (prod)** | Redis | 📋 v3.0 |
| **Reverse Proxy** | nginx | 📋 v3.0 |
```
**Grund:** Keine Produktionsinfrastruktur mit PostgreSQL/Redis/nginx geplant.

---

### Zeile 119: Multi-User Prep
**Entfernt:**
```
| **Multi-User Prep** | Groundwork for multi-user | P2 | Medium | 📋 Planned |
```
**Grund:** Kein Multi-User Support vorgesehen.

---

### Zeile 124: Token encryption
**Entfernt:**
```
- [ ] Tokens encrypted in database/Redis
```
**Grund:** Redis-bezogen, nicht benötigt.

---

### Zeile 131: Redis sessions
**Entfernt:**
```
- Redis or database-backed sessions (optional for Phase 7, required for v3.0)
```
**Grund:** Redis-Sessions nicht erforderlich.

---

### Zeilen 264-267: Version 3.0 Infrastructure
**Entfernt:**
```
| **PostgreSQL Integration** | Production-ready database | P0 | Large | 📋 v3.0 |
| **Redis Integration** | Distributed cache & sessions | P0 | Large | 📋 v3.0 |
| **nginx Setup** | Reverse proxy, SSL, load balancing | P1 | Medium | 📋 v3.0 |
| **Database Migration** | SQLite → PostgreSQL tooling | P0 | Large | 📋 v3.0 |
```
**Grund:** Komplette v3.0 Infrastruktur-Features entfernt.

---

### Zeilen 271-273: Production Readiness Checklist
**Entfernt:**
```
- [ ] PostgreSQL fully integrated and tested
- [ ] Redis for caching and sessions
- [ ] nginx configured with SSL/TLS
```
**Grund:** Diese Infrastruktur nicht geplant.

---

### Zeile 291: Ingress Configuration
**Entfernt:**
```
| **Ingress Configuration** | External access routing | P1 | Medium | 📋 v3.0 |
```
**Grund:** Kein External Access vorgesehen (lokal-only).

---

### Zeilen 359-360: Critical Services
**Entfernt:**
```
| **PostgreSQL** | Production database | CRITICAL | Regular backups, replication |
| **Redis** | Cache & sessions | HIGH | Persistent storage, fallback to DB |
```
**Grund:** Diese Services nicht Teil der Architektur.

---

### Zeile 385: Infrastructure Dependencies
**Entfernt:**
```
    ├─→ PostgreSQL + Redis (Infrastructure)
```
**Grund:** Diese Infrastruktur-Abhängigkeit entfernt.

---

### Zeilen 416-417: External Documentation Links
**Entfernt:**
```
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
```
**Grund:** Nicht mehr relevant.

---

## 5. docs/history/PHASE1_SUMMARY.md

### Zeile 4: PostgreSQL/Redis Deferral
**Entfernt:**
```
Successfully implemented Phase 1 of the SoulSpot Bridge project, focusing on foundation setup with SQLite database (PostgreSQL and Redis deferred to later phases per requirements).
```
**Ersetzt durch:**
```
Successfully implemented Phase 1 of the SoulSpot Bridge project, focusing on foundation setup with SQLite database (local-only architecture).
```
**Grund:** Keine zukünftigen PostgreSQL/Redis-Pläne mehr.

---

### Zeile 27: Key Decision
**Entfernt:**
```
**Key Decision:** SQLite only, no PostgreSQL or Redis (per user requirement)
```
**Ersetzt durch:**
```
**Key Decision:** SQLite only for local-only deployment
```
**Grund:** Klarstellung der lokalen Architektur.

---

### Zeile 117: Services Comment
**Entfernt:**
```
- Only slskd service (no PostgreSQL or Redis)
```
**Ersetzt durch:**
```
- Only slskd service (local setup)
```
**Grund:** Vereinfachung der Beschreibung.

---

### Zeilen 175-177: Deferred Features
**Entfernt:**
```
✅ **SQLite statt PostgreSQL** - Implemented SQLite-only approach
✅ **Kein Redis** - Removed Redis from dependencies
✅ **Später** - Deferred PostgreSQL and Redis to future phases
```
**Ersetzt durch:**
```
✅ **SQLite** - Implemented SQLite-only approach for local deployment
```
**Grund:** Keine zukünftigen Pläne für PostgreSQL/Redis.

---

## 6. docs/history/PR10_SUMMARY.md

### Zeile 211: Redis-Integration Todo
**Entfernt:**
```
1. **Redis-Integration:** In-Memory SessionStore durch Redis ersetzen
```
**Grund:** Redis-Integration nicht vorgesehen.

---

### Zeile 220: Redis-Backend Todo
**Entfernt:**
```
- [ ] Redis-Backend für SessionStore
```
**Grund:** Redis nicht geplant.

---

## 7. docs/history/PHASE4_SUMMARY.md

### Zeilen 473, 481: Redis Replacement Notes
**Entfernt:**
```
**Note:** Can be replaced with Redis/Celery for production
**Note:** Can be replaced with Redis/Memcached for production
```
**Grund:** Redis-Optionen nicht relevant für lokalen Betrieb.

---

### Zeilen 684, 691: Redis Considerations
**Entfernt:**
```
  - Consider Redis for persistence
  - Consider Redis for larger caches
```
**Grund:** Redis nicht Teil der Architektur.

---

## 8. docs/history/PHASE2_SUMMARY.md

### Zeile 23: Profile Support
**Entfernt:**
```
- **Profile Support:** Simple (SQLite) and Standard (PostgreSQL + Redis) profiles
```
**Ersetzt durch:**
```
- **Profile Support:** Simple (SQLite) profile for local deployment
```
**Grund:** Kein Standard-Profil mit PostgreSQL/Redis.

---

### Zeile 164: Standard Profile
**Entfernt:**
```
- `standard`: PostgreSQL + Redis (ready for Phase 3+)
```
**Grund:** Standard-Profil nicht vorgesehen.

---

### Zeile 350: Production Mitigation
**Entfernt:**
```
- **Mitigation:** Use PostgreSQL for production (standard profile)
```
**Grund:** Kein Production Profile mit PostgreSQL.

---

## 9. docs/features/soulspot-ideas.md

### Zeile 26: Media-Server Integration
**Entfernt:**
```
  - Media-Server: Plex / Jellyfin / Navidrome (Rescan, Mapping)
```
**Grund:** Keine Media-Server-Integration geplant.

---

### Zeile 64: Ratings-Sync
**Entfernt:**
```
  - Ratings-Sync (Plex/Jellyfin/Navidrome ↔ Datei/DB), Mapping & Konfliktregeln
```
**Grund:** Keine Media-Server Sync-Features.

---

### Zeile 81: Playlist-Sync
**Entfernt:**
```
  - Playlist-Sync zwischen Spotify, Plex, Navidrome, Jellyfin (A→B oder bidirektional)
```
**Grund:** Keine Cross-Platform Playlist-Sync vorgesehen.

---

### Zeile 89: Multi-User Support
**Entfernt:**
```
  - Multi-User / Rechteverwaltung (Admin vs Read-only)
```
**Grund:** Kein Multi-User Support geplant.

---

### Zeile 161: Advanced Features
**Entfernt (teilweise):**
```
- AcoustID, KI-Features, plugin-architecture, multi-user support, production infra
```
**Ersetzt durch:**
```
- AcoustID, KI-Features, plugin-architecture
```
**Grund:** Multi-User und Production Infra entfernt.

---

## 10. docs/analysis/initial-assessment.md

### Zeile 1121: PostgreSQL und Redis Services
**Entfernt:**
```
- [ ] PostgreSQL und Redis Services
```
**Grund:** Diese Services nicht Teil der Architektur.

---

### Zeile 1187: PostgreSQL Client
**Entfernt:**
```
- PostgreSQL Client (psql) für DB-Debugging
```
**Grund:** Kein PostgreSQL.

---

### Zeile 1217: Database Comment
**Entfernt:**
```
# Database (SQLite für simple, PostgreSQL für standard)
```
**Ersetzt durch:**
```
# Database (SQLite for local deployment)
```
**Grund:** Nur SQLite unterstützt.

---

### Zeile 1236: Services Comment
**Entfernt:**
```
# Alle Services starten (slskd, PostgreSQL, Redis)
```
**Ersetzt durch:**
```
# Service starten (slskd)
```
**Grund:** Nur slskd Service.

---

### Zeilen 1345-1349: PostgreSQL Status Check
**Entfernt:**
```
# PostgreSQL-Status prüfen
docker-compose ps postgres

# DB-Connect
psql postgresql://user:password@localhost:5432/soulspot
```
**Grund:** Keine PostgreSQL-Installation.

---

## Große Sektion: Version 3.0 — Production Hardening & Enterprise Deployment

### docs/archive/development-roadmap-archived.md - Zeilen 837-1151 (315 Zeilen)

**Komplette Sektion entfernt:**
Die gesamte Version 3.0 Sektion wurde entfernt, da sie ausschließlich Features für skalierbaren, internet-fähigen Produktionsbetrieb beschreibt:
- PostgreSQL Integration (Production Database)
- Redis Integration (Distributed Caching & Sessions)
- nginx Reverse Proxy (Production Web Server)
- Kubernetes Manifests (Container Orchestration)  
- External Access & Ingress Configuration
- Multi-User RBAC und erweiterte Authentifizierung

**Grund:** SoulSpot wird als lokaler Single-User Dienst im privaten Netzwerk betrieben. Die komplexe Enterprise-Infrastruktur ist nicht erforderlich.

**Original-Content:** Vollständiger Abschnitt mit 315 Zeilen wurde in `/tmp/v3_section_archived.txt` gesichert.

---


## Zusammenfassung der Änderungen

**Datum:** 2025-11-12  
**Änderungen:** Umfassende Entfernung aller Remote/Multi-User/Internet-Access Features aus der Dokumentation

### Betroffene Bereiche

1. **Multi-User Support** - Komplett entfernt
   - RBAC (Role-Based Access Control)
   - Admin vs. Read-only Rollen
   - Mehrbenutzer-Authentifizierung
   - User-spezifische Features

2. **Produktions-Infrastruktur** - Komplett entfernt
   - PostgreSQL Integration & Migration
   - Redis Integration (Caching, Sessions, Queue)
   - nginx Reverse Proxy
   - Kubernetes Deployment & Orchestrierung

3. **Media-Server-Integrationen** - Teilweise entfernt
   - ❌ Jellyfin (Rescan, Ratings Sync)
   - ❌ Navidrome (Rescan, Path Mapping)
   - ❌ Subsonic API Integration
   - ✅ Plex bleibt (optional, lokal nutzbar)

4. **External/Remote Access** - Komplett entfernt
   - Ingress Configuration
   - Internet Accessibility
   - Public Access
   - Remote Access Features

### Verbleibende Architektur

**SoulSpot ist jetzt ausschließlich für lokalen Betrieb ausgelegt:**
- SQLite als Datenbank (kein PostgreSQL)
- In-Memory Caching (kein Redis)
- Kein Reverse Proxy (kein nginx)
- Kein Container-Orchestrierung (kein Kubernetes)
- Single-User (kein Multi-User Support)
- Lokales Netzwerk only (kein Internet-Zugriff)
- Docker Compose für einfaches lokales Deployment

### Bearbeitete Dateien (Hauptdokumente)

1. ✅ docs/docker-setup.md
2. ✅ docs/backend-development-roadmap.md
3. ✅ docs/archive/development-roadmap-archived.md (inkl. 315-Zeilen v3.0 Sektion)
4. ✅ docs/roadmap-crosscutting.md
5. ✅ docs/development-roadmap.md
6. ✅ docs/deployment-guide.md
7. ✅ docs/roadmap
8. ✅ docs/history/PHASE1_SUMMARY.md
9. ✅ docs/history/PHASE2_SUMMARY.md
10. ✅ docs/history/PHASE4_SUMMARY.md
11. ✅ docs/history/PR10_SUMMARY.md
12. ✅ docs/features/soulspot-ideas.md
13. ✅ docs/analysis/initial-assessment.md

### Verbleibende Referenzen

Einige technische Dokumente enthalten noch Referenzen in historischen/technischen Kontexten:
- `docs/architecture.md` - Architektur-Beschreibungen (historisch/technisch)
- `docs/setup-guide.md` - Setup-Anleitung mit optionalen Sektionen
- `docs/operations-runbook.md` - Operations-Runbook mit optionalen Szenarien
- `docs/troubleshooting-guide.md` - Troubleshooting für verschiedene Setups
- `docs/spotify-auth-improvement.md` - Feature-Planung (historisch)
- `docs/PHASE6_COMPLETION_SUMMARY.md` - Phase-Zusammenfassung (historisch)
- `docs/achievements-verification.md` - Achievements-Liste (historisch)
- `docs/issues/*.md` - Issue-Templates (Archiv)

Diese Dokumente bleiben teilweise unverändert, da sie:
1. Historische Dokumentation darstellen
2. Technische Optionen für Fortgeschrittene beschreiben
3. Issue-Templates/Planungsdokumente sind

### Empfehlungen für Benutzer

**Für neue Benutzer:**
- Lesen Sie `docs/setup-guide.md` Abschnitt "Simple Profile" (SQLite)
- Ignorieren Sie alle "Standard Profile" oder "PostgreSQL"-Sektionen
- Verwenden Sie Docker Compose für lokales Deployment
- SoulSpot ist ausschließlich für Ihr lokales Netzwerk gedacht

**Für Entwickler:**
- Die Architektur ist auf Single-User optimiert
- SQLite ist die einzige unterstützte Datenbank
- Keine externen Services erforderlich (außer slskd)
- Deployment erfolgt ausschließlich lokal

---

**Ende der Dokumentation**
