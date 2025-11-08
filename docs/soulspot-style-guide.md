Style Guide & Design System

- Produkt: Soulspot (einheitliches Design-System)
- Version: 1.0.0
- Letzte Aktualisierung: 2025-11-04

Implementierung:

- CSS-Framework: **Tailwind CSS**
- Tokens werden in `tailwind.config.js` unter `theme` gespiegelt.
- Projektspezifische Komponenten-Styles in `static/css/app.css` und ggf. `static/css/components/*.css`.

---

## 0. Regeln

### 0.1 Verbindliche Regeln (MUST)

- Neue Styles:
  - verwenden Tailwind-Klassen, die in `tailwind.config.js` auf Basis der definierten Tokens konfiguriert sind.
  - nutzen ausschließlich die hier definierte Farb-, Typografie- und Spacing-Skala.
- Neue Layouts und Komponenten:
  - setzen auf bestehende Tailwind-Utilities oder dokumentierte Komponentenklassen (z. B. `.btn`, `.card`, `.alert`) auf.
  - werden in den vorgesehenen CSS-Dateien ergänzt (z. B. `static/css/components/buttons.css`, `app.css`), nicht in vereinzelten Seiten-Dateien.
- Accessibility:
  - alle interaktiven Elemente erhalten sichtbare `:focus-visible`-Zustände.
  - ARIA-Attribute werden gemäß den Vorgaben in diesem Dokument gesetzt.

### 0.2 Verbote (MUST NOT)

- Keine neuen Hexfarben oder RGB/HSL-Werte außerhalb der Palette.
- Keine neuen Fontgrößen, Spacing-Werte oder Breakpoints außerhalb der Skalen.
- Keine Inline-Styles für Layout/Design (außer explizit markierte Sonderfälle).
- Keine eigenen globalen Utility-Klassen, die Tailwind duplizieren.

### 0.3 Empfehlungen (SHOULD)

- Bestehende Komponenten (Buttons, Cards, Alerts, Forms) möglichst wiederverwenden.
- Vor neuen Komponenten prüfen, ob eine Komposition aus Tailwind-Utilities und vorhandenen Komponenten ausreicht.
- Animationen sparsam einsetzen und `prefers-reduced-motion` respektieren.

### 0.4 Mapping zur Codebase

- Design-Tokens: `tailwind.config.js` → `theme`.
- Baseline-/Komponenten-CSS:
  - `static/css/app.css`
  - optional: `static/css/components/*.css`
- Icon-Sprites:
  - z. B. `static/img/icons.svg`

---

## 1. Design-Prinzipien

### 1.1 Klarheit über Komplexität

- Einfache, verständliche UI vor komplexen Features.
- Klare visuelle Hierarchie.
- Konsistente Patterns über alle Pages.

### 1.2 Zugänglichkeit für alle

- WCAG AA als Minimum.
- Vollständige Keyboard-Navigation für alle interaktiven Elemente.
- Screen-Reader-kompatible Struktur.
- Farbkontraste gemäß Regeln in Abschnitt 2.5.

### 1.3 Performance-First

- Ziel: LCP < 2 s auf typischen Geräten.
- Minimale CSS- und JS-Bundle-Sizes.
- Progressive Enhancement: UI funktioniert ohne JS, wird mit JS besser.

### 1.4 Mobile-First

- Design ab kleinsten Viewports geplant.
- Touch-Targets ≥ 44×44 px.
- Mobile-optimierte Layouts, dann Skalierung nach oben.

---

## 2. Farbpalette

> Alle Farben werden in Tailwind als `theme.colors` gespiegelt, z. B.  
> `--color-primary-500` → `theme.colors.primary.500`.

### 2.1 Primärfarben

**Primary (Hauptfarbe)**

```css
--color-primary-50:  #f0f9ff;
--color-primary-100: #e0f2fe;
--color-primary-200: #bae6fd;
--color-primary-300: #7dd3fc;
--color-primary-400: #38bdf8;
--color-primary-500: #0ea5e9;  /* Main Primary */
--color-primary-600: #0284c7;
--color-primary-700: #0369a1;
--color-primary-800: #075985;
--color-primary-900: #0c4a6e;
```
Verwendung:

