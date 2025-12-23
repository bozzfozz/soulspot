/**
 * Download Center - JavaScript
 * 
 * Hey future me - This handles all the interactivity for the Download Center!
 * Uses HTMX for auto-refresh and server communication.
 * 
 * Features:
 * - View toggle (cards/table)
 * - Auto-refresh control
 * - Tab navigation
 * - Sidebar collapse
 * - Batch operations
 * - Filters
 * - Export functionality
 */

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

const DCState = {
    autoRefreshEnabled: true,
    currentView: 'cards',
    currentTab: 'queue',
    sidebarCollapsed: false,
    selectedDownloads: new Set(),
    sessionStartTime: Date.now(),
    connectionStatus: 'connecting'
};

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

function initDownloadCenter() {
    // Load saved preferences
    loadPreferences();
    
    // Setup event listeners
    setupEventListeners();
    
    // Start session timer
    startSessionTimer();
    
    // Check connection status
    checkConnectionStatus();
    
    // Set initial HTMX trigger condition
    updateHtmxTriggers();
    
    console.log('Download Center initialized');
}

function loadPreferences() {
    // Load from localStorage
    const savedView = localStorage.getItem('dc-view');
    if (savedView) {
        DCState.currentView = savedView;
        setView(savedView, false);
    }
    
    const savedAutoRefresh = localStorage.getItem('dc-auto-refresh');
    if (savedAutoRefresh !== null) {
        DCState.autoRefreshEnabled = savedAutoRefresh === 'true';
        document.getElementById('auto-refresh-toggle').checked = DCState.autoRefreshEnabled;
    }
    
    const savedSidebar = localStorage.getItem('dc-sidebar-collapsed');
    if (savedSidebar === 'true') {
        DCState.sidebarCollapsed = true;
        document.getElementById('sidebar').classList.add('collapsed');
    }
}

