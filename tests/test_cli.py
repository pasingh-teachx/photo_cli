"""Tests for the CLI module."""

import pytest
import tempfile
from pathlib import Path

from photo_organizer.cli import create_parser, validate_location, main


class TestCreateParser:
    """Tests for argument parser creation."""
    
    @pytest.fixture
    def parser(self):
        """Create parser for testing."""
        return create_parser()
    
    def test_required_positional_args(self, parser):
        """Test that source and destination are required."""
        with pytest.raises(SystemExit):
            parser.parse_args([])
        
        with pytest.raises(SystemExit):
            parser.parse_args(['/source'])
    
    def test_basic_args(self, parser):
        """Test basic argument parsing."""
        args = parser.parse_args(['/source', '/dest'])
        
        assert args.source == '/source'
        assert args.destination == '/dest'
    
    def test_move_flag(self, parser):
        """Test --move flag."""
        args = parser.parse_args(['/source', '/dest', '--move'])
        assert args.move is True
        
        args = parser.parse_args(['/source', '/dest'])
        assert args.move is False
    
    def test_dry_run_flag(self, parser):
        """Test --dry-run flag."""
        args = parser.parse_args(['/source', '/dest', '--dry-run'])
        assert args.dry_run is True
    
    def test_location_arg(self, parser):
        """Test --location argument."""
        args = parser.parse_args(['/source', '/dest', '--location', '37.7749,-122.4194'])
        assert args.location == '37.7749,-122.4194'
    
    def test_skip_location_flag(self, parser):
        """Test --skip-location flag."""
        args = parser.parse_args(['/source', '/dest', '--skip-location'])
        assert args.skip_location is True
    
    def test_folder_pattern(self, parser):
        """Test --folder-pattern argument."""
        args = parser.parse_args(['/source', '/dest', '--folder-pattern', '{year}/{month}'])
        assert args.folder_pattern == '{year}/{month}'
    
    def test_filename_pattern(self, parser):
        """Test --filename-pattern argument."""
        args = parser.parse_args(['/source', '/dest', '--filename-pattern', '{original_name}'])
        assert args.filename_pattern == '{original_name}'
    
    def test_verbose_flag(self, parser):
        """Test -v/--verbose flag."""
        args = parser.parse_args(['/source', '/dest', '-v'])
        assert args.verbose is True
        
        args = parser.parse_args(['/source', '/dest', '--verbose'])
        assert args.verbose is True
    
    def test_images_only_flag(self, parser):
        """Test --images-only flag."""
        args = parser.parse_args(['/source', '/dest', '--images-only'])
        assert args.images_only is True
    
    def test_videos_only_flag(self, parser):
        """Test --videos-only flag."""
        args = parser.parse_args(['/source', '/dest', '--videos-only'])
        assert args.videos_only is True
    
    def test_no_recursive_flag(self, parser):
        """Test --no-recursive flag."""
        args = parser.parse_args(['/source', '/dest', '--no-recursive'])
        assert args.no_recursive is True


class TestValidateLocation:
    """Tests for location validation."""
    
    def test_valid_location(self):
        """Test valid location strings."""
        assert validate_location('37.7749,-122.4194') is True
        assert validate_location('0,0') is True
        assert validate_location('-90,-180') is True
        assert validate_location('90,180') is True
        assert validate_location('45.5,12.3') is True
    
    def test_invalid_format(self):
        """Test invalid format strings."""
        assert validate_location('invalid') is False
        assert validate_location('37.7749') is False
        assert validate_location('37.7749,-122.4194,0') is False
        assert validate_location('') is False
    
    def test_out_of_range_latitude(self):
        """Test latitude out of range."""
        assert validate_location('91,0') is False
        assert validate_location('-91,0') is False
        assert validate_location('100,0') is False
    
    def test_out_of_range_longitude(self):
        """Test longitude out of range."""
        assert validate_location('0,181') is False
        assert validate_location('0,-181') is False
        assert validate_location('0,200') is False


class TestMainFunction:
    """Tests for main CLI function."""
    
    def test_missing_source(self):
        """Test error when source doesn't exist."""
        result = main(['/nonexistent/path', '/dest'])
        assert result == 1
    
    def test_invalid_location_format(self):
        """Test error with invalid location format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = main([tmpdir, '/dest', '--location', 'invalid'])
            assert result == 1
    
    def test_mutually_exclusive_filters(self):
        """Test error with both --images-only and --videos-only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = main([tmpdir, '/dest', '--images-only', '--videos-only'])
            assert result == 1