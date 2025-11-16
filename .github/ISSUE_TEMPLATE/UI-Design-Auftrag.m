# UI-Design-Auftrag für Frontend-KI (SoulSpot Bridge)

> Diesen Block 1:1 als Auftrag/Prompt an die KI geben und nur die Platzhalter ausfüllen.

## Kontext

- Seite / Feature: `<z.B. Dashboard "Downloads & Status">`
- Hauptziel dieser Seite: `<z.B. Überblick über aktive Downloads + schnelle Aktionen>`
- Wichtigste Aktionen (Top 3): `<z.B. Pause/Resume, Retry, Open in Player>`
- Wichtige Infos (Top 5): `<z.B. Fortschritt, ETA, Quelle, Qualität, Fehlerstatus>`

---

## Verbindlicher Auftrag an die KI

Du sollst ein **modernes, klar strukturiertes und visuell ansprechendes UI** für SoulSpot Bridge entwerfen, das auf dem **UI 1.0 Design System** basiert und ohne zusätzliche Fantasie-Styles auskommt.

---

### 1. Design-System-Pflicht (MUST)

- Verwende ausschließlich Klassen aus:
  - `ui/theme.css`
  - `ui/components.css`
  - `ui/layout.css`
- Nutze konsequent `ui-` Komponenten:
  - Layout: `.ui-page`, `.ui-page-header`, `.ui-page-content`, `.ui-page-footer`, `.ui-container`, `.ui-grid`, `.ui-grid-cols-*`
  - Komponenten: `.ui-card*`, `.ui-btn*`, `.ui-badge*`, `.ui-alert*`, `.ui-input`, `.ui-textarea`, `.ui-form-group`, `.ui-table*`, `.ui-modal*`, `.ui-spinner`, `.ui-skeleton`
- **Design-Tokens:**
  - Die bestehenden Design-Tokens aus `theme.css` (UI 1.0) gelten als **stabil**.
  - Der Frontend-KI-Agent DARF:
    - keine bestehenden Tokens in `theme.css` ändern,
    - keine neuen Tokens direkt in `theme.css` anlegen.
  - Wenn zusätzliche Tokens sinnvoll wären (z. B. SoulSpot-spezifische Akzentfarbe), SOLL der Agent:
    - nur einen **Vorschlag** als Text liefern (z. B. in einem Abschnitt „Token-Vorschläge“),
    - und NICHT eigenständig CSS-Dateien anpassen.
- Zusätzliches projektspezifisches Styling nur über spätere Dateien wie `soulspot-custom.css` (separater Auftrag), nicht ad hoc per Inline-Styles.

---

### 2. Look & Feel – „cooles“ UI in Regeln (MUST/SHOULD)

- **Layout:**
  - Nutze ein **Dashboard-Layout** mit klaren Zonen:
    - Oben: kompakter Header mit Titel + wichtigsten Aktionen
    - Mitte: 1–3 Reihen aus `.ui-card`-Widgets in einem `.ui-grid`
    - Unten: Sekundärinfos / Logs / Status
  - Maximalbreite über Container (zentriert), ausreichend Weißraum, kein gequetschtes Layout.
- **Karten:**
  - Wichtige Infos in **Cards** (`.ui-card`) mit:
    - `.ui-card-header` (Titel, optional Badge/Filter)
    - `.ui-card-body` (Hauptinhalt, Tabellen, Listen, Stats)
    - `.ui-card-footer` (Aktionen, Meta-Infos)
- **Buttons & States:**
  - Primäre Aktion: `.ui-btn ui-btn-primary`
  - Sekundäre Aktionen: `.ui-btn ui-btn-secondary` oder `.ui-btn ui-btn-outline`
  - Gefährliche Aktionen: `.ui-btn ui-btn-danger`
  - Immer erkennbare Hover-/Active-/Disabled-States (aus `components.css` nutzen).
- **Status-Visualisierung:**
  - Verwende `.ui-badge-*` und `.ui-alert-*` für Stati (running, queued, error, done).
  - Fortschritt mit `.ui-progress` / `.ui-spinner` / Skeletons visualisieren.
