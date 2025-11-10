# 🌐 P2P Torrent Client with Tracker Server

A decentralized file-sharing application with a centralized tracker server, built with Python, Flask, and WebSockets. Enables direct peer-to-peer file transfers with real-time progress tracking and management.

## 🚀 Features

- [x] Centralized Tracker Server for peer discovery
- [x] Web-based interface with real-time updates
- [x] Peer registration and management
- [x] Real-time download/upload progress tracking
- [x] Multi-peer file distribution
- [x] Support for .torrent files
- [x] Connection status monitoring
- [x] Detailed activity logging
- [x] Automatic reconnection handling
- [x] Responsive UI with Bootstrap 5

## 🛠️ Tech Stack
<img width="10784" height="2856" alt="image" src="https://github.com/user-attachments/assets/c1b0c40a-19bd-4829-b5e6-71eddca70c1a" />
- **Backend**: Python 3.8+, Flask, Flask-SocketIO
- **Frontend**: HTML5, JavaScript (ES6+), Bootstrap 5
- **Networking**: WebSockets, HTTP Tracker Protocol
- **Storage**: Local file system with configurable paths
- **Dependencies**: 
  - python-socketio
  - python-engineio
  - bencodepy
  - bitstring
  - flask-cors

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone https://github.com/AyinalaDhorasatyamurthy/peer2peer_prj.git
   cd peer2peer_prj/backend
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # OR
   source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   
4. **Set up environment variables**:
   Create a `.env` file in the backend directory with:
   ```
   FLASK_APP=main.py
   FLASK_ENV=development
   SECRET_KEY=your-secret-key-here
   ```

## ⚙️ Configuration

Edit `config.py` to set up your network settings:

```python
# Network Configuration
HOST = '0.0.0.0'  # Bind to all interfaces
PORT = 5000  # Port to run the application
TRACKER_URL = 'http://192.168.56.3:5001'  # Default tracker URL (VM IP)

# File Storage
UPLOAD_FOLDER = 'uploads'  # Directory for uploaded files
TORRENT_FOLDER = 'torrents'  # Directory for .torrent files
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size

# Security
SECRET_KEY = 'your-secret-key-here'  # Change in production
```

## 🚀 Getting Started

### Running the Tracker (VM)

1. **VM Network Configuration** (One-time setup):
   - Open VirtualBox Manager
   - Right-click your VM and select **Settings**
   - Go to **Network** tab
   - Set **Attached to:** to **Host-only Adapter**
   - Ensure **Promiscuous Mode** is set to **Allow All**
   - Click **OK** to save settings
   - Start the VM and note its IP address (run `ipconfig` on Windows or `ifconfig` on Linux)

2. **Start the tracker server** (run this in the VM):
   ```bash
   python main.py
   ```
   The tracker will be available at `http://<VM_IP>:5001`
   
   > **Important**: Make sure the VM's firewall allows incoming connections on port 5001

### Running a Peer (Host Machine)

1. **Start a peer client**:
   ```bash
   python main.py
   ```
   The peer interface will be available at `http://localhost:5000`

2. **Using the Web Interface**:
   - Upload .torrent files through the web interface
   - Monitor active connections and download progress
   - View real-time logs and peer information

## 📡 Network Architecture

```
+----------------+         +-----------------+
|   Peer 1       | <-----> |                 |
+----------------+         |                 |
                           |   Tracker       |
+----------------+         |   (VM)          |
|   Peer 2       | <-----> |   192.168.56.3  |
+----------------+         |   :5001         |
                           |                 |
+----------------+         |                 |
|   Host Machine | <-----> |                 |
+----------------+         +-----------------+
```

## 🔍 Troubleshooting

- **Connection Issues**:
  - Ensure the VM's network is in Bridged or NAT mode
  - Verify the tracker URL in `config.py` matches the VM's IP
  - Check firewall settings to ensure the port is open

- **File Transfer Issues**:
  - Verify .torrent file integrity
  - Check available disk space
  - Ensure proper file permissions

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with ❤️ for educational purposes
- Inspired by BitTorrent protocol
- Uses various open-source libraries

## 🌟 Multi-Peer Testing

### Option 1: Multiple Browser Tabs (Easiest)
For quick testing, you can simulate multiple peers using different browser tabs:
1. Open `http://localhost:5000` in multiple browser tabs or different browsers
2. Each tab will act as a separate peer with a unique ID
3. You can test file sharing between these peer instances

### Option 2: Multiple VMs (Advanced)
For more realistic testing across different machines:
1. Set up VMs with these static IPs (or use DHCP with reservations):
   - Tracker: 192.168.56.103
   - Peer 1: 192.168.56.104
   - Peer 2: 192.168.56.105

2. On each VM (including the tracker):
   ```bash
   # Clone the repository
   git clone https://github.com/AyinalaDhorasatyamurthy/peer2peer_prj.git
   cd peer2peer_prj/backend
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Edit config.py
   # - Set HOST = '0.0.0.0'
   # - Set PORT = 5000 (or different port for each peer)
   # - Set TRACKER_URL = 'http://192.168.56.103:5000' (tracker's IP)
   
   # Run the application
   python main.py
   ```

3. Access each peer through its respective IP in a web browser

## 📂 Project Structure

```
peer2peer_prj/
├── backend/
│   ├── app/               # Application modules
│   │   ├── peer.py        # Peer management
│   │   ├── torrent.py     # Torrent handling
│   │   └── tracker.py     # Tracker logic
│   ├── web/               # Web interface
│   │   ├── static/        # Static files (JS, CSS)
│   │   └── templates/     # HTML templates
│   ├── uploads/           # Default upload directory
│   ├── config.py          # Configuration
│   ├── main.py            # Entry point
│   └── requirements.txt   # Dependencies
└── README.md
```
<img width="1913" height="882" alt="image" src="https://github.com/user-attachments/assets/d9961204-cbde-4ceb-8898-63a70c6dc086" />
<img width="1911" height="877" alt="image" src="https://github.com/user-attachments/assets/e8d964f3-5f02-461a-b6bd-e677d7bbab37" />


## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with ❤️ using Python, Flask, and Socket.IO
- Inspired by BitTorrent protocol
- Icons by [Bootstrap Icons](https://icons.getbootstrap.com/)
