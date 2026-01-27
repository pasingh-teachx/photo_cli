"""Tests for WhatsApp filename parsing."""

import pytest
from datetime import date, time

from photo_organizer.whatsapp import (
    parse_whatsapp_filename,
    is_whatsapp_file,
    format_whatsapp_datetime,
    get_whatsapp_media_type,
)


class TestParseWhatsAppFilename:
    """Tests for parse_whatsapp_filename function."""
    
    def test_full_datetime_image_am(self):
        """Test parsing WhatsApp Image with full datetime (AM)."""
        result = parse_whatsapp_filename("WhatsApp Image 2024-10-01 at 10.06.47 AM.jpeg")
        
        assert result is not None
        assert result.date_value == date(2024, 10, 1)
        assert result.time_value == time(10, 6, 47)
        assert result.pattern_type == 'full'
    
    def test_full_datetime_video_pm(self):
        """Test parsing WhatsApp Video with full datetime (PM)."""
        result = parse_whatsapp_filename("WhatsApp Video 2025-02-03 at 2.38.55 PM.mp4")
        
        assert result is not None
        assert result.date_value == date(2025, 2, 3)
        assert result.time_value == time(14, 38, 55)  # 2 PM = 14:00
        assert result.pattern_type == 'full'
    
    def test_full_datetime_12_am(self):
        """Test parsing midnight (12 AM)."""
        result = parse_whatsapp_filename("WhatsApp Image 2024-01-15 at 12.30.00 AM.jpeg")
        
        assert result is not None
        assert result.time_value == time(0, 30, 0)  # 12 AM = 00:00
    
    def test_full_datetime_12_pm(self):
        """Test parsing noon (12 PM)."""
        result = parse_whatsapp_filename("WhatsApp Image 2024-01-15 at 12.30.00 PM.jpeg")
        
        assert result is not None
        assert result.time_value == time(12, 30, 0)
    
    def test_full_datetime_no_ampm(self):
        """Test parsing without AM/PM (24-hour format)."""
        result = parse_whatsapp_filename("WhatsApp Image 2024-10-01 at 14.30.45.jpeg")
        
        assert result is not None
        assert result.time_value == time(14, 30, 45)
    
    def test_date_only_img_dash(self):
        """Test parsing IMG-YYYYMMDD-WA format."""
        result = parse_whatsapp_filename("IMG-20241001-WA0001.jpg")
        
        assert result is not None
        assert result.date_value == date(2024, 10, 1)
        assert result.time_value is None
        assert result.pattern_type == 'date_only'
    
    def test_date_only_vid_dash(self):
        """Test parsing VID-YYYYMMDD-WA format."""
        result = parse_whatsapp_filename("VID-20241001-WA0001.mp4")
        
        assert result is not None
        assert result.date_value == date(2024, 10, 1)
        assert result.time_value is None
        assert result.pattern_type == 'date_only'
    
    def test_date_only_img_underscore(self):
        """Test parsing IMG_YYYYMMDD_WA format."""
        result = parse_whatsapp_filename("IMG_20241001_WA0001.jpg")
        
        assert result is not None
        assert result.date_value == date(2024, 10, 1)
        assert result.time_value is None
    
    def test_date_only_vid_underscore(self):
        """Test parsing VID_YYYYMMDD_WA format."""
        result = parse_whatsapp_filename("VID_20241001_WA0001.mp4")
        
        assert result is not None
        assert result.date_value == date(2024, 10, 1)
        assert result.time_value is None
    
    def test_case_insensitive(self):
        """Test case insensitivity."""
        result1 = parse_whatsapp_filename("WHATSAPP IMAGE 2024-10-01 at 10.06.47 AM.jpeg")
        result2 = parse_whatsapp_filename("whatsapp image 2024-10-01 at 10.06.47 am.jpeg")
        result3 = parse_whatsapp_filename("img-20241001-wa0001.jpg")
        
        assert result1 is not None
        assert result2 is not None
        assert result3 is not None
    
    def test_non_whatsapp_file(self):
        """Test non-WhatsApp files return None."""
        assert parse_whatsapp_filename("IMG_3900.jpg") is None
        assert parse_whatsapp_filename("photo.jpg") is None
        assert parse_whatsapp_filename("2024-10-01_image.jpg") is None
    
    def test_with_path(self):
        """Test parsing filenames with paths."""
        result = parse_whatsapp_filename("/home/user/photos/IMG-20241001-WA0001.jpg")
        
        assert result is not None
        assert result.date_value == date(2024, 10, 1)