- **Dark Mode:**
  - Layout und Komponenten so bauen, dass sie mit den vorhandenen CSS-Variablen in Light & Dark Mode gut funktionieren (kein Hardcoding von Hintergründen/Fonts).

---

### 3. HTMX-Ready-Struktur (MUST)

- Baue das HTML so, dass:
  - sinnvolle Container als HTMX-Targets genutzt werden können (z. B. einzelne `.ui-card-body`, Listenbereiche, Tabellenkörper),
  - asynchrone Bereiche klar gekapselt sind (z. B. Job-Listen, Widget-Inhalte, modale Dialoge).
- Wichtige Leitlinien:
  - Keine Logik in das Template mischen, die HTMX-Patterns blockiert (z. B. harte Inline-Events im JS-Stil).
  - Denke in **Fragments**: einzelne Cards / Widgets müssen allein gerendert und per HTMX geswappt werden können.

---

### 4. UX & Interaktion (SHOULD)

- **Ladezustände:**
  - Asynchrone Bereiche mit Skeletons oder Spinnern aus `components.css` versehen.
- **Fehlermeldungen:**
  - Fehler sichtbar als `.ui-alert ui-alert-danger` im relevanten Bereich anzeigen, nicht verstecken.
- **Leere Zustände:**
  - Sinnvolle Empty States in Cards (Icon + kurzer Text + CTA-Button) statt leerer Tabellen.
- **Tastatur & Screenreader:**
  - Buttons für zentrale Aktionen nutzen, keine Links misbrauchen.
  - Sinnvolle `aria-label` / Beschriftungen vorbereiten (Platzhalter-Kommentare, wo Backend/Daten fehlen).

---

## Erwarteter Output pro Seite (MUST)

Wenn du dieses UI entwirfst, liefere IMMER:

1. **HTML-Template (Jinja2-kompatibel)**  
   - Vollständige Struktur für die Seite oder das Fragment.  
   - Nur Klassen aus UI 1.0 (`ui-`-Klassen), plus minimal Projekt-spezifische IDs/Names, aber ohne neue Styles zu erfinden.

2. **Kurze UI-Beschreibung in Textform**  
   - `UI-Layout:` Wie sind Header, Cards, Grids, Seitenbereiche aufgebaut?  
   - `Interaktionen:` Welche Elemente sind klickbar, welche haben Lade-/Fehlerzustände, welche sind HTMX-Ziele?  
   - `Responsiveness:` Wie bricht das Layout auf Mobile/Tablet/Desktop um?

3. **Liste der verwendeten `ui-` Komponenten**  
   - Stichpunktliste, z. B.:  
     - `ui-card`, `ui-card-header`, `ui-card-body`, `ui-card-footer`  
     - `ui-btn-primary`, `ui-btn-secondary`, `ui-btn-danger`  
     - `ui-badge-success`, `ui-badge-warning`, `ui-alert-danger`  
     - `ui-grid ui-grid-cols-3`, `ui-container`, `ui-page`, `ui-page-header`, `ui-page-content`  

4. **Optional: Token-Vorschläge (nur Text)**  
   - Wenn du merkst, dass bestimmte UI-Muster mit zusätzlichen Tokens sauberer wären, liste sie in einem eigenen Abschnitt:  
     - `Token-Vorschläge:` z. B.  
       - `--ui-accent-soulspot: #...` für spezielle Akzentfarbe  
       - `--ui-radius-pill-lg` für spezielle Pill-Radien  
   - Nur Vorschlag als Text, keine direkte Änderung/Erweiterung von `theme.css`.

---

## Konkreter Auftrag (zum Ausfüllen)

> Erstelle auf Basis des UI 1.0 Design Systems ein modernes, card-basiertes, übersichtliches UI für:
>
> - Seite/Feature: `<hier eintragen>`
> - Hauptziel der Seite: `<hier eintragen>`
> - Wichtigste Aktionen (3): `<hier eintragen>`
> - Wichtigste Informationen (5): `<hier eintragen>`
>
> Verwende nur `ui-` Klassen aus `theme.css`, `components.css` und `layout.css`.  
> Liefere: (1) HTML-Template, (2) UI-Beschreibung, (3) Liste verwendeter `ui-` Komponenten, (4) optional Token-Vorschläge als Text.
