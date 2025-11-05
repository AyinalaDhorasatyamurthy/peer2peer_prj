"""
Module for handling .torrent files and their metadata.
"""
import os
import hashlib
import logging
from typing import Dict, List, Optional, Union, TYPE_CHECKING
from dataclasses import dataclass

# Import Tracker only for type checking to avoid circular imports
if TYPE_CHECKING:
    from .tracker import Tracker

@dataclass
class FileInfo:
    """Represents a file within a multi-file torrent."""
    path: str
    length: int
    md5sum: Optional[str] = None

@dataclass
class TorrentInfo:
    """Represents the 'info' dictionary in a .torrent file."""
    name: str
    piece_length: int
    pieces: List[bytes]  # List of 20-byte SHA-1 hashes
    private: bool = False
    files: Optional[List[FileInfo]] = None  # For multi-file torrents
    length: Optional[int] = None  # For single-file torrents
    md5sum: Optional[str] = None  # For single-file torrents

class Torrent:
    """Represents a .torrent file and its metadata."""
    
    def __init__(self, torrent_path: str):
        """
        Initialize a Torrent object from a .torrent file.
        
        Args:
            torrent_path: Path to the .torrent file
        """
        self.torrent_path = os.path.abspath(torrent_path)
        self.info_hash: bytes = b''
        self.announce: str = ''
        self.announce_list: List[List[str]] = []
        self.creation_date: Optional[int] = None
        self.comment: Optional[str] = None
        self.created_by: Optional[str] = None
        self.encoding: Optional[str] = None
        self.info: Optional[TorrentInfo] = None
        
        self._load_torrent_file()
    
    def _load_torrent_file(self) -> None:
        """Load and parse the .torrent file."""
        import os
        from .bencode import bdecode
        
        if not os.path.exists(self.torrent_path):
            raise FileNotFoundError(f"Torrent file not found: {self.torrent_path}")
        
        with open(self.torrent_path, 'rb') as f:
            data = f.read()
        
        try:
            decoded = bdecode(data)
        except Exception as e:
            raise ValueError(f"Invalid .torrent file: {e}")
        
        # Parse the decoded data
        self.announce = decoded.get(b'announce', b'').decode('utf-8')
        
        # Handle announce-list (BEP-0012)
        if b'announce-list' in decoded:
            self.announce_list = [
                [url.decode('utf-8') for url in tier]
                for tier in decoded[b'announce-list']
            ]
        
        # Parse info dictionary
        if b'info' not in decoded:
            raise ValueError("Invalid .torrent file: missing 'info' dictionary")
        
        info = decoded[b'info']
        self.info_hash = hashlib.sha1(data[data.find(b'd8:infod'):data.find(b'e', data.find(b'd8:infod') + 8) + 1]).digest()
        
        # Parse common fields
        self.creation_date = decoded.get(b'creation date')
        self.comment = decoded.get(b'comment', b'').decode('utf-8') if b'comment' in decoded else None
        self.created_by = decoded.get(b'created by', b'').decode('utf-8') if b'created by' in decoded else None
        self.encoding = decoded.get(b'encoding', b'utf-8').decode('utf-8')
        
        # Parse info dictionary
        self._parse_info(info)
    
    def _parse_info(self, info: Dict[bytes, any]) -> None:
        """Parse the 'info' dictionary from the .torrent file."""
        # Common fields
        name = info[b'name'].decode('utf-8')
        piece_length = info[b'piece length']
        pieces = [info[b'pieces'][i:i+20] for i in range(0, len(info[b'pieces']), 20)]
        private = bool(info.get(b'private', 0))
        
        # Handle single-file vs multi-file
        if b'files' in info:
            # Multi-file torrent
            files = []
            for file_info in info[b'files']:
                path = os.path.join(*[p.decode('utf-8') for p in file_info[b'path']])
                length = file_info[b'length']
                md5sum = file_info.get(b'md5sum', b'').decode('utf-8') if b'md5sum' in file_info else None
                files.append(FileInfo(path=path, length=length, md5sum=md5sum))
            
            self.info = TorrentInfo(
                name=name,
                piece_length=piece_length,
                pieces=pieces,
                private=private,
                files=files
            )
        else:
            # Single-file torrent
            length = info[b'length']
            md5sum = info.get(b'md5sum', b'').decode('utf-8') if b'md5sum' in info else None
            
            self.info = TorrentInfo(
                name=name,
                piece_length=piece_length,
                pieces=pieces,
                private=private,
                length=length,
                md5sum=md5sum
            )
    
    def get_total_size(self) -> int:
        """Get the total size of all files in the torrent in bytes."""
        if not self.info:
            return 0
            
        if self.info.files:
            return sum(f.length for f in self.info.files)
        return self.info.length or 0
    
    def get_file_list(self) -> List[str]:
        """Get a list of all files in the torrent."""
        if not self.info:
            return []
            
        if self.info.files:
            return [f.path for f in self.info.files]
        return [self.info.name]
    
    def create_tracker(self) -> 'Tracker':
        """
        Create a Tracker instance for this torrent.

        Returns:
            Tracker: A new Tracker instance
        """
        from .tracker import Tracker
        return Tracker(self)

    def __str__(self) -> str:
        """String representation of the torrent."""
        return (f"Torrent: {self.info.name}\n"
                f"Size: {self.get_total_size() / (1024*1024):.2f} MB\n"
                f"Files: {len(self.get_file_list())}\n"
                f"Pieces: {len(self.info.pieces) if self.info else 0}")