"""
Duplicate detection for media files using content-based hashing.
"""

import hashlib
from pathlib import Path
from typing import Dict, Set, Optional, List, Tuple
from dataclasses import dataclass, field


@dataclass
class DuplicateInfo:
    """Information about a detected duplicate."""
    source_path: Path
    existing_path: Path
    content_hash: str


class DuplicateDetector:
    """
    Detect duplicate files based on content hash.
    
    Uses SHA-256 hashing of file contents for reliable duplicate detection.
    """
    
    def __init__(self, chunk_size: int = 65536):
        """
        Initialize the duplicate detector.
        
        Args:
            chunk_size: Size of chunks to read when hashing (default 64KB)
        """
        self.chunk_size = chunk_size
        # Map of hash -> file path for known files
        self._hash_registry: Dict[str, Path] = {}
        # Cache of filepath -> hash for efficiency
        self._hash_cache: Dict[Path, str] = {}
    
    def compute_hash(self, filepath: Path) -> str:
        """
        Compute SHA-256 hash of a file's contents.
        
        Args:
            filepath: Path to the file
        
        Returns:
            Hex string of the SHA-256 hash
        """
        # Check cache first
        filepath = filepath.resolve()
        if filepath in self._hash_cache:
            return self._hash_cache[filepath]
        
        hasher = hashlib.sha256()
        
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        
        hash_value = hasher.hexdigest()
        self._hash_cache[filepath] = hash_value
        
        return hash_value
    
    def register_file(self, filepath: Path, hash_value: Optional[str] = None) -> str:
        """
        Register a file in the duplicate registry.
        
        Args:
            filepath: Path to the file
            hash_value: Optional pre-computed hash
        
        Returns:
            The hash value of the file
        """
        filepath = filepath.resolve()
        
        if hash_value is None:
            hash_value = self.compute_hash(filepath)
        
        if hash_value not in self._hash_registry:
            self._hash_registry[hash_value] = filepath
        
        return hash_value
    
    def is_duplicate(self, filepath: Path) -> Tuple[bool, Optional[Path]]:
        """
        Check if a file is a duplicate of a registered file.
        
        Args:
            filepath: Path to check
        
        Returns:
            Tuple of (is_duplicate, existing_path_if_duplicate)
        """
        filepath = filepath.resolve()
        hash_value = self.compute_hash(filepath)
        
        if hash_value in self._hash_registry:
            existing = self._hash_registry[hash_value]
            # Don't consider it a duplicate of itself
            if existing != filepath:
                return True, existing
        
        return False, None
    
    def check_and_register(self, filepath: Path) -> Tuple[bool, Optional[Path], str]:
        """
        Check if a file is a duplicate and register it if not.
        
        Args:
            filepath: Path to check
        
        Returns:
            Tuple of (is_duplicate, existing_path_if_duplicate, hash_value)
        """
        filepath = filepath.resolve()
        hash_value = self.compute_hash(filepath)
        
        if hash_value in self._hash_registry:
            existing = self._hash_registry[hash_value]
            if existing != filepath:
                return True, existing, hash_value
        
        self._hash_registry[hash_value] = filepath
        return False, None, hash_value
    
    def scan_directory(self, directory: Path, extensions: Optional[Set[str]] = None,
                      recursive: bool = True) -> Dict[str, List[Path]]:
        """
        Scan a directory and find all duplicates.
        
        Args:
            directory: Directory to scan
            extensions: Optional set of extensions to include (e.g., {'.jpg', '.png'})
            recursive: Whether to scan recursively
        
        Returns:
            Dictionary mapping hash -> list of duplicate file paths
        """
        hash_to_files: Dict[str, List[Path]] = {}
        
        pattern = '**/*' if recursive else '*'
        
        for filepath in directory.glob(pattern):
            if not filepath.is_file():
                continue
            
            if extensions and filepath.suffix.lower() not in extensions:
                continue
            
            try:
                hash_value = self.compute_hash(filepath)
                
                if hash_value not in hash_to_files:
                    hash_to_files[hash_value] = []
                hash_to_files[hash_value].append(filepath)
                
            except (IOError, OSError) as e:
                print(f"Warning: Could not hash {filepath}: {e}")
        
        # Filter to only include actual duplicates (more than one file per hash)
        duplicates = {h: files for h, files in hash_to_files.items() if len(files) > 1}
        
        return duplicates
    
    def build_registry_from_directory(self, directory: Path, 
                                      extensions: Optional[Set[str]] = None,
                                      recursive: bool = True) -> int:
        """
        Build the hash registry from all files in a directory.
        
        Args:
            directory: Directory to scan
            extensions: Optional set of extensions to include
            recursive: Whether to scan recursively
        
        Returns:
            Number of files registered
        """
        count = 0
        pattern = '**/*' if recursive else '*'
        
        for filepath in directory.glob(pattern):
            if not filepath.is_file():
                continue
            
            if extensions and filepath.suffix.lower() not in extensions:
                continue
            
            try:
                self.register_file(filepath)
                count += 1
            except (IOError, OSError) as e:
                print(f"Warning: Could not hash {filepath}: {e}")
        
        return count
    
    def clear_registry(self):
        """Clear the hash registry."""
        self._hash_registry.clear()
    
    def clear_cache(self):
        """Clear the hash cache."""
        self._hash_cache.clear()
    
    @property
    def registry_size(self) -> int:
        """Number of files in the registry."""
        return len(self._hash_registry)
    
    @property
    def cache_size(self) -> int:
        """Number of files in the cache."""
        return len(self._hash_cache)