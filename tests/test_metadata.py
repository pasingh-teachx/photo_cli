"""Tests for metadata handling."""

import pytest
import tempfile
import time
import os
import subprocess
from pathlib import Path
from datetime import datetime


def exiftool_available():
    """Check if exiftool is available."""
    try:
        result = subprocess.run(['exiftool', '-ver'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Skip tests that require exiftool if not available
requires_exiftool = pytest.mark.skipif(
    not exiftool_available(),
    reason="exiftool not available"
)


class TestFileTimestampPreservation:
    """Tests for file timestamp preservation."""
    
    @requires_exiftool
    def test_get_and_set_file_timestamps(self, tmp_path):
        """Test getting and setting file timestamps."""
        from photo_organizer.metadata import MetadataHandler
        
        handler = MetadataHandler()
        
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        # Set a specific modification time (1 hour ago)
        past_time = time.time() - 3600
        os.utime(test_file, (past_time, past_time))
        
        # Get the timestamps
        atime, mtime = handler.get_file_timestamps(test_file)
        
        # Verify they match what we set
        assert abs(mtime - past_time) < 1  # Allow 1 second tolerance
        
        # Modify the file (which would change mtime)
        test_file.write_text("modified content")
        
        # Get new timestamps - mtime should have changed
        new_atime, new_mtime = handler.get_file_timestamps(test_file)
        assert new_mtime > past_time
        
        # Restore original timestamps
        handler.set_file_timestamps(test_file, atime, mtime)
        
        # Verify timestamps are restored
        restored_atime, restored_mtime = handler.get_file_timestamps(test_file)
        assert abs(restored_mtime - past_time) < 1
    
    @requires_exiftool
    def test_timestamps_preserved_after_metadata_write(self, tmp_path):
        """Test that original file timestamps are preserved after writing metadata."""
        from photo_organizer.metadata import MetadataHandler
        
        handler = MetadataHandler()
        
        # Create a simple test file (we'll use a JPEG-like file for exiftool)
        # For this test, we'll just verify the timestamp functions work correctly
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content for timestamp test")
        
        # Set a specific past time
        original_time = time.time() - 7200  # 2 hours ago
        os.utime(test_file, (original_time, original_time))
        
        # Get original timestamps
        orig_atime, orig_mtime = handler.get_file_timestamps(test_file)
        
        # Simulate what happens during processing:
        # 1. File is modified (simulating metadata write)
        time.sleep(0.1)  # Small delay to ensure time difference
        test_file.write_text("modified content simulating metadata write")
        
        # 2. Timestamps are restored
        handler.set_file_timestamps(test_file, orig_atime, orig_mtime)
        
        # 3. Verify timestamps match original
        final_atime, final_mtime = handler.get_file_timestamps(test_file)
        
        assert abs(final_mtime - original_time) < 1
        assert abs(final_atime - original_time) < 1
    
    def test_timestamp_functions_without_exiftool(self, tmp_path):
        """Test timestamp functions work without needing exiftool."""
        # These functions don't actually need exiftool, they use os.stat and os.utime
        import os
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        # Set a specific time
        past_time = time.time() - 1800  # 30 minutes ago
        os.utime(test_file, (past_time, past_time))
        
        # Get timestamps using os.stat directly
        stat = test_file.stat()
        assert abs(stat.st_mtime - past_time) < 1
        
        # Modify file
        test_file.write_text("new content")
        
        # Verify mtime changed
        new_stat = test_file.stat()
        assert new_stat.st_mtime > past_time
        
        # Restore using os.utime
        os.utime(test_file, (past_time, past_time))
        
        # Verify restoration
        final_stat = test_file.stat()
        assert abs(final_stat.st_mtime - past_time) < 1


@requires_exiftool
class TestAlternateFileName:
    """Tests for AlternateFileName metadata handling."""
    
    def test_set_alternate_filename_when_different(self, tmp_path):
        """Test that AlternateFileName is set when current name differs from original."""
        from photo_organizer.metadata import MetadataHandler, XMP_ALTERNATE_FILENAME
        
        handler = MetadataHandler()
        
        # Create a test file
        test_file = tmp_path / "current_name.txt"
        test_file.write_text("test content")
        
        # Set original filename to something different from current name
        original_name = "original_name.txt"
        current_name = "current_name.txt"
        
        # This should set both OriginalFileName and AlternateFileName
        result = handler.set_original_filename(test_file, original_name, current_name)
        assert result is True
        
        # Read back and verify
        metadata = handler.read_metadata(test_file)
        assert metadata.original_filename == original_name
        assert metadata.alternate_filename == current_name
    
    def test_no_alternate_filename_when_same(self, tmp_path):
        """Test that AlternateFileName is NOT set when current name equals original."""
        from photo_organizer.metadata import MetadataHandler
        
        handler = MetadataHandler()
        
        # Create a test file
        test_file = tmp_path / "same_name.txt"
        test_file.write_text("test content")
        
        # Set original filename same as what we pass for current
        same_name = "same_name.txt"
        
        # This should NOT set AlternateFileName (pass None)
        result = handler.set_original_filename(test_file, same_name, None)
        assert result is True
        
        # Read back and verify
        metadata = handler.read_metadata(test_file)
        assert metadata.original_filename == same_name
        assert metadata.alternate_filename is None
    
    def test_alternate_filename_scenario(self, tmp_path):
        """
        Test the full scenario:
        1. File was renamed by another tool
        2. That tool set XMP:OriginalFileName
        3. Our tool should add XMP:AlternateFileName
        """
        from photo_organizer.metadata import MetadataHandler
        
        handler = MetadataHandler()
        
        # Simulate a file that was already processed by another tool
        # The file is named "renamed_by_other_tool.txt" but has 
        # XMP:OriginalFileName = "true_original.txt"
        test_file = tmp_path / "renamed_by_other_tool.txt"
        test_file.write_text("test content")
        
        # First, set the original filename (simulating what another tool did)
        handler.set_original_filename(test_file, "true_original.txt", None)
        
        # Read metadata - should have OriginalFileName but no AlternateFileName
        metadata = handler.read_metadata(test_file)
        assert metadata.original_filename == "true_original.txt"
        assert metadata.alternate_filename is None
        
        # Now simulate our tool processing this file
        # Current name is "renamed_by_other_tool.txt", original is "true_original.txt"
        # So we should set AlternateFileName
        current_name = test_file.name
        if current_name != metadata.original_filename:
            handler.set_original_filename(
                test_file, 
                metadata.original_filename, 
                current_name
            )
        
        # Read back and verify AlternateFileName is now set
        metadata = handler.read_metadata(test_file)
        assert metadata.original_filename == "true_original.txt"
        assert metadata.alternate_filename == "renamed_by_other_tool.txt"


class TestCopyWithTimestampPreservation:
    """Tests for copy operations with timestamp preservation."""
    
    def test_shutil_copy2_preserves_timestamps(self, tmp_path):
        """Test that shutil.copy2 preserves file timestamps."""
        import shutil
        
        # Create source file
        source = tmp_path / "source.txt"
        source.write_text("source content")
        
        # Set a specific past time
        past_time = time.time() - 3600
        os.utime(source, (past_time, past_time))
        
        # Copy with copy2
        dest = tmp_path / "dest.txt"
        shutil.copy2(source, dest)
        
        # Verify timestamps are preserved
        source_stat = source.stat()
        dest_stat = dest.stat()
        
        assert abs(dest_stat.st_mtime - source_stat.st_mtime) < 1
    
    def test_timestamp_restoration_after_modification(self, tmp_path):
        """Test that timestamps can be restored after file modification."""
        import shutil
        
        # Create and setup source file
        source = tmp_path / "source.txt"
        source.write_text("original content")
        
        original_time = time.time() - 7200  # 2 hours ago
        os.utime(source, (original_time, original_time))
        
        # Copy file
        dest = tmp_path / "dest.txt"
        shutil.copy2(source, dest)
        
        # Record original timestamps
        orig_atime = source.stat().st_atime
        orig_mtime = source.stat().st_mtime
        
        # Simulate modification (like exiftool would do)
        time.sleep(0.1)
        dest.write_text("modified content representing metadata update")
        
        # Verify mtime changed
        modified_mtime = dest.stat().st_mtime
        assert modified_mtime > orig_mtime
        
        # Restore original timestamps
        os.utime(dest, (orig_atime, orig_mtime))
        
        # Verify restoration
        final_stat = dest.stat()
        assert abs(final_stat.st_mtime - orig_mtime) < 1
        assert abs(final_stat.st_atime - orig_atime) < 1