class TestIsWhatsAppFile:
    """Tests for is_whatsapp_file function."""
    
    def test_whatsapp_files(self):
        """Test detection of WhatsApp files."""
        assert is_whatsapp_file("WhatsApp Image 2024-10-01 at 10.06.47 AM.jpeg")
        assert is_whatsapp_file("WhatsApp Video 2025-02-03 at 2.38.55 PM.mp4")
        assert is_whatsapp_file("IMG-20241001-WA0001.jpg")
        assert is_whatsapp_file("VID-20241001-WA0001.mp4")
    
    def test_non_whatsapp_files(self):
        """Test non-WhatsApp files."""
        assert not is_whatsapp_file("IMG_3900.jpg")
        assert not is_whatsapp_file("photo.jpg")


class TestFormatWhatsAppDatetime:
    """Tests for format_whatsapp_datetime function."""
    
    def test_with_full_datetime(self):
        """Test formatting with full datetime."""
        wa_dt = parse_whatsapp_filename("WhatsApp Image 2024-10-01 at 10.06.47 AM.jpeg")
        dt = format_whatsapp_datetime(wa_dt)
        
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 10
        assert dt.day == 1
        assert dt.hour == 10
        assert dt.minute == 6
        assert dt.second == 47
    
    def test_date_only_with_inferred_time(self):
        """Test formatting date-only with inferred time."""
        wa_dt = parse_whatsapp_filename("IMG-20241001-WA0001.jpg")
        inferred = time(14, 30, 0)
        dt = format_whatsapp_datetime(wa_dt, inferred_time=inferred)
        
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 10
        assert dt.day == 1
        assert dt.hour == 14
        assert dt.minute == 30
    
    def test_date_only_without_inferred_time(self):
        """Test formatting date-only without inferred time returns None."""
        wa_dt = parse_whatsapp_filename("IMG-20241001-WA0001.jpg")
        dt = format_whatsapp_datetime(wa_dt)
        
        assert dt is None


class TestGetWhatsAppMediaType:
    """Tests for get_whatsapp_media_type function."""
    
    def test_image_types(self):
        """Test image detection."""
        assert get_whatsapp_media_type("WhatsApp Image 2024-10-01 at 10.06.47 AM.jpeg") == 'image'
        assert get_whatsapp_media_type("IMG-20241001-WA0001.jpg") == 'image'
        assert get_whatsapp_media_type("IMG_20241001_WA0001.jpg") == 'image'
    
    def test_video_types(self):
        """Test video detection."""
        assert get_whatsapp_media_type("WhatsApp Video 2025-02-03 at 2.38.55 PM.mp4") == 'video'
        assert get_whatsapp_media_type("VID-20241001-WA0001.mp4") == 'video'
        assert get_whatsapp_media_type("VID_20241001_WA0001.mp4") == 'video'
    
    def test_non_whatsapp(self):
        """Test non-WhatsApp files return None."""
        assert get_whatsapp_media_type("photo.jpg") is None
        assert get_whatsapp_media_type("video.mp4") is None


class TestRenamedWhatsAppFiles:
    """Tests for WhatsApp files that have been renamed by external programs."""
    
    def test_renamed_whatsapp_file_not_recognized_by_current_name(self):
        """Test that renamed WhatsApp files are not recognized by current filename."""
        # A file renamed from IMG-20180215-WA0000.jpg to include date prefix
        renamed_filename = "2018-02-15_14-26-26-img-20180215-wa0000.jpg"
        
        # Should NOT be recognized as WhatsApp by current name
        result = parse_whatsapp_filename(renamed_filename)
        assert result is None
    
    def test_original_whatsapp_name_still_parseable(self):
        """Test that the original WhatsApp filename can still be parsed."""
        original_filename = "IMG-20180215-WA0000.jpg"
        
        result = parse_whatsapp_filename(original_filename)
        assert result is not None
        assert result.date_value == date(2018, 2, 15)
        assert result.pattern_type == 'date_only'
    
    def test_whatsapp_pattern_variants(self):
        """Test various WhatsApp filename patterns."""
        # Standard WhatsApp patterns
        assert parse_whatsapp_filename("IMG-20241001-WA0001.jpg") is not None
        assert parse_whatsapp_filename("VID-20241001-WA0001.mp4") is not None
        assert parse_whatsapp_filename("IMG_20241001_WA0001.jpg") is not None
        
        # Renamed patterns (should NOT match)
        assert parse_whatsapp_filename("2024-10-01_12-00-00-IMG-20241001-WA0001.jpg") is None
        assert parse_whatsapp_filename("photo_IMG-20241001-WA0001.jpg") is None