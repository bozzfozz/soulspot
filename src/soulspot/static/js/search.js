// Advanced Search Manager
// Handles search functionality for Spotify + Soulseek, autocomplete, filters, and history
// Hey future me - this was extended to support Spotify artist search with Follow button!

const SearchManager = {
    // State management
    state: {
        currentQuery: '',
        results: [],
        selectedTracks: new Set(),
        searchSource: 'spotify',  // 'spotify' or 'soulseek'
        spotifyType: 'artists',   // 'artists', 'albums', or 'tracks'
        followingStatus: {},      // Map of artistId -> isFollowing
        filters: {
            quality: 'any',
            artist: '',
            album: '',
            duration: []
        },
        searchHistory: []
    },

    // Debounce timer for autocomplete
    autocompleteTimer: null,

    // Initialize the search manager
    init() {
        this.loadSearchHistory();
        this.setupEventListeners();
        this.updateUIForSearchSource();
        console.log('SearchManager initialized with Spotify+Soulseek support');
    },

    // Set search source (spotify or soulseek)
    setSearchSource(source) {
        this.state.searchSource = source;
        this.updateUIForSearchSource();
        console.log(`Search source set to: ${source}`);
    },

    // Set Spotify search type (artists, albums, tracks)
    setSpotifyType(type) {
        this.state.spotifyType = type;
        console.log(`Spotify type set to: ${type}`);
    },

    // Update UI based on search source
    updateUIForSearchSource() {
        const isSpotify = this.state.searchSource === 'spotify';
        const sourceLabel = document.getElementById('search-source-label');
        const spotifyTypeGroup = document.getElementById('spotify-type-filter-group');
        const qualityGroup = document.getElementById('quality-filter-group');
        const searchInput = document.getElementById('search-input');

        if (sourceLabel) {
            sourceLabel.textContent = isSpotify ? 'Spotify' : 'Soulseek';
            sourceLabel.style.color = isSpotify ? '#1DB954' : '#3b82f6';
        }

        if (spotifyTypeGroup) {
            spotifyTypeGroup.style.display = isSpotify ? 'block' : 'none';
        }

        if (qualityGroup) {
            qualityGroup.style.display = isSpotify ? 'none' : 'block';
        }

        if (searchInput) {
            searchInput.placeholder = isSpotify 
                ? 'Search for artists, albums, or tracks on Spotify...'
                : 'Search for downloadable files on Soulseek...';
        }
    },

    // Setup event listeners
    setupEventListeners() {
        // Listen for filter changes
        document.querySelectorAll('input[name="quality"]').forEach(input => {
            input.addEventListener('change', (e) => {
                this.state.filters.quality = e.target.value;
                this.applyFilters();
            });
        });

        document.querySelectorAll('input[name="duration"]').forEach(input => {
            input.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.state.filters.duration.push(e.target.value);
                } else {
                    const index = this.state.filters.duration.indexOf(e.target.value);
                    if (index > -1) {
                        this.state.filters.duration.splice(index, 1);
                    }
                }
                this.applyFilters();
            });
        });

        // Close autocomplete when clicking outside
        document.addEventListener('click', (e) => {
            const autocompleteEl = document.getElementById('autocomplete-results');
            const searchInput = document.getElementById('search-input');
            if (e.target !== searchInput && e.target !== autocompleteEl && !autocompleteEl.contains(e.target)) {
                this.hideAutocomplete();
            }
        });
    },

    // Handle search input with debouncing for autocomplete
    handleSearchInput(event) {
        const query = event.target.value.trim();

        // Clear previous timer
        if (this.autocompleteTimer) {
            clearTimeout(this.autocompleteTimer);
        }

        // Show autocomplete after 300ms delay
        if (query.length >= 2) {
            this.autocompleteTimer = setTimeout(() => {
                this.fetchAutocompleteSuggestions(query);
            }, 300);
        } else {
            this.hideAutocomplete();
        }
    },

    // Fetch autocomplete suggestions
    async fetchAutocompleteSuggestions(query) {
        try {
            // Get access token from session storage or cookie
            const accessToken = sessionStorage.getItem('spotify_access_token') || 
                                this.getCookie('spotify_access_token');

            if (!accessToken) {
                console.log('No access token available for autocomplete');
                return;
            }

            const response = await fetch(`/api/tracks/search?query=${encodeURIComponent(query)}&limit=5&access_token=${accessToken}`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch suggestions');
            }

            const data = await response.json();
            this.showAutocompleteSuggestions(data.tracks || []);
        } catch (error) {
            console.error('Autocomplete error:', error);
            this.hideAutocomplete();
        }
    },

    // Show autocomplete suggestions
    showAutocompleteSuggestions(tracks) {
        const autocompleteEl = document.getElementById('autocomplete-results');
        
        if (tracks.length === 0) {
            this.hideAutocomplete();
            return;
        }

        autocompleteEl.innerHTML = tracks.map((track, index) => `
            <div 
                class="p-3 hover:bg-gray-100 cursor-pointer flex items-center gap-3 transition-colors focus-ring"
                onclick="SearchManager.selectSuggestion('${this.escapeHtml(track.name)}', '${this.escapeHtml(track.artists[0].name)}')"
                role="option"
                tabindex="0"
                onkeydown="if(event.key === 'Enter') SearchManager.selectSuggestion('${this.escapeHtml(track.name)}', '${this.escapeHtml(track.artists[0].name)}')"
            >
                <div class="flex-1">
                    <div class="text-sm font-medium text-gray-900">${this.escapeHtml(track.name)}</div>
                    <div class="text-xs text-gray-600">${this.escapeHtml(track.artists[0].name)} • ${this.escapeHtml(track.album.name)}</div>
                </div>
                <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                </svg>
            </div>
        `).join('');

        autocompleteEl.classList.remove('hidden');
    },

    // Hide autocomplete
    hideAutocomplete() {
        const autocompleteEl = document.getElementById('autocomplete-results');
        if (autocompleteEl) {
            autocompleteEl.classList.add('hidden');
            autocompleteEl.style.display = 'none';
        }
    },

    // Select a suggestion
    selectSuggestion(trackName, artistName) {
        const query = `${trackName} ${artistName}`;
        document.getElementById('search-input').value = query;
        this.hideAutocomplete();
        this.performSearch(null, query);
    },

    // Perform search - routes to Spotify or Soulseek based on state
    async performSearch(event, overrideQuery = null) {
        if (event) {
            event.preventDefault();
        }

        const query = overrideQuery || document.getElementById('search-input').value.trim();
        
        if (!query) {
            if (typeof ToastManager !== 'undefined') {
                ToastManager.warning('Please enter a search query');
            }
            return;
        }

        this.state.currentQuery = query;
        this.addToSearchHistory(query);
        this.hideAutocomplete();

        // Route to appropriate search method
        if (this.state.searchSource === 'spotify') {
            await this.performSpotifySearch(query);
        } else {
            await this.performSoulseekSearch(query);
        }
    },

    // Perform Spotify search
    async performSpotifySearch(query) {
        // Show loading state
        document.getElementById('search-results').innerHTML = `
            <div class="card" style="text-align: center; padding: 4rem var(--space-6);">
                <div style="display: flex; align-items: center; justify-content: center; gap: var(--space-3);">
                    <div class="spinner" style="border-color: #1DB954; border-top-color: transparent;"></div>
                    <span style="color: var(--text-muted);">Searching Spotify...</span>
                </div>
            </div>
        `;

        try {
            const type = this.state.spotifyType;
            const response = await fetch(`/api/search/spotify/${type}?query=${encodeURIComponent(query)}&limit=30`);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Search failed');
            }

            const data = await response.json();
            
            // Store results and check following status for artists
            if (type === 'artists' && data.artists && data.artists.length > 0) {
                this.state.results = data.artists;
                await this.checkFollowingStatus(data.artists.map(a => a.id));
                this.displaySpotifyArtists(data.artists);
            } else if (type === 'albums' && data.albums) {
                this.state.results = data.albums;
                this.displaySpotifyAlbums(data.albums);
            } else if (type === 'tracks' && data.tracks) {
                this.state.results = data.tracks;
                this.displaySpotifyTracks(data.tracks);
            } else {
                this.displayNoResults();
            }

            if (typeof ToastManager !== 'undefined') {
                ToastManager.success(`Found ${this.state.results.length} results`);
            }
        } catch (error) {
            console.error('Spotify search error:', error);
            this.displaySearchError(error.message);
        }
    },

    // Perform Soulseek search (original behavior)
    async performSoulseekSearch(query) {
        // Show loading state
        document.getElementById('search-results').innerHTML = `
            <div class="card" style="text-align: center; padding: 4rem var(--space-6);">
                <div style="display: flex; align-items: center; justify-content: center; gap: var(--space-3);">
                    <div class="spinner" style="border-color: #3b82f6; border-top-color: transparent;"></div>
                    <span style="color: var(--text-muted);">Searching Soulseek network...</span>
                </div>
            </div>
        `;

        try {
            const response = await fetch(`/api/search/soulseek?query=${encodeURIComponent(query)}&timeout=30`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Search failed');
            }

            const data = await response.json();
            this.state.results = data.files || [];
            this.displaySoulseekResults(data.files || []);

            if (typeof ToastManager !== 'undefined') {
                ToastManager.success(`Found ${this.state.results.length} files`);
            }
        } catch (error) {
            console.error('Soulseek search error:', error);
            this.displaySearchError(error.message);
        }
    },

    // Check following status for artists
    async checkFollowingStatus(artistIds) {
        if (!artistIds || artistIds.length === 0) return;
        
        try {
            const response = await fetch('/api/artists/spotify/following-status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ artist_ids: artistIds })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.state.followingStatus = data.statuses || {};
            }
        } catch (error) {
            console.warn('Could not check following status:', error);
        }
    },

    // Display Spotify artist results
    displaySpotifyArtists(artists) {
        const resultsEl = document.getElementById('search-results');
        
        if (!artists || artists.length === 0) {
            this.displayNoResults();
            return;
        }

        const html = `
            <div class="card">
                <div style="padding: var(--space-4); border-bottom: 1px solid var(--border-primary);">
                    <h3 style="font-weight: var(--font-weight-semibold); display: flex; align-items: center; gap: var(--space-2);">
                        <i class="bi bi-spotify" style="color: #1DB954;"></i>
                        Artists (${artists.length})
                    </h3>
                </div>
                <div>
                    ${artists.map(artist => this.renderArtistCard(artist)).join('')}
                </div>
            </div>
        `;

        resultsEl.innerHTML = html;
    },

    // Render single artist card
    renderArtistCard(artist) {
        const isFollowing = this.state.followingStatus[artist.id] || false;
        const imageUrl = artist.image_url || '/static/images/artist-placeholder.svg';
        const genres = (artist.genres || []).slice(0, 3).join(', ') || 'No genres';
        const followers = this.formatNumber(artist.followers || 0);

        return `
            <div class="spotify-result-card" data-artist-id="${artist.id}">
                <img src="${imageUrl}" alt="${this.escapeHtml(artist.name)}" class="spotify-result-image"
                     onerror="this.src='/static/images/artist-placeholder.svg'">
                <div class="spotify-result-info">
                    <div class="spotify-result-name">${this.escapeHtml(artist.name)}</div>
                    <div class="spotify-result-meta">
                        <span>${genres}</span>
                        <span style="margin: 0 var(--space-2);">•</span>
                        <span>${followers} followers</span>
                    </div>
                </div>
                <div class="spotify-result-actions">
                    <button class="btn btn-sm ${isFollowing ? 'btn-following' : 'btn-follow'}"
                            onclick="SearchManager.toggleFollow('${artist.id}', ${isFollowing})"
                            id="follow-btn-${artist.id}">
                        <i class="bi ${isFollowing ? 'bi-check-lg' : 'bi-plus-lg'}"></i>
                        ${isFollowing ? 'Following' : 'Follow'}
                    </button>
                    <a href="${artist.spotify_url || '#'}" target="_blank" class="btn btn-ghost btn-sm"
                       title="Open in Spotify">
                        <i class="bi bi-box-arrow-up-right"></i>
                    </a>
                </div>
            </div>
        `;
    },

    // Toggle follow/unfollow artist
    async toggleFollow(artistId, isCurrentlyFollowing) {
        const button = document.getElementById(`follow-btn-${artistId}`);
        if (!button) return;

        // Optimistic UI update
        button.disabled = true;
        button.innerHTML = '<div class="spinner spinner-sm"></div>';

        try {
            const method = isCurrentlyFollowing ? 'DELETE' : 'POST';
            const response = await fetch(`/api/artists/spotify/${artistId}/follow`, { method });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Operation failed');
            }

            // Update state and UI
            const newStatus = !isCurrentlyFollowing;
            this.state.followingStatus[artistId] = newStatus;

            button.className = `btn btn-sm ${newStatus ? 'btn-following' : 'btn-follow'}`;
            button.innerHTML = `
                <i class="bi ${newStatus ? 'bi-check-lg' : 'bi-plus-lg'}"></i>
                ${newStatus ? 'Following' : 'Follow'}
            `;
            button.onclick = () => this.toggleFollow(artistId, newStatus);

            if (typeof ToastManager !== 'undefined') {
                ToastManager.success(newStatus ? 'Artist followed!' : 'Artist unfollowed');
            }
        } catch (error) {
            console.error('Follow/unfollow error:', error);
            // Revert button state
            button.className = `btn btn-sm ${isCurrentlyFollowing ? 'btn-following' : 'btn-follow'}`;
            button.innerHTML = `
                <i class="bi ${isCurrentlyFollowing ? 'bi-check-lg' : 'bi-plus-lg'}"></i>
                ${isCurrentlyFollowing ? 'Following' : 'Follow'}
            `;
            if (typeof ToastManager !== 'undefined') {
                ToastManager.error(error.message || 'Failed to update follow status');
            }
        } finally {
            button.disabled = false;
        }
    },

    // Display Spotify album results
    displaySpotifyAlbums(albums) {
        const resultsEl = document.getElementById('search-results');
        
        if (!albums || albums.length === 0) {
            this.displayNoResults();
            return;
        }

        const html = `
            <div class="card">
                <div style="padding: var(--space-4); border-bottom: 1px solid var(--border-primary);">
                    <h3 style="font-weight: var(--font-weight-semibold); display: flex; align-items: center; gap: var(--space-2);">
                        <i class="bi bi-disc" style="color: #1DB954;"></i>
                        Albums (${albums.length})
                    </h3>
                </div>
                <div>
                    ${albums.map(album => this.renderAlbumCard(album)).join('')}
                </div>
            </div>
        `;

        resultsEl.innerHTML = html;
    },

    // Render single album card
    renderAlbumCard(album) {
        const imageUrl = album.image_url || '/static/images/album-placeholder.svg';
        const releaseYear = album.release_date ? album.release_date.substring(0, 4) : '';
        const albumType = album.album_type ? album.album_type.charAt(0).toUpperCase() + album.album_type.slice(1) : '';

        return `
            <div class="spotify-result-card" data-album-id="${album.id}">
                <img src="${imageUrl}" alt="${this.escapeHtml(album.name)}" class="spotify-result-image"
                     onerror="this.src='/static/images/album-placeholder.svg'">
                <div class="spotify-result-info">
                    <div class="spotify-result-name">${this.escapeHtml(album.name)}</div>
                    <div class="spotify-result-meta">
                        <span>${this.escapeHtml(album.artist_name)}</span>
                        <span style="margin: 0 var(--space-2);">•</span>
                        <span>${releaseYear}</span>
                        ${albumType ? `<span style="margin: 0 var(--space-2);">•</span><span>${albumType}</span>` : ''}
                        <span style="margin: 0 var(--space-2);">•</span>
                        <span>${album.total_tracks} tracks</span>
                    </div>
                </div>
                <div class="spotify-result-actions">
                    <button class="btn btn-primary btn-sm" onclick="SearchManager.searchAlbumOnSoulseek('${this.escapeHtml(album.name)}', '${this.escapeHtml(album.artist_name)}')">
                        <i class="bi bi-download"></i>
                        Find Downloads
                    </button>
                    <a href="${album.spotify_url || '#'}" target="_blank" class="btn btn-ghost btn-sm" title="Open in Spotify">
                        <i class="bi bi-box-arrow-up-right"></i>
                    </a>
                </div>
            </div>
        `;
    },

    // Display Spotify track results
    displaySpotifyTracks(tracks) {
        const resultsEl = document.getElementById('search-results');
        
        if (!tracks || tracks.length === 0) {
            this.displayNoResults();
            return;
        }

        const html = `
            <div class="card">
                <div style="padding: var(--space-4); border-bottom: 1px solid var(--border-primary);">
                    <h3 style="font-weight: var(--font-weight-semibold); display: flex; align-items: center; gap: var(--space-2);">
                        <i class="bi bi-music-note" style="color: #1DB954;"></i>
                        Tracks (${tracks.length})
                    </h3>
                </div>
                <div>
                    ${tracks.map(track => this.renderTrackSearchCard(track)).join('')}
                </div>
            </div>
        `;

        resultsEl.innerHTML = html;
    },

    // Render single track card for Spotify search
    renderTrackSearchCard(track) {
        const duration = this.formatDuration(track.duration_ms);

        return `
            <div class="spotify-result-card" data-track-id="${track.id}">
                <div style="width: 40px; height: 40px; background: var(--bg-tertiary); border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    <i class="bi bi-music-note" style="color: var(--text-muted);"></i>
                </div>
                <div class="spotify-result-info">
                    <div class="spotify-result-name">${this.escapeHtml(track.name)}</div>
                    <div class="spotify-result-meta">
                        <span>${this.escapeHtml(track.artist_name)}</span>
                        ${track.album_name ? `<span style="margin: 0 var(--space-2);">•</span><span>${this.escapeHtml(track.album_name)}</span>` : ''}
                        <span style="margin: 0 var(--space-2);">•</span>
                        <span>${duration}</span>
                    </div>
                </div>
                <div class="spotify-result-actions">
                    <button class="btn btn-primary btn-sm" onclick="SearchManager.searchTrackOnSoulseek('${this.escapeHtml(track.name)}', '${this.escapeHtml(track.artist_name)}')">
                        <i class="bi bi-download"></i>
                        Find Downloads
                    </button>
                    <a href="${track.spotify_url || '#'}" target="_blank" class="btn btn-ghost btn-sm" title="Open in Spotify">
                        <i class="bi bi-box-arrow-up-right"></i>
                    </a>
                </div>
            </div>
        `;
    },

    // Display Soulseek results
    displaySoulseekResults(files) {
        const resultsEl = document.getElementById('search-results');
        
        if (!files || files.length === 0) {
            this.displayNoResults();
            return;
        }

        const html = `
            <div class="card">
                <div style="padding: var(--space-4); border-bottom: 1px solid var(--border-primary);">
                    <h3 style="font-weight: var(--font-weight-semibold); display: flex; align-items: center; gap: var(--space-2);">
                        <i class="bi bi-cloud-download" style="color: #3b82f6;"></i>
                        Soulseek Files (${files.length})
                    </h3>
                </div>
                <div>
                    ${files.map(file => this.renderSoulseekFileCard(file)).join('')}
                </div>
            </div>
        `;

        resultsEl.innerHTML = html;
    },

    // Render single Soulseek file card
    renderSoulseekFileCard(file) {
        const filename = file.filename.split(/[/\\]/).pop() || file.filename;
        const size = this.formatFileSize(file.size);
        const bitrate = file.bitrate ? `${file.bitrate}kbps` : 'Unknown';

        return `
            <div class="spotify-result-card">
                <div style="width: 40px; height: 40px; background: var(--bg-tertiary); border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    <i class="bi bi-file-earmark-music" style="color: #3b82f6;"></i>
                </div>
                <div class="spotify-result-info">
                    <div class="spotify-result-name" title="${this.escapeHtml(file.filename)}">${this.escapeHtml(filename)}</div>
                    <div class="spotify-result-meta">
                        <span>@${this.escapeHtml(file.username)}</span>
                        <span style="margin: 0 var(--space-2);">•</span>
                        <span>${bitrate}</span>
                        <span style="margin: 0 var(--space-2);">•</span>
                        <span>${size}</span>
                    </div>
                </div>
                <div class="spotify-result-actions">
                    <button class="btn btn-primary btn-sm" onclick="SearchManager.downloadFile('${this.escapeHtml(file.username)}', '${this.escapeHtml(file.filename)}')">
                        <i class="bi bi-download"></i>
                        Download
                    </button>
                </div>
            </div>
        `;
    },

    // Search album on Soulseek
    searchAlbumOnSoulseek(albumName, artistName) {
        this.setSearchSource('soulseek');
        document.querySelector('input[name="searchSource"][value="soulseek"]').checked = true;
        this.updateUIForSearchSource();
        const query = `${artistName} ${albumName}`;
        document.getElementById('search-input').value = query;
        this.performSearch(null, query);
    },

    // Search track on Soulseek
    searchTrackOnSoulseek(trackName, artistName) {
        this.setSearchSource('soulseek');
        document.querySelector('input[name="searchSource"][value="soulseek"]').checked = true;
        this.updateUIForSearchSource();
        const query = `${artistName} ${trackName}`;
        document.getElementById('search-input').value = query;
        this.performSearch(null, query);
    },

    // Download file from Soulseek
    async downloadFile(username, filename) {
        try {
            const response = await fetch('/api/downloads', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, filename })
            });

            if (!response.ok) {
                throw new Error('Download request failed');
            }

            if (typeof ToastManager !== 'undefined') {
                ToastManager.success('Download started!');
            }
        } catch (error) {
            console.error('Download error:', error);
            if (typeof ToastManager !== 'undefined') {
                ToastManager.error('Failed to start download');
            }
        }
    },

    // Display no results message
    displayNoResults() {
        document.getElementById('search-results').innerHTML = `
            <div class="card" style="text-align: center; padding: 4rem var(--space-6);">
                <i class="bi bi-search" style="font-size: 4rem; color: var(--text-muted); margin-bottom: var(--space-4); display: block;"></i>
                <h3 style="font-size: var(--font-size-lg); margin-bottom: var(--space-2);">No Results Found</h3>
                <p style="color: var(--text-muted);">Try a different search query</p>
            </div>
        `;
    },

    // Display search error
    displaySearchError(message) {
        document.getElementById('search-results').innerHTML = `
            <div class="card" style="text-align: center; padding: 4rem var(--space-6);">
                <i class="bi bi-exclamation-triangle" style="font-size: 4rem; color: #ef4444; margin-bottom: var(--space-4); display: block;"></i>
                <h3 style="font-size: var(--font-size-lg); margin-bottom: var(--space-2);">Search Failed</h3>
                <p style="color: var(--text-muted);">${this.escapeHtml(message)}</p>
            </div>
        `;
        if (typeof ToastManager !== 'undefined') {
            ToastManager.error(message || 'Search failed');
        }
    },

    // Format number with K/M suffix
    formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toString();
    },

    // Format file size
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    },

    // Legacy performSearch for backward compatibility - now routes to new methods
    async performLegacySearch(event, overrideQuery = null) {
        if (event) {
            event.preventDefault();
        }

        const query = overrideQuery || document.getElementById('search-input').value.trim();
        
        if (!query) {
            ToastManager.warning('Please enter a search query');
            return;
        }

        this.state.currentQuery = query;
        this.addToSearchHistory(query);
        this.hideAutocomplete();

        // Show loading state
        document.getElementById('search-results').innerHTML = `
            <div class="flex items-center justify-center py-12">
                <span class="spinner spinner-lg text-primary-500"></span>
                <span class="ml-3 text-gray-600">Searching...</span>
            </div>
        `;

        try {
            // Get access token
            const accessToken = sessionStorage.getItem('spotify_access_token') || 
                                this.getCookie('spotify_access_token');

            if (!accessToken) {
                throw new Error('Please authenticate with Spotify first');
            }

            const response = await fetch(`/api/tracks/search?query=${encodeURIComponent(query)}&limit=50&access_token=${accessToken}`);
            
            if (!response.ok) {
                throw new Error('Search failed');
            }

            const data = await response.json();
            this.state.results = data.tracks || [];
            this.displayResults(this.state.results);
            ToastManager.success(`Found ${this.state.results.length} results`);
        } catch (error) {
            console.error('Search error:', error);
            ToastManager.error(error.message || 'Search failed');
            document.getElementById('search-results').innerHTML = `
                <div class="card text-center py-12">
                    <div class="card-body">
                        <svg class="w-16 h-16 mx-auto text-error-400 mb-4" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                        </svg>
                        <h3 class="text-lg font-medium text-gray-900 mb-2">Search Failed</h3>
                        <p class="text-gray-600">${this.escapeHtml(error.message)}</p>
                    </div>
                </div>
            `;
        }
    },

    // Display search results
    displayResults(tracks) {
        const resultsEl = document.getElementById('search-results');
        
        if (tracks.length === 0) {
            resultsEl.innerHTML = `
                <div class="card text-center py-12">
                    <div class="card-body">
                        <svg class="w-16 h-16 mx-auto text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <h3 class="text-lg font-medium text-gray-900 mb-2">No Results Found</h3>
                        <p class="text-gray-600">Try a different search query</p>
                    </div>
                </div>
            `;
            return;
        }

        resultsEl.innerHTML = tracks.map((track, index) => this.renderTrackCard(track, index)).join('');
    },

    // Render individual track card
    renderTrackCard(track, index) {
        const duration = this.formatDuration(track.duration_ms);
        const isSelected = this.state.selectedTracks.has(track.id);

        return `
            <div class="card hover:shadow-md transition-shadow" id="track-${track.id}">
                <div class="flex items-start gap-4">
                    <!-- Checkbox for bulk selection -->
                    <label class="flex items-center pt-4">
                        <input 
                            type="checkbox" 
                            class="w-5 h-5 text-primary-500 rounded focus-ring track-checkbox"
                            ${isSelected ? 'checked' : ''}
                            onchange="SearchManager.toggleTrackSelection('${track.id}', this.checked)"
                            aria-label="Select ${this.escapeHtml(track.name)}"
                        />
                    </label>

                    <!-- Track Info -->
                    <div class="flex-1">
                        <div class="flex items-start justify-between">
                            <div>
                                <h3 class="text-lg font-medium text-gray-900">${this.escapeHtml(track.name)}</h3>
                                <p class="text-sm text-gray-600">${this.escapeHtml(track.artists.map(a => a.name).join(', '))}</p>
                                <p class="text-xs text-gray-500 mt-1">${this.escapeHtml(track.album.name)} • ${duration}</p>
                            </div>
                            <button 
                                class="btn btn-ghost btn-icon focus-ring"
                                onclick="SearchManager.toggleTrackDetails('${track.id}')"
                                aria-label="Toggle details for ${this.escapeHtml(track.name)}"
                                aria-expanded="false"
                                aria-controls="details-${track.id}">
                                <svg class="w-5 h-5" id="expand-icon-${track.id}" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                                </svg>
                            </button>
                        </div>

                        <!-- Expandable Details -->
                        <div id="details-${track.id}" class="hidden mt-4 pt-4 border-t border-gray-200">
                            <div class="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                    <span class="font-medium text-gray-700">Track ID:</span>
                                    <span class="text-gray-600">${track.id}</span>
                                </div>
                                <div>
                                    <span class="font-medium text-gray-700">URI:</span>
                                    <span class="text-gray-600 text-xs break-all">${track.uri}</span>
                                </div>
                                <div>
                                    <span class="font-medium text-gray-700">Duration:</span>
                                    <span class="text-gray-600">${duration}</span>
                                </div>
                                <div>
                                    <span class="font-medium text-gray-700">Album:</span>
                                    <span class="text-gray-600">${this.escapeHtml(track.album.name)}</span>
                                </div>
                            </div>
                        </div>

                        <!-- Action Buttons -->
                        <div class="flex gap-2 mt-4">
                            <button 
                                class="btn btn-primary btn-sm focus-ring"
                                onclick="SearchManager.downloadTrack('${track.id}', '${this.escapeHtml(track.name)}')"
                                aria-label="Download ${this.escapeHtml(track.name)}">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"></path>
                                </svg>
                                Download
                            </button>
                            <a 
                                href="${track.uri}" 
                                target="_blank"
                                class="btn btn-secondary btn-sm focus-ring"
                                aria-label="Open ${this.escapeHtml(track.name)} in Spotify">
                                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
                                </svg>
                                Spotify
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    // Toggle track details expansion
    toggleTrackDetails(trackId) {
        const detailsEl = document.getElementById(`details-${trackId}`);
        const iconEl = document.getElementById(`expand-icon-${trackId}`);
        const button = iconEl.closest('button');
        
        if (detailsEl.classList.contains('hidden')) {
            detailsEl.classList.remove('hidden');
            iconEl.style.transform = 'rotate(180deg)';
            button.setAttribute('aria-expanded', 'true');
        } else {
            detailsEl.classList.add('hidden');
            iconEl.style.transform = 'rotate(0deg)';
            button.setAttribute('aria-expanded', 'false');
        }
    },

    // Toggle track selection for bulk actions
    toggleTrackSelection(trackId, checked) {
        if (checked) {
            this.state.selectedTracks.add(trackId);
        } else {
            this.state.selectedTracks.delete(trackId);
        }
        this.updateBulkActionsBar();
    },

    // Toggle select all
    toggleSelectAll(checked) {
        const checkboxes = document.querySelectorAll('.track-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = checked;
            const trackId = checkbox.closest('[id^="track-"]').id.replace('track-', '');
            this.toggleTrackSelection(trackId, checked);
        });
    },

    // Update bulk actions bar
    updateBulkActionsBar() {
        const bulkActionsBar = document.getElementById('bulk-actions-bar');
        const selectedCountEl = document.getElementById('selected-count');
        const count = this.state.selectedTracks.size;

        if (count > 0) {
            bulkActionsBar.classList.remove('hidden');
            selectedCountEl.textContent = `${count} selected`;
        } else {
            bulkActionsBar.classList.add('hidden');
        }
    },

    // Clear selection
    clearSelection() {
        this.state.selectedTracks.clear();
        document.querySelectorAll('.track-checkbox').forEach(cb => cb.checked = false);
        document.getElementById('select-all-checkbox').checked = false;
        this.updateBulkActionsBar();
    },

    // Download a single track
    async downloadTrack(trackId, trackName) {
        try {
            LoadingManager.showOverlay(document.querySelector(`#track-${trackId}`));
            
            const response = await fetch(`/api/tracks/${trackId}/download?quality=${this.state.filters.quality}`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error('Download failed');
            }

            const data = await response.json();
            ToastManager.success(`Download started for "${trackName}"`, 'Download Started');
        } catch (error) {
            console.error('Download error:', error);
            ToastManager.error(`Failed to download "${trackName}"`, 'Download Failed');
        } finally {
            LoadingManager.hideOverlay(document.querySelector(`#track-${trackId}`));
        }
    },

    // Bulk download selected tracks
    async bulkDownload() {
        const selectedIds = Array.from(this.state.selectedTracks);
        
        if (selectedIds.length === 0) {
            ToastManager.warning('No tracks selected');
            return;
        }

        ToastManager.info(`Starting download for ${selectedIds.length} tracks...`, 'Bulk Download');
        
        let successCount = 0;
        let failCount = 0;

        for (const trackId of selectedIds) {
            try {
                const response = await fetch(`/api/tracks/${trackId}/download?quality=${this.state.filters.quality}`, {
                    method: 'POST'
                });

                if (response.ok) {
                    successCount++;
                } else {
                    failCount++;
                }
            } catch (error) {
                failCount++;
            }
        }

        if (successCount > 0) {
            ToastManager.success(`${successCount} downloads started successfully`, 'Bulk Download Complete');
        }
        if (failCount > 0) {
            ToastManager.warning(`${failCount} downloads failed`, 'Partial Success');
        }

        this.clearSelection();
    },

    // Apply filters to current results
    applyFilters() {
        const filteredResults = this.state.results.filter(track => {
            // Artist filter
            if (this.state.filters.artist) {
                const artistMatch = track.artists.some(artist => 
                    artist.name.toLowerCase().includes(this.state.filters.artist.toLowerCase())
                );
                if (!artistMatch) return false;
            }

            // Album filter
            if (this.state.filters.album) {
                if (!track.album.name.toLowerCase().includes(this.state.filters.album.toLowerCase())) {
                    return false;
                }
            }

            // Duration filter
            if (this.state.filters.duration.length > 0) {
                const durationMinutes = track.duration_ms / 60000;
                const matchesDuration = this.state.filters.duration.some(range => {
                    if (range === 'short' && durationMinutes < 3) return true;
                    if (range === 'medium' && durationMinutes >= 3 && durationMinutes <= 5) return true;
                    if (range === 'long' && durationMinutes > 5) return true;
                    return false;
                });
                if (!matchesDuration) return false;
            }

            return true;
        });

        this.displayResults(filteredResults);
        ToastManager.info(`Showing ${filteredResults.length} of ${this.state.results.length} results`, 'Filters Applied');
    },

    // Update filters from inputs
    updateFilters() {
        this.state.filters.artist = document.getElementById('artist-filter-input')?.value || '';
        this.state.filters.album = document.getElementById('album-filter-input')?.value || '';
        this.applyFilters();
    },

    // Clear all filters
    clearFilters() {
        this.state.filters = {
            quality: 'any',
            artist: '',
            album: '',
            duration: []
        };

        document.querySelectorAll('input[name="quality"]').forEach(input => {
            input.checked = input.value === 'any';
        });
        document.querySelectorAll('input[name="duration"]').forEach(input => {
            input.checked = false;
        });
        document.getElementById('artist-filter-input').value = '';
        document.getElementById('album-filter-input').value = '';

        if (this.state.results.length > 0) {
            this.displayResults(this.state.results);
            ToastManager.info('Filters cleared', 'Reset');
        }
    },

    // Clear search
    clearSearch() {
        document.getElementById('search-input').value = '';
        this.state.currentQuery = '';
        this.state.results = [];
        this.clearSelection();
        document.getElementById('search-results').innerHTML = `
            <div class="card text-center py-12">
                <div class="card-body">
                    <svg class="w-16 h-16 mx-auto text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                    </svg>
                    <h3 class="text-lg font-medium text-gray-900 mb-2">Start Your Search</h3>
                    <p class="text-gray-600">Search for your favorite artists, albums, or tracks</p>
                </div>
            </div>
        `;
    },

    // Search history management
    addToSearchHistory(query) {
        // Don't add duplicates
        if (this.state.searchHistory.includes(query)) {
            return;
        }

        this.state.searchHistory.unshift(query);
        
        // Limit to 10 recent searches
        if (this.state.searchHistory.length > 10) {
            this.state.searchHistory = this.state.searchHistory.slice(0, 10);
        }

        this.saveSearchHistory();
        this.renderSearchHistory();
    },

    loadSearchHistory() {
        try {
            const history = localStorage.getItem('search_history');
            if (history) {
                this.state.searchHistory = JSON.parse(history);
                this.renderSearchHistory();
            }
        } catch (error) {
            console.error('Failed to load search history:', error);
        }
    },

    saveSearchHistory() {
        try {
            localStorage.setItem('search_history', JSON.stringify(this.state.searchHistory));
        } catch (error) {
            console.error('Failed to save search history:', error);
        }
    },

    renderSearchHistory() {
        const historyEl = document.getElementById('search-history');
        
        if (this.state.searchHistory.length === 0) {
            historyEl.innerHTML = '<p class="text-sm text-gray-500">No recent searches</p>';
            return;
        }

        historyEl.innerHTML = this.state.searchHistory.map(query => `
            <button 
                class="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md transition-colors focus-ring"
                onclick="SearchManager.performSearch(null, '${this.escapeHtml(query)}')"
            >
                <svg class="w-4 h-4 inline mr-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                ${this.escapeHtml(query)}
            </button>
        `).join('');
    },

    clearHistory() {
        this.state.searchHistory = [];
        this.saveSearchHistory();
        this.renderSearchHistory();
        ToastManager.info('Search history cleared');
    },

    // Utility functions
    formatDuration(ms) {
        const minutes = Math.floor(ms / 60000);
        const seconds = Math.floor((ms % 60000) / 1000);
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }
};

// Toggle filter section
function toggleFilterSection(section) {
    const filterEl = document.getElementById(`${section}-filter`);
    const iconEl = document.getElementById(`${section}-icon`);
    const button = iconEl.closest('button');
    
    if (filterEl.classList.contains('collapsed')) {
        filterEl.classList.remove('collapsed');
        iconEl.style.transform = 'rotate(180deg)';
        button.setAttribute('aria-expanded', 'true');
    } else {
        filterEl.classList.add('collapsed');
        iconEl.style.transform = 'rotate(0deg)';
        button.setAttribute('aria-expanded', 'false');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    SearchManager.init();
});
