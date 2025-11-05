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

    // WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const socket = new WebSocket(protocol + window.location.host + '/ws');

    // Socket event handlers
    socket.onopen = () => log('Connected to server');
    socket.onclose = () => log('Disconnected from server');
    socket.onerror = (error) => log(`WebSocket error: ${error.message}`);
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
            case 'status':
                log(data.message);
                break;
                
            case 'progress':
                updateProgress(data.progress);
                break;
                
            case 'peers':
                updatePeersList(data.peers);
                break;
                
            case 'speed':
                updateSpeed(data.download, data.upload);
                break;
                
            case 'error':
                log(`Error: ${data.message}`, 'error');
                break;
        }
    };

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
        } finally {
            setLoading(false);
        }
    }

    function log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type}`;
        logEntry.textContent = `[${timestamp}] ${message}`;
        statusDiv.prepend(logEntry);
    }

    function updateProgress(percent) {
        const roundedPercent = Math.round(percent);
        progressBar.style.width = `${roundedPercent}%`;
        progressBar.setAttribute('aria-valuenow', roundedPercent);
        progressText.textContent = `${roundedPercent}%`;
        
        if (roundedPercent >= 100) {
            progressBar.classList.remove('progress-bar-animated');
            log('Download completed!', 'success');
        }
    }

    function updatePeersList(peers) {
        peersList.innerHTML = '';
        
        if (peers.length === 0) {
            noPeers.classList.remove('d-none');
            return;
        }
        
        noPeers.classList.add('d-none');
        peers.forEach(peer => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-primary peer-badge';
            badge.textContent = peer;
            peersList.appendChild(badge);
        });
    }

    function updateSpeed(download, upload) {
        downloadSpeed.textContent = `${formatSpeed(download)}/s ↓`;
        uploadSpeed.textContent = `${formatSpeed(upload)}/s ↑`;
    }

    function formatSpeed(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    function setLoading(isLoading) {
        if (isLoading) {
            uploadBtn.disabled = true;
            uploadSpinner.classList.remove('d-none');
        } else {
            uploadBtn.disabled = false;
            uploadSpinner.classList.add('d-none');
        }
    }
});