- Primäre Call-to-Actions (Buttons, Links)
- Navigation-Highlights
- Fokus-States

Secondary (Sekundärfarbe)

```css
--color-secondary-50:  #faf5ff;
--color-secondary-100: #f3e8ff;
--color-secondary-200: #e9d5ff;
--color-secondary-300: #d8b4fe;
--color-secondary-400: #c084fc;
--color-secondary-500: #a855f7;  /* Main Secondary */
--color-secondary-600: #9333ea;
--color-secondary-700: #7e22ce;
--color-secondary-800: #6b21a8;
--color-secondary-900: #581c87;
```
Verwendung:

- Akzente und Highlights
- Secondary-Actions
- Dekorative Elemente

### 2.2 Semantische Farben

Success
```css
--color-success-50:  #f0fdf4;
--color-success-100: #dcfce7;
--color-success-500: #22c55e;  /* Main Success */
--color-success-900: #14532d;
```
Verwendung: Erfolgs-Meldungen, positive States.

Error
```css
--color-error-50:  #fef2f2;
--color-error-100: #fee2e2;
--color-error-500: #ef4444;  /* Main Error */
--color-error-900: #7f1d1d;
```
Verwendung: Fehlermeldungen, destruktive Aktionen.

Warning
```css
--color-warning-50:  #fffbeb;
--color-warning-100: #fef3c7;
--color-warning-500: #f59e0b;  /* Main Warning */
--color-warning-900: #78350f;
```
Verwendung: Warnungen.

Info
```css
--color-info-50:  #eff6ff;
--color-info-100: #dbeafe;
--color-info-500: #3b82f6;  /* Main Info */
--color-info-900: #1e3a8a;
```
Verwendung: neutrale Informationen.

### 2.3 Neutral-Farben (Grays)
```css
--color-gray-50:  #f9fafb;  /* Lightest */
--color-gray-100: #f3f4f6;
--color-gray-200: #e5e7eb;
--color-gray-300: #d1d5db;
--color-gray-400: #9ca3af;
--color-gray-500: #6b7280;  /* Mid-Gray */
--color-gray-600: #4b5563;
--color-gray-700: #374151;
--color-gray-800: #1f2937;
--color-gray-900: #111827;  /* Darkest */
```
Verwendung:

- Text: 900, 800, 700
- Borders: 300, 200
- Backgrounds: 50, 100
- Disabled-States: 400, 500

### 2.4 Dark-Mode-Anpassungen
```css
@media (prefers-color-scheme: dark) {
  :root {
    --color-gray-50: #111827;
    --color-gray-100: #1f2937;
    --color-gray-200: #374151;
    --color-gray-300: #4b5563;
    --color-gray-400: #6b7280;
    --color-gray-500: #9ca3af;
    --color-gray-600: #d1d5db;
    --color-gray-700: #e5e7eb;
    --color-gray-800: #f3f4f6;
    --color-gray-900: #f9fafb;
  }
}
```
Dark-Mode-Konfiguration in Tailwind optional ergänzen.

### 2.5 Color-Contrast-Regeln
Background | Text-Color | Ratio | WCAG
- White | Gray-900 | 16.6:1 | AAA
- Gray-50 | Gray-900 | 15.8:1 | AAA
- Primary-500 | White | 4.5:1 | AA
- Error-500 | White | 4.5:1 | AA
- Success-500 | White | 3.3:1 | AA Large

Regel:

- Normaler Text: mindestens 4.5:1.
- Großer Text (≥ 18 px oder ≥ 14 px fett): mindestens 3:1.

---

## 3. Typography

### 3.1 Font-Families
```css
--font-family-sans: system-ui, -apple-system, BlinkMacSystemFont,
                    "Segoe UI", Roboto, "Helvetica Neue", Arial,
                    sans-serif;

--font-family-mono: "SFMono-Regular", Consolas, "Liberation Mono",
                    Menlo, Courier, monospace;
```
Verwendung:

