# Archiv: Entfernte Discogs-Referenzen

**Datum:** 2025-11-12  
**Grund:** Discogs-Integration wird aktuell nicht unterstützt / lokal-only policy

---

## Übersicht

Dieses Dokument archiviert alle entfernten Abschnitte und Erwähnungen zur Discogs-Integration aus der SoulSpot Dokumentation. Die Discogs-Integration ist derzeit nicht Teil des Produkts und wurde aus den Planungsdokumenten entfernt, da SoulSpot als lokaler Dienst betrieben wird.

Falls die Integration später wieder erwünscht ist, kann sie als neues Roadmap-Item oder in einem separaten Dokument wieder aufgenommen werden.

---

## Entfernte Referenzen

### 1. docs/backend-development-roadmap.md

#### Zeile 112: External Integrations Tabelle
```markdown
| **Discogs** | Release details (planned) | 📋 Phase 7 |
```

**Kontext:** Teil der External Integrations Tabelle, die verschiedene API-Integrationen auflistet.

---

#### Zeilen 179-193: Metadata Management - Discogs Integration Task
```markdown
| **Discogs Integration** | Add Discogs as metadata source | P1 | Medium | 📋 Planned |
```

**Kontext:** Teil der Metadata Management Epic Aufgabenliste.

---

#### Zeile 185: Acceptance Criteria - Authority Hierarchy
```markdown
- [ ] Authority hierarchy: Manual > MusicBrainz > Discogs > Spotify > Last.fm
```

**Kontext:** Acceptance Criteria für Multi-Source Metadata Engine.

---

#### Zeile 187: Acceptance Criteria - Discogs API Integration
```markdown
- [ ] Discogs API integration complete
```

**Kontext:** Acceptance Criteria für Metadata Management Epic.

---

#### Zeile 193: Dependencies - External API Rate Limits
```markdown
- External API rate limits (MusicBrainz: 1 req/sec, Discogs: TBD)
```

**Kontext:** Dependencies Section im Metadata Management Epic.

---

#### Zeile 357: External Dependencies Tabelle
```markdown
| **Discogs API** | Metadata enrichment | MEDIUM | Optional feature, graceful fallback |
```

**Kontext:** Teil der External Dependencies Risiko-Analyse Tabelle.

---

### 2. docs/development-roadmap.md

#### Zeile 31: Backend Development Roadmap - Key Areas
```markdown
- External integrations (Spotify, slskd, MusicBrainz, Discogs, Last.fm)
```

**Kontext:** Auflistung der Key Areas im Backend Development Roadmap.

---

### 3. docs/features/soulspot-ideas.md

#### Zeile 24: Quellen & Integrationen - Externe Metadaten
```markdown
- Externe Metadaten & Artwork: MusicBrainz, Discogs, Last.fm, CoverArtArchive, Fanart.tv
```

**Kontext:** Liste der externen Metadata- und Artwork-Quellen.

---

#### Zeile 59: Metadaten & Tagging - Multi-Source-Tagging
```markdown
- Multi-Source-Tagging & Merge-Logik (Spotify, MusicBrainz, Discogs, Last.fm)
```

**Kontext:** Beschreibung der Multi-Source-Tagging-Funktionalität.

---

#### Zeile 60: Authority-Hierarchie
```markdown
- Authority-Hierarchie (manual > Spotify > MusicBrainz > Discogs > Last.fm > fallback)
```

**Kontext:** Definition der Metadaten-Prioritätshierarchie.

---

#### Zeile 133: Should (Phase 2) - Metadata Enrichment
```markdown
4. Metadata enrichment Discogs + Last.fm + merge-logic (mittel) [help wanted]
```

**Kontext:** Priorisiertes Backlog Item im "Should (Phase 2)" Bereich.

---

#### Zeile 165: Mittelfristig (Phase 2)
```markdown
- Missing-song-discovery, batch-downloads, ratings-sync connector (Plex), Discogs/Last.fm enrichers, batch-fixer UI
```

**Kontext:** Mittelfristige Entwicklungsziele.

---

#### Zeile 180: Policies / Defaults - Default Merge-Priorität
```markdown
- Default merge-priorität: manual > MusicBrainz > Discogs > Spotify > fallback
```

**Kontext:** Vorgeschlagene Default-Policy für Metadaten-Merge-Priorität.

---

### 4. docs/archive/development-roadmap-archived.md

#### Zeile 42: Kernnutzen - Konsistente Metadaten
```markdown
- **Konsistente, perfekte Metadaten** – kombiniert aus Spotify, MusicBrainz, Discogs, Last.fm
```

**Kontext:** Beschreibung des Kernnutzens im Vision-Abschnitt.

---

#### Zeile 109: External Data Sources Tabelle
```markdown
| **Discogs** | Release Details, Year, Edition, Label | 📋 Planned | Phase 7 |
```

**Kontext:** Teil der External Data Sources Tabelle.

---

#### Zeile 178: Kernfunktionalität - Metadata Enrichment
```markdown
1. Metadata Enrichment (Spotify + MusicBrainz + Discogs + Last.fm)
```

**Kontext:** Liste der Kernfunktionalitäten.

---

#### Zeile 216: Source Prioritization
```markdown
3. Discogs               (Release Details)
```

**Kontext:** Metadata Source Prioritization Liste.

---

#### Zeile 466: Metadata Management Row
```markdown
| - Manual > MusicBrainz > Discogs > Spotify | LOW | HIGH |
```

**Kontext:** Prioritäts-Matrix für Metadata Management.

---

#### Zeile 469: Discogs Integration Row
```markdown
| - Discogs integration | MEDIUM | MEDIUM |
```

**Kontext:** Prioritäts-Matrix Eintrag.

---

#### Zeile 2578: Additional Metadata Sources
```markdown
- Additional Metadata Sources (Discogs, Last.fm)
```

**Kontext:** Liste zusätzlicher Metadatenquellen in Feature-Details.

---

#### Zeile 2651: Source Prioritization (Wiederholung)
```markdown
3. Discogs               (Release Details)
```

**Kontext:** Wiederholte Erwähnung der Source Prioritization.

---

## Zusammenfassung

**Insgesamt entfernt:** 24 Discogs-Referenzen aus 4 Dokumentationsdateien

**Betroffene Dateien:**
- docs/backend-development-roadmap.md (7 Referenzen)
- docs/development-roadmap.md (1 Referenz)
- docs/features/soulspot-ideas.md (7 Referenzen)
- docs/archive/development-roadmap-archived.md (9 Referenzen)

**Grund für Entfernung:**
Die Discogs-Integration ist derzeit nicht Teil des SoulSpot-Produktplans. SoulSpot wird als lokaler Dienst betrieben und konzentriert sich auf die Integration mit Spotify, Soulseek und MusicBrainz. Eine zukünftige Erweiterung um Discogs bleibt möglich, ist aber nicht im aktuellen Scope.
