"""
Configuration handling for Photo Organizer.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List
from pathlib import Path


# Supported media file extensions
SUPPORTED_IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.webp', '.heic', '.heif', '.raw', '.cr2', '.cr3', '.nef',
    '.arw', '.dng', '.orf', '.rw2', '.pef', '.srw'
}

SUPPORTED_VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm',
    '.m4v', '.3gp', '.3g2', '.mts', '.m2ts', '.ts'
}

SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS


@dataclass
class OrganizerConfig:
    """Configuration for the photo organizer."""

    # Source and destination paths
    source_path: Path = field(default_factory=lambda: Path('.'))
    destination_path: Path = field(default_factory=lambda: Path('./organized'))

    # Operation mode
    move_files: bool = False  # False = copy (default), True = move
    dry_run: bool = False  # Preview changes without applying
    non_interactive: bool = False  # Skip prompts for missing data
    collect_skipped: bool = True  # Collect unprocessable files in skipped folder
    
    # Folder and filename patterns
    # Default folder: 2025-01-Jan (year-month_num-month_short)
    folder_pattern: str = "{year}-{month:02d}-{month_name_short}"
    # Default filename: 2015-06-29_16-34-14-img_3900.jpg
    filename_pattern: str = "{year}-{month:02d}-{day:02d}_{hour:02d}-{min:02d}-{sec:02d}-{original_name}"
    
    # Location handling
    skip_location: bool = False  # If True, don't prompt for missing GPS
    default_location: Optional[Tuple[float, float]] = None  # (lat, lon) for batch processing
    
    # Duplicate handling
    skip_duplicates: bool = True  # Skip exact content duplicates
    
    # File type filters
    include_images: bool = True
    include_videos: bool = True
    
    # Recursive scanning
    recursive: bool = True
    
    # Verbosity
    verbose: bool = False

    # Derived properties
    @property
    def interactive(self) -> bool:
        """Whether the tool can prompt for user input."""
        return not self.dry_run and not self.non_interactive

    @property
    def supported_extensions(self) -> set:
        """Get the set of supported file extensions based on config."""
        extensions = set()
        if self.include_images:
            extensions |= SUPPORTED_IMAGE_EXTENSIONS
        if self.include_videos:
            extensions |= SUPPORTED_VIDEO_EXTENSIONS
        return extensions
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of error messages."""
        errors = []
        
        if not self.source_path.exists():
            errors.append(f"Source path does not exist: {self.source_path}")
        
        if self.default_location is not None:
            lat, lon = self.default_location
            if not (-90 <= lat <= 90):
                errors.append(f"Invalid latitude: {lat}. Must be between -90 and 90.")
            if not (-180 <= lon <= 180):
                errors.append(f"Invalid longitude: {lon}. Must be between -180 and 180.")
        
        if not self.folder_pattern:
            errors.append("Folder pattern cannot be empty")
        
        if not self.filename_pattern:
            errors.append("Filename pattern cannot be empty")
        
        return errors
    
    @classmethod
    def from_args(cls, args) -> 'OrganizerConfig':
        """Create config from argparse namespace."""
        location = None
        if hasattr(args, 'location') and args.location:
            try:
                lat, lon = map(float, args.location.split(','))
                location = (lat, lon)
            except ValueError:
                pass  # Will be caught in validation
        
        return cls(
            source_path=Path(args.source),
            destination_path=Path(args.destination),
            move_files=getattr(args, 'move', False),
            dry_run=getattr(args, 'dry_run', False),
            non_interactive=getattr(args, 'non_interactive', False),
            collect_skipped=not getattr(args, 'no_collect_skipped', False),  # Default True, flag disables
            folder_pattern=getattr(args, 'folder_pattern', cls.folder_pattern),
            filename_pattern=getattr(args, 'filename_pattern', cls.filename_pattern),
            skip_location=getattr(args, 'skip_location', False),
            default_location=location,
            skip_duplicates=not getattr(args, 'allow_duplicates', False),
            include_images=not getattr(args, 'videos_only', False),
            include_videos=not getattr(args, 'images_only', False),
            recursive=not getattr(args, 'no_recursive', False),
            verbose=getattr(args, 'verbose', False),
        )