- Sans: Body, UI, Überschriften.
- Mono: Code, IDs, technische Daten.

### 3.2 Font-Sizes
```css
--font-size-xs:   0.75rem;   /* 12px */
--font-size-sm:   0.875rem;  /* 14px */
--font-size-base: 1rem;      /* 16px */
--font-size-lg:   1.125rem;  /* 18px */
--font-size-xl:   1.25rem;   /* 20px */
--font-size-2xl:  1.5rem;    /* 24px */
--font-size-3xl:  1.875rem;  /* 30px */
--font-size-4xl:  2.25rem;   /* 36px */
--font-size-5xl:  3rem;      /* 48px */
```
Tailwind-Mapping: text-xs … text-5xl.

### 3.3 Font-Weights
```css
--font-weight-normal:    400;
--font-weight-medium:    500;
--font-weight-semibold:  600;
--font-weight-bold:      700;
```
Tailwind: font-normal, font-medium, font-semibold, font-bold.

### 3.4 Line-Heights
```css
--line-height-tight:    1.25;
--line-height-normal:   1.5;
--line-height-relaxed:  1.75;
```
Tailwind: leading-tight, leading-normal, leading-relaxed.

### 3.5 Typography-Scale
Element | Size | Weight | Line-Height | Use Case
- h1 | 3xl (30px) | Bold (700) | Tight (1.25) | Page-Title
- h2 | 2xl (24px) | Semibold | Tight (1.25) | Section-Title
- h3 | xl (20px) | Semibold | Tight (1.25) | Subsection
- h4 | lg (18px) | Medium | Normal (1.5) | Card-Title
- body | base (16px) | Normal | Normal (1.5) | Body-Text
- small | sm (14px) | Normal | Normal (1.5) | Helper-Text
- caption | xs (12px) | Normal | Normal (1.5) | Labels

### 3.6 Typography-Beispiele
```html
<h1 class="text-3xl font-bold text-gray-900">
  Harmony – Music Downloader
</h1>

<h2 class="text-2xl font-semibold text-gray-800 mb-4">
  Soulseek-Status
</h2>

<p class="text-base text-gray-700 leading-normal">
  Ihre Bibliothek umfasst 1.234 Tracks von 56 Künstlern.
</p>

<span class="text-sm text-gray-500">
  Zuletzt aktualisiert: vor 5 Minuten
</span>
```

---

## 4. Spacing-System (4px-Grid)

### 4.1 Spacing-Scale
```css
--spacing-0:  0;
--spacing-1:  0.25rem;  /* 4px */
--spacing-2:  0.5rem;   /* 8px */
--spacing-3:  0.75rem;  /* 12px */
--spacing-4:  1rem;     /* 16px */
--spacing-5:  1.25rem;  /* 20px */
--spacing-6:  1.5rem;   /* 24px */
--spacing-8:  2rem;     /* 32px */
--spacing-10: 2.5rem;   /* 40px */
--spacing-12: 3rem;     /* 48px */
--spacing-16: 4rem;     /* 64px */
--spacing-20: 5rem;     /* 80px */
--spacing-24: 6rem;     /* 96px */
```
Tailwind-Mapping: p-0 … p-24, m-0 … etc.

### 4.2 Spacing-Verwendung
Kontext | Spacing | Pixel | Verwendung
- Tight | 1–2 | 4–8 | Icon-to-Text, Inline-Elements
- Compact | 3–4 | 12–16 | Form-Fields, List-Items
- Normal | 4–6 | 16–24 | Card-Padding, Section-Spacing
- Relaxed | 8–12 | 32–48 | Section-Breaks, Page-Spacing
- Loose | 16–24 | 64–96 | Hero-Sections

### 4.3 Spacing-Beispiele
```html
<div class="p-6">
  <h3 class="mb-4">Title</h3>
  <p class="mb-2">Text</p>
</div>

<div class="flex gap-2">
  <button>OK</button>
  <button>Cancel</button>
</div>

<section class="py-12">
  ...
</section>
```