function setupEventListeners() {
    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('settings-dropdown');
        if (dropdown && !e.target.closest('.dc-settings-dropdown')) {
            dropdown.classList.remove('open');
        }
    });
    
    // HTMX events
    document.body.addEventListener('htmx:afterSwap', handleHtmxSwap);
    document.body.addEventListener('htmx:afterRequest', handleHtmxRequest);
    
    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboard);
    
    // Checkbox selection in table view
    document.addEventListener('change', (e) => {
        if (e.target.classList.contains('dc-row-select')) {
            handleRowSelect(e.target);
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// VIEW TOGGLE
// ═══════════════════════════════════════════════════════════════════════════

function setView(view, save = true) {
    DCState.currentView = view;
    
    // Update buttons
    document.querySelectorAll('.dc-view-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    
    // Update list container
    const list = document.getElementById('downloads-list');
    if (list) {
        list.dataset.view = view;
    }
    
    // Save preference
    if (save) {
        localStorage.setItem('dc-view', view);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB NAVIGATION
// ═══════════════════════════════════════════════════════════════════════════

function switchTab(tabId) {
    DCState.currentTab = tabId;
    
    // Update tab buttons
    document.querySelectorAll('.dc-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabId);
    });
    
    // Update tab content
    document.querySelectorAll('.dc-tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabId}`);
    });
    
    // Trigger HTMX load for lazy-loaded tabs
    const tabContent = document.getElementById(`tab-${tabId}`);
    if (tabContent) {
        htmx.trigger(tabContent.querySelector('[hx-get]'), 'revealed');
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SIDEBAR
// ═══════════════════════════════════════════════════════════════════════════

function toggleSidebar() {
    DCState.sidebarCollapsed = !DCState.sidebarCollapsed;
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('collapsed', DCState.sidebarCollapsed);
    localStorage.setItem('dc-sidebar-collapsed', DCState.sidebarCollapsed);
}

// ═══════════════════════════════════════════════════════════════════════════
// AUTO-REFRESH
// ═══════════════════════════════════════════════════════════════════════════

function toggleAutoRefresh() {
    DCState.autoRefreshEnabled = document.getElementById('auto-refresh-toggle').checked;
    localStorage.setItem('dc-auto-refresh', DCState.autoRefreshEnabled);
    
    // Update status display
    document.getElementById('refresh-status').textContent = DCState.autoRefreshEnabled ? 'ON' : 'OFF';
    
    // Update HTMX triggers
    updateHtmxTriggers();
}

function updateHtmxTriggers() {
    // Enable/disable auto-refresh on HTMX elements
    // HTMX uses [auto-refresh-enabled] in the trigger to conditionally poll
    document.body.setAttribute('auto-refresh-enabled', DCState.autoRefreshEnabled);
    
    // Force re-process HTMX elements
    const containers = document.querySelectorAll('[hx-trigger*="auto-refresh-enabled"]');
    containers.forEach(el => {
        if (DCState.autoRefreshEnabled) {
            htmx.process(el);
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// FILTERS
// ═══════════════════════════════════════════════════════════════════════════

function applyFilters() {
    const status = document.getElementById('status-filter')?.value || '';
    const provider = document.getElementById('provider-filter')?.value || '';
    
    // Build URL with filters
    let url = '/api/downloads/center/htmx/queue';
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (provider) params.set('provider', provider);
    if (params.toString()) url += '?' + params.toString();
    
    // Update HTMX target URL
    const list = document.getElementById('downloads-list');
    if (list) {
        list.setAttribute('hx-get', url);
        htmx.trigger(list, 'load');
    }
}

function clearFilters() {
    document.getElementById('status-filter').value = '';
    document.getElementById('provider-filter').value = '';
    applyFilters();
}

function filterByStatus(status) {
    document.getElementById('status-filter').value = status;
    applyFilters();
}

// ═══════════════════════════════════════════════════════════════════════════
// DOWNLOAD CARD INTERACTIONS
// ═══════════════════════════════════════════════════════════════════════════

function toggleDownloadExpand(card) {
    // Don't expand if clicking on actions
    if (event.target.closest('.dc-card-actions') || event.target.closest('.dc-details-actions')) {
        return;
    }
    
    card.classList.toggle('expanded');
}

function searchAlternative(trackId) {
    // Open search with track info pre-filled
    window.location.href = `/search?track_id=${trackId}&mode=alternative`;
}

function viewTrack(trackId) {
    // Open track detail modal or page
    window.location.href = `/library/tracks/${trackId}`;
}

// ═══════════════════════════════════════════════════════════════════════════
// BATCH OPERATIONS
// ═══════════════════════════════════════════════════════════════════════════

function toggleSelectAll() {
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.dc-row-select');
    
    DCState.selectedDownloads.clear();
    
    checkboxes.forEach(cb => {
        cb.checked = selectAll.checked;
        if (selectAll.checked) {
            DCState.selectedDownloads.add(cb.value);
        }
    });
    
    updateBatchBar();
}

function handleRowSelect(checkbox) {
    if (checkbox.checked) {
        DCState.selectedDownloads.add(checkbox.value);
    } else {
        DCState.selectedDownloads.delete(checkbox.value);
    }
    
    // Update select-all checkbox state
    const selectAll = document.getElementById('select-all');
    const allCheckboxes = document.querySelectorAll('.dc-row-select');
    selectAll.checked = DCState.selectedDownloads.size === allCheckboxes.length;
    selectAll.indeterminate = DCState.selectedDownloads.size > 0 && DCState.selectedDownloads.size < allCheckboxes.length;
    
    updateBatchBar();
}

function updateBatchBar() {
    const batchBar = document.getElementById('batch-bar');
    const countSpan = document.getElementById('selected-count');
    
    if (DCState.selectedDownloads.size > 0) {
        batchBar.classList.add('visible');
        countSpan.textContent = DCState.selectedDownloads.size;
    } else {
        batchBar.classList.remove('visible');
    }
}

async function batchPause() {
    await performBatchAction('pause');
}

async function batchResume() {
    await performBatchAction('resume');
}

async function batchCancel() {
    if (!confirm(`Cancel ${DCState.selectedDownloads.size} downloads?`)) return;
    await performBatchAction('cancel');
}

async function performBatchAction(action) {
    const ids = Array.from(DCState.selectedDownloads);
    
    try {
        const response = await fetch('/api/downloads/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, download_ids: ids })
        });
        
        if (response.ok) {
            // Clear selection
            DCState.selectedDownloads.clear();
            document.querySelectorAll('.dc-row-select').forEach(cb => cb.checked = false);
            document.getElementById('select-all').checked = false;
            updateBatchBar();
            
            // Refresh list
            htmx.trigger('#downloads-list', 'load');
        } else {
            console.error('Batch action failed:', await response.text());
        }
    } catch (error) {
        console.error('Batch action error:', error);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SETTINGS DROPDOWN
// ═══════════════════════════════════════════════════════════════════════════

function toggleSettingsDropdown() {
    const dropdown = document.getElementById('settings-dropdown');
    dropdown.classList.toggle('open');
}

function toggleNotifications() {
    const enabled = document.getElementById('notifications-toggle').checked;
    
    if (enabled && 'Notification' in window) {
        Notification.requestPermission().then(permission => {
            if (permission !== 'granted') {
                document.getElementById('notifications-toggle').checked = false;
                alert('Please enable notifications in your browser settings.');
            }
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SPEED LIMITER MODAL
// ═══════════════════════════════════════════════════════════════════════════

function showSpeedLimiter() {
    document.getElementById('speed-limiter-modal').classList.add('open');
}

function hideSpeedLimiter() {
    document.getElementById('speed-limiter-modal').classList.remove('open');
}

function updateSpeedLabel(type) {
    const slider = document.getElementById(`${type}-limit`);
    const label = document.getElementById(`${type}-limit-label`);
    
    const value = parseInt(slider.value);
    label.textContent = value === 0 ? 'Unlimited' : `${value} MB/s`;
}

async function applySpeedLimits() {
    const downloadLimit = parseInt(document.getElementById('download-limit').value);
    const uploadLimit = parseInt(document.getElementById('upload-limit').value);
    
    try {
        await fetch('/api/downloads/speed-limits', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                download_limit_mbps: downloadLimit || null,
                upload_limit_mbps: uploadLimit || null
            })
        });
        
        hideSpeedLimiter();
    } catch (error) {
        console.error('Failed to apply speed limits:', error);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORT
// ═══════════════════════════════════════════════════════════════════════════

async function exportDownloads(format) {
    try {
        const response = await fetch(`/api/downloads/manager/export?format=${format}`);
        
        if (format === 'csv') {
            const blob = await response.blob();
            
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `downloads-${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
        } else {
            // JSON - download as file
            const data = await response.json();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `downloads-${new Date().toISOString().slice(0, 10)}.json`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
        }
        
        showToast('Export completed', 'success');
    } catch (error) {
        console.error('Export failed:', error);
        showToast('Export failed', 'error');
    }
}

// Alias for template compatibility
function exportQueue(format = 'json') {
    exportDownloads(format);
}

// ═══════════════════════════════════════════════════════════════════════════
// SESSION TIMER
// ═══════════════════════════════════════════════════════════════════════════

function startSessionTimer() {
    setInterval(() => {
        const elapsed = Math.floor((Date.now() - DCState.sessionStartTime) / 1000);
        const hours = Math.floor(elapsed / 3600);
        const minutes = Math.floor((elapsed % 3600) / 60);
        
        let timeStr = '';
        if (hours > 0) timeStr += `${hours}h `;
        timeStr += `${minutes}m`;
        
        document.getElementById('session-time').textContent = timeStr;
    }, 60000); // Update every minute
}

// ═══════════════════════════════════════════════════════════════════════════
// CONNECTION STATUS
// ═══════════════════════════════════════════════════════════════════════════

function checkConnectionStatus() {
    // Check slskd connection via health endpoint
    fetch('/api/downloads/manager/health')
        .then(response => response.json())
        .then(data => {
            const indicator = document.getElementById('connection-status');
            const text = document.getElementById('connection-text');
            
            if (data.overall_healthy) {
                indicator.className = 'dc-status-indicator connected';
                text.textContent = 'Connected';
                DCState.connectionStatus = 'connected';
            } else {
                indicator.className = 'dc-status-indicator disconnected';
                text.textContent = 'Disconnected';
                DCState.connectionStatus = 'disconnected';
            }
        })
        .catch(() => {
            const indicator = document.getElementById('connection-status');
            const text = document.getElementById('connection-text');
            indicator.className = 'dc-status-indicator disconnected';
            text.textContent = 'Error';
            DCState.connectionStatus = 'error';
        });
    
    // Check again in 30 seconds
    setTimeout(checkConnectionStatus, 30000);
}

// ═══════════════════════════════════════════════════════════════════════════
// HTMX EVENT HANDLERS
// ═══════════════════════════════════════════════════════════════════════════

function handleHtmxSwap(event) {
    // Update tab counts after swap
    updateTabCounts();
    
    // Re-apply view mode
    const list = document.getElementById('downloads-list');
    if (list) {
        list.dataset.view = DCState.currentView;
    }
    
    // Check for active downloads and pulse header icon
    updateHeaderPulse();
}

function handleHtmxRequest(event) {
    // Handle completed downloads notification
    if (event.detail.successful && DCState.notificationsEnabled) {
        // Check if any downloads just completed
        // This would need server-side support to track state changes
    }
}

function updateTabCounts() {
    // Extract counts from data attributes or server response
    // This is a placeholder - actual implementation depends on server data
}

function updateHeaderPulse() {
    const pulse = document.getElementById('download-pulse');
    const hasActiveDownloads = document.querySelector('.dc-status-downloading') !== null;
    
    if (pulse) {
        pulse.classList.toggle('active', hasActiveDownloads);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// KEYBOARD SHORTCUTS
// ═══════════════════════════════════════════════════════════════════════════

function handleKeyboard(event) {
    // Only handle shortcuts when not in input
    if (event.target.matches('input, textarea, select')) return;
    
    switch (event.key) {
        case 'r':
            // Refresh
            if (!event.ctrlKey && !event.metaKey) {
                htmx.trigger('#downloads-list', 'load');
            }
            break;
        case 'v':
            // Toggle view
            setView(DCState.currentView === 'cards' ? 'table' : 'cards');
            break;
        case 'Escape':
            // Close modals
            hideSpeedLimiter();
            break;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatSpeed(bytesPerSecond) {
    return formatBytes(bytesPerSecond) + '/s';
}

function formatEta(seconds) {
    if (!seconds || seconds <= 0) return '-';
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

// ═══════════════════════════════════════════════════════════════════════════
// HISTORY TAB ACTIONS
// ═══════════════════════════════════════════════════════════════════════════

function clearHistory(days) {
    if (!confirm(`Remove downloads older than ${days} days from history?`)) {
        return;
    }
    
    fetch(`/api/downloads/manager/history/clear?days=${days}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (response.ok) {
            showToast('History cleared successfully', 'success');
            htmx.trigger('#downloads-list', 'load');
        } else {
            showToast('Failed to clear history', 'error');
        }
    })
    .catch(() => showToast('Error clearing history', 'error'));
}

function openInLibrary(trackId) {
    window.location.href = `/library/track/${trackId}`;
}

function redownload(downloadId) {
    fetch(`/api/downloads/${downloadId}/redownload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (response.ok) {
            showToast('Download queued again', 'success');
            // Switch to queue tab
            switchTab('queue');
        } else {
            showToast('Failed to queue download', 'error');
        }
    })
    .catch(() => showToast('Error queuing download', 'error'));
}

function deleteHistoryItem(downloadId) {
    if (!confirm('Remove this download from history?')) {
        return;
    }
    
    fetch(`/api/downloads/${downloadId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (response.ok) {
            // Remove from DOM with animation
            const card = document.querySelector(`[data-download-id="${downloadId}"]`);
            if (card) {
                card.style.animation = 'fadeOut 0.3s ease forwards';
                setTimeout(() => card.remove(), 300);
            }
            showToast('Removed from history', 'success');
        } else {
            showToast('Failed to remove', 'error');
        }
    })
    .catch(() => showToast('Error removing download', 'error'));
}

// ═══════════════════════════════════════════════════════════════════════════
// FAILED TAB ACTIONS
// ═══════════════════════════════════════════════════════════════════════════

function retryDownload(downloadId) {
    fetch(`/api/downloads/${downloadId}/retry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (response.ok) {
            showToast('Download retry scheduled', 'success');
            // Remove from failed list with animation
            const card = document.querySelector(`[data-download-id="${downloadId}"]`);
            if (card) {
                card.style.animation = 'fadeOut 0.3s ease forwards';
                setTimeout(() => {
                    card.remove();
                    htmx.trigger('#downloads-list', 'load');
                }, 300);
            }
        } else {
            showToast('Failed to retry download', 'error');
        }
    })
    .catch(() => showToast('Error retrying download', 'error'));
}

function retryAllFailed() {
    if (!confirm('Retry all failed downloads?')) {
        return;
    }
    
    fetch('/api/downloads/retry-all-failed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        showToast(`${data.retried || 0} downloads queued for retry`, 'success');
        htmx.trigger('#downloads-list', 'load');
    })
    .catch(() => showToast('Error retrying downloads', 'error'));
}

function clearAllFailed() {
    if (!confirm('Remove all failed downloads permanently?')) {
        return;
    }
    
    fetch('/api/downloads/clear-failed', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (response.ok) {
            showToast('Failed downloads cleared', 'success');
            htmx.trigger('#downloads-list', 'load');
        } else {
            showToast('Failed to clear', 'error');
        }
    })
    .catch(() => showToast('Error clearing downloads', 'error'));
}

function searchAlternative(title, artist) {
    // Open Soulseek search with track info
    const query = encodeURIComponent(`${artist} ${title}`);
    window.location.href = `/search?q=${query}&source=soulseek`;
}

function deleteDownload(downloadId) {
    if (!confirm('Remove this failed download permanently?')) {
        return;
    }
    
    fetch(`/api/downloads/${downloadId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (response.ok) {
            const card = document.querySelector(`[data-download-id="${downloadId}"]`);
            if (card) {
                card.style.animation = 'fadeOut 0.3s ease forwards';
                setTimeout(() => card.remove(), 300);
            }
            showToast('Download removed', 'success');
        } else {
            showToast('Failed to remove', 'error');
        }
    })
    .catch(() => showToast('Error removing download', 'error'));
}

// Toast notification helper
function showToast(message, type = 'info') {
    // Try to use existing toast system if available
    if (window.Toast && window.Toast.show) {
        window.Toast.show(message, type);
        return;
    }
    
    // Fallback: create simple toast
    const toast = document.createElement('div');
    toast.className = `dc-toast dc-toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    // Style the toast
    Object.assign(toast.style, {
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        padding: '12px 20px',
        background: type === 'success' ? 'var(--color-success)' : type === 'error' ? 'var(--color-error)' : 'var(--bg-secondary)',
        color: type === 'info' ? 'var(--text-primary)' : 'white',
        borderRadius: 'var(--radius-md)',
        boxShadow: 'var(--shadow-lg)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        zIndex: '9999',
        animation: 'slideInRight 0.3s ease'
    });
    
    document.body.appendChild(toast);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add fadeOut animation if not exists
if (!document.getElementById('dc-animations')) {
    const style = document.createElement('style');
    style.id = 'dc-animations';
    style.textContent = `
        @keyframes fadeOut {
            from { opacity: 1; transform: translateY(0); }
            to { opacity: 0; transform: translateY(-10px); }
        }
        @keyframes slideInRight {
            from { opacity: 0; transform: translateX(100px); }
            to { opacity: 1; transform: translateX(0); }
        }
    `;
    document.head.appendChild(style);
}

// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL EXPORT - For onclick handlers in templates
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Hey future me - DownloadCenter is the global API for template onclick handlers!
 * All functions that need to be called from HTML onclick attributes must be
 * exposed through this object. This keeps the global namespace clean while
 * allowing template access to functionality.
 */
window.DownloadCenter = {
    // View & Navigation
    setView,
    switchTab,
    toggleSidebar,
    toggleAutoRefresh,
    toggleSettingsDropdown,
    
    // Queue Actions
    pauseDownload,
    resumeDownload,
    cancelDownload,
    retryDownload,
    
    // Batch Actions
    pauseAll,
    resumeAll,
    cancelAll,
    selectAll,
    
    // History Actions
    clearHistory,
    openInLibrary,
    redownload,
    deleteHistoryItem,
    
    // Failed Actions
    retryAllFailed,
    clearAllFailed,
    searchAlternative,
    deleteDownload,
    
    // Filters
    applyFilter,
    applySort,
    
    // Speed Limiter
    showSpeedLimiter,
    hideSpeedLimiter,
    applySpeedLimit,
    
    // Export
    exportQueue,
    
    // Utility
    showToast
};
