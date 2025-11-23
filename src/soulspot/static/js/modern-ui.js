// AI-Model: Claude 3.5 Sonnet
// Modern UI interactions and utilities for SoulSpot Bridge

/**
 * Toast Notification System
 * Creates beautiful, accessible toast notifications
 */
class ToastManager {
  constructor() {
    this.container = this.createContainer();
    this.toasts = new Map();
  }

  createContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'fixed top-4 right-4 z-50 flex flex-col gap-3 pointer-events-none';
      container.setAttribute('aria-live', 'polite');
      container.setAttribute('aria-atomic', 'true');
      document.body.appendChild(container);
    }
    return container;
  }

  show(message, type = 'info', duration = 5000) {
    const id = Date.now() + Math.random();
    const toast = this.createToast(message, type, id);
    
    this.container.appendChild(toast);
    this.toasts.set(id, toast);

    // Animate in
    requestAnimationFrame(() => {
      toast.classList.add('animate-slide-up');
      toast.style.pointerEvents = 'auto';
    });

    // Auto dismiss
    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }

    return id;
  }

  createToast(message, type, id) {
    const toast = document.createElement('div');
    toast.className = `toast-modern toast-${type} max-w-md w-full`;
    toast.setAttribute('role', 'alert');
    
    const icon = this.getIcon(type);
    const closeBtn = `
      <button 
        class="ml-auto flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors focus-visible-ring"
        onclick="window.toastManager.dismiss(${id})"
        aria-label="Close notification"
      >
        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
        </svg>
      </button>
    `;

    toast.innerHTML = `
      ${icon}
      <div class="flex-1">
        <p class="font-medium text-gray-900 dark:text-white">${message}</p>
      </div>
      ${closeBtn}
    `;

    return toast;
  }

  getIcon(type) {
    const icons = {
      success: `
        <svg class="w-6 h-6 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
        </svg>
      `,
      error: `
        <svg class="w-6 h-6 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
        </svg>
      `,
      warning: `
        <svg class="w-6 h-6 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>
      `,
      info: `
        <svg class="w-6 h-6 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
        </svg>
      `
    };
    return icons[type] || icons.info;
  }

  dismiss(id) {
    const toast = this.toasts.get(id);
    if (toast) {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => {
        toast.remove();
        this.toasts.delete(id);
      }, 300);
    }
  }

  success(message, duration) {
    return this.show(message, 'success', duration);
  }

  error(message, duration) {
    return this.show(message, 'error', duration);
  }

  warning(message, duration) {
    return this.show(message, 'warning', duration);
  }

  info(message, duration) {
    return this.show(message, 'info', duration);
  }
}

// Global toast manager instance
window.toastManager = new ToastManager();

/**
 * Loading Overlay Utility
 * Shows/hides loading overlays on elements
 */
class LoadingOverlay {
  static show(element, message = 'Loading...') {
    const overlay = document.createElement('div');
    overlay.className = 'absolute inset-0 z-50 flex flex-col items-center justify-center bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm rounded-lg';
    overlay.innerHTML = `
      <div class="spinner-modern mb-4"></div>
      <p class="text-sm text-gray-600 dark:text-gray-400">${message}</p>
    `;
    overlay.setAttribute('data-loading-overlay', 'true');
    
    element.style.position = 'relative';
    element.appendChild(overlay);
  }

  static hide(element) {
    const overlay = element.querySelector('[data-loading-overlay="true"]');
    if (overlay) {
      overlay.style.opacity = '0';
      setTimeout(() => overlay.remove(), 200);
    }
  }
}

window.LoadingOverlay = LoadingOverlay;

/**
 * Enhanced HTMX Event Handlers
 * Provides better UX feedback for HTMX requests
 */
document.body.addEventListener('htmx:beforeRequest', function(event) {
  const target = event.detail.target;
  
  // Add loading class
  target.classList.add('htmx-loading');
  
  // Show loading indicator for longer requests
  const loadingTimeout = setTimeout(() => {
    if (target.classList.contains('htmx-loading')) {
      LoadingOverlay.show(target);
    }
  }, 500);
  
  target.setAttribute('data-loading-timeout', loadingTimeout);
});

