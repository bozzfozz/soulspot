// SoulSpot New UI - Main JavaScript
// Hey future me - this is the main JS for the new UI. It handles sidebar toggle, notifications,
// modals, context menus, and HTMX event listeners. The SoulSpot global object is the main entry
// point. Make sure to call SoulSpot.init() on DOMContentLoaded!

const SoulSpot = {
    // Initialize - called on DOMContentLoaded
    init() {
        this.setupSidebar();
        this.setupTabs();
        this.setupMockInteractions();
        console.log('SoulSpot UI initialized');
    },

    // Sidebar toggle and mobile menu handling
    setupSidebar() {
        const toggle = document.getElementById('sidebar-toggle');
        const sidebar = document.querySelector('.app-sidebar');

        if (toggle && sidebar) {
            // Restore state (desktop only)
            if (window.innerWidth > 768) {
                const collapsed = localStorage.getItem('sidebar-collapsed') === 'true';
                if (collapsed) sidebar.classList.add('collapsed');
            }

            toggle.addEventListener('click', () => {
                if (window.innerWidth <= 768) {
                    sidebar.classList.toggle('mobile-open');
                } else {
                    sidebar.classList.toggle('collapsed');
                    localStorage.setItem('sidebar-collapsed', sidebar.classList.contains('collapsed'));
                }
            });

            // Close mobile sidebar when clicking outside
            document.addEventListener('click', (e) => {
                if (window.innerWidth <= 768 &&
                    sidebar.classList.contains('mobile-open') &&
                    !sidebar.contains(e.target) &&
                    !toggle.contains(e.target)) {
                    sidebar.classList.remove('mobile-open');
                }
            });
        }
    },

    // Tab switching functionality
    setupTabs() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetId = e.target.dataset.tab;
                const container = e.target.closest('.tabs-container') || document.body;

                // Update buttons
                container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');

                // Update content
                container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                const targetContent = container.querySelector(`#${targetId}`);
                if (targetContent) targetContent.classList.add('active');
            });
        });
    },

    // Event delegation for play/download buttons - HTMX friendly
    setupMockInteractions() {
        document.body.addEventListener('click', (e) => {
            // Play Button Logic
            const playBtn = e.target.closest('.btn-icon');
            if (playBtn && playBtn.querySelector('.fa-play, .fa-pause')) {
                e.preventDefault();
                const icon = playBtn.querySelector('i');
                const isPlaying = icon.classList.contains('fa-pause');

                // Reset all other play buttons
                document.querySelectorAll('.fa-pause').forEach(i => {
                    if (i !== icon) {
                        i.classList.remove('fa-pause');
                        i.classList.add('fa-play');
                    }
                });

                if (!isPlaying) {
                    icon.classList.remove('fa-play');
                    icon.classList.add('fa-pause');
                    this.showNotification('Playback started', 'success');
                } else {
                    icon.classList.remove('fa-pause');
                    icon.classList.add('fa-play');
                    this.showNotification('Playback paused', 'info');
                }
                return;
            }

            // Download Button Logic (ignore sidebar items)
            const downloadBtn = e.target.closest('.btn-icon, .btn');
            if (downloadBtn && !downloadBtn.disabled && downloadBtn.querySelector('.fa-download')) {
                if (downloadBtn.classList.contains('sidebar-item')) return;
                e.preventDefault();
                downloadBtn.disabled = true;
                this.showNotification('Added to download queue', 'success');
                return;
            }
        });
    },

    // Notification/Toast System
    showNotification(message, type = 'info', duration = 5000) {
        const container = this.getToastContainer();
        const toast = this.createToast(message, type);
        container.appendChild(toast);

        // Auto-remove after duration
        setTimeout(() => {
            this.removeToast(toast);
        }, duration);
    },

    getToastContainer() {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    },

    createToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-times-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        toast.innerHTML = `
            <div class="toast-icon">
                <i class="fa-solid ${icons[type] || icons.info}"></i>
            </div>
            <div class="toast-content">
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" onclick="SoulSpot.removeToast(this.parentElement)">
                <i class="fa-solid fa-times"></i>
            </button>
        `;

        return toast;
    },

    removeToast(toast) {
        toast.classList.add('removing');
        setTimeout(() => {
            toast.remove();
        }, 300);
    },

    // Modal System
    showModal(title, content, buttons = []) {
        const backdrop = document.createElement('div');
        backdrop.className = 'modal-backdrop';
        backdrop.onclick = (e) => {
            if (e.target === backdrop) this.closeModal(backdrop);
        };

        const modal = document.createElement('div');
        modal.className = 'modal';

        let buttonsHtml = '';
        if (buttons.length > 0) {
            buttonsHtml = '<div class="modal-footer">';
            buttons.forEach(btn => {
                buttonsHtml += `<button class="btn ${btn.class || 'btn-outline'}" onclick="${btn.onclick}">${btn.text}</button>`;
            });
            buttonsHtml += '</div>';
        }

        modal.innerHTML = `
            <div class="modal-header">
                <div class="modal-title">${title}</div>
                <button class="modal-close" onclick="SoulSpot.closeModal(this.closest('.modal-backdrop'))">
                    <i class="fa-solid fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                ${content}
            </div>
            ${buttonsHtml}
        `;

        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
        document.body.style.overflow = 'hidden';

        return backdrop;
    },

    closeModal(backdrop) {
        backdrop.style.opacity = '0';
        setTimeout(() => {
            backdrop.remove();
            document.body.style.overflow = '';
        }, 200);
    },

    // Context Menu
    showContextMenu(event, items) {
        event.preventDefault();

        const existing = document.querySelector('.context-menu');
        if (existing) existing.remove();

        const menu = document.createElement('div');
        menu.className = 'context-menu';

        items.forEach(item => {
            if (item.separator) {
                menu.innerHTML += '<div class="context-menu-separator"></div>';
            } else {
                const menuItem = document.createElement('button');
                menuItem.className = `context-menu-item ${item.danger ? 'danger' : ''}`;
                menuItem.innerHTML = `
                    ${item.icon ? `<i class="${item.icon}"></i>` : ''}
                    <span>${item.text}</span>
                `;
                menuItem.onclick = () => {
                    item.onclick();
                    menu.remove();
                };
                menu.appendChild(menuItem);
            }
        });

        document.body.appendChild(menu);

        // Position menu
        const x = Math.min(event.clientX, window.innerWidth - menu.offsetWidth - 10);
        const y = Math.min(event.clientY, window.innerHeight - menu.offsetHeight - 10);
        menu.style.left = x + 'px';
        menu.style.top = y + 'px';

        // Close on click outside
        setTimeout(() => {
            document.addEventListener('click', function closeMenu() {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            });
        }, 0);
    },

    // Breadcrumbs Helper
    createBreadcrumbs(items) {
        const container = document.createElement('div');
        container.className = 'breadcrumbs';

        items.forEach((item, index) => {
            if (index > 0) {
                const separator = document.createElement('span');
                separator.className = 'breadcrumb-separator';
                separator.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
                container.appendChild(separator);
            }

            const link = document.createElement('a');
            link.className = `breadcrumb-item ${item.active ? 'active' : ''}`;
            link.href = item.url || '#';
            link.textContent = item.text;
            if (item.active) {
                link.onclick = (e) => e.preventDefault();
            }
            container.appendChild(link);
        });

        return container;
    }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    SoulSpot.init();

    // HTMX event listeners for debugging and error handling
    document.body.addEventListener('htmx:afterSwap', (event) => {
        console.log('HTMX content swapped:', event.detail);
    });

    // Hey future me - this handles ALL HTMX errors globally!
    // Extracts error message from JSON response if available, otherwise shows generic error.
    // Most API endpoints return {detail: "error message"} on failure.
    document.body.addEventListener('htmx:responseError', (event) => {
        console.error('HTMX error:', event.detail);
        
        let errorMsg = 'An error occurred. Please try again.';
        
        // Try to extract detail from JSON response
        try {
            const xhr = event.detail.xhr;
            if (xhr && xhr.responseText) {
                const response = JSON.parse(xhr.responseText);
                if (response.detail) {
                    errorMsg = response.detail;
                } else if (response.message) {
                    errorMsg = response.message;
                }
            }
        } catch (e) {
            console.debug('Could not parse error response:', e);
        }
        
        SoulSpot.showNotification(errorMsg, 'error');
    });

    // Hey future me - htmx:afterRequest fires for ALL requests including successful ones!
    // We use this to show success toasts ONLY if request succeeded (status 2xx).
    // Partials use hx-on::after-request which calls SoulSpot.toast() - but we need
    // to check if there was an error first to avoid showing "success" on failures!
    document.body.addEventListener('htmx:afterRequest', (event) => {
        const xhr = event.detail.xhr;
        // If request failed (non-2xx), htmx:responseError already handled it
        if (xhr && xhr.status >= 400) {
            // Prevent inline hx-on::after-request from showing success toast
            event.detail.successful = false;
        }
    });
});

// Utility functions
const utils = {
    formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    },

    formatDate(date) {
        return new Intl.DateTimeFormat('de-DE').format(new Date(date));
    },

    formatDuration(seconds) {
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
};

// Alias toast() to showNotification() for HTMX templates compatibility
// Hey future me - some HTMX partials use SoulSpot.toast() but the actual method is showNotification().
// This alias ensures backwards compatibility without having to update all templates!
SoulSpot.toast = function(message, type = 'info', duration = 5000) {
    return SoulSpot.showNotification(message, type, duration);
};

// Export for use in other scripts
window.SoulSpot = SoulSpot;
window.utils = utils;
