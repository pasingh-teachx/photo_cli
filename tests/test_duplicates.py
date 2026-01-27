"""Tests for duplicate detection and file operations."""

import pytest
import tempfile
import time
import os
import subprocess
from pathlib import Path

from photo_organizer.duplicates import DuplicateDetector


def exiftool_available():
    """Check if exiftool is available."""
    try:
        result = subprocess.run(['exiftool', '-ver'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


requires_exiftool = pytest.mark.skipif(
    not exiftool_available(),
    reason="exiftool not available"
)


@pytest.fixture
def detector():
    """Create a fresh DuplicateDetector for each test."""
    return DuplicateDetector()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestDuplicateDetector:
    """Tests for DuplicateDetector class."""
    
    def test_compute_hash_consistent(self, detector, temp_dir):
        """Test that hash computation is consistent."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")
        
        hash1 = detector.compute_hash(test_file)
        hash2 = detector.compute_hash(test_file)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length
    
    def test_compute_hash_different_content(self, detector, temp_dir):
        """Test that different content produces different hashes."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        
        file1.write_text("Content A")
        file2.write_text("Content B")
        
        hash1 = detector.compute_hash(file1)
        hash2 = detector.compute_hash(file2)
        
        assert hash1 != hash2
    
    def test_compute_hash_same_content(self, detector, temp_dir):
        """Test that same content produces same hash."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        
        file1.write_text("Same content")
        file2.write_text("Same content")
        
        assert detector.compute_hash(file1) == detector.compute_hash(file2)
    
    def test_register_file(self, detector, temp_dir):
        """Test file registration."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")
        
        hash_value = detector.register_file(test_file)
        
        assert detector.registry_size == 1
        assert len(hash_value) == 64
    
    def test_is_duplicate_not_duplicate(self, detector, temp_dir):
        """Test is_duplicate for non-duplicate files."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        
        file1.write_text("Content A")
        file2.write_text("Content B")
        
        detector.register_file(file1)
        is_dup, existing = detector.is_duplicate(file2)
        
        assert not is_dup
        assert existing is None
    
    def test_is_duplicate_is_duplicate(self, detector, temp_dir):
        """Test is_duplicate for duplicate files."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        
        file1.write_text("Same content")
        file2.write_text("Same content")
        
        detector.register_file(file1)
        is_dup, existing = detector.is_duplicate(file2)
        
        assert is_dup
        assert existing == file1.resolve()
    
    def test_is_duplicate_self(self, detector, temp_dir):
        """Test that a file is not considered duplicate of itself."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")
        
        detector.register_file(test_file)
        is_dup, existing = detector.is_duplicate(test_file)
        
        assert not is_dup
    
    def test_check_and_register(self, detector, temp_dir):
        """Test check_and_register function."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        file3 = temp_dir / "file3.txt"
        
        file1.write_text("Content A")
        file2.write_text("Content A")  # Duplicate of file1
        file3.write_text("Content B")
        
        # First file should not be duplicate and get registered
        is_dup1, existing1, hash1 = detector.check_and_register(file1)
        assert not is_dup1
        assert existing1 is None
        assert detector.registry_size == 1
        
        # Second file is duplicate
        is_dup2, existing2, hash2 = detector.check_and_register(file2)
        assert is_dup2
        assert existing2 == file1.resolve()
        assert hash1 == hash2
        
        # Third file is not duplicate
        is_dup3, existing3, hash3 = detector.check_and_register(file3)
        assert not is_dup3
        assert detector.registry_size == 2
    
    def test_scan_directory(self, detector, temp_dir):
        """Test scanning a directory for duplicates."""
        # Create some files with duplicates
        (temp_dir / "file1.txt").write_text("Unique A")
        (temp_dir / "file2.txt").write_text("Duplicate")
        (temp_dir / "file3.txt").write_text("Duplicate")
        (temp_dir / "file4.txt").write_text("Unique B")
        
        duplicates = detector.scan_directory(temp_dir)
        
        # Should find one set of duplicates
        assert len(duplicates) == 1
        
        # The duplicate set should have 2 files
        dup_files = list(duplicates.values())[0]
        assert len(dup_files) == 2
    
    def test_scan_directory_with_extensions(self, detector, temp_dir):
        """Test scanning with extension filter."""
        (temp_dir / "file1.txt").write_text("Text file")
        (temp_dir / "file2.jpg").write_text("Image file")
        (temp_dir / "file3.txt").write_text("Text file")  # Duplicate
        
        # Only scan .txt files
        duplicates = detector.scan_directory(temp_dir, extensions={'.txt'})
        
        assert len(duplicates) == 1
    
    def test_scan_directory_recursive(self, detector, temp_dir):
        """Test recursive scanning."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        
        (temp_dir / "file1.txt").write_text("Same content")
        (subdir / "file2.txt").write_text("Same content")
        
        # Recursive scan
        duplicates = detector.scan_directory(temp_dir, recursive=True)
        assert len(duplicates) == 1
        
        # Clear and test non-recursive
        detector.clear_registry()
        detector.clear_cache()
        duplicates = detector.scan_directory(temp_dir, recursive=False)
        assert len(duplicates) == 0
    
    def test_build_registry_from_directory(self, detector, temp_dir):
        """Test building registry from directory."""
        (temp_dir / "file1.txt").write_text("Content A")
        (temp_dir / "file2.txt").write_text("Content B")
        (temp_dir / "file3.txt").write_text("Content C")
        
        count = detector.build_registry_from_directory(temp_dir)
        
        assert count == 3
        assert detector.registry_size == 3
    
    def test_clear_registry(self, detector, temp_dir):
        """Test clearing the registry."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test")
        
        detector.register_file(test_file)
        assert detector.registry_size == 1
        
        detector.clear_registry()
        assert detector.registry_size == 0
    
    def test_clear_cache(self, detector, temp_dir):
        """Test clearing the cache."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test")
        
        detector.compute_hash(test_file)
        assert detector.cache_size == 1
        
        detector.clear_cache()
        assert detector.cache_size == 0
    
    def test_hash_caching(self, detector, temp_dir):
        """Test that hashes are cached."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")
        
        # First call computes and caches
        hash1 = detector.compute_hash(test_file)
        assert detector.cache_size == 1
        
        # Second call uses cache
        hash2 = detector.compute_hash(test_file)
        assert hash1 == hash2
        assert detector.cache_size == 1  # Still just one entry


