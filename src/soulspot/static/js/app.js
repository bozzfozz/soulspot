// SoulSpot Bridge JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-refresh downloads page every 5 seconds if on downloads page
    if (window.location.pathname.includes('/downloads')) {
        setInterval(function() {
            htmx.trigger('#downloads-list', 'refresh');
        }, 5000);
    }

    // Handle HTMX events
    document.body.addEventListener('htmx:afterRequest', function(event) {
        if (event.detail.successful) {
            console.log('Request successful');
        } else {
            console.error('Request failed');
        }
    });

    // Auto-fill code verifier and state from authorization response
    document.body.addEventListener('htmx:afterSwap', function(event) {
        if (event.target.id === 'auth-result') {
            try {
                const response = JSON.parse(event.target.textContent);
                if (response.state && response.code_verifier) {
                    document.getElementById('state').value = response.state;
                    document.getElementById('code_verifier').value = response.code_verifier;
                    
                    // Open authorization URL in new tab
                    if (response.authorization_url) {
                        window.open(response.authorization_url, '_blank');
                    }
                }
            } catch (e) {
                console.log('Not a JSON response');
            }
        }
    });
});
