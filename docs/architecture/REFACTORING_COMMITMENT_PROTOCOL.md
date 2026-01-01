# Refactoring-Commitment Protocol

> **VERBINDLICH für alle Agents/Sessions die an diesem Refactoring arbeiten**

---

## 🚨 ZERO TOLERANCE: Keine Ausreden, Keine Umwege

### Was "Faulheit" bei Refactoring bedeutet

| Faulheit-Symptom | Beispiel | VERBOTEN |
|------------------|----------|----------|
| **"Temporäre" Lösungen** | "Wir können das später richtig machen" | ❌ |
| **Copy-Paste statt Abstraktion** | "Ich kopiere den Code erstmal schnell" | ❌ |
| **Halb-fertige Migration** | "Die anderen 3 Funktionen mache ich morgen" | ❌ |
| **Shortcuts** | "Ich rufe den alten Worker einfach vom neuen aus auf" | ❌ |
| **Kompromisse** | "Das Feature ist nicht kritisch, lassen wir erstmal" | ❌ |
| **Workarounds** | "Wenn wir hier ein Flag setzen, funktioniert es auch" | ❌ |
| **Partial Refactoring** | "Ich ändere nur diese eine Stelle" | ❌ |

---

## ✅ Was stattdessen gilt

### Prinzip 1: KOMPLETT oder GAR NICHT

```
Wenn du eine Funktion migrierst → Migriere die GANZE Funktion
Wenn du einen Worker ersetzt → Lösche den ALTEN Worker
Wenn du ein Pattern änderst → Ändere es ÜBERALL

Keine halben Sachen!
```

### Prinzip 2: DELETE THE OLD CODE

```python
# ❌ VERBOTEN: Alten Code "für später" behalten
# "Falls wir zurückrollen müssen..."
# Das ist KEIN Rollback-Plan, das ist Vermüllung!

# ✅ RICHTIG: Alten Code LÖSCHEN sobald Migration fertig
# Git hat den alten Code in der History
# Feature Flag zum Aktivieren/Deaktivieren
```

### Prinzip 3: EINE WAHRHEIT (Single Source of Truth)

```python
# ❌ VERBOTEN: Zwei Wege zum gleichen Ziel
class SpotifySyncWorker:  # Alt
    async def sync_artists(self): ...

class UnifiedLibraryManager:  # Neu
    async def _task_sync_spotify_likes(self): ...

# Beide existieren gleichzeitig → CHAOS

# ✅ RICHTIG: Nur EINER existiert
# Migration: Alt → Neu → Alt löschen → Fertig
```

### Prinzip 4: KEINE "TODO: Later" Kommentare

```python
# ❌ VERBOTEN
async def _task_sync_cloud_sources(self):
    # TODO: Deezer hinzufügen später
    await self._sync_spotify()

# ✅ RICHTIG
async def _task_sync_cloud_sources(self):
    await self._sync_spotify()
    await self._sync_deezer()  # Jetzt implementiert, nicht "später"
```

### Prinzip 5: TESTS VOR LÖSCHUNG (Live Testing)

```
Bevor alte Datei gelöscht wird:
1. Neue Implementation LIVE testen
2. Alle Funktionen der alten Datei überprüfen
3. 1 Tag Beobachtung ohne Fehler
4. DANN löschen

Kein "das sollte funktionieren"!
```

---

## 📋 Migrations-Checkliste (PFLICHT bei jeder Migration)

### Vor dem Start

- [ ] Alte Implementation vollständig verstanden (Code gelesen!)
- [ ] Alle Funktionen der alten Komponente aufgelistet
- [ ] Neue Implementation VOLLSTÄNDIG geplant
- [ ] Feature Flag angelegt (falls nötig)

### Während Migration

- [ ] JEDE Funktion 1:1 übertragen (keine ausgelassen)
- [ ] Keine "später" Kommentare hinzugefügt
- [ ] Keine Shortcuts genommen
- [ ] Keine Copy-Paste-Duplikate erstellt

### Nach Migration

- [ ] Neue Implementation LIVE getestet
- [ ] Alle ursprünglichen Funktionen funktionieren
- [ ] Alte Dateien GELÖSCHT (nicht auskommentiert!)
- [ ] Imports in anderen Dateien aktualisiert
- [ ] Dokumentation aktualisiert

### Finale Bestätigung

- [ ] Git diff zeigt: Alte Datei weg, neue Datei da
- [ ] Keine `# TODO: migrate` Kommentare übrig
- [ ] Keine `# DEPRECATED` Marker (Code ist WEG, nicht deprecated)

---

## 🔴 STOP-Bedingungen

### Wann SOFORT aufhören

1. **"Das dauert zu lange"** → NEIN, es dauert so lange wie nötig
2. **"Ist nicht kritisch"** → DOCH, Halb-Migrationen sind schlimmer als keine
3. **"Machen wir später fertig"** → JETZT fertig machen oder nicht anfangen
4. **"Funktioniert auch so"** → Nicht akzeptabel wenn Plan anders ist

### Bei Zweifeln

```
FRAGE: Ist das eine Abkürzung?
       ↓
    JA → NICHT MACHEN
       ↓
   NEIN → OK, weitermachen
```

---

## 📝 Commit-Message-Pflicht

Jeder Migration-Commit MUSS enthalten:

```
[MIGRATE] ComponentName: Description

- ✅ Migriert: function1(), function2(), function3()
- ✅ Gelöscht: old_file.py (XXX Zeilen)
- ✅ Getestet: Live in Docker

KEINE offenen TODOs in dieser Migration.
```

---

## ⚠️ Warnung an zukünftige Agents

```
WENN DU DIESES DOKUMENT LIEST:

Du bist dabei, am SoulSpot Unified Library Worker zu arbeiten.
Der User hat EXPLIZIT gesagt: "Keine Ausreden, keine Umwege, nicht faul sein."

Das bedeutet:
1. Du machst die Migration KOMPLETT oder GAR NICHT
2. Du löschst alten Code SOFORT nach erfolgreicher Migration
3. Du nimmst KEINE Shortcuts
4. Du hinterlässt KEINE "TODO: später" Kommentare
5. Du testest LIVE bevor du sagst "fertig"

Wenn du denkst "das kann ich später machen" → FALSCH
Wenn du denkst "das ist nicht kritisch" → FALSCH
Wenn du denkst "funktioniert auch so" → FALSCH

MACH ES RICHTIG ODER MACH ES GAR NICHT.
```

---

## 🎯 Erfolgs-Definition

Migration ist NUR erfolgreich wenn:

1. ✅ Alte Komponente GELÖSCHT
2. ✅ Neue Komponente VOLLSTÄNDIG implementiert
3. ✅ LIVE getestet und funktioniert
4. ✅ Keine "offenen" TODOs
5. ✅ Dokumentation aktualisiert

Alles andere = NICHT FERTIG = NOCHMAL MACHEN

---

## Unterschrift

Dieses Dokument ist verbindlich für alle Refactoring-Arbeiten am UnifiedLibraryManager.

**Erstellt:** 2025-01-XX
**Kontext:** Task #18 - User-Anforderung: "wirklich ohne irgendwelche Ausreden oder Umwege"
