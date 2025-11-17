/**
 * SSE (Server-Sent Events) Client Utility
 * 
 * Provides a robust EventSource wrapper with automatic reconnection,
 * error handling, and event listeners.
 */

class SSEClient {
    constructor(url, options = {}) {
        this.url = url;
        this.options = {
            reconnectInterval: options.reconnectInterval || 3000,
            maxReconnectAttempts: options.maxReconnectAttempts || 10,
            heartbeatTimeout: options.heartbeatTimeout || 60000,
            debug: options.debug || false,
            ...options
        };
        
        this.eventSource = null;
        this.reconnectAttempts = 0;
        this.reconnectTimeout = null;
        this.heartbeatTimer = null;
        this.listeners = new Map();
        this.isConnected = false;
        this.shouldReconnect = true;
        
        this.log('SSEClient initialized', { url, options: this.options });
    }

    /**
     * Connect to the SSE endpoint
     */
    connect() {
        if (this.eventSource) {
            this.log('Already connected or connecting');
            return;
        }

        this.log('Connecting to SSE endpoint...');
        this.eventSource = new EventSource(this.url);

        // Connection opened
        this.eventSource.addEventListener('open', (event) => {
            this.log('SSE connection opened');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.startHeartbeatMonitor();
            this.emit('connected', { timestamp: new Date().toISOString() });
        });

        // Connection error
        this.eventSource.addEventListener('error', (event) => {
            this.log('SSE connection error', event);
            this.isConnected = false;
            this.stopHeartbeatMonitor();
            this.emit('error', { error: event, timestamp: new Date().toISOString() });

            if (this.shouldReconnect) {
                this.reconnect();
            }
        });

        // Generic message handler (for events without type)
        this.eventSource.addEventListener('message', (event) => {
            this.log('Received message event', event.data);
            this.emit('message', this.parseData(event.data));
        });

        // Register custom event listeners
        this.registerEventListeners();
    }

    /**
     * Register all custom event listeners
     */
    registerEventListeners() {
        // Connected event
        this.eventSource.addEventListener('connected', (event) => {
            this.log('Connected event received');
            const data = this.parseData(event.data);
            this.emit('connected', data);
        });

        // Downloads update event
        this.eventSource.addEventListener('downloads_update', (event) => {
            this.log('Downloads update received');
            const data = this.parseData(event.data);
            this.resetHeartbeatMonitor();
            this.emit('downloads_update', data);
        });

        // Heartbeat event
        this.eventSource.addEventListener('heartbeat', (event) => {
            this.log('Heartbeat received');
            this.resetHeartbeatMonitor();
            this.emit('heartbeat', this.parseData(event.data));
        });

        // Error event
        this.eventSource.addEventListener('error', (event) => {
            this.log('Error event received', event.data);
            this.emit('sse_error', this.parseData(event.data));
        });
    }

    /**
     * Disconnect from SSE endpoint
     */
    disconnect() {
        this.log('Disconnecting from SSE endpoint');
        this.shouldReconnect = false;
        
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
        }

        this.stopHeartbeatMonitor();

        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }

        this.isConnected = false;
        this.emit('disconnected', { timestamp: new Date().toISOString() });
    }

    /**
     * Reconnect to SSE endpoint
     */
    reconnect() {
        if (!this.shouldReconnect) {
            return;
        }

        if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            this.log('Max reconnection attempts reached');
            this.emit('max_reconnect_attempts', {
                attempts: this.reconnectAttempts,
                timestamp: new Date().toISOString()
            });
            return;
        }

        this.reconnectAttempts++;
        const delay = this.options.reconnectInterval * Math.min(this.reconnectAttempts, 5);
        
        this.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }

        this.reconnectTimeout = setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * Start monitoring heartbeat
     */
    startHeartbeatMonitor() {
        this.resetHeartbeatMonitor();
    }

    /**
     * Reset heartbeat timer
     */
    resetHeartbeatMonitor() {
        if (this.heartbeatTimer) {
            clearTimeout(this.heartbeatTimer);
        }

        this.heartbeatTimer = setTimeout(() => {
            this.log('Heartbeat timeout - connection may be stale');
            this.emit('heartbeat_timeout', { timestamp: new Date().toISOString() });
            
            if (this.shouldReconnect) {
                this.disconnect();
                this.shouldReconnect = true; // Re-enable reconnect
                this.reconnect();
            }
        }, this.options.heartbeatTimeout);
    }

    /**
     * Stop heartbeat monitor
     */
    stopHeartbeatMonitor() {
        if (this.heartbeatTimer) {
            clearTimeout(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    /**
     * Add event listener
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
        
        this.log(`Event listener registered: ${event}`);
    }

    /**
     * Remove event listener
     */
    off(event, callback) {
        if (!this.listeners.has(event)) {
            return;
        }

        const callbacks = this.listeners.get(event);
        const index = callbacks.indexOf(callback);
        
        if (index > -1) {
            callbacks.splice(index, 1);
            this.log(`Event listener removed: ${event}`);
        }
    }

    /**
     * Emit event to all listeners
     */
    emit(event, data) {
        if (!this.listeners.has(event)) {
            return;
        }

        const callbacks = this.listeners.get(event);
        callbacks.forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                this.log(`Error in event listener for ${event}:`, error);
            }
        });
    }

    /**
     * Parse event data
     */
    parseData(data) {
        try {
            return JSON.parse(data);
        } catch (error) {
            this.log('Error parsing event data:', error);
            return data;
        }
    }

    /**
     * Log debug messages
     */
    log(...args) {
        if (this.options.debug) {
            console.log('[SSEClient]', ...args);
        }
    }

    /**
     * Get connection status
     */
    getStatus() {
        return {
            isConnected: this.isConnected,
            reconnectAttempts: this.reconnectAttempts,
            url: this.url
        };
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SSEClient;
}
