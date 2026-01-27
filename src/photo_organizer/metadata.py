"""
Metadata handling for EXIF/XMP operations.

Uses exiftool for reading and writing metadata to ensure all metadata is preserved.
"""

import subprocess
import json
import os
from datetime import datetime, date, time, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from dataclasses import dataclass


# Common date/time tags in order of preference
DATETIME_TAGS = [
    'EXIF:DateTimeOriginal',
    'EXIF:CreateDate',
    'EXIF:ModifyDate',
    'XMP:DateTimeOriginal',
    'XMP:CreateDate',
    'XMP:ModifyDate',
    'QuickTime:CreateDate',
    'QuickTime:ModifyDate',
    'QuickTime:MediaCreateDate',
    'QuickTime:MediaModifyDate',
    'QuickTime:TrackCreateDate',
    'QuickTime:TrackModifyDate',
]

# All possible date tags including system dates (for inference only)
ALL_DATE_TAGS = DATETIME_TAGS + [
    'File:FileModifyDate',
    'File:FileAccessDate',
    'File:FileCreateDate',  # Windows only
]

# GPS coordinate tags
GPS_TAGS = {
    'latitude': ['EXIF:GPSLatitude', 'XMP:GPSLatitude', 'Composite:GPSLatitude'],
    'longitude': ['EXIF:GPSLongitude', 'XMP:GPSLongitude', 'Composite:GPSLongitude'],
    'latitude_ref': ['EXIF:GPSLatitudeRef', 'XMP:GPSLatitudeRef'],
    'longitude_ref': ['EXIF:GPSLongitudeRef', 'XMP:GPSLongitudeRef'],
}

# Standard XMP tag for original filename - compatible with other software
# This is a commonly used tag that other tools may have already written
XMP_ORIGINAL_FILENAME = 'XMP:OriginalFileName'

# When reading with -G flag, exiftool may return different namespace prefixes
# We check multiple variants to ensure compatibility
XMP_ORIGINAL_FILENAME_READ_VARIANTS = [
    'XMP:OriginalFileName',
    'XMP-xmpMM:OriginalFileName',
    'XMP-photoOrganizer:OriginalFileName',
]

# Custom XMP tags specific to our tool - using our custom namespace
# These are defined in exiftool_config.pl with namespace 'XMP-photoOrganizer'
XMP_ALTERNATE_FILENAME = 'XMP-photoOrganizer:AlternateFileName'
XMP_DATETIME_INFERRED = 'XMP-photoOrganizer:DateTimeInferred'
XMP_DATETIME_INFERENCE_SOURCE = 'XMP-photoOrganizer:DateTimeInferenceSource'
XMP_LOCATION_MANUALLY_SET = 'XMP-photoOrganizer:LocationManuallySet'
XMP_PROCESSED_BY_VERSION = 'XMP-photoOrganizer:ProcessedByVersion'


def _get_exiftool_config_path() -> Path:
    """Get the path to the exiftool config file."""
    return Path(__file__).parent / 'exiftool_config.pl'


@dataclass
class MediaMetadata:
    """Structured metadata for a media file."""
    filepath: Path
    all_metadata: Dict[str, Any]
    
    # Parsed fields
    datetime_original: Optional[datetime] = None
    datetime_source_tag: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    original_filename: Optional[str] = None
    alternate_filename: Optional[str] = None
    datetime_inferred: bool = False
    datetime_inference_source: Optional[str] = None
    
    @property
    def has_datetime(self) -> bool:
        return self.datetime_original is not None
    
    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None
    
    @property
    def has_original_filename(self) -> bool:
        return self.original_filename is not None and self.original_filename.strip() != ''