document.body.addEventListener('htmx:afterRequest', function(event) {
  const target = event.detail.target;
  
  // Clear loading state
  target.classList.remove('htmx-loading');
  const timeout = target.getAttribute('data-loading-timeout');
  if (timeout) {
    clearTimeout(parseInt(timeout));
    target.removeAttribute('data-loading-timeout');
  }
  LoadingOverlay.hide(target);
  
  // Show success/error toast
  const xhr = event.detail.xhr;
  if (xhr.status >= 200 && xhr.status < 300) {
    // Success - show toast only for mutations (POST, PUT, DELETE)
    const verb = event.detail.requestConfig.verb;
    if (['post', 'put', 'patch', 'delete'].includes(verb.toLowerCase())) {
      const successMessage = target.getAttribute('data-success-message');
      if (successMessage) {
        toastManager.success(successMessage);
      }
    }
  }
});

document.body.addEventListener('htmx:responseError', function(event) {
  const target = event.detail.target;
  LoadingOverlay.hide(target);
  
  const errorMessage = target.getAttribute('data-error-message') || 'An error occurred. Please try again.';
  toastManager.error(errorMessage);
  
  console.error('HTMX Error:', event.detail);
});

document.body.addEventListener('htmx:sendError', function(event) {
  const target = event.detail.target;
  LoadingOverlay.hide(target);
  
  toastManager.error('Network error. Please check your connection.');
  console.error('HTMX Send Error:', event.detail);
});

/**
 * Smooth Scroll Utility
 */
function smoothScrollTo(target, offset = 0) {
  const element = typeof target === 'string' ? document.querySelector(target) : target;
  if (!element) return;
  
  const targetPosition = element.getBoundingClientRect().top + window.pageYOffset - offset;
  window.scrollTo({
    top: targetPosition,
    behavior: 'smooth'
  });
}

window.smoothScrollTo = smoothScrollTo;

/**
 * Copy to Clipboard Utility
 */
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    toastManager.success('Copied to clipboard!', 2000);
    return true;
  } catch (err) {
    toastManager.error('Failed to copy');
    console.error('Copy failed:', err);
    return false;
  }
}

window.copyToClipboard = copyToClipboard;

/**
 * Confirm Dialog Utility
 * Creates a modern confirm dialog
 */
function confirmAction(message, title = 'Confirm Action') {
  return new Promise((resolve) => {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in';
    modal.innerHTML = `
      <div class="card-modern max-w-md w-full p-6 animate-scale-in">
        <h3 class="text-xl font-bold text-gray-900 dark:text-white mb-4">${title}</h3>
        <p class="text-gray-600 dark:text-gray-400 mb-6">${message}</p>
        <div class="flex justify-end gap-3">
          <button class="btn btn-secondary btn-modern" data-action="cancel">
            Cancel
          </button>
          <button class="btn btn-danger btn-modern" data-action="confirm">
            Confirm
          </button>
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    
    modal.addEventListener('click', function(e) {
      const action = e.target.closest('[data-action]')?.getAttribute('data-action');
      if (action) {
        modal.style.opacity = '0';
        setTimeout(() => modal.remove(), 200);
        resolve(action === 'confirm');
      }
    });
  });
}

window.confirmAction = confirmAction;

/**
 * Initialize all interactive components
 */
document.addEventListener('DOMContentLoaded', function() {
  // Auto-init tooltips, popovers, etc.
  console.log('🎨 Modern UI initialized');
  
  // Add stagger animation to grid items
  document.querySelectorAll('[data-stagger]').forEach(container => {
    container.classList.add('stagger-children');
  });
});

/**
 * Progress Bar Component
 */
class ProgressBar {
  constructor(element) {
    this.element = element;
    this.fill = element.querySelector('.progress-fill-modern') || this.createFill();
  }

  createFill() {
    const fill = document.createElement('div');
    fill.className = 'progress-fill-modern';
    this.element.appendChild(fill);
    return fill;
  }

  set value(percent) {
    this.fill.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  }

  get value() {
    return parseFloat(this.fill.style.width) || 0;
  }

  animate(from, to, duration = 1000) {
    const start = performance.now();
    const diff = to - from;

    const step = (timestamp) => {
      const elapsed = timestamp - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = this.easeOutCubic(progress);
      
      this.value = from + (diff * eased);

      if (progress < 1) {
        requestAnimationFrame(step);
      }
    };

    requestAnimationFrame(step);
  }

  easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }
}

window.ProgressBar = ProgressBar;

/**
 * Debounce utility for search inputs
 */
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

window.debounce = debounce;

/**
 * Format duration (ms to human readable)
 */
function formatDuration(ms) {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  
  if (hours > 0) {
    return `${hours}:${String(minutes % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  }
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
}

window.formatDuration = formatDuration;

/**
 * Format file size
 */
function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

window.formatFileSize = formatFileSize;
