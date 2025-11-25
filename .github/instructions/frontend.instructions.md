---
applyTo: "{src/soulspot/templates/**/*,src/soulspot/static/**/*,*.html,*.css,*.js}"
---

# Frontend Guidelines

## Tech Stack
- **Templates:** Jinja2 templates in `src/soulspot/templates/`
- **Styling:** TailwindCSS (config in `tailwind.config.js`)
- **Interactivity:** HTMX for dynamic updates

## Template Structure
- Base template: `templates/base.html`
- Partials for HTMX responses in `templates/partials/`
- Page templates extend the base template.

## HTMX Patterns
- Use `hx-get`, `hx-post` for server requests.
- Use `hx-target` to specify update targets.
- Use `hx-swap` to control DOM replacement.

## CSS Guidelines
- Use TailwindCSS utility classes.
- Avoid custom CSS when Tailwind utilities suffice.
- Keep responsive design in mind (`sm:`, `md:`, `lg:` prefixes).

## Accessibility
- Use semantic HTML elements.
- Include `aria-` attributes for interactive elements.
- Ensure keyboard navigation works.

## Static Files
- Static assets in `src/soulspot/static/`.
- Reference via `/static/` URL prefix.
