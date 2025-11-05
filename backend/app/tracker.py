"""
Module for communicating with BitTorrent trackers.
"""
import socket
import random
import urllib.parse
import urllib.request
import urllib.error
import struct
import time
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Peer:
    """Represents a peer in the BitTorrent network."""
    ip: str
    port: int
    peer_id: Optional[bytes] = None
    
    def __str__(self) -> str:
        return f"{self.ip}:{self.port}"

class TrackerError(Exception):
    """Exception raised for tracker communication errors."""
    pass

class Tracker:
    """Handles communication with a BitTorrent tracker."""
    
    def __init__(self, torrent: 'Torrent'):  # type: ignore
        """
        Initialize with a Torrent object.
        
        Args:
            torrent: The Torrent instance containing tracker information
        """
        self.torrent = torrent
        self.peer_id = self._generate_peer_id()
        self.uploaded = 0
        self.downloaded = 0
        self.left = self.torrent.get_total_size()
        self.peers: List[Peer] = []
        self.interval = 1800  # Default interval in seconds
        self.min_interval = 300  # Minimum interval in seconds
        
    def _generate_peer_id(self) -> bytes:
        """Generate a unique peer ID for this client."""
        # Format: -PC0001-<random-12-chars>
        return ('-PC0001-' + ''.join(
            random.choices('0123456789abcdefghijklmnopqrstuvwxyz', k=12)
        )).encode()
    
    def _prepare_http_announce(self, event: str = '') -> Dict[str, str]:
        """Prepare parameters for HTTP tracker announce."""
        return {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': '6881',  # Default BitTorrent port
            'uploaded': str(self.uploaded),
            'downloaded': str(self.downloaded),
            'left': str(max(0, self.left)),
            'compact': '1',  # Use compact response
            'event': event or 'started',
        }
    
    def _parse_peers_compact(self, peers_data: bytes) -> List[Peer]:
        """Parse compact peer list from tracker response."""
        peers = []
        # Compact format: <IP (4 bytes)><Port (2 bytes)>
        for i in range(0, len(peers_data), 6):
            if i + 6 > len(peers_data):
                break
                
            ip_bytes = peers_data[i:i+4]
            port_bytes = peers_data[i+4:i+6]
            
            ip = '.'.join(str(b) for b in ip_bytes)
            port = struct.unpack('!H', port_bytes)[0]
            
            peers.append(Peer(ip=ip, port=port))
            
        return peers
    
    def _parse_tracker_response(self, response: Dict[str, Any]) -> None:
        """Parse tracker response and update peer list."""
        if b'failure reason' in response:
            raise TrackerError(f"Tracker error: {response[b'failure reason'].decode()}")
            
        if b'interval' in response:
            self.interval = response[b'interval']
            
        if b'min interval' in response:
            self.min_interval = response[b'min interval']
            
        if b'peers' in response:
            peers_data = response[b'peers']
            if isinstance(peers_data, list):
                # Dictionary model (non-compact)
                self.peers = [
                    Peer(ip=p[b'ip'].decode(), port=p[b'port'])
                    for p in peers_data
                ]
            else:
                # Compact model
                self.peers = self._parse_peers_compact(peers_data)
    
    def http_announce(self, event: str = '') -> List[Peer]:
        """
        Announce to the tracker and get the list of peers.
        
        Args:
            event: One of 'started', 'stopped', 'completed', or empty string
            
        Returns:
            List of Peer objects
        """
        if not self.torrent.announce:
            raise TrackerError("No announce URL in torrent")
            
        params = self._prepare_http_announce(event)
        url = f"{self.torrent.announce}?{urllib.parse.urlencode(params)}"
        
        logger.info(f"Announcing to tracker: {url}")
        
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                from bencode import bdecode
                response_data = response.read()
                decoded = bdecode(response_data)
                self._parse_tracker_response(decoded)
                return self.peers
                
        except urllib.error.URLError as e:
            raise TrackerError(f"Failed to connect to tracker: {e}")
        except Exception as e:
            raise TrackerError(f"Error in tracker communication: {e}")
    
    def udp_announce(self) -> List[Peer]:
        """
        Announce to a UDP tracker (not yet implemented).
        
        Returns:
            List of Peer objects
        """
        # TODO: Implement UDP tracker support
        raise NotImplementedError("UDP tracker support not implemented yet")
    
    def announce(self, event: str = '') -> List[Peer]:
        """
        Announce to the tracker using the appropriate protocol.
        
        Args:
            event: One of 'started', 'stopped', 'completed', or empty string
            
        Returns:
            List of Peer objects
        """
        if not self.torrent.announce:
            raise TrackerError("No announce URL in torrent")
            
        if self.torrent.announce.startswith('http'):
            return self.http_announce(event)
        elif self.torrent.announce.startswith('udp'):
            return self.udp_announce()
        else:
            raise TrackerError(f"Unsupported tracker protocol: {self.torrent.announce}")
