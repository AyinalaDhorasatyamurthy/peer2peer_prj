""
Bencode encoding and decoding for BitTorrent protocol.
"""
import io
import json
from typing import Any, Dict, List, Union, BinaryIO

class BencodeDecodeError(ValueError):
    """Exception raised for errors in bencode decoding."""
    pass

def decode_int(stream: BinaryIO) -> int:
    """
    Decode a bencoded integer from the stream.
    
    Format: i<number>e
    Example: i42e -> 42
    """
    result = 0
    sign = 1
    char = stream.read(1)
    
    if char == b"-":
        sign = -1
        char = stream.read(1)
    
    while char.isdigit():
        result = result * 10 + int(char)
        char = stream.read(1)
    
    if char != b"e":
        raise BencodeDecodeError("Expected 'e' at end of integer")
    
    return sign * result

def decode_string(stream: BinaryIO) -> bytes:
    """
    Decode a bencoded string from the stream.
    
    Format: <length>:<data>
    Example: 5:hello -> b'hello'
    """
    length_str = b""
    char = stream.read(1)
    
    while char.isdigit():
        length_str += char
        char = stream.read(1)
    
    if char != b":":
        raise BencodeDecodeError("Expected ':' after string length")
    
    length = int(length_str)
    return stream.read(length)

def decode(stream: Union[BinaryIO, bytes, str]) -> Any:
    """
    Decode a bencoded value from the stream or bytes.
    
    Args:
        stream: A file-like object or bytes containing bencoded data
        
    Returns:
        The decoded Python object (int, bytes, list, or dict)
    """
    if isinstance(stream, (bytes, str)):
        if isinstance(stream, str):
            stream = stream.encode('utf-8')
        stream = io.BytesIO(stream)
    
    char = stream.read(1)
    
    if char == b"i":
        return decode_int(stream)
    elif char.isdigit():
        stream.seek(-1, 1)  # Go back one byte
        return decode_string(stream)
    elif char == b"l":
        return _decode_list(stream)
    elif char == b"d":
        return _decode_dict(stream)
    elif char == b"e":
        return None
    else:
        raise BencodeDecodeError(f"Unexpected token: {char}")

def _decode_list(stream: BinaryIO) -> List[Any]:
    """Decode a bencoded list."""
    result = []
    while True:
        value = decode(stream)
        if value is None:  # Reached end of list
            break
        result.append(value)
    return result

def _decode_dict(stream: BinaryIO) -> Dict[bytes, Any]:
    """Decode a bencoded dictionary."""
    result = {}
    while True:
        key = decode(stream)
        if key is None:  # Reached end of dict
            break
        if not isinstance(key, bytes):
            raise BencodeDecodeError("Dictionary keys must be strings")
        value = decode(stream)
        result[key] = value
    return result

def encode(obj: Any) -> bytes:
    """
    Encode a Python object to bencode format.
    
    Args:
        obj: The object to encode (int, str, bytes, list, or dict)
        
    Returns:
        The bencoded data as bytes
    """
    if isinstance(obj, int):
        return f"i{obj}e".encode()
    elif isinstance(obj, (str, bytes)):
        if isinstance(obj, str):
            obj = obj.encode('utf-8')
        return f"{len(obj)}:".encode() + obj
    elif isinstance(obj, list):
        return b"l" + b"".join(encode(item) for item in obj) + b"e"
    elif isinstance(obj, dict):
        result = [b"d"]
        for k, v in sorted(obj.items()):
            if not isinstance(k, (str, bytes)):
                raise ValueError("Dictionary keys must be strings")
            result.append(encode(k))
            result.append(encode(v))
        result.append(b"e")
        return b"".join(result)
    else:
        raise ValueError(f"Unsupported type: {type(obj)}")

def bdecode(data: Union[bytes, str]) -> Any:
    """Decode bencoded data."""
    return decode(data)

def bencode(obj: Any) -> bytes:
    """Encode an object to bencode format."""
    return encode(obj)
