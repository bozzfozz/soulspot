# Keyboard Navigation Guide

SoulSpot supports comprehensive keyboard navigation for improved accessibility and power user workflows.

## Global Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + K` | Focus search input (when available) |
| `Esc` | Close modals and dialogs |
| `Tab` | Navigate to next focusable element |
| `Shift + Tab` | Navigate to previous focusable element |

## Accessibility Features

### Skip to Content
Press `Tab` on page load to reveal a "Skip to main content" link that allows keyboard users to bypass navigation and jump directly to the main content.

### Focus Indicators
All interactive elements (buttons, links, form inputs) display a clear blue focus ring when navigated to via keyboard. This ensures you always know where you are on the page.

### Modal Focus Trapping
When a modal or dialog is open, keyboard focus is trapped within that modal, preventing you from accidentally navigating to elements behind it. Press `Esc` to close modals.

### ARIA Labels
All interactive elements include appropriate ARIA labels for screen reader users, ensuring a fully accessible experience.

## Page-Specific Navigation

### Dashboard (`/ui/`)
- Tab through statistics cards
- Navigate to Quick Actions buttons

### Playlists (`/ui/playlists`)
- Navigate through playlist cards
- Use `Enter` or `Space` to activate Sync buttons

### Downloads (`/ui/downloads`)
- Tab through filter buttons
- Navigate download items and their action buttons (Retry, Cancel)

### Import Playlist (`/ui/playlists/import`)
- Tab to playlist input field
- Navigate to checkbox and buttons
- Form validation works with keyboard submission

## Tips for Keyboard Users

1. **Use Tab liberally**: All interactive elements are keyboard accessible
2. **Look for the focus ring**: A blue outline shows your current position
3. **Use Enter/Space**: Activate buttons and links
4. **Use Escape**: Quick way to dismiss modals and notifications
5. **Forms**: Use Tab to move between fields, Enter to submit

## Browser Support

Keyboard navigation works in all modern browsers:
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Feedback

If you encounter any keyboard navigation issues, please report them so we can improve accessibility for all users.
