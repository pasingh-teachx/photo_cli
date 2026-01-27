"""Tests for the main organizer module."""

import pytest
import subprocess
from datetime import datetime
from pathlib import Path

from photo_organizer.organizer import PhotoOrganizer
from photo_organizer.config import OrganizerConfig


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


@requires_exiftool
class TestPhotoOrganizerPatterns:
    """Tests for pattern formatting in PhotoOrganizer."""
    
    @pytest.fixture
    def organizer(self, tmp_path):
        """Create an organizer for testing."""
        config = OrganizerConfig(
            source_path=tmp_path,
            destination_path=tmp_path / 'output',
        )
        return PhotoOrganizer(config)
    
    def test_format_pattern_basic(self, organizer):
        """Test basic pattern formatting."""
        dt = datetime(2024, 6, 15, 14, 30, 45)
        result = organizer._format_pattern(
            "{year}-{month}-{day}",
            dt, "test.jpg", ".jpg"
        )
        assert result == "2024-6-15"
    
    def test_format_pattern_zero_padded(self, organizer):
        """Test zero-padded formatting."""
        dt = datetime(2024, 1, 5, 9, 5, 3)
        result = organizer._format_pattern(
            "{year}-{month:02d}-{day:02d}_{hour:02d}-{min:02d}-{sec:02d}",
            dt, "test.jpg", ".jpg"
        )
        assert result == "2024-01-05_09-05-03"
    
    def test_format_pattern_month_names(self, organizer):
        """Test month name formatting."""
        dt = datetime(2024, 3, 15, 12, 0, 0)
        
        result_full = organizer._format_pattern(
            "{month_name}",
            dt, "test.jpg", ".jpg"
        )
        assert result_full == "March"
        
        result_short = organizer._format_pattern(
            "{month_name_short}",
            dt, "test.jpg", ".jpg"
        )
        assert result_short == "Mar"
    
    def test_format_pattern_original_name(self, organizer):
        """Test original name in pattern."""
        dt = datetime(2024, 6, 15, 14, 30, 45)
        result = organizer._format_pattern(
            "{year}-{original_name}",
            dt, "IMG_3900.jpg", ".jpg"
        )
        assert result == "2024-IMG_3900"
    
    def test_format_pattern_extension(self, organizer):
        """Test extension in pattern."""
        dt = datetime(2024, 6, 15, 14, 30, 45)
        result = organizer._format_pattern(
            "{original_name}.{ext}",
            dt, "photo.JPG", ".JPG"
        )
        assert result == "photo.jpg"  # Extension should be lowercase
    
    def test_format_pattern_default_folder(self, organizer):
        """Test default folder pattern."""
        dt = datetime(2025, 1, 15, 12, 0, 0)
        result = organizer._format_pattern(
            "{year}-{month:02d}-{month_name_short}",
            dt, "test.jpg", ".jpg"
        )
        assert result == "2025-01-Jan"
    
    def test_format_pattern_default_filename(self, organizer):
        """Test default filename pattern."""
        dt = datetime(2015, 6, 29, 16, 34, 14)
        result = organizer._format_pattern(
            "{year}-{month:02d}-{day:02d}_{hour:02d}-{min:02d}-{sec:02d}-{original_name}",
            dt, "img_3900.jpg", ".jpg"
        )
        assert result == "2015-06-29_16-34-14-img_3900"


@requires_exiftool
class TestGetDestinationPath:
    """Tests for destination path calculation."""
    
    @pytest.fixture
    def organizer(self, tmp_path):
        """Create an organizer with custom patterns."""
        config = OrganizerConfig(
            source_path=tmp_path,
            destination_path=tmp_path / 'output',
            folder_pattern="{year}-{month:02d}-{month_name_short}",
            filename_pattern="{year}-{month:02d}-{day:02d}_{hour:02d}-{min:02d}-{sec:02d}-{original_name}",
        )
        return PhotoOrganizer(config)
    
    def test_destination_path_basic(self, organizer, tmp_path):
        """Test basic destination path calculation."""
        dt = datetime(2024, 6, 15, 14, 30, 45)
        dest = organizer._get_destination_path(dt, "photo.jpg", ".jpg")
        
        expected = tmp_path / 'output' / '2024-06-Jun' / '2024-06-15_14-30-45-photo.jpg'
        assert dest == expected
    
    def test_destination_path_preserves_extension(self, organizer, tmp_path):
        """Test that extension is preserved correctly."""
        dt = datetime(2024, 6, 15, 14, 30, 45)
        dest = organizer._get_destination_path(dt, "video.MP4", ".MP4")
        
        assert dest.suffix.lower() == '.mp4'
    
    def test_destination_path_different_months(self, organizer, tmp_path):
        """Test destination paths for different months."""
        for month in range(1, 13):
            dt = datetime(2024, month, 15, 12, 0, 0)
            dest = organizer._get_destination_path(dt, "test.jpg", ".jpg")
            
            month_short = PhotoOrganizer.MONTH_NAMES_SHORT[month]
            expected_folder = f"2024-{month:02d}-{month_short}"
            assert expected_folder in str(dest)


class TestMonthNames:
    """Tests for month name constants."""
    
    def test_month_names_count(self):
        """Test correct number of month names."""
        # Index 0 is empty, so 13 total
        assert len(PhotoOrganizer.MONTH_NAMES) == 13
        assert len(PhotoOrganizer.MONTH_NAMES_SHORT) == 13
    
    def test_month_names_values(self):
        """Test month name values."""
        assert PhotoOrganizer.MONTH_NAMES[1] == 'January'
        assert PhotoOrganizer.MONTH_NAMES[12] == 'December'
        assert PhotoOrganizer.MONTH_NAMES_SHORT[1] == 'Jan'
        assert PhotoOrganizer.MONTH_NAMES_SHORT[12] == 'Dec'
    
    def test_month_names_index_zero(self):
        """Test that index 0 is empty string."""
        assert PhotoOrganizer.MONTH_NAMES[0] == ''
        assert PhotoOrganizer.MONTH_NAMES_SHORT[0] == ''