class ExifToolWrapper:
    """Wrapper for exiftool command-line operations."""
    
    def __init__(self):
        self._check_exiftool()
        self._config_path = _get_exiftool_config_path()
    
    def _check_exiftool(self):
        """Verify exiftool is installed."""
        try:
            result = subprocess.run(
                ['exiftool', '-ver'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError("exiftool returned non-zero exit code")
        except FileNotFoundError:
            raise RuntimeError(
                "exiftool not found. Please install it:\n"
                "  Ubuntu/Debian: sudo apt-get install libimage-exiftool-perl\n"
                "  macOS: brew install exiftool\n"
                "  Windows: Download from https://exiftool.org/"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("exiftool check timed out")
    
    def _get_base_args(self) -> List[str]:
        """Get base exiftool arguments including config file."""
        args = ['exiftool']
        if self._config_path.exists():
            args.extend(['-config', str(self._config_path)])
        return args
    
    def read_metadata(self, filepath: Path) -> Dict[str, Any]:
        """Read all metadata from a file using exiftool."""
        try:
            args = self._get_base_args()
            args.extend(['-j', '-G', '-n', '-a', str(filepath)])
            
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                return {}
            
            data = json.loads(result.stdout)
            if data and len(data) > 0:
                return data[0]
            return {}
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            print(f"Warning: Could not read metadata from {filepath}: {e}")
            return {}
    
    def write_metadata(self, filepath: Path, tags: Dict[str, Any], 
                       preserve_original: bool = True) -> bool:
        """
        Write metadata tags to a file.
        
        Args:
            filepath: Path to the file
            tags: Dictionary of tag names to values
            preserve_original: If True, creates backup with _original suffix
        
        Returns:
            True if successful
        """
        if not tags:
            return True
        
        args = self._get_base_args()
        
        if not preserve_original:
            args.append('-overwrite_original')
        
        # Add each tag
        for tag, value in tags.items():
            if value is not None:
                args.append(f'-{tag}={value}')
        
        args.append(str(filepath))
        
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                print(f"Warning: exiftool write failed for {filepath}")
                print(f"  stderr: {result.stderr}")
                print(f"  stdout: {result.stdout}")
                return False
            return True
        except subprocess.TimeoutExpired:
            print(f"Warning: Timeout writing metadata to {filepath}")
            return False
    
    def copy_all_metadata(self, source: Path, destination: Path) -> bool:
        """Copy all metadata from source to destination file."""
        try:
            args = self._get_base_args()
            args.extend(['-TagsFromFile', str(source), '-all:all', 
                        '-overwrite_original', str(destination)])
            
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False


class MetadataHandler:
    """High-level metadata operations for the photo organizer."""
    
    def __init__(self):
        self.exiftool = ExifToolWrapper()
    
    @staticmethod
    def _get_tag_value(raw_metadata: Dict[str, Any], tag_variants: list) -> Optional[Any]:
        """
        Get a tag value by trying multiple possible tag names.
        
        This handles the fact that exiftool returns different tag names
        depending on flags used (e.g., with -G flag it returns full namespace).
        """
        for tag in tag_variants:
            value = raw_metadata.get(tag)
            if value is not None:
                return value
        return None
    
    def read_metadata(self, filepath: Path) -> MediaMetadata:
        """Read and parse metadata from a media file."""
        raw_metadata = self.exiftool.read_metadata(filepath)
        
        metadata = MediaMetadata(
            filepath=filepath,
            all_metadata=raw_metadata
        )
        
        # Parse datetime
        metadata.datetime_original, metadata.datetime_source_tag = self._parse_datetime(raw_metadata)
        
        # Parse GPS coordinates
        metadata.latitude, metadata.longitude = self._parse_gps(raw_metadata)
        
        # Parse XMP tags - original_filename uses standard tag (compatible with other software)
        # We check multiple variants since exiftool may return different namespace prefixes
        metadata.original_filename = self._get_tag_value(raw_metadata, XMP_ORIGINAL_FILENAME_READ_VARIANTS)
        
        # Our custom tags use our namespace directly
        metadata.alternate_filename = raw_metadata.get(XMP_ALTERNATE_FILENAME)
        
        datetime_inferred_val = raw_metadata.get(XMP_DATETIME_INFERRED)
        metadata.datetime_inferred = str(datetime_inferred_val or '').lower() == 'true'
        metadata.datetime_inference_source = raw_metadata.get(XMP_DATETIME_INFERENCE_SOURCE)
        
        return metadata
    
    def _parse_datetime(self, raw_metadata: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[str]]:
        """Parse datetime from metadata, trying multiple tags."""
        for tag in DATETIME_TAGS:
            value = raw_metadata.get(tag)
            if value:
                dt = self._parse_datetime_string(value)
                if dt:
                    return dt, tag
        return None, None
    
    def _parse_datetime_string(self, value: Any) -> Optional[datetime]:
        """Parse a datetime string in various formats."""
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return value
        
        value_str = str(value).strip()
        if not value_str or value_str == '0000:00:00 00:00:00':
            return None
        
        # Common EXIF formats
        formats = [
            '%Y:%m:%d %H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y:%m:%d %H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y/%m/%d %H:%M:%S',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value_str[:19], fmt[:len(fmt.replace('%z', '').replace('Z', ''))])
            except ValueError:
                continue
        
        return None
    
    def _parse_gps(self, raw_metadata: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        """Parse GPS coordinates from metadata."""
        lat = None
        lon = None
        
        # Try to find latitude
        for tag in GPS_TAGS['latitude']:
            value = raw_metadata.get(tag)
            if value is not None:
                try:
                    lat = float(value)
                    break
                except (ValueError, TypeError):
                    continue
        
        # Try to find longitude
        for tag in GPS_TAGS['longitude']:
            value = raw_metadata.get(tag)
            if value is not None:
                try:
                    lon = float(value)
                    break
                except (ValueError, TypeError):
                    continue
        
        # Check for reference (N/S, E/W) and adjust sign if needed
        if lat is not None:
            for tag in GPS_TAGS['latitude_ref']:
                ref = raw_metadata.get(tag)
                if ref and str(ref).upper() == 'S' and lat > 0:
                    lat = -lat
                    break
        
        if lon is not None:
            for tag in GPS_TAGS['longitude_ref']:
                ref = raw_metadata.get(tag)
                if ref and str(ref).upper() == 'W' and lon > 0:
                    lon = -lon
                    break
        
        return lat, lon
    
    def get_all_dates(self, filepath: Path) -> Dict[str, datetime]:
        """Get all available dates from metadata including system dates."""
        raw_metadata = self.exiftool.read_metadata(filepath)
        dates = {}
        
        for tag in ALL_DATE_TAGS:
            value = raw_metadata.get(tag)
            if value:
                dt = self._parse_datetime_string(value)
                if dt:
                    dates[tag] = dt
        
        return dates
    
    def find_matching_date(self, filepath: Path, target_date: date, 
                          tolerance_days: int = 2) -> Optional[Tuple[datetime, str]]:
        """
        Find a datetime in metadata that matches the target date within tolerance.
        
        Args:
            filepath: Path to the file
            target_date: The date to match
            tolerance_days: Number of days tolerance for matching
        
        Returns:
            Tuple of (datetime, source_tag) if found, None otherwise
        """
        all_dates = self.get_all_dates(filepath)
        
        for tag, dt in all_dates.items():
            days_diff = abs((dt.date() - target_date).days)
            if days_diff <= tolerance_days:
                return dt, tag
        
        return None
    
    def set_original_filename(self, filepath: Path, original_name: str,
                             current_name: Optional[str] = None,
                             dry_run: bool = False) -> bool:
        """
        Set the XMP:OriginalFileName and optionally XMP:AlternateFileName.
        
        Args:
            filepath: Path to the file
            original_name: The original filename to store
            current_name: Current filename (if different from original, store as alternate)
            dry_run: If True, don't actually write
        
        Returns:
            True if successful (or dry run)
        """
        if dry_run:
            return True
        
        tags = {XMP_ORIGINAL_FILENAME: original_name}
        
        if current_name and current_name != original_name:
            tags[XMP_ALTERNATE_FILENAME] = current_name
        
        return self.exiftool.write_metadata(filepath, tags, preserve_original=False)
    
    def set_datetime_original(self, filepath: Path, dt: datetime,
                             inferred: bool = False,
                             inference_source: Optional[str] = None,
                             dry_run: bool = False) -> bool:
        """
        Set the DateTimeOriginal metadata.
        
        Args:
            filepath: Path to the file
            dt: The datetime to set
            inferred: If True, mark as inferred
            inference_source: Source of inference (tag name or description)
            dry_run: If True, don't actually write
        
        Returns:
            True if successful (or dry run)
        """
        if dry_run:
            return True
        
        dt_str = dt.strftime('%Y:%m:%d %H:%M:%S')
        
        tags = {
            'EXIF:DateTimeOriginal': dt_str,
            'XMP:DateTimeOriginal': dt_str,
        }
        
        if inferred:
            tags[XMP_DATETIME_INFERRED] = 'true'
            if inference_source:
                tags[XMP_DATETIME_INFERENCE_SOURCE] = inference_source
        
        return self.exiftool.write_metadata(filepath, tags, preserve_original=False)
    
    def set_gps_coordinates(self, filepath: Path, latitude: float, longitude: float,
                           dry_run: bool = False) -> bool:
        """
        Set GPS coordinates in metadata.
        
        Args:
            filepath: Path to the file
            latitude: GPS latitude (-90 to 90)
            longitude: GPS longitude (-180 to 180)
            dry_run: If True, don't actually write
        
        Returns:
            True if successful (or dry run)
        """
        if dry_run:
            return True
        
        lat_ref = 'N' if latitude >= 0 else 'S'
        lon_ref = 'E' if longitude >= 0 else 'W'
        
        tags = {
            'EXIF:GPSLatitude': abs(latitude),
            'EXIF:GPSLatitudeRef': lat_ref,
            'EXIF:GPSLongitude': abs(longitude),
            'EXIF:GPSLongitudeRef': lon_ref,
            'XMP:GPSLatitude': latitude,
            'XMP:GPSLongitude': longitude,
            XMP_LOCATION_MANUALLY_SET: 'true',
        }
        
        return self.exiftool.write_metadata(filepath, tags, preserve_original=False)
    
    def set_processed_version(self, filepath: Path, version: str,
                              dry_run: bool = False) -> bool:
        """
        Set the tool version that processed this file.
        
        Args:
            filepath: Path to the file
            version: Version string of the photo-organizer tool
            dry_run: If True, don't actually write
        
        Returns:
            True if successful (or dry run)
        """
        if dry_run:
            return True
        
        tags = {XMP_PROCESSED_BY_VERSION: version}
        
        return self.exiftool.write_metadata(filepath, tags, preserve_original=False)
    
    def get_file_timestamps(self, filepath: Path) -> Tuple[float, float]:
        """
        Get the access and modification times of a file.
        
        Args:
            filepath: Path to the file
        
        Returns:
            Tuple of (access_time, modification_time) as timestamps
        """
        stat = filepath.stat()
        return (stat.st_atime, stat.st_mtime)
    
    def set_file_timestamps(self, filepath: Path, atime: float, mtime: float) -> bool:
        """
        Set the access and modification times of a file.
        
        Args:
            filepath: Path to the file
            atime: Access time as timestamp
            mtime: Modification time as timestamp
        
        Returns:
            True if successful
        """
        import os
        try:
            os.utime(filepath, (atime, mtime))
            return True
        except OSError as e:
            print(f"Warning: Could not set file timestamps for {filepath}: {e}")
            return False
    
    def copy_file_with_metadata(self, source: Path, destination: Path,
                                dry_run: bool = False) -> bool:
        """
        Copy a file and ensure all metadata is preserved.
        
        Args:
            source: Source file path
            destination: Destination file path
            dry_run: If True, don't actually copy
        
        Returns:
            True if successful (or dry run)
        """
        if dry_run:
            return True
        
        import shutil
        
        # Create destination directory if needed
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy the file (copy2 preserves metadata including timestamps)
        shutil.copy2(source, destination)
        
        return True
    
    def move_file_with_metadata(self, source: Path, destination: Path,
                               dry_run: bool = False) -> bool:
        """
        Move a file (metadata is preserved automatically).
        
        Args:
            source: Source file path  
            destination: Destination file path
            dry_run: If True, don't actually move
        
        Returns:
            True if successful (or dry run)
        """
        if dry_run:
            return True
        
        import shutil
        
        # Create destination directory if needed
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Move the file
        shutil.move(str(source), str(destination))
        
        return True