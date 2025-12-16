/**
 * Focus Trap Utility
 * 
 * Hey future me - this is CRITICAL for accessibility (WCAG 2.4.3)!
 * When a modal/dialog is open, Tab key should cycle through focusable elements
 * inside the modal ONLY - not escape to elements behind it.
 * 
 * This is used by:
 * - Command Palette (_command_palette.html)
 * - Bottom Sheet (_bottom_sheet.html)
 * - Any modal dialog
 * 
 * Usage:
 *   const trap = new FocusTrap(modalElement, {
 *     initialFocus: firstInput,           // Element to focus on open
 *     returnFocus: true,                  // Return focus on close
 *     escapeDeactivates: true             // Close on Escape
 *   });
 *   
 *   trap.activate();   // Start trapping
 *   trap.deactivate(); // Stop trapping and return focus
 * 
 * Features:
 * - Tab cycles through focusable elements
 * - Shift+Tab goes backwards
 * - Escape key closes (optional)
 * - Returns focus to trigger element on close
 * - Handles dynamically added content
 */

class FocusTrap {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      initialFocus: options.initialFocus || null,
      returnFocus: options.returnFocus !== false,
      escapeDeactivates: options.escapeDeactivates !== false,
      onDeactivate: options.onDeactivate || null,
      ...options
    };
    
    this.previousActiveElement = null;
    this.active = false;
    
    // Bind methods
    this.handleKeydown = this.handleKeydown.bind(this);
    this.handleFocusIn = this.handleFocusIn.bind(this);
  }
  
  /**
   * Get all focusable elements within the trap container
   */
  getFocusableElements() {
    const selector = [
      'a[href]',
      'button:not([disabled])',
      'input:not([disabled]):not([type="hidden"])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
      '[contenteditable="true"]',
      'audio[controls]',
      'video[controls]',
      'details>summary:first-of-type'
    ].join(', ');
    
    const elements = Array.from(this.element.querySelectorAll(selector));
    
    // Filter out elements that are not visible
    return elements.filter(el => {
      return !el.closest('[hidden]') && 
             !el.closest('[aria-hidden="true"]') &&
             el.offsetParent !== null &&
             getComputedStyle(el).visibility !== 'hidden';
    });
  }
  
  /**
   * Activate the focus trap
   */
  activate() {
    if (this.active) return;
    this.active = true;
    
    // Store the currently focused element to return to later
    this.previousActiveElement = document.activeElement;
    
    // Add event listeners
    document.addEventListener('keydown', this.handleKeydown);
    document.addEventListener('focusin', this.handleFocusIn);
    
    // Set initial focus
    this.setInitialFocus();
    
    return this;
  }
  
  /**
   * Deactivate the focus trap
   */
  deactivate() {
    if (!this.active) return;
    this.active = false;
    
    // Remove event listeners
    document.removeEventListener('keydown', this.handleKeydown);
    document.removeEventListener('focusin', this.handleFocusIn);
    
    // Return focus to previous element
    if (this.options.returnFocus && this.previousActiveElement) {
      try {
        this.previousActiveElement.focus();
      } catch (e) {
        // Element might have been removed from DOM
      }
    }
    
    // Call deactivation callback
    if (this.options.onDeactivate) {
      this.options.onDeactivate();
    }
    
    return this;
  }
  
  /**
   * Set initial focus when trap is activated
   */
  setInitialFocus() {
    // Use specified initial focus element
    if (this.options.initialFocus) {
      const initialEl = typeof this.options.initialFocus === 'string'
        ? this.element.querySelector(this.options.initialFocus)
        : this.options.initialFocus;
      
      if (initialEl) {
        initialEl.focus();
        return;
      }
    }
    
    // Look for autofocus attribute
    const autofocusEl = this.element.querySelector('[autofocus]');
    if (autofocusEl) {
      autofocusEl.focus();
      return;
    }
    
    // Look for data-focus-initial attribute (custom)
    const initialDataEl = this.element.querySelector('[data-focus-initial]');
    if (initialDataEl) {
      initialDataEl.focus();
      return;
    }
    
    // Focus first focusable element
    const focusable = this.getFocusableElements();
    if (focusable.length > 0) {
      focusable[0].focus();
    }
  }
  
  /**
   * Handle keydown events for Tab and Escape
   */
  handleKeydown(event) {
    // Escape key
    if (event.key === 'Escape' && this.options.escapeDeactivates) {
      event.preventDefault();
      this.deactivate();
      return;
    }
    
    // Tab key
    if (event.key === 'Tab') {
      const focusable = this.getFocusableElements();
      
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      
      const firstElement = focusable[0];
      const lastElement = focusable[focusable.length - 1];
      
      // Shift+Tab on first element -> go to last
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
        return;
      }
      
      // Tab on last element -> go to first
      if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
        return;
      }
    }
  }
  
  /**
   * Handle focus events - ensure focus stays within trap
   */
  handleFocusIn(event) {
    if (!this.element.contains(event.target)) {
      // Focus escaped! Bring it back
      event.stopPropagation();
      const focusable = this.getFocusableElements();
      if (focusable.length > 0) {
        focusable[0].focus();
      }
    }
  }
  
  /**
   * Update focusable elements (call after dynamic content changes)
   */
  update() {
    // Just triggers a refresh of focusable elements on next Tab
    return this;
  }
  
  /**
   * Check if trap is currently active
   */
  isActive() {
    return this.active;
  }
}

// ===== AUTO-INITIALIZATION =====
// Automatically set up focus traps for elements with data-focus-trap attribute

document.addEventListener('DOMContentLoaded', () => {
  // Store active traps
  window._focusTraps = window._focusTraps || new Map();
  
  // Watch for dialogs opening (via hidden attribute changes)
  const observer = new MutationObserver((mutations) => {
    mutations.forEach(mutation => {
      if (mutation.type === 'attributes' && mutation.attributeName === 'hidden') {
        const dialog = mutation.target;
        
        // Skip if not a dialog/modal
        if (!dialog.matches('[role="dialog"], [data-focus-trap]')) return;
        
        const trapId = dialog.id || Math.random().toString(36);
        
        if (!dialog.hidden) {
          // Dialog opened - create trap
          if (!window._focusTraps.has(trapId)) {
            const trap = new FocusTrap(dialog, {
              escapeDeactivates: false, // Let dialog handle its own escape
              returnFocus: true
            });
            trap.activate();
            window._focusTraps.set(trapId, trap);
          }
        } else {
          // Dialog closed - remove trap
          const trap = window._focusTraps.get(trapId);
          if (trap) {
            trap.deactivate();
            window._focusTraps.delete(trapId);
          }
        }
      }
    });
  });
  
  observer.observe(document.body, {
    attributes: true,
    subtree: true,
    attributeFilter: ['hidden']
  });
});

// ===== HTMX INTEGRATION =====
// Re-initialize focus traps after HTMX swaps

document.addEventListener('htmx:afterSwap', (event) => {
  const dialog = event.detail.target.closest('[role="dialog"], [data-focus-trap]');
  if (dialog && !dialog.hidden) {
    const trap = window._focusTraps.get(dialog.id);
    if (trap) {
      trap.update();
    }
  }
});

// Export for use in other scripts
window.FocusTrap = FocusTrap;
