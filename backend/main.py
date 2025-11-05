"""
Main entry point for the Peer2Peer Torrent Client web application.
"""
import os
import asyncio
import hashlib
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS
from app.peer import PeerManager, BlockRequest
from app.torrent import Torrent
from app.tracker import Tracker

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__,
              static_folder='web/static',
              template_folder='web/templates')

    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-123')
    app.config['UPLOAD_FOLDER'] = 'uploads'

    # Initialize extensions
    CORS(app)
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Global peer manager
    peer_manager = None

    @app.route('/')
    def index():
        """Serve the main application page."""
        return render_template('index.html')

    @app.route('/api/peers', methods=['GET'])
    def get_peers():
        """Get list of connected peers."""
        if peer_manager:
            peers = [f"{ip}:{port}" for ip, port in peer_manager.peers.keys()]
            return jsonify({"peers": peers})
        return jsonify({"peers": []})

    @app.route('/api/peers/connect', methods=['POST'])
    async def connect_peers():
        """Connect to peers from a torrent file."""
        global peer_manager
        
        try:
            data = request.get_json()
            torrent_path = data.get('torrent_path')
            
            if not torrent_path or not os.path.exists(torrent_path):
                return jsonify({"error": "Invalid torrent path"}), 400

            # Load torrent file
            torrent = Torrent(torrent_path)
            
            # Create tracker and get peers
            tracker = Tracker(torrent)
            peers = tracker.announce()
            
            # Create peer manager
            peer_id = b"-PC0001-" + os.urandom(12)  # Generate random peer ID
            peer_manager = PeerManager(torrent.info_hash, peer_id)
            
            # Connect to peers
            connected_peers = []
            for peer in peers:
                peer_conn = await peer_manager.add_peer(peer.ip, peer.port)
                if peer_conn:
                    connected_peers.append(f"{peer.ip}:{peer.port}")
            
            return jsonify({
                "status": "success",
                "connected_peers": connected_peers
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/download/start', methods=['POST'])
    async def start_download():
        """Start downloading a piece from peers."""
        try:
            data = request.get_json()
            piece_index = data.get('piece_index', 0)
            
            if not peer_manager:
                return jsonify({"error": "No peers connected"}), 400

            # Get a peer that has the piece
            peer = await peer_manager.get_peer_for_piece(piece_index)
            if not peer:
                return jsonify({"error": "No peer has the requested piece"}), 404

            # Request the first block of the piece
            block = BlockRequest(piece_index=piece_index, offset=0)
            data = await peer.request_piece(piece_index, block)
            
            if data:
                return jsonify({
                    "status": "success",
                    "piece": piece_index,
                    "data_size": len(data)
                })
            else:
                return jsonify({"error": "Failed to download piece"}), 500
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/static/<path:path>')
    def serve_static(path):
        """Serve static files."""
        return send_from_directory('web/static', path)

    return app, socketio

if __name__ == '__main__':
    # Create the web/static and web/templates directories if they don't exist
    os.makedirs('web/static/js', exist_ok=True)
    os.makedirs('web/templates', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)

    # Create a basic index.html if it doesn't exist
    index_path = os.path.join('web', 'templates', 'index.html')
    if not os.path.exists(index_path):
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write('''<!DOCTYPE html>
<html>
<head>
    <title>Peer2Peer Torrent Client</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .status {
            margin: 20px 0;
            padding: 10px;
            background: #e9ecef;
            border-radius: 4px;
        }
        .peers {
            margin: 20px 0;
        }
        .peer {
            padding: 8px;
            margin: 4px 0;
            background: #f8f9fa;
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
        }
        button {
            background: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
        }
        button:disabled {
            background: #6c757d;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Peer2Peer Torrent Client</h1>
        
        <div class="upload-section">
            <h2>Upload Torrent</h2>
            <input type="file" id="torrent-file" accept=".torrent">
            <button id="upload-btn">Start Download</button>
        </div>
        
        <div class="status" id="status">
            Ready to download torrents...
        </div>
        
        <div class="peers">
            <h2>Connected Peers</h2>
            <div id="peers-list">
                <p>No peers connected yet</p>
            </div>
            <button id="connect-btn">Connect to Peers</button>
        </div>
    </div>
    
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body>
</html>''')

    # Create a basic app.js if it doesn't exist
    js_dir = os.path.join('web', 'static', 'js')
    os.makedirs(js_dir, exist_ok=True)
    js_path = os.path.join(js_dir, 'app.js')
    if not os.path.exists(js_path):
        with open(js_path, 'w', encoding='utf-8') as f:
            f.write('''// Main application JavaScript
document.addEventListener('DOMContentLoaded', () => {
    const uploadBtn = document.getElementById('upload-btn');
    const connectBtn = document.getElementById('connect-btn');
    const torrentFile = document.getElementById('torrent-file');
    const statusDiv = document.getElementById('status');
    const peersList = document.getElementById('peers-list');

    // Handle file upload
    uploadBtn.addEventListener('click', async () => {
        const file = torrentFile.files[0];
        if (!file) {
            statusDiv.textContent = 'Please select a .torrent file';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            statusDiv.textContent = 'Uploading torrent file...';
            const response = await fetch('/api/torrents', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();
            if (response.ok) {
                statusDiv.textContent = `Download started: ${result.filename}`;
                // Enable the connect button after successful upload
                connectBtn.disabled = false;
            } else {
                statusDiv.textContent = `Error: ${result.error}`;
            }
        } catch (error) {
            statusDiv.textContent = `Error: ${error.message}`;
        }
    });

    // Handle peer connection
    connectBtn.addEventListener('click', async () => {
        try {
            statusDiv.textContent = "Connecting to peers...";
            const response = await fetch('/api/peers/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    torrent_path: 'path/to/your.torrent'  // Update this path
                })
            });
            
            const result = await response.json();
            
            if (result.error) {
                statusDiv.textContent = `Error: ${result.error}`;
            } else {
                statusDiv.textContent = `Connected to ${result.connected_peers.length} peers`;
                updatePeerList(result.connected_peers);
            }
        } catch (error) {
            statusDiv.textContent = `Error connecting to peers: ${error.message}`;
        }
    });

    // Update the peer list in the UI
    function updatePeerList(peers) {
        peersList.innerHTML = peers.length > 0 
            ? peers.map(peer => `<div class="peer">${peer}</div>`).join('')
            : '<p>No peers connected</p>';
    }

    // Initial fetch of peers
    async function fetchPeers() {
        try {
            const response = await fetch('/api/peers');
            const data = await response.json();
            updatePeerList(data.peers || []);
        } catch (error) {
            console.error('Error fetching peers:', error);
        }
    }

    // Initial fetch
    fetchPeers();
});
''')

    # Create the application and run it
    app, socketio = create_app()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)