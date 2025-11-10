"""
Configuration settings for the Peer2Peer Torrent application.
Loads configuration from .env file with fallback to defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.absolute()

# ===== VM Configuration =====
VM_IP = os.getenv('VM_IP', '192.168.56.3')
VM_PORT = int(os.getenv('VM_PORT', '5001'))
VM_USER = os.getenv('VM_USER', 'user')
VM_PASSWORD = os.getenv('VM_PASSWORD', 'password')

# ===== Network Settings =====
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '5000'))
TRACKER_URL = os.getenv('TRACKER_URL', f'http://{VM_IP}:{VM_PORT}')
MAX_PEERS = int(os.getenv('MAX_PEERS', '50'))

# ===== File Storage =====
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
TORRENT_FOLDER = os.path.join(BASE_DIR, 'torrents')

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TORRENT_FOLDER, exist_ok=True)

# ===== Tracker Settings =====
TRACKER_INTERVAL = int(os.getenv('TRACKER_INTERVAL', '30'))  # seconds
TRACKER_TIMEOUT = int(os.getenv('TRACKER_TIMEOUT', '120'))  # seconds

# ===== WebSocket Settings =====
WEBSOCKET_PING_TIMEOUT = int(os.getenv('WEBSOCKET_PING_TIMEOUT', '30'))
WEBSOCKET_PING_INTERVAL = int(os.getenv('WEBSOCKET_PING_INTERVAL', '10'))

# ===== Peer Configuration =====
PEER_ID_PREFIX = os.getenv('PEER_ID_PREFIX', 'PEER_')
MAX_RECONNECT_ATTEMPTS = int(os.getenv('MAX_RECONNECT_ATTEMPTS', '10'))
RECONNECT_DELAY = int(os.getenv('RECONNECT_DELAY', '2000'))  # ms

# ===== Application Settings =====
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO' if not DEBUG else 'DEBUG')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# ===== Print Configuration (for debugging) =====
if DEBUG:
    print("\n=== Configuration ===")
    print(f"VM Connection: {VM_USER}@{VM_IP}:{VM_PORT}")
    print(f"Server: http://{HOST}:{PORT}")
    print(f"Tracker URL: {TRACKER_URL}")
    print(f"Debug Mode: {DEBUG}")
    print("==================\n")
