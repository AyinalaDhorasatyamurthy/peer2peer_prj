"""
Peer communication module for the BitTorrent client.
Handles peer connections and message protocol.
"""
import asyncio
import hashlib
import logging
import struct
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple, Set

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BlockRequest:
    """Represents a requested block of data from a piece."""
    piece_index: int
    offset: int
    length: int = 2**14  # Default block size: 16KB

class PeerConnection:
    """Handles communication with a single peer."""
    
    def __init__(self, ip: str, port: int, peer_id: bytes, info_hash: bytes):
        self.ip = ip
        self.port = port
        self.peer_id = peer_id
        self.info_hash = info_hash
        self.reader = None
        self.writer = None
        self.bitfield = None
        self.am_choking = True
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False
        self.connected = False
        self.pieces_have = set()
        self.download_speed = 0
        self.upload_speed = 0

    async def connect(self) -> bool:
        """Establish connection to the peer."""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.ip, self.port)
            self.connected = True
            logger.info(f"Connected to peer {self.ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.ip}:{self.port}: {e}")
            return False

    async def perform_handshake(self) -> bool:
        """Perform BitTorrent handshake with the peer."""
        if not self.connected or not self.writer:
            return False

        try:
            handshake = (
                struct.pack("!B", 19) +  # Protocol string length
                b"BitTorrent protocol" +  # Protocol string
                bytes(8) +                # 8 reserved bytes
                self.info_hash +          # Info hash
                self.peer_id              # Our peer ID
            )
            
            self.writer.write(handshake)
            await self.writer.drain()

            response = await self.reader.readexactly(68)
            
            if (len(response) == 68 and 
                response[1:20] == b"BitTorrent protocol" and
                response[28:48] == self.info_hash):
                logger.info(f"Handshake successful with {self.ip}:{self.port}")
                return True
                
        except Exception as e:
            logger.error(f"Handshake failed with {self.ip}:{self.port}: {e}")
            
        return False

    async def send_interested(self) -> None:
        """Send interested message to peer."""
        if self.connected and self.writer:
            self.writer.write(struct.pack("!IB", 1, 2))
            await self.writer.drain()
            self.am_interested = True

    async def request_piece(self, piece_index: int, block: BlockRequest) -> Optional[bytes]:
        """Request a block of data from a piece."""
        if not self.connected or not self.writer:
            return None

        try:
            message = struct.pack(
                "!IBIII", 
                13,  # message length
                6,   # request id
                piece_index,
                block.offset,
                block.length
            )
            
            self.writer.write(message)
            await self.writer.drain()
            
            length = struct.unpack("!I", await self.reader.readexactly(4))[0]
            if length == 0:
                return None
                
            message_id = struct.unpack("!B", await self.reader.readexactly(1))[0]
            
            if message_id == 7:  # piece message
                piece = struct.unpack("!I", await self.reader.readexactly(4))[0]
                offset = struct.unpack("!I", await self.reader.readexactly(4))[0]
                data = await self.reader.readexactly(length - 9)
                return data
                
        except Exception as e:
            logger.error(f"Error requesting piece {piece_index}: {e}")
            
        return None

    async def close(self) -> None:
        """Close the connection."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            self.connected = False
            logger.info(f"Closed connection to {self.ip}:{self.port}")

class PeerManager:
    """Manages multiple peer connections."""
    
    def __init__(self, info_hash: bytes, peer_id: bytes):
        self.info_hash = info_hash
        self.peer_id = peer_id
        self.peers = {}
        self.lock = asyncio.Lock()

    async def add_peer(self, ip: str, port: int):
        """Add and connect to a new peer."""
        if (ip, port) in self.peers:
            return self.peers[(ip, port)]

        peer = PeerConnection(ip, port, self.peer_id, self.info_hash)
        if await peer.connect() and await peer.perform_handshake():
            async with self.lock:
                self.peers[(ip, port)] = peer
            return peer
        return None

    async def get_peer_for_piece(self, piece_index: int):
        """Get a peer that has the specified piece."""
        async with self.lock:
            for peer in self.peers.values():
                if piece_index in peer.pieces_have:
                    return peer
        return None

    async def close_all(self) -> None:
        """Close all peer connections."""
        async with self.lock:
            for peer in self.peers.values():
                await peer.close()
            self.peers.clear()