---

## 5. Layout & Grid

### 5.1 Breakpoints
```css
--breakpoint-sm: 640px;
--breakpoint-md: 768px;
--breakpoint-lg: 1024px;
--breakpoint-xl: 1280px;
--breakpoint-2xl: 1536px;
```
Tailwind: sm, md, lg, xl, 2xl.

### 5.2 Container
```css
.container {
  width: 100%;
  margin-left: auto;
  margin-right: auto;
  padding-left: var(--spacing-4);
  padding-right: var(--spacing-4);
}

@media (min-width: 640px)  { .container { max-width: 640px; } }
@media (min-width: 768px)  { .container { max-width: 768px; } }
@media (min-width: 1024px) { .container { max-width: 1024px; } }
@media (min-width: 1280px) { .container { max-width: 1280px; } }
```
Tailwind: container mx-auto px-4.

### 5.3 Grid-System
```html
<div class="grid grid-cols-12 gap-4">
  <aside class="col-span-12 md:col-span-3">
    ...
  </aside>
  <main class="col-span-12 md:col-span-9">
    ...
  </main>
</div>

<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  <div class="card">...</div>
  <div class="card">...</div>
  <div class="card">...</div>
</div>
```

---

## 6. Komponenten

Komponenten = HTML-Struktur + Tailwind-Utilities, optional ergänzt durch CSS-Komponentenklassen (.btn, .card, .alert).

### 6.1 Buttons

Varianten:
```html
<button class="btn btn-primary">
  Speichern
</button>

<button class="btn btn-secondary">
  Abbrechen
</button>

<button class="btn btn-outline">
  Details
</button>

<button class="btn btn-ghost">
  Bearbeiten
</button>

<button class="btn btn-danger">
  Löschen
</button>
```

Größen:
```html
<button class="btn btn-primary btn-sm">Klein</button>
<button class="btn btn-primary btn-md">Normal</button>
<button class="btn btn-primary btn-lg">Groß</button>
```

States:
```html
<button class="btn btn-primary" disabled>Disabled</button>

<button class="btn btn-primary">
  <span class="spinner"></span>
  Lädt...
</button>

<button class="btn btn-icon btn-primary">
  <svg>...</svg>
</button>
```

Beispiel-CSS (Tailwind-basiertes Layer, Umsetzung je nach Setup):
```css
.btn {
  @apply inline-flex items-center justify-center gap-2
         px-4 py-2 text-base font-medium leading-tight
         rounded-md border border-transparent
         transition-all;
}

.btn:focus-visible {
  outline: 2px solid var(--color-primary-500);
  outline-offset: 2px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  @apply text-white;
  background-color: var(--color-primary-500);
}
.btn-primary:hover:not(:disabled) {
  background-color: var(--color-primary-600);
}
```

### 6.2 Forms

Grundregeln:

- Jedes Input hat ein Label (for/id).
- Fehlerzustände:
  - aria-invalid="true"
  - aria-describedby="<id-des-fehlers>" und role="alert".

Beispiel:
```html
<div class="space-y-1">
  <label for="email" class="block text-sm font-medium text-gray-700">
    E-Mail-Adresse <span class="text-red-500">*</span>
  </label>

  <input
    type="email"
    id="email"
    name="email"
    class="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm"
    placeholder="beispiel@mail.de"
    required
  />

  <p class="text-xs text-gray-500">
    Wir teilen Ihre E-Mail niemals mit Dritten.
  </p>
</div>
```

Error-Variante:
```html
<div class="space-y-1">
  <label for="password" class="block text-sm font-medium text-gray-700">
    Passwort
  </label>

  <input
    type="password"
    id="password"
    name="password"
    class="block w-full rounded-md border-red-500 shadow-sm focus:border-red-500 focus:ring-red-500 text-sm"
    aria-invalid="true"
    aria-describedby="password-error"
  />

  <p id="password-error" class="text-xs text-red-600" role="alert">
    Passwort muss mindestens 8 Zeichen enthalten.
  </p>
</div>
```