@requires_exiftool
class TestIdempotentDuplicateDetection:
    """Tests for idempotent duplicate detection using XMP:OriginalFileName."""
    
    def test_processed_files_registry_building(self, tmp_path):
        """Test building processed files registry from destination with metadata."""
        from photo_organizer.organizer import PhotoOrganizer
        from photo_organizer.config import OrganizerConfig
        from photo_organizer.metadata import MetadataHandler
        
        # Create a simple destination structure with a file that has XMP:OriginalFileName
        dest = tmp_path / "dest"
        dest.mkdir()
        
        # Create a test file and set its XMP:OriginalFileName
        test_file = dest / "processed_file.txt"
        test_file.write_text("Test content for registry test")
        
        handler = MetadataHandler()
        handler.set_original_filename(test_file, "original_name.txt")
        
        # Create organizer and build registry
        config = OrganizerConfig(
            source_path=tmp_path / "source",
            destination_path=dest,
        )
        
        # Create source dir
        (tmp_path / "source").mkdir()
        
        organizer = PhotoOrganizer(config)
        count = organizer._build_processed_files_registry()
        
        # The file should be registered by its original filename
        assert "original_name.txt" in organizer._processed_files_registry
    
    def test_is_already_processed_detection(self, tmp_path):
        """Test that _is_already_processed correctly identifies processed files."""
        from photo_organizer.organizer import PhotoOrganizer
        from photo_organizer.config import OrganizerConfig
        from photo_organizer.metadata import MetadataHandler, MediaMetadata
        
        # Setup
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        
        # Create a "processed" file in destination with XMP:OriginalFileName
        processed_file = dest / "2024-01-01_12-00-00-test_photo.jpg"
        processed_file.write_text("Processed photo content")
        
        handler = MetadataHandler()
        handler.set_original_filename(processed_file, "test_photo.jpg")
        
        # Create organizer and build registry
        config = OrganizerConfig(
            source_path=source,
            destination_path=dest,
        )
        
        organizer = PhotoOrganizer(config)
        organizer._build_processed_files_registry()
        
        # Create a source file with the same original name
        source_file = source / "test_photo.jpg"
        source_file.write_text("Source photo content")
        
        # Read metadata of source file
        source_metadata = handler.read_metadata(source_file)
        
        # Check if it's detected as already processed
        is_processed, existing = organizer._is_already_processed(source_file, source_metadata)
        
        assert is_processed is True
        assert existing == processed_file
    
    def test_new_file_not_detected_as_processed(self, tmp_path):
        """Test that new files are not incorrectly detected as processed."""
        from photo_organizer.organizer import PhotoOrganizer
        from photo_organizer.config import OrganizerConfig
        from photo_organizer.metadata import MetadataHandler
        
        # Setup
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        
        # Create a "processed" file in destination
        processed_file = dest / "2024-01-01_12-00-00-old_photo.jpg"
        processed_file.write_text("Processed photo")
        
        handler = MetadataHandler()
        handler.set_original_filename(processed_file, "old_photo.jpg")
        
        # Create organizer and build registry
        config = OrganizerConfig(
            source_path=source,
            destination_path=dest,
        )
        
        organizer = PhotoOrganizer(config)
        organizer._build_processed_files_registry()
        
        # Create a NEW source file with different name
        new_source_file = source / "new_photo.jpg"
        new_source_file.write_text("New photo content")
        
        # Read metadata
        source_metadata = handler.read_metadata(new_source_file)
        
        # Check that it's NOT detected as processed
        is_processed, existing = organizer._is_already_processed(new_source_file, source_metadata)
        
        assert is_processed is False
        assert existing is None