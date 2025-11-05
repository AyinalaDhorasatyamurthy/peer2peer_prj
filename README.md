# Peer2Peer Torrent Client

A decentralized file-sharing application built with Python and WebSockets, enabling direct peer-to-peer file transfers with real-time progress tracking.

## 🚀 Features

- [x] Direct peer-to-peer file transfers
- [x] Web-based interface for easy access
- [x] Real-time progress tracking
- [x] Automatic peer discovery
- [x] Download/upload speed monitoring
- [x] Multi-peer file distribution
- [x] Support for .torrent files

## 🛠️ Tech Stack

- **Backend**: Python, Flask, Socket.IO
- **Frontend**: HTML5, JavaScript, Bootstrap 5
- **Networking**: WebSockets, HTTP Tracker Protocol
- **Storage**: Local file system

## 📦 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/AyinalaDhorasatyamurthy/peer2peer_prj.git
   cd peer2peer_prj/backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # OR
   source venv/bin/activate  # Linux/Mac
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## ⚙️ Configuration

Edit `config.py` to set up your network settings:

```python
HOST = 'YOUR_IP_ADDRESS'  # Your machine's IP
PORT = 5000  # Port to run the application
TRACKER_URL = 'http://TRACKER_IP:5000'  # URL of the tracker
```

## 🚀 Usage

1. Start the application:
   ```bash
   python main.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

3. Upload a .torrent file to start downloading

## 🌟 Multi-VM Setup

For testing with multiple peers:

1. Set up 3 VMs with IPs: 192.168.56.103, 192.168.56.104, 192.168.56.105
2. On each VM:
   - Clone the repository
   - Update `config.py` with the VM's IP
   - Set `TRACKER_URL` to the tracker's IP (VM 1)
   - Run `python main.py`

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