### 6.3 Cards
```html
<div class="card bg-white rounded-lg shadow-sm border border-gray-200 p-6">
  <div class="card-header mb-4">
    <h3 class="card-title text-lg font-medium text-gray-900">Card-Title</h3>
  </div>

  <div class="card-body space-y-2">
    <p class="text-sm text-gray-700">Card-Content hier...</p>
  </div>

  <div class="card-footer mt-4 flex justify-end">
    <button class="btn btn-primary btn-sm">Action</button>
  </div>
</div>
```

### 6.4 Alerts
```html
<div class="alert alert-success flex items-start gap-3 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800" role="alert">
  <svg class="alert-icon h-5 w-5 mt-0.5" aria-hidden="true">
    <use href="/static/icons.svg#icon-check"></use>
  </svg>
  <div class="alert-content">
    <strong class="font-semibold">Erfolg!</strong> Ihre Änderungen wurden gespeichert.
  </div>
  <button class="alert-close ml-auto text-green-700 hover:text-green-900" aria-label="Alert schließen">
    &times;
  </button>
</div>
```
Varianten: alert-error, alert-warning, alert-info mit entsprechenden Farben.

### 6.5 Badges
```html
<span class="badge inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-primary-100 text-primary-800">
  Neu
</span>
```
Weitere Varianten: badge-success, badge-error, badge-warning, badge-gray.

### 6.6 Tables
```html
<table class="table min-w-full divide-y divide-gray-200 text-sm">
  <thead class="bg-gray-50">
    <tr>
      <th scope="col" class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Name
      </th>
      <th scope="col" class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Status
      </th>
      <th scope="col" class="px-4 py-2 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Actions
      </th>
    </tr>
  </thead>
  <tbody class="divide-y divide-gray-200 bg-white">
    <tr>
      <td class="px-4 py-2 whitespace-nowrap">Track 1</td>
      <td class="px-4 py-2 whitespace-nowrap">
        <span class="badge badge-success">Verfügbar</span>
      </td>
      <td class="px-4 py-2 whitespace-nowrap text-right">
        <button class="btn btn-ghost btn-sm">Details</button>
      </td>
    </tr>
  </tbody>
</table>
```

### 6.7 Modals
```html
<div class="modal fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="modal-title">
  <!-- Overlay -->
  <div class="modal-overlay fixed inset-0 bg-black/40"></div>

  <!-- Modal-Content -->
  <div class="modal-content relative z-10 w-full max-w-lg rounded-lg bg-white shadow-lg">
    <div class="modal-header flex items-center justify-between border-b border-gray-200 px-4 py-3">
      <h2 id="modal-title" class="modal-title text-lg font-semibold text-gray-900">
        Modal-Title
      </h2>
      <button class="modal-close text-gray-400 hover:text-gray-600" aria-label="Modal schließen">
        &times;
      </button>
    </div>

    <div class="modal-body px-4 py-3">
      <p class="text-sm text-gray-700">
        Modal-Content...
      </p>
    </div>

    <div class="modal-footer flex justificy-end gap-2 border-t border-gray-200 px-4 py-3">
      <button class="btn btn-secondary btn-sm">Abbrechen</button>
      <button class="btn btn-primary btn-sm">Bestätigen</button>
    </div>
  </div>
</div>
```

Anforderungen:

- Fokus beim Öffnen in das Modal setzen.
- Fokus beim Schließen zurück zum auslösenden Element.
- Escape schließt das Modal.
- Tab-Reihenfolge vollständig und logisch.

---

## 7. Icons

### 7.1 Icon-System
Sprite:
(Icon-Sprite z. B. `static/img/icons.svg` nutzen und via `<use href="/static/img/icons.svg#id">` einbinden.)

Verwendung:
```html
<svg class="icon icon-md" aria-hidden="true">
  <use href="/static/img/icons.svg#icon-name"></use

