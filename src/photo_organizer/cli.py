"""
Command-line interface for the Photo Organizer.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__
from .config import OrganizerConfig
from .organizer import PhotoOrganizer
from .metadata import check_exiftool_available


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog='photo-organizer',
        description='EXIF metadata-based photo and video organizer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands', required=True)

    # Import command (existing functionality)
    import_parser = subparsers.add_parser(
        'import',
        help='Import and organize photos/videos',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic import (copy mode)
  photo-organizer import /path/to/source /path/to/destination

  # Dry run - preview changes
  photo-organizer import /path/to/source /path/to/destination --dry-run

  # Move files instead of copying
  photo-organizer import /path/to/source /path/to/destination --move

  # Set GPS for batch of photos from same location
  photo-organizer import /path/to/source /path/to/destination --location "37.7749,-122.4194"

  # Skip location prompts
  photo-organizer import /path/to/source /path/to/destination --skip-location

  # Custom folder and filename patterns
  photo-organizer import /path/to/source /path/to/destination \\
    --folder-pattern "{year}/{month:02d}-{month_name}" \\
    --filename-pattern "{year}{month:02d}{day:02d}_{hour:02d}{min:02d}{sec:02d}_{original_name}"

Pattern Variables:
  {year}             - 4-digit year (2025)
  {month}            - Month number (1-12)
  {month:02d}        - Zero-padded month (01-12)
  {month_name}       - Full month name (January)
  {month_name_short} - Short month name (Jan)
  {day}              - Day of month (1-31)
  {day:02d}          - Zero-padded day (01-31)
  {hour}, {min}, {sec} - Time components
  {original_name}    - Original filename without extension
  {ext}              - File extension (lowercase)
"""
    )

    # Import command arguments
    import_parser.add_argument(
        'source',
        type=str,
        help='Source directory or file to import'
    )
    import_parser.add_argument(
        'destination',
        type=str,
        help='Destination directory for organized files'
    )
    
    # Import operation mode
    mode_group = import_parser.add_argument_group('Operation Mode')
    mode_group.add_argument(
        '--move',
        action='store_true',
        default=False,
        help='Move files instead of copying (default: copy)'
    )
    mode_group.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Preview changes without modifying files'
    )
    mode_group.add_argument(
        '--non-interactive',
        action='store_true',
        default=False,
        help='Skip user prompts for missing data (e.g., GPS, datetime)'
    )
    mode_group.add_argument(
        '--no-collect-skipped',
        action='store_true',
        default=False,
        help='Do not collect files that cannot be processed (skip them instead)'
    )
    
    # Import output patterns
    pattern_group = import_parser.add_argument_group('Output Patterns')
    pattern_group.add_argument(
        '--folder-pattern',
        type=str,
        default=OrganizerConfig.folder_pattern,
        help='Folder structure pattern (default: %(default)s)'
    )
    pattern_group.add_argument(
        '--filename-pattern',
        type=str,
        default=OrganizerConfig.filename_pattern,
        help='Filename pattern (default: %(default)s)'
    )
    
    # Import location handling
    location_group = import_parser.add_argument_group('Location Handling')
    location_group.add_argument(
        '--location',
        type=str,
        metavar='LAT,LON',
        help='Set GPS coordinates for all files (e.g., "37.7749,-122.4194")'
    )
    location_group.add_argument(
        '--skip-location',
        action='store_true',
        default=False,
        help='Skip prompting for missing GPS coordinates'
    )
    
    # Import duplicate handling
    dup_group = import_parser.add_argument_group('Duplicate Handling')
    dup_group.add_argument(
        '--allow-duplicates',
        action='store_true',
        default=False,
        help='Process files even if they are duplicates'
    )
    
    # Import reporting
    report_group = import_parser.add_argument_group('Reporting')
    report_group.add_argument(
        '--report-dir',
        type=str,
        metavar='DIR',
        help='Directory for saving reports (default: destination/reports)'
    )
    report_group.add_argument(
        '--no-report',
        action='store_true',
        default=False,
        help='Do not generate reports'
    )
    
    # Import file type filters
    filter_group = import_parser.add_argument_group('File Filters')
    filter_group.add_argument(
        '--images-only',
        action='store_true',
        default=False,
        help='Process only image files'
    )
    filter_group.add_argument(
        '--videos-only',
        action='store_true',
        default=False,
        help='Process only video files'
    )
    filter_group.add_argument(
        '--no-recursive',
        action='store_true',
        default=False,
        help='Do not scan subdirectories'
    )

    # Flatten command
    flatten_parser = subparsers.add_parser(
        'flatten',
        help='Flatten skipped folders into a single directory',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Flatten skipped folders (copy mode)
  photo-organizer flatten /path/to/skipped /path/to/destination

  # Flatten and move files
  photo-organizer flatten /path/to/skipped /path/to/destination --move

  # Dry run - preview changes
  photo-organizer flatten /path/to/skipped /path/to/destination --dry-run
"""
    )

    flatten_parser.add_argument(
        'source',
        type=str,
        help='Source directory containing skipped folders to flatten'
    )
    flatten_parser.add_argument(
        'destination',
        type=str,
        help='Destination directory for flattened files'
    )

    flatten_parser.add_argument(
        '--move',
        action='store_true',
        default=False,
        help='Move files instead of copying (default: copy)'
    )
    flatten_parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Preview changes without modifying files'
    )

    # Add verbose to both subcommands
    import_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        default=False,
        help='Enable verbose output'
    )
    flatten_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        default=False,
        help='Enable verbose output'
    )

    # General options
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )



    return parser


def validate_location(location_str: str) -> bool:
    """Validate location string format."""
    try:
        lat, lon = map(float, location_str.split(','))
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (ValueError, AttributeError):
        return False


def main(argv=None):
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Handle different commands
    if args.command == 'flatten':
        return main_flatten(args)
    elif args.command == 'import' or args.command is None:
        return main_import(args)
    else:
        parser.print_help()
        return 1


def main_import(args):
    """Handle the import command."""
    # Check if exiftool is available
    if not check_exiftool_available():
        print("Error: exiftool is not installed or not available in PATH.", file=sys.stderr)
        print("Photo Organizer requires exiftool to read and write metadata.", file=sys.stderr)
        print("Please install exiftool:", file=sys.stderr)
        print("  - Ubuntu/Debian: sudo apt-get install libimage-exiftool-perl", file=sys.stderr)
        print("  - macOS: brew install exiftool", file=sys.stderr)
        print("  - Windows: Download from https://exiftool.org/", file=sys.stderr)
        print("  - Or visit https://exiftool.org/ for installation instructions.", file=sys.stderr)
        return 1

    # Validate source exists
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: Source path does not exist: {args.source}", file=sys.stderr)
        return 1
    
    # Validate location format if provided
    if args.location and not validate_location(args.location):
        print(f"Error: Invalid location format: {args.location}", file=sys.stderr)
        print("Expected format: latitude,longitude (e.g., 37.7749,-122.4194)", file=sys.stderr)
        return 1
    
    # Validate mutually exclusive options
    if args.images_only and args.videos_only:
        print("Error: Cannot use both --images-only and --videos-only", file=sys.stderr)
        return 1
    
    # Create configuration
    try:
        config = OrganizerConfig.from_args(args)
    except Exception as e:
        print(f"Error creating configuration: {e}", file=sys.stderr)
        return 1
    
    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        return 1
    
    # Create and run organizer
    try:
        report_dir = Path(args.report_dir) if args.report_dir else None
        organizer = PhotoOrganizer(config, report_dir=report_dir)
        results, report = organizer.run(save_report=not args.no_report)
        
        # Return appropriate exit code
        if organizer.stats['errors'] > 0:
            return 1
        return 0
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main_flatten(args):
    """Handle the flatten command."""
    from .flatten import flatten_skipped_folders

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: Source path does not exist: {args.source}", file=sys.stderr)
        return 1

    destination_path = Path(args.destination)

    try:
        flatten_skipped_folders(
            source_path,
            destination_path,
            move_files=args.move,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
