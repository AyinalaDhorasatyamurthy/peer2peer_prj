"""
Main entry point for the Peer2Peer Torrent Client (Host Machine)
"""
import os
import asyncio
import hashlib
import socket
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_from_directory, current_app
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from config import (
    HOST, PORT, TRACKER_URL, VM_IP, VM_PORT, 
    WEBSOCKET_PING_TIMEOUT, WEBSOCKET_PING_INTERVAL,
    MAX_RECONNECT_ATTEMPTS, RECONNECT_DELAY
)

# Import app modules
from app.peer import PeerManager, BlockRequest
from app.torrent import Torrent
from app.tracker import Tracker

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__,
              static_folder='web/static',
              template_folder='web/templates')
              
    # Ensure upload directory exists
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_dir

    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-123')
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
    app.config['TRACKER_URL'] = TRACKER_URL  # Set tracker URL from config
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Initialize CORS with more permissive settings
    CORS(app, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })

    socketio = SocketIO(
        app,
        async_mode='threading',
        cors_allowed_origins="*",
        logger=True,
        engineio_logger=True,
        ping_timeout=30,
        ping_interval=10,
        max_http_buffer_size=1e8,  # 100MB max message size
        allow_upgrades=True,
        http_compression=True,
        async_handlers=True,
        always_connect=True
    )

    # Connect Host Machine's Flask app to VM Tracker
    tracker_socket = None

    def connect_to_tracker():
        global tracker_socket
        try:
            print(f"🔌 Connecting Host Flask app to tracker: {TRACKER_URL}")
            
            # Import the correct Client class
            import socketio
            
            # Create a new client instance
            tracker_socket = socketio.Client(
                reconnection=True,
                reconnection_attempts=5,
                reconnection_delay=1,
                reconnection_delay_max=5,
                randomization_factor=0.5,
                logger=True,
                engineio_logger=True
            )
            
            @tracker_socket.event
            def connect():
                print("✅ Successfully connected to tracker")
                # Register Host as a peer with the tracker
                tracker_socket.emit('register_peer', {
                    'peer_id': f'HOST_FLASK_{PORT}',
                    'port': PORT,
                    'client_type': 'host_flask_server',
                    'ip_address': HOST,
                    'capabilities': ['seeding', 'leeching']
                })
                print(f"✅ Registered as peer: HOST_FLASK_{PORT}")
            
            @tracker_socket.event
            def message(data):
                print(f"📨 Tracker message: {data}")
            
            @tracker_socket.event
            def peers_updated(data):
                count = data.get('count', 0)
                print(f"👥 Peers updated: {count} peers in network")
                # Forward to all connected clients
                socketio.emit('peers_updated', data)
                
            @tracker_socket.event
            def disconnect():
                print("❌ Disconnected from tracker")
                
            @tracker_socket.event
            def connect_error(data):
                print(f"❌ Connection error: {data}")
            
            # Connect to the tracker
            try:
                tracker_socket.connect(
                    TRACKER_URL,
                    transports=['websocket', 'polling'],
                    namespaces=['/'],
                    wait_timeout=10
                )
                return True
            except Exception as e:
                print(f"❌ Failed to connect to tracker: {str(e)}")
                return False
                
        except ImportError as e:
            print(f"❌ Missing required package: {e}")
            print("Please install it with: pip install python-socketio[client]")
            return False
            
        except Exception as e:
            print(f"❌ Failed to initialize tracker connection: {e}")
            return False

    # Call this when the app starts
    connect_to_tracker()

    # Configuration endpoint
    @app.route('/api/config')
    def get_config():
        return jsonify({
            'trackerUrl': TRACKER_URL,
            'vmIp': VM_IP,
            'vmPort': VM_PORT,
            'reconnectAttempts': MAX_RECONNECT_ATTEMPTS,
            'reconnectDelay': RECONNECT_DELAY,
            'pingTimeout': WEBSOCKET_PING_TIMEOUT,
            'pingInterval': WEBSOCKET_PING_INTERVAL
        })
        
    # File upload endpoint is now at /api/torrents

    # Global peer manager
    peer_manager = None
    current_torrent = None

    # WebSocket event handlers
    @socketio.on('connect')
    def handle_connect():
        print(f"Client connected: {request.sid}")
        
        # Register this client as a peer with the tracker IMMEDIATELY
        emit('register_peer', {
            'peer_id': f'HOST_PEER_{request.sid[-6:]}',
            'port': PORT,
            'client_type': 'host_client', 
            'ip_address': HOST,
            'capabilities': ['download', 'upload']
        })
        
        emit('server_message', {
            'type': 'success',
            'message': 'Connected to P2P Client and registered with tracker as peer'
        })

    @socketio.on('register_peer')
    def handle_register_peer(data):
        """Handle peer registration response from tracker"""
        print(f"Peer registration response: {data}")
        emit('server_message', {
            'type': 'success',
            'message': f'Registered as peer with tracker: {data.get("peer_id", "unknown")}'
        })
    
    @socketio.on('test_connection')
    def handle_test_connection(data):
        client_ip = request.remote_addr
        print(f"Test connection from {request.sid}: {data}")
        
        # Send server_message response
        emit('server_message', {
            'type': 'success',
            'message': 'Connection test successful'
        })
        
        # Also send test_connection_response for backward compatibility
        emit('test_connection_response', 
             {
                 'status': 'success',
                 'server_time': str(datetime.utcnow()),
                 'server_version': '1.0.0',
                 'client_id': request.sid,
                 'message': f'Connected to {HOST}:{PORT}'
             },
             room=request.sid)

    @socketio.on('disconnect')
    def handle_disconnect():
        print(f'Client disconnected: {request.sid}')

    @socketio.on_error_default
    def error_handler(e):
        print(f'WebSocket error: {str(e)}')
        emit('server_message', {
            'type': 'error',
            'message': f'WebSocket error: {str(e)}'
        })

    # Additional WebSocket events for torrent operations
    @socketio.on('torrent_uploaded')
    def handle_torrent_uploaded(data):
        print(f"Torrent uploaded: {data}")
        emit('server_message', {
            'type': 'success',
            'message': f'Torrent {data.get("filename", "unknown")} uploaded successfully'
        })

    @socketio.on('download_started')
    def handle_download_started(data):
        print(f"Download started: {data}")
        emit('server_message', {
            'type': 'info',
            'message': f'Download started for piece {data.get("piece_index", 0)}'
        })

    @socketio.on('download_complete')
    def handle_download_complete(data):
        print(f"Download complete: {data}")
        emit('server_message', {
            'type': 'success',
            'message': 'Download completed successfully'
        })

    @socketio.on('download_error')
    def handle_download_error(data):
        print(f"Download error: {data}")
        emit('server_message', {
            'type': 'error',
            'message': f'Download error: {data.get("error", "Unknown error")}'
        })

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    def scan_torrents_directory(torrents_dir, request_id=None):
        """Scan the torrents directory and return a list of torrent files with metadata."""
        if request_id is None:
            request_id = str(uuid.uuid4())[:8]
            
        print(f"\n{'='*50}")
        print(f"[{request_id}] SCANNING TORRENT DIRECTORY")
        print(f"{'='*50}")
        print(f"[{request_id}] Directory: {torrents_dir}")
        
        if not os.path.exists(torrents_dir):
            try:
                os.makedirs(torrents_dir, exist_ok=True)
                print(f"[{request_id}] Created directory: {torrents_dir}")
            except Exception as e:
                error_msg = f"Failed to create directory: {str(e)}"
                print(f"[{request_id}] {error_msg}")
                return {'success': False, 'error': error_msg, 'torrents': []}
        
        if not os.path.isdir(torrents_dir):
            error_msg = f"Path is not a directory: {torrents_dir}"
            print(f"[{request_id}] {error_msg}")
            return {'success': False, 'error': error_msg, 'torrents': []}
        
        torrents = []
        try:
            # List all files in the directory
            all_files = os.listdir(torrents_dir)
            print(f"\n[{request_id}] Found {len(all_files)} items in directory:")
            
            # Filter for .torrent files (case-insensitive)
            torrent_files = [f for f in all_files if f.lower().endswith('.torrent')]
            print(f"[{request_id}] Found {len(torrent_files)} .torrent files: {torrent_files}")
            
            # Process each .torrent file
            for filename in torrent_files:
                filepath = os.path.join(torrents_dir, filename)
                if not os.path.isfile(filepath):
                    print(f"[{request_id}] Skipping non-file: {filepath}")
                    continue
                
                try:
                    # Get file metadata
                    file_size = os.path.getsize(filepath)
                    file_mtime = os.path.getmtime(filepath)
                    
                    # Read file content to compute hash
                    with open(filepath, 'rb') as f:
                        file_content = f.read()
                    
                    if not file_content:
                        print(f"[{request_id}] Warning: {filename} is empty")
                        continue
                    
                    # Compute info hash
                    info_hash = compute_torrent_info_hash(file_content)
                    
                    # Create torrent data
                    torrent_data = {
                        'filename': filename,
                        'filepath': filepath,
                        'size': file_size,
                        'uploaded_at': datetime.datetime.fromtimestamp(file_mtime).isoformat(),
                        'info_hash': info_hash,
                        'peers': []
                    }
                    
                    torrents.append(torrent_data)
                    print(f"[{request_id}] Processed: {filename} (hash: {info_hash[:8]}..., size: {file_size} bytes)")
                    
                except Exception as e:
                    print(f"[{request_id}] Error processing {filename}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"\n[{request_id}] Successfully processed {len(torrents)} torrent files")
            return {
                'success': True,
                'torrents': torrents,
                'count': len(torrents),
                'request_id': request_id
            }
            
        except Exception as e:
            error_msg = f"Error scanning directory: {str(e)}"
            print(f"[{request_id}] {error_msg}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': error_msg, 'torrents': []}
    
    @socketio.on('get_torrents')
    def handle_get_torrents(callback=None):
        """Handle request for list of available torrents"""
        request_id = str(uuid.uuid4())[:8]
        print(f"\n=== Handling get_torrents request ===")
        print(f"Request ID: {request_id}")
        
        try:
            # Get the torrents directory
            torrents_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
            print(f"[{request_id}] Scanning directory: {torrents_dir}")
            
            # Scan the directory for torrent files
            result = scan_torrents_directory(torrents_dir, request_id)
            print(f"[{request_id}] Scan result - Success: {result.get('success', False)}, Found {len(result.get('torrents', []))} torrents")
            
            # Ensure we have the expected structure
            if 'torrents' not in result:
                result['torrents'] = []
            
            # Update in-memory storage
            if result['success']:
                # Initialize in-memory storage if it doesn't exist
                if 'torrents' not in app.config:
                    app.config['torrents'] = {}
                
                # Update in-memory storage with the latest torrents
                for torrent in result['torrents']:
                    if 'info_hash' in torrent:
                        app.config['torrents'][torrent['info_hash']] = torrent
                
                print(f"[{request_id}] Updated in-memory storage with {len(result['torrents'])} torrents")
            
            # If this was a callback request, send the response back
            if callable(callback):
                print(f"[{request_id}] Sending callback response")
                callback(result)
            
            # Always emit the torrents_list event
            print(f"[{request_id}] Emitting torrents_list event with {len(result['torrents'])} torrents")
            socketio.emit('torrents_list', result)
            
            print(f"[{request_id}] Request completed successfully")
            return result
            
        except Exception as e:
            error_msg = f"Error processing torrents request: {str(e)}"
            print(f"[{request_id}] {error_msg}")
            import traceback
            traceback.print_exc()
            error_result = {'success': False, 'error': error_msg, 'torrents': []}
            if callable(callback):
                print(f"[{request_id}] Sending error callback")
                callback(error_result)
            print(f"[{request_id}] Emitting error event")
            socketio.emit('torrents_list', error_result)
            return error_result
            # Get the torrents list
            result = get_torrents_list()
            
            # Ensure we have the expected structure
            if not isinstance(result, dict) or 'torrents' not in result:
                result = {
                    'success': True,
                    'torrents': result if isinstance(result, list) else [],
                    'count': len(result) if isinstance(result, list) else 0,
                    'request_id': request_id
                }
            
            # Add timestamp
            result['timestamp'] = datetime.datetime.utcnow().isoformat()
            
            # If callback is provided, use it
            if callable(callback):
                print(f"[{request_id}] Sending response via callback")
                try:
                    callback(result)
                except Exception as e:
                    print(f"[{request_id}] Error in callback: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            # Always emit the event
            print(f"[{request_id}] Emitting torrents_list event with {len(result.get('torrents', []))} torrents")
            socketio.emit('torrents_list', result)
            
            # Return the response for direct calls
            return result
                
        except Exception as e:
            error_msg = f'Error getting torrents: {str(e)}'
            print(error_msg)
            import traceback
            traceback.print_exc()
            error_response = {
                'success': False,
                'error': error_msg,
                'torrents': [],
                'count': 0,
                'request_id': request_id,
                'timestamp': datetime.datetime.utcnow().isoformat()
            }
            
            print(f"[{request_id}] Error response: {error_response}")
            
            if callable(callback):
                try:
                    callback(error_response)
                except Exception as e:
                    print(f"[{request_id}] Error in error callback: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            # Always emit the error event
            socketio.emit('torrents_list', error_response)
                
            return error_response

    @socketio.on('download_started')
    def handle_download_started(data):
        print(f"Download started: {data}")
        emit('server_message', {
            'type': 'info',
            'message': f'Download started for piece {data.get("piece_index", 0)}'
        })

    @socketio.on('download_complete')
    def handle_download_complete(data):
        print(f"Download complete: {data}")
        emit('server_message', {
            'type': 'success',
            'message': 'Download completed successfully'
        })

    @socketio.on('download_error')
    def handle_download_error(data):
        print(f"Download error: {data}")
        emit('server_message', {
            'type': 'error',
            'message': f'Download error: {data.get("error", "Unknown error")}'
        })

    # Register routes
    @app.route('/')
    def index():
        """Serve the main application page."""
        try:
            return render_template('index.html', tracker_url=TRACKER_URL)
        except Exception as e:
            app.logger.error(f"Error rendering index.html: {str(e)}")
            return f"Error loading page: {str(e)}", 500
            
    @app.route('/about')
    @app.route('/about.html')
    def about():
        """Serve the about page."""
        try:
            return render_template('about.html')
        except Exception as e:
            app.logger.error(f"Error rendering about.html: {str(e)}")
            return f"Error loading about page: {str(e)}", 500

    def compute_torrent_info_hash(torrent_data):
        """Compute the info_hash of a torrent file."""
        import hashlib
        import bencodepy
        
        try:
            # Parse the torrent file
            metadata = bencodepy.decode(torrent_data)
            # Get the 'info' dictionary and re-encode it
            info = metadata[b'info']
            info_hash = hashlib.sha1(bencodepy.encode(info)).hexdigest()
            return info_hash
        except Exception as e:
            print(f"Error computing info_hash: {e}")
            # Fallback to MD5 of filename if we can't parse the torrent
            return hashlib.md5(torrent_data).hexdigest()[:8]

    # Add CORS headers to all responses
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        return response
        
    # Define upload handler function
    @app.route('/upload-torrent', methods=['POST', 'OPTIONS'])
    @app.route('/api/torrents', methods=['POST'])
    def handle_upload():
        """Handle torrent file upload."""
        if request.method == 'OPTIONS':
            return jsonify({'status': 'ok'})
            
        try:
            print("\n=== New Upload Request ===")
            print(f"Files received: {request.files}")
            
            # Check for both 'file' and 'torrent' field names for compatibility
            if 'file' in request.files:
                file = request.files['file']
                print("Using 'file' field for upload")
            elif 'torrent' in request.files:
                file = request.files['torrent']
                print("Using 'torrent' field for upload")
            else:
                error_msg = "No file part in the request. Expected 'file' or 'torrent' field."
                print(f"Error: {error_msg}")
                return jsonify({
                    "success": False,
                    "error": "No file part",
                    "message": error_msg
                }), 400
            print(f"Processing file: {file.filename}")
            
            if file.filename == '':
                error_msg = "No file was selected"
                print(f"Error: {error_msg}")
                return jsonify({
                    "success": False,
                    "error": "No selected file",
                    "message": error_msg
                }), 400

            if not file.filename.lower().endswith('.torrent'):
                error_msg = f"Invalid file type: {file.filename}"
                print(f"Error: {error_msg}")
                return jsonify({
                    "success": False,
                    "error": "Invalid file type",
                    "message": "File must be a .torrent file"
                }), 400

            # Ensure upload directory exists
            upload_dir = app.config['UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)
            print(f"\n=== Upload Request ===")
            print(f"Upload directory: {os.path.abspath(upload_dir)}")
            print(f"Directory exists: {os.path.exists(upload_dir)}")
            print(f"Directory is writable: {os.access(upload_dir, os.W_OK)}")
            print(f"Files in directory before upload: {os.listdir(upload_dir) if os.path.exists(upload_dir) else 'Directory does not exist'}")

            try:
                # Read the file data
                file_data = file.read()
                if not file_data:
                    raise ValueError("File is empty")
                print(f"Read {len(file_data)} bytes from file")
                
                # Generate a safe filename
                from werkzeug.utils import secure_filename
                filename = secure_filename(file.filename)
                filepath = os.path.join(upload_dir, filename)
                
                # Check if file already exists to avoid overwriting
                if os.path.exists(filepath):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(filepath):
                        filename = f"{base}_{counter}{ext}"
                        filepath = os.path.join(upload_dir, filename)
                        counter += 1
                
                # Save the file first
                print(f"\n=== Saving File ===")
                print(f"Saving to: {filepath}")
                print(f"File already exists: {os.path.exists(filepath)}")
                
                try:
                    with open(filepath, 'wb') as f:
                        f.write(file_data)
                    
                    # Verify file was written
                    if not os.path.exists(filepath):
                        raise IOError("File was not created after write operation")
                        
                    file_size = os.path.getsize(filepath)
                    print(f"File saved successfully. Size: {file_size} bytes")
                    print(f"File exists after write: {os.path.exists(filepath)}")
                    print(f"File size on disk: {os.path.getsize(filepath)} bytes")
                    print(f"Files in directory after save: {os.listdir(upload_dir)}")
                    
                except Exception as e:
                    print(f"Error saving file: {str(e)}")
                    print(f"Current working directory: {os.getcwd()}")
                    print(f"Directory contents: {os.listdir(os.path.dirname(filepath) if os.path.dirname(filepath) else '.')}")
                    raise
                
                # Compute info_hash from the torrent file
                info_hash = compute_torrent_info_hash(file_data)
                print(f"Computed info_hash: {info_hash}")
                
                # Create metadata
                torrent_metadata = {
                    'filename': filename,
                    'filepath': filepath,
                    'info_hash': info_hash,
                    'size': file_size,
                    'uploaded_at': datetime.datetime.utcnow().isoformat(),
                    'peers': []
                }
                
                # Add to our in-memory storage
                if 'torrents' not in app.config:
                    app.config['torrents'] = {}
                app.config['torrents'][info_hash] = torrent_metadata
                
                # Prepare response
                response_data = {
                    "success": True,
                    "message": "Torrent uploaded successfully",
                    "filename": filename,
                    "file_path": filepath,
                    "info_hash": info_hash,
                    "size": file_size,
                    "status": "success"
                }
                
                print("\n=== Upload Response ===")
                print(f"Response data: {response_data}")
                print(f"File exists in response handler: {os.path.exists(filepath)}")
                print(f"File size in response handler: {os.path.getsize(filepath) if os.path.exists(filepath) else 0} bytes")
                
                print(f"Upload successful. Response: {response_data}")
                
                # Emit torrent_added event to all connected clients
                socketio.emit('torrent_added', {
                    'filename': filename,
                    'info_hash': info_hash,
                    'size': file_size,
                    'uploaded_at': datetime.datetime.utcnow().isoformat()
                })
                
                return jsonify(response_data)
                
            except Exception as e:
                error_msg = f"Error processing file: {str(e)}"
                print(f"Error: {error_msg}")
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        print(f"Removed partially uploaded file: {filepath}")
                    except Exception as cleanup_error:
                        print(f"Error cleaning up file: {cleanup_error}")
                
                return jsonify({
                    "success": False,
                    "error": "File processing error",
                    "message": error_msg
                }), 500
                
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"Unexpected error: {error_msg}")
            return jsonify({
                "success": False,
                "error": "Upload failed",
                "message": error_msg
            }), 500
            
        except Exception as e:
            print(f"Error in upload_torrent: {str(e)}")
            # Emit WebSocket error event
            socketio.emit('torrent_upload_error', {
                'error': str(e),
                'timestamp': datetime.datetime.utcnow().isoformat()
            }, namespace='/')
            return jsonify({
                "success": False,
                "error": "Upload failed",
                "message": str(e)
            }), 500

    @app.route('/api/peers', methods=['GET'])
    def get_peers():
        """Get list of connected peers from the tracker."""
        try:
            # This endpoint will be called by the frontend to get the list of peers
            if peer_manager and hasattr(peer_manager, 'peers'):
                peers = [f"{ip}:{port}" for ip, port in peer_manager.peers.keys()]
                
                # Emit WebSocket event for peer list update
                socketio.emit('peers', {
                    'peers': peers,
                    'count': len(peers),
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                return jsonify({
                    "status": "success",
                    "peers": peers,
                    "count": len(peers),
                    "tracker": TRACKER_URL
                })
            return jsonify({
                "status": "success",
                "peers": [],
                "count": 0,
                "tracker": TRACKER_URL,
                "message": "No peer manager initialized"
            })
        except Exception as e:
            socketio.emit('server_message', {
                'type': 'error',
                'message': f'Failed to fetch peers: {str(e)}'
            })
            return jsonify({
                "status": "error",
                "message": f"Failed to fetch peers: {str(e)}",
                "tracker": TRACKER_URL
            }), 500

    @app.route('/api/peers/connect', methods=['POST'])
    async def connect_peers():
        """Connect to peers through the tracker."""
        global peer_manager, current_torrent

        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400

            torrent_path = data.get('torrent_path')
            if not torrent_path:
                return jsonify({"error": "No torrent path provided"}), 400

            if not os.path.exists(torrent_path):
                return jsonify({"error": f"Torrent file not found: {torrent_path}"}), 404

            try:
                # Load torrent file
                current_torrent = Torrent(torrent_path)

                # After loading torrent, register with tracker as download client
                socketio.emit('register_peer', {
                    'peer_id': f"DOWNLOAD_PEER_{hash(current_torrent.info_hash) % 10000:04d}",
                    'port': PORT,
                    'client_type': 'download_client',
                    'torrent_hash': current_torrent.info_hash.hex() if hasattr(current_torrent.info_hash, 'hex') else str(current_torrent.info_hash),
                    'torrent_name': os.path.basename(torrent_path),
                    'ip_address': HOST
                })

                # Create tracker and get peers
                tracker = Tracker(current_torrent)
                peers = await tracker.get_peers()  # Make sure this is async

                # Create peer manager
                peer_id = b"-HOST01-" + os.urandom(12)  # Unique ID for host
                peer_manager = PeerManager(current_torrent.info_hash, peer_id)

                # Connect to peers
                connected_peers = []
                for peer in peers:
                    try:
                        if peer.ip != HOST or peer.port != PORT:  # Don't connect to self
                            peer_conn = await peer_manager.add_peer(peer.ip, peer.port)
                            if peer_conn:
                                connected_peers.append(f"{peer.ip}:{peer.port}")
                    except Exception as peer_error:
                        print(f"Failed to connect to peer {peer.ip}:{peer.port}: {peer_error}")

                # Notify tracker about this peer
                try:
                    await tracker.announce(peer_id, PORT, event='started')
                except Exception as e:
                    print(f"Warning: Could not announce to tracker: {e}")

                # Emit WebSocket events
                socketio.emit('server_message', {
                    'type': 'success',
                    'message': f'Connected to {len(connected_peers)} peers'
                })
                
                socketio.emit('peers', {
                    'peers': connected_peers,
                    'count': len(connected_peers),
                    'total_found': len(peers)
                })

                # Register as active download peer
                socketio.emit('register_peer', {
                    'peer_id': f"ACTIVE_PEER_{hash(current_torrent.info_hash) % 10000:04d}",
                    'port': PORT,
                    'client_type': 'active_downloader',
                    'torrent_hash': current_torrent.info_hash.hex() if hasattr(current_torrent.info_hash, 'hex') else str(current_torrent.info_hash),
                    'connected_peers': len(connected_peers),
                    'ip_address': HOST
                })

                return jsonify({
                    "status": "success",
                    "connected_peers": connected_peers,
                    "total_peers_found": len(peers),
                    "tracker": TRACKER_URL
                })

            except Exception as e:
                socketio.emit('server_message', {
                    'type': 'error',
                    'message': f'Error processing torrent: {str(e)}'
                })
                return jsonify({"error": f"Error processing torrent: {str(e)}"}), 500

        except Exception as e:
            socketio.emit('server_message', {
                'type': 'error',
                'message': f'Server error: {str(e)}'
            })
            return jsonify({"error": f"Server error: {str(e)}"}), 500

    @app.route('/api/download/start', methods=['POST'])
    async def start_download():
        """Start downloading a piece from peers."""
        try:
            data = request.get_json()
            piece_index = data.get('piece_index', 0)

            if not peer_manager:
                return jsonify({"error": "No peers connected"}), 400

            # Emit download started event
            socketio.emit('download_started', {
                'piece_index': piece_index,
                'timestamp': datetime.utcnow().isoformat()
            })

            # Get a peer that has the piece
            peer = await peer_manager.get_peer_for_piece(piece_index)
            if not peer:
                socketio.emit('server_message', {
                    'type': 'error',
                    'message': f'No peer has piece {piece_index}'
                })
                return jsonify({"error": "No peer has the requested piece"}), 404

            # Request the first block of the piece
            block = BlockRequest(piece_index=piece_index, offset=0)
            data = await peer.request_piece(piece_index, block)

            if data:
                socketio.emit('server_message', {
                    'type': 'success',
                    'message': f'Successfully downloaded piece {piece_index} ({len(data)} bytes)'
                })
                
                # Update tracker about download progress
                if current_torrent:
                    socketio.emit('register_peer', {
                        'peer_id': f"DOWNLOAD_PEER_{hash(current_torrent.info_hash) % 10000:04d}",
                        'port': PORT,
                        'client_type': 'downloading',
                        'torrent_hash': current_torrent.info_hash.hex() if hasattr(current_torrent.info_hash, 'hex') else str(current_torrent.info_hash),
                        'downloaded_pieces': piece_index + 1,
                        'ip_address': HOST
                    })
                
                return jsonify({
                    "status": "success",
                    "piece": piece_index,
                    "data_size": len(data)
                })
            else:
                socketio.emit('server_message', {
                    'type': 'error',
                    'message': f'Failed to download piece {piece_index}'
                })
                return jsonify({"error": "Failed to download piece"}), 500

        except Exception as e:
            socketio.emit('server_message', {
                'type': 'error',
                'message': f'Download error: {str(e)}'
            })
            return jsonify({"error": str(e)}), 500

    @app.route('/static/<path:path>')
    def serve_static(path):
        """Serve static files."""
        return send_from_directory('web/static', path)

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app, socketio

def create_basic_index():
    """Create a basic index.html if it doesn't exist."""
    index_path = os.path.join('web', 'templates', 'index.html')
    if not os.path.exists(index_path):
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write('''<!DOCTYPE html>
<html>
<head>
    <title>P2P Torrent Client (Host)</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .progress { height: 25px; }
        .progress-bar { transition: width 0.3s; }
        .peer-list { max-height: 300px; overflow-y: auto; }
    </style>
</head>
<body>
    <div class="container mt-4">
        <h1 class="mb-4">P2P Torrent Client (Host)</h1>
        
        <div class="row">
            <div class="col-md-6">
                <div class="card mb-4">
                    <div class="card-header">
                        <h5>Upload Torrent</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <input type="file" id="torrent-file" class="form-control" accept=".torrent">
                        </div>
                        <button id="upload-btn" class="btn btn-primary">Upload & Start</button>
                        <div id="upload-status" class="mt-2"></div>
                    </div>
                </div>

                <div class="card mb-4">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5>Download Progress</h5>
                        <span id="download-speed" class="badge bg-info">0 KB/s</span>
                    </div>
                    <div class="card-body">
                        <div class="progress mb-2">
                            <div id="progress-bar" class="progress-bar" role="progressbar" style="width: 0%">0%</div>
                        </div>
                        <div id="progress-text" class="text-muted small">No active downloads</div>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5>Connected Peers</h5>
                        <button id="refresh-peers" class="btn btn-sm btn-outline-secondary">⟳ Refresh</button>
                    </div>
                    <div class="card-body p-0">
                        <div id="peers-list" class="list-group list-group-flush peer-list">
                            <div class="list-group-item text-muted">Not connected to any peers</div>
                        </div>
                    </div>
                    <div class="card-footer text-muted small">
                        Tracker: <span id="tracker-url">{{ tracker_url }}</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="card mt-4">
            <div class="card-header">
                <h5>Logs</h5>
            </div>
            <div class="card-body p-0">
                <pre id="logs" class="p-3 mb-0 bg-dark text-light" style="min-height: 100px; max-height: 200px; overflow-y: auto;"></pre>
            </div>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        // Configuration
        const config = {
            trackerUrl: document.getElementById('tracker-url').textContent,
            socketUrl: window.location.origin
        };

        // DOM Elements
        const elements = {
            uploadBtn: document.getElementById('upload-btn'),
            torrentFile: document.getElementById('torrent-file'),
            uploadStatus: document.getElementById('upload-status'),
            peersList: document.getElementById('peers-list'),
            progressBar: document.getElementById('progress-bar'),
            progressText: document.getElementById('progress-text'),
            downloadSpeed: document.getElementById('download-speed'),
            refreshPeers: document.getElementById('refresh-peers'),
            logs: document.getElementById('logs')
        };

        // Initialize Socket.IO - Connect to TRACKER
        const socket = io(config.trackerUrl, {
            reconnection: true,
            reconnectionAttempts: config.reconnectAttempts,
            reconnectionDelay: config.reconnectDelay
        });

        // Socket Events
        socket.on('connect', () => {
            log('Connected to Tracker server');
        });

        socket.on('disconnect', () => {
            log('Disconnected from Tracker server');
        });

        socket.on('server_message', (data) => {
            log(`[${data.type}] ${data.message}`);
        });

        socket.on('status', (data) => {
            log(`Status: ${data.message}`);
        });

        socket.on('peers', (data) => {
            updatePeerList(data.peers || []);
            log(`Peer list updated: ${data.count} peers connected`);
        });

        socket.on('download_started', (data) => {
            log(`Download started for piece ${data.piece_index}`);
        });

        // UI Event Handlers
        elements.uploadBtn.addEventListener('click', handleUpload);
        elements.refreshPeers.addEventListener('click', fetchPeers);

        // Functions
        function log(message) {
            const logEntry = document.createElement('div');
            logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            elements.logs.appendChild(logEntry);
            elements.logs.scrollTop = elements.logs.scrollHeight;
        }

        async function handleUpload() {
            const file = elements.torrentFile.files[0];
            if (!file) {
                alert('Please select a .torrent file first');
                return;
            }

            const formData = new FormData();
            formData.append('file', file);

            try {
                elements.uploadBtn.disabled = true;
                elements.uploadStatus.textContent = 'Uploading torrent file...';
                
                const response = await fetch(config.uploadEndpoint, {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                
                if (response.ok) {
                    log(`Successfully uploaded: ${result.filename}`);
                    await connectToPeers(result.file_path);
                } else {
                    throw new Error(result.error || 'Failed to upload torrent');
                }
            } catch (error) {
                log(`Error: ${error.message}`);
                elements.uploadStatus.textContent = `Error: ${error.message}`;
            } finally {
                elements.uploadBtn.disabled = false;
            }
        }

        async function connectToPeers(torrentPath) {
            try {
                log('Connecting to peers...');
                const response = await fetch('/api/peers/connect', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        torrent_path: torrentPath
                    })
                });

                const result = await response.json();
                
                if (response.ok) {
                    log(`Connected to ${result.connected_peers.length} out of ${result.total_peers_found} peers`);
                    updatePeerList(result.connected_peers);
                } else {
                    throw new Error(result.error || 'Failed to connect to peers');
                }
            } catch (error) {
                log(`Error connecting to peers: ${error.message}`);
            }
        }

        async function fetchPeers() {
            try {
                // Try to get config from server
                const response = await fetch(config.apiBase + '/config');
                const data = await response.json();
                
                if (data.status === 'success') {
                    updatePeerList(data.peers || []);
                }
            } catch (error) {
                log(`Error fetching peers: ${error.message}`);
            }
        }

        function updatePeerList(peers) {
            if (peers.length === 0) {
                elements.peersList.innerHTML = '<div class="list-group-item text-muted">No peers connected</div>';
                return;
            }

            elements.peersList.innerHTML = peers
                .map(peer => `
                    <div class="list-group-item d-flex justify-content-between align-items-center">
                        <span>${peer}</span>
                        <span class="badge bg-success">Connected</span>
                    </div>
                `)
                .join('');
        }

        // Initial setup
        fetchPeers();
        log('Client initialized. Ready to upload torrents.');
    </script>
</body>
</html>''')

def get_local_ip():
    """Get the local IP address of the machine."""
    try:
        # Connect to an external server to get the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        return "127.0.0.1"

def run_app():
    # Create necessary directories
    os.makedirs('web/static/js', exist_ok=True)
    os.makedirs('web/templates', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('torrents', exist_ok=True)

    # Create basic index.html if it doesn't exist
    create_basic_index()
    
    # Create and configure the app
    app = Flask(__name__,
              static_folder='web/static',
              template_folder='web/templates')
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-123')
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
    app.config['TRACKER_URL'] = TRACKER_URL
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    # Register routes
    @app.route('/')
    def index():
        """Serve the main application page."""
        try:
            return render_template('index.html', tracker_url=TRACKER_URL)
        except Exception as e:
            app.logger.error(f"Error rendering index.html: {str(e)}")
            return f"Error loading page: {str(e)}", 500
            
    @app.route('/about')
    @app.route('/about.html')
    def about():
        """Serve the about page."""
        try:
            return render_template('about.html')
        except Exception as e:
            app.logger.error(f"Error rendering about.html: {str(e)}")
            return f"Error loading about page: {str(e)}", 500
    
    # Get local IP for network access
    local_ip = get_local_ip()
    
    print(f"\n{'='*70}")
    print(f"P2P Client v1.0.0")
    print(f"{'='*70}")
    print(f"Local URL:    http://localhost:{PORT}")
    print(f"Network URL:  http://{local_ip}:{PORT}")
    print(f"Tracker URL:  {TRACKER_URL}")
    print(f"{'='*70}")
    
    return app, socketio

def add_routes(app):
    """Add all routes to the Flask application."""
    
    @app.route('/test')
    def test():
        return jsonify({
            'status': 'ok',
            'message': 'Server is running',
            'endpoints': [
                {'method': 'GET', 'path': '/test', 'description': 'Test endpoint'},
                {'method': 'POST', 'path': '/upload', 'description': 'Upload torrent file'},
                {'method': 'GET', 'path': '/', 'description': 'Main interface'}
            ]
        })
    
    @app.route('/upload', methods=['POST'])
    def upload():
        """Simple file upload endpoint for testing."""
        try:
            print("\n=== Upload Request Received ===")
            print(f"Files received: {request.files}")
            
            if 'file' not in request.files:
                print("No file part in request")
                return jsonify({'error': 'No file part'}), 400
                
            file = request.files['file']
            if file.filename == '':
                print("No file selected")
                return jsonify({'error': 'No selected file'}), 400
                
            if file and file.filename.endswith('.torrent'):
                upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                filename = os.path.join(upload_dir, file.filename)
                print(f"Saving file to: {filename}")
                file.save(filename)
                
                if not os.path.exists(filename):
                    print(f"Error: File was not saved to {filename}")
                    return jsonify({'error': 'Failed to save file'}), 500
                    
                print(f"File saved successfully: {os.path.getsize(filename)} bytes")
                
                # Trigger a torrent list refresh and emit to all clients
                try:
                    torrents_dir = os.path.dirname(filename)
                    result = scan_torrents_directory(torrents_dir)
                    if result['success']:
                        print(f"Successfully refreshed torrent list with {len(result.get('torrents', []))} torrents")
                        # Emit the updated list to all connected clients
                        socketio.emit('torrents_list', result)
                    else:
                        print(f"Warning: Failed to refresh torrent list: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    print(f"Error refreshing torrent list: {str(e)}")
                
                return jsonify({
                    'success': True,
                    'message': 'File uploaded successfully',
                    'filename': file.filename,
                    'path': filename
                })
            else:
                print(f"Invalid file type: {file.filename}")
                return jsonify({'error': 'Invalid file type'}), 400
                
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error in upload handler: {error_trace}")
            return jsonify({
                'error': str(e),
                'message': 'An error occurred during file upload',
                'trace': error_trace
            }), 500

if __name__ == '__main__':
    app, socketio = run_app()
    
    # Add all routes
    add_routes(app)
    
    # Print available routes
    print("\n" + "="*70)
    print("Available HTTP Endpoints:")
    print("  - GET  /                     # Main interface")
    print("  - GET  /test                # Test endpoint")
    print("  - POST /upload              # Upload torrent file")
    print("  - GET  /api/peers           # List connected peers")
    print("  - POST /api/peers/connect   # Connect to peers")
    print("  - POST /api/torrents        # Upload torrent file")
    print("  - WS   /socket.io/          # WebSocket endpoint")
    print("\nWebSocket Events:")
    print("  - connect                   # Client connection")
    print("  - test_connection           # Connection test")
    print("  - server_message            # Server notifications")
    print("  - torrent_uploaded          # Torrent upload events")
    print("  - download_started          # Download start events")
    print("  - peers                     # Peer list updates")
    print("  - register_peer             # Register with tracker")
    print("="*70 + "\n")
    
    # Start the server
    try:
        socketio.run(app, 
                    host=HOST, 
                    port=PORT, 
                    debug=True, 
                    use_reloader=False,
                    allow_unsafe_werkzeug=True)
    except Exception as e:
        print(f"Error starting server: {e}")
        raise