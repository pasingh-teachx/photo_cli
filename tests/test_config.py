"""Tests for configuration module."""

import pytest
import tempfile
from pathlib import Path
from argparse import Namespace

from photo_organizer.config import (
    OrganizerConfig,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
)


class TestOrganizerConfig:
    """Tests for OrganizerConfig class."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = OrganizerConfig()
        
        assert config.move_files is False
        assert config.dry_run is False
        assert config.skip_location is False
        assert config.default_location is None
        assert config.skip_duplicates is True
        assert config.include_images is True
        assert config.include_videos is True
        assert config.recursive is True
        assert config.verbose is False
    
    def test_default_patterns(self):
        """Test default folder and filename patterns."""
        config = OrganizerConfig()
        
        assert '{year}' in config.folder_pattern
        assert '{month' in config.folder_pattern
        assert '{year}' in config.filename_pattern
        assert '{original_name}' in config.filename_pattern
    
    def test_supported_extensions_both(self):
        """Test supported extensions with both images and videos."""
        config = OrganizerConfig(include_images=True, include_videos=True)
        
        assert '.jpg' in config.supported_extensions
        assert '.mp4' in config.supported_extensions
        assert config.supported_extensions == SUPPORTED_EXTENSIONS
    
    def test_supported_extensions_images_only(self):
        """Test supported extensions with images only."""
        config = OrganizerConfig(include_images=True, include_videos=False)
        
        assert '.jpg' in config.supported_extensions
        assert '.mp4' not in config.supported_extensions
        assert config.supported_extensions == SUPPORTED_IMAGE_EXTENSIONS
    
    def test_supported_extensions_videos_only(self):
        """Test supported extensions with videos only."""
        config = OrganizerConfig(include_images=False, include_videos=True)
        
        assert '.jpg' not in config.supported_extensions
        assert '.mp4' in config.supported_extensions
        assert config.supported_extensions == SUPPORTED_VIDEO_EXTENSIONS
    
    def test_validate_valid_config(self):
        """Test validation with valid config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = OrganizerConfig(
                source_path=Path(tmpdir),
                destination_path=Path(tmpdir) / 'output',
            )
            
            errors = config.validate()
            assert len(errors) == 0
    
    def test_validate_missing_source(self):
        """Test validation with missing source directory."""
        config = OrganizerConfig(
            source_path=Path('/nonexistent/path'),
        )
        
        errors = config.validate()
        assert len(errors) > 0
        assert any('Source path' in e for e in errors)
    
    def test_validate_invalid_latitude(self):
        """Test validation with invalid latitude."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = OrganizerConfig(
                source_path=Path(tmpdir),
                default_location=(100, 0),  # Invalid latitude
            )
            
            errors = config.validate()
            assert len(errors) > 0
            assert any('latitude' in e.lower() for e in errors)
    
    def test_validate_invalid_longitude(self):
        """Test validation with invalid longitude."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = OrganizerConfig(
                source_path=Path(tmpdir),
                default_location=(0, 200),  # Invalid longitude
            )
            
            errors = config.validate()
            assert len(errors) > 0
            assert any('longitude' in e.lower() for e in errors)
    
    def test_validate_empty_patterns(self):
        """Test validation with empty patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = OrganizerConfig(
                source_path=Path(tmpdir),
                folder_pattern='',
                filename_pattern='',
            )
            
            errors = config.validate()
            assert len(errors) >= 2
    
    def test_from_args(self):
        """Test creating config from argparse namespace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = Namespace(
                source=tmpdir,
                destination='/output',
                move=True,
                dry_run=True,
                folder_pattern='{year}/{month:02d}',
                filename_pattern='{original_name}',
                skip_location=True,
                location='37.7749,-122.4194',
                allow_duplicates=False,
                videos_only=False,
                images_only=False,
                no_recursive=False,
                verbose=True,
            )
            
            config = OrganizerConfig.from_args(args)
            
            assert config.source_path == Path(tmpdir)
            assert config.destination_path == Path('/output')
            assert config.move_files is True
            assert config.dry_run is True
            assert config.folder_pattern == '{year}/{month:02d}'
            assert config.filename_pattern == '{original_name}'
            assert config.skip_location is True
            assert config.default_location == (37.7749, -122.4194)
            assert config.verbose is True
    
    def test_from_args_invalid_location(self):
        """Test creating config with invalid location string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = Namespace(
                source=tmpdir,
                destination='/output',
                move=False,
                dry_run=False,
                folder_pattern='{year}',
                filename_pattern='{original_name}',
                skip_location=False,
                location='invalid',
                allow_duplicates=False,
                videos_only=False,
                images_only=False,
                no_recursive=False,
                verbose=False,
            )
            
            config = OrganizerConfig.from_args(args)
            
            # Invalid location should result in None
            assert config.default_location is None


class TestSupportedExtensions:
    """Tests for supported file extension constants."""
    
    def test_image_extensions_lowercase(self):
        """Test that image extensions are lowercase."""
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            assert ext == ext.lower()
            assert ext.startswith('.')
    
    def test_video_extensions_lowercase(self):
        """Test that video extensions are lowercase."""
        for ext in SUPPORTED_VIDEO_EXTENSIONS:
            assert ext == ext.lower()
            assert ext.startswith('.')
    
    def test_common_extensions_present(self):
        """Test that common extensions are present."""
        # Common image formats
        assert '.jpg' in SUPPORTED_IMAGE_EXTENSIONS
        assert '.jpeg' in SUPPORTED_IMAGE_EXTENSIONS
        assert '.png' in SUPPORTED_IMAGE_EXTENSIONS
        assert '.heic' in SUPPORTED_IMAGE_EXTENSIONS
        
        # Common video formats
        assert '.mp4' in SUPPORTED_VIDEO_EXTENSIONS
        assert '.mov' in SUPPORTED_VIDEO_EXTENSIONS
        assert '.avi' in SUPPORTED_VIDEO_EXTENSIONS
    
    def test_combined_extensions(self):
        """Test that combined set contains all extensions."""
        assert SUPPORTED_EXTENSIONS == SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS