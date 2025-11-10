// Main application JavaScript
document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const uploadBtn = document.getElementById('upload-btn');
    const torrentFile = document.getElementById('torrent-file');
    const statusDiv = document.getElementById('status');
    const uploadSpinner = document.getElementById('upload-spinner');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const peersList = document.getElementById('peers-list');
    const noPeers = document.getElementById('no-peers');
    const downloadSpeed = document.getElementById('download-speed');
    const uploadSpeed = document.getElementById('upload-speed');
    const statusElement = document.getElementById('connection-status');
    const statusText = document.getElementById('status-text');
    const logContainer = document.getElementById('log-container');

    // WebSocket configuration
    const API_URL = 'http://192.168.56.3:5001/api';
    const WS_URL = 'http://192.168.56.3:5001';
    
    console.log('Connecting to WebSocket at:', WS_URL);
    
    const socket = io(WS_URL, {
        path: '/socket.io',
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
        timeout: 10000,
        transports: ['websocket', 'polling']
    });

    // Update connection status
    function updateConnectionStatus(connected) {
        if (connected) {
            statusElement.className = 'status-indicator connected';
            statusText.textContent = 'Connected';
            log('Connected to WebSocket server', 'success');
        } else {
            statusElement.className = 'status-indicator disconnected';
            statusText.textContent = 'Disconnected';
        }
    }

    // Socket.IO event handlers
    socket.on('connect', () => {
        console.log('Successfully connected to WebSocket server at', WS_URL);
        updateConnectionStatus(true);
        
        // Test the WebSocket connection
        socket.emit('test_connection', { 
            client: 'host_machine',
            message: 'Hello from client',
            timestamp: new Date().toISOString()
        });
    });

    socket.on('disconnect', (reason) => {
        console.log('Disconnected from WebSocket server. Reason:', reason);
        updateConnectionStatus(false);
        log(`Disconnected from server: ${reason}`, 'warning');
    });

    socket.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error);
        updateConnectionStatus(false);
        const errorMsg = error.message || 'Connection failed';
        log(`Connection error: ${errorMsg}`, 'error');
    });

    // Handle test connection response
    socket.on('test_connection_response', (data) => {
        console.log('Server test connection response:', data);
        log(`Server version: ${data.server_version || 'unknown'}`, 'success');
    });

    socket.on('server_message', (data) => {
        log(data.message, data.type || 'info');
    });

    // Handle progress updates
    socket.on('progress', (data) => {
        updateProgress(data.progress);
    });

    // Handle peer updates
    socket.on('peers', (data) => {
        updatePeersList(data.peers);
    });

    // Handle speed updates
    socket.on('speed', (data) => {
        updateSpeed(data.download, data.upload);
    });

    // Handle download status
    socket.on('download_status', (data) => {
        log(data.message, data.type || 'info');
    });

    // Event Listeners
    uploadBtn.addEventListener('click', handleUpload);

    // Functions
    async function handleUpload() {
        const file = torrentFile.files[0];
        if (!file) {
            log('Please select a .torrent file', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('torrent', file);

        try {
            setLoading(true);
            log('Uploading torrent file...');
            
            // First upload the torrent file
            const response = await fetch('/api/peers/connect', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to upload torrent');
            }

            const result = await response.json();
            log(`Connected to ${result.connected_peers.length} peers`);
            
            // Emit socket event for torrent upload
            socket.emit('torrent_uploaded', {
                filename: file.name,
                peers_count: result.connected_peers.length
            });
            
            // Start downloading the first piece
            const downloadResponse = await fetch('/api/download/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ piece_index: 0 })
            });

            if (!downloadResponse.ok) {
                throw new Error('Failed to start download');
            }
            
            log('Download started successfully!', 'success');
            
        } catch (error) {
            log(`Error: ${error.message}`, 'error');
            console.error('Upload error:', error);
            
            // Emit error event
            socket.emit('download_error', {
                error: error.message,
                timestamp: new Date().toISOString()
            });
        } finally {
            setLoading(false);
        }
    }

    function updateStatus(message, type = 'info') {
        const statusElement = document.getElementById('status-message');
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.className = `alert alert-${type} mb-3`;
            
            // Auto-hide success messages after 5 seconds
            if (type === 'success') {
                setTimeout(() => {
                    if (statusElement.textContent === message) {
                        statusElement.className = 'd-none';
                    }
                }, 5000);
            }
        }
        log(message, type);
    }

    function log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry text-${type} small`;
        logEntry.innerHTML = `[${timestamp}] ${message}`;
        
        // Use the unified log container
        if (logContainer) {
            logContainer.appendChild(logEntry);
            logContainer.scrollTop = logContainer.scrollHeight;
        }
        
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    function updateProgress(percent) {
        const roundedPercent = Math.round(percent);
        if (progressBar) {
            progressBar.style.width = `${roundedPercent}%`;
            progressBar.setAttribute('aria-valuenow', roundedPercent);
        }
        if (progressText) {
            progressText.textContent = `${roundedPercent}%`;
        }
        
        if (roundedPercent >= 100) {
            if (progressBar) {
                progressBar.classList.remove('progress-bar-animated');
            }
            log('Download completed!', 'success');
            
            // Emit completion event
            socket.emit('download_complete', {
                timestamp: new Date().toISOString(),
                file_size: 'unknown' // You can add actual file size here
            });
        }
    }

    function updatePeersList(peers) {
        if (!peersList) return;
        
        peersList.innerHTML = '';
        
        if (peers.length === 0) {
            if (noPeers) noPeers.classList.remove('d-none');
            return;
        }
        
        if (noPeers) noPeers.classList.add('d-none');
        peers.forEach(peer => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-primary peer-badge me-1 mb-1';
            badge.textContent = peer;
            peersList.appendChild(badge);
        });
    }

    function updateSpeed(download, upload) {
        if (downloadSpeed) {
            downloadSpeed.textContent = `${formatSpeed(download)}/s ↓`;
        }
        if (uploadSpeed) {
            uploadSpeed.textContent = `${formatSpeed(upload)}/s ↑`;
        }
    }

    function formatSpeed(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    function setLoading(isLoading) {
        if (isLoading) {
            uploadBtn.disabled = true;
            if (uploadSpinner) uploadSpinner.classList.remove('d-none');
        } else {
            uploadBtn.disabled = false;
            if (uploadSpinner) uploadSpinner.classList.add('d-none');
        }
    }

    // Initialize connection status
    updateConnectionStatus(false);
    log('Initializing WebSocket connection...', 'info');
});