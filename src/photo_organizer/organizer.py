"""
Main photo organizer logic that coordinates all modules.
"""

import re
import sys
from pathlib import Path
from datetime import datetime, date, time
from typing import Optional, List, Dict, Tuple, Any, Set
from dataclasses import dataclass

from . import __version__
from .config import OrganizerConfig, SUPPORTED_EXTENSIONS
from .metadata import MetadataHandler, MediaMetadata, XMP_ORIGINAL_FILENAME
from .duplicates import DuplicateDetector
from .whatsapp import parse_whatsapp_filename, WhatsAppDateTime
from .reports import ImportReport, FileRecord, ReportGenerator, ImportLogger


@dataclass
class ProcessingResult:
    """Result of processing a single file."""
    source_path: Path
    destination_path: Optional[Path]
    status: str  # 'success', 'skipped_duplicate', 'skipped_no_datetime', 'error', 'skipped_no_location'
    message: str
    datetime_used: Optional[datetime] = None
    datetime_source: Optional[str] = None
    original_filename: Optional[str] = None
    original_filename_set: bool = False
    location_set: bool = False
    version_set: bool = False


class PhotoOrganizer:
    """
    Main class for organizing photos and videos based on EXIF metadata.
    """
    
    # Month names for pattern formatting
    MONTH_NAMES = [
        '', 'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    MONTH_NAMES_SHORT = [
        '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ]
    
    def __init__(self, config: OrganizerConfig, report_dir: Optional[Path] = None):
        """
        Initialize the photo organizer.
        
        Args:
            config: Configuration for the organizer
            report_dir: Optional directory for saving reports (default: destination/reports)
        """
        self.config = config
        self.metadata_handler = MetadataHandler()
        self.duplicate_detector = DuplicateDetector()
        self.version = __version__
        
        # Report directory
        if report_dir:
            self.report_dir = Path(report_dir)
        else:
            self.report_dir = config.destination_path / 'reports'
        
        # Registry of already-processed files by their original filename
        # Maps original_filename -> destination_path
        self._processed_files_registry: Dict[str, Path] = {}
        
        # Statistics
        self.stats = {
            'total_files': 0,
            'processed': 0,
            'skipped_duplicate': 0,
            'skipped_no_datetime': 0,
            'skipped_no_location': 0,
            'errors': 0,
        }
    
    def _log(self, message: str, verbose_only: bool = False):
        """Print a log message."""
        if verbose_only and not self.config.verbose:
            return
        print(message)
    
    def _format_pattern(self, pattern: str, dt: datetime, original_name: str, ext: str) -> str:
        """
        Format a pattern string with datetime and filename components.
        
        Available variables:
        - {year}, {month}, {day}, {hour}, {min}, {sec}
        - {month_name}, {month_name_short}
        - {original_name}, {ext}
        """
        # Remove extension from original name if present
        original_stem = Path(original_name).stem
        
        # Build format variables
        format_vars = {
            'year': dt.year,
            'month': dt.month,
            'day': dt.day,
            'hour': dt.hour,
            'min': dt.minute,
            'sec': dt.second,
            'month_name': self.MONTH_NAMES[dt.month],
            'month_name_short': self.MONTH_NAMES_SHORT[dt.month],
            'original_name': original_stem,
            'ext': ext.lower().lstrip('.'),
        }
        
        # Handle format specifiers like {month:02d}
        result = pattern
        for key, value in format_vars.items():
            # Match both {key} and {key:format}
            result = re.sub(
                rf'\{{{key}(?::([^}}]+))?\}}',
                lambda m: format(value, m.group(1) or ''),
                result
            )
        
        return result
    
    def _get_destination_path(self, dt: datetime, original_filename: str, 
                             ext: str) -> Path:
        """
        Calculate the destination path for a file.
        
        Args:
            dt: The datetime to use for organization
            original_filename: Original filename
            ext: File extension
        
        Returns:
            Full destination path
        """
        folder = self._format_pattern(self.config.folder_pattern, dt, original_filename, ext)
        filename = self._format_pattern(self.config.filename_pattern, dt, original_filename, ext)
        
        # Ensure extension is added
        if not filename.lower().endswith(ext.lower()):
            filename = f"{filename}.{ext.lstrip('.')}"
        
        return self.config.destination_path / folder / filename
    
    def _prompt_for_location(self, filepath: Path, metadata: MediaMetadata) -> Optional[Tuple[float, float]]:
        """
        Prompt user to enter GPS coordinates for a file.
        
        Returns:
            Tuple of (latitude, longitude) or None if skipped
        """
        print(f"\nFile: {filepath.name}")
        print("No GPS coordinates found in metadata.")
        
        while True:
            response = input("Enter lat,lon (e.g., 37.7749,-122.4194) or 's' to skip this file: ").strip()
            
            if response.lower() == 's':
                return None
            
            try:
                lat, lon = map(float, response.split(','))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
                else:
                    print("Invalid coordinates. Latitude must be -90 to 90, longitude -180 to 180.")
            except ValueError:
                print("Invalid format. Please enter as: latitude,longitude (e.g., 37.7749,-122.4194)")
    
    def _prompt_for_time(self, filepath: Path, wa_datetime: WhatsAppDateTime) -> Optional[time]:
        """
        Prompt user to enter time for a WhatsApp file with date-only.
        
        Returns:
            time object or None if skipped
        """
        print(f"\nFile: {filepath.name}")
        print(f"WhatsApp file detected with date {wa_datetime.date_value} but no time.")
        print("Could not infer time from metadata.")
        
        while True:
            response = input("Enter time as HH:MM:SS (e.g., 14:30:00) or 's' to skip setting DateTimeOriginal: ").strip()
            
            if response.lower() == 's':
                return None
            
            try:
                parts = response.split(':')
                if len(parts) == 3:
                    hour, minute, second = map(int, parts)
                    return time(hour, minute, second)
                elif len(parts) == 2:
                    hour, minute = map(int, parts)
                    return time(hour, minute, 0)
                else:
                    print("Invalid format. Please enter as HH:MM:SS or HH:MM")
            except ValueError as e:
                print(f"Invalid time: {e}. Please enter as HH:MM:SS (e.g., 14:30:00)")
    
    def _handle_whatsapp_datetime(self, filepath: Path, metadata: MediaMetadata,
                                  wa_datetime: WhatsAppDateTime) -> Tuple[Optional[datetime], Optional[str], bool]:
        """
        Handle datetime extraction for WhatsApp files.
        
        Returns:
            Tuple of (datetime, source_description, is_inferred)
        """
        # If full datetime is available from filename
        if wa_datetime.time_value is not None:
            dt = datetime.combine(wa_datetime.date_value, wa_datetime.time_value)
            return dt, f"WhatsApp filename ({wa_datetime.original_pattern})", False
        
        # Date-only case: try to infer time from metadata
        match_result = self.metadata_handler.find_matching_date(
            filepath, 
            wa_datetime.date_value,
            tolerance_days=2
        )
        
        if match_result:
            matched_dt, source_tag = match_result
            # Use the matched datetime's time with the WhatsApp date
            inferred_dt = datetime.combine(wa_datetime.date_value, matched_dt.time())
            return inferred_dt, f"Inferred from {source_tag} (matched date within 2 days)", True
        
        # No match found - prompt user for time
        if not self.config.dry_run:
            user_time = self._prompt_for_time(filepath, wa_datetime)
            if user_time:
                dt = datetime.combine(wa_datetime.date_value, user_time)
                return dt, "User-provided time for WhatsApp date-only file", True
        
        # Return just the date with midnight time - but don't set DateTimeOriginal
        return None, None, False
    
    def _handle_original_filename(self, filepath: Path, metadata: MediaMetadata) -> Tuple[str, bool]:
        """
        Handle XMP:OriginalFileName tracking.
        
        Returns:
            Tuple of (original_filename_to_use, need_to_set_metadata)
        """
        current_name = filepath.name
        
        # If file already has OriginalFileName, use that
        if metadata.has_original_filename:
            original = metadata.original_filename
            
            # Check if current name differs from original (might need AlternateFileName)
            if current_name != original and current_name != metadata.alternate_filename:
                # Need to potentially update AlternateFileName
                return original, True
            
            return original, False
        
        # No OriginalFileName set - current name becomes the original
        return current_name, True
    
    def _build_processed_files_registry(self) -> int:
        """
        Build a registry of already-processed files from the destination directory.
        
        Scans the destination directory for files with XMP:OriginalFileName metadata
        and registers them so we can detect duplicates.
        
        Returns:
            Number of files registered
        """
        if not self.config.destination_path.exists():
            return 0
        
        count = 0
        extensions = self.config.supported_extensions
        
        for filepath in self.config.destination_path.glob('**/*'):
            if not filepath.is_file():
                continue
            if filepath.suffix.lower() not in extensions:
                continue
            
            try:
                # Read metadata to get XMP:OriginalFileName
                metadata = self.metadata_handler.read_metadata(filepath)
                
                if metadata.original_filename:
                    # Register by original filename
                    self._processed_files_registry[metadata.original_filename] = filepath
                    count += 1
                    
                    # Also register by alternate filename if present
                    if metadata.alternate_filename:
                        self._processed_files_registry[metadata.alternate_filename] = filepath
                        
            except Exception as e:
                self._log(f"Warning: Could not read metadata from {filepath}: {e}", verbose_only=True)
        
        return count
    
    def _is_already_processed(self, filepath: Path, metadata: MediaMetadata) -> Tuple[bool, Optional[Path]]:
        """
        Check if a file has already been processed to the destination.
        
        Uses XMP:OriginalFileName to detect if the file was previously imported.
        
        Args:
            filepath: Path to the source file
            metadata: Metadata of the source file
        
        Returns:
            Tuple of (is_duplicate, existing_destination_path)
        """
        # Determine the file's identity (what name to look up)
        if metadata.original_filename:
            # File already has an OriginalFileName - use that
            identity = metadata.original_filename
        else:
            # Use current filename as identity
            identity = filepath.name
        
        # Check if this identity exists in the processed files registry
        if identity in self._processed_files_registry:
            return True, self._processed_files_registry[identity]
        
        # Also check by current filename (in case it was processed with a different name)
        if filepath.name in self._processed_files_registry:
            return True, self._processed_files_registry[filepath.name]
        
        return False, None
    
    def scan_source_files(self) -> List[Path]:
        """
        Scan source directory for media files.
        
        Returns:
            List of file paths
        """
        source = self.config.source_path
        extensions = self.config.supported_extensions
        
        files = []
        
        if source.is_file():
            if source.suffix.lower() in extensions:
                files.append(source)
        else:
            pattern = '**/*' if self.config.recursive else '*'
            for filepath in source.glob(pattern):
                if filepath.is_file() and filepath.suffix.lower() in extensions:
                    files.append(filepath)
        
        return sorted(files)
    
    def process_file(self, filepath: Path) -> ProcessingResult:
        """
        Process a single media file.
        
        Args:
            filepath: Path to the file to process
        
        Returns:
            ProcessingResult with details of what happened
        """
        self.stats['total_files'] += 1
        
        try:
            # Read metadata
            metadata = self.metadata_handler.read_metadata(filepath)
            
            # Check if file was already processed (using XMP:OriginalFileName registry)
            # This is the primary idempotency check
            if self.config.skip_duplicates:
                is_processed, existing_dest = self._is_already_processed(filepath, metadata)
                if is_processed:
                    self.stats['skipped_duplicate'] += 1
                    return ProcessingResult(
                        source_path=filepath,
                        destination_path=existing_dest,
                        status='skipped_duplicate',
                        message=f"Already processed to {existing_dest}"
                    )
                
                # Also check for exact content duplicates within source files
                # (different files with identical content)
                is_content_dup, content_dup_source, _ = self.duplicate_detector.check_and_register(filepath)
                if is_content_dup:
                    self.stats['skipped_duplicate'] += 1
                    return ProcessingResult(
                        source_path=filepath,
                        destination_path=None,
                        status='skipped_duplicate',
                        message=f"Exact content duplicate of {content_dup_source}"
                    )
            
            # Handle original filename tracking
            original_filename, need_filename_update = self._handle_original_filename(filepath, metadata)
            
            # Determine datetime
            dt = None
            dt_source = None
            dt_inferred = False
            
            # First check if file already has datetime in metadata
            if metadata.has_datetime:
                dt = metadata.datetime_original
                dt_source = metadata.datetime_source_tag
            else:
                # Check for WhatsApp filename pattern in current filename
                wa_datetime = parse_whatsapp_filename(filepath.name)
                
                # If not found in current filename, also check XMP:OriginalFileName
                # This handles files renamed by external programs
                if not wa_datetime and metadata.original_filename:
                    wa_datetime = parse_whatsapp_filename(metadata.original_filename)
                    if wa_datetime:
                        self._log(f"  Found WhatsApp pattern in OriginalFileName: {metadata.original_filename}", verbose_only=True)
                
                if wa_datetime:
                    dt, dt_source, dt_inferred = self._handle_whatsapp_datetime(
                        filepath, metadata, wa_datetime
                    )
            
            # If still no datetime, skip the file
            if dt is None:
                self.stats['skipped_no_datetime'] += 1
                return ProcessingResult(
                    source_path=filepath,
                    destination_path=None,
                    status='skipped_no_datetime',
                    message="No datetime found in metadata or filename"
                )
            
            # Handle location requirement
            location_to_set = None
            if not metadata.has_location:
                if self.config.default_location:
                    location_to_set = self.config.default_location
                elif not self.config.skip_location:
                    if not self.config.dry_run:
                        location_to_set = self._prompt_for_location(filepath, metadata)
                        if location_to_set is None:
                            self.stats['skipped_no_location'] += 1
                            return ProcessingResult(
                                source_path=filepath,
                                destination_path=None,
                                status='skipped_no_location',
                                message="User skipped file (no location provided)"
                            )
                    else:
                        self._log(f"  [DRY RUN] Would prompt for location for: {filepath.name}")
            
            # Calculate destination path
            dest_path = self._get_destination_path(dt, original_filename, filepath.suffix)
            
            # Handle filename collision
            if dest_path.exists() and not self.config.dry_run:
                # Check if it's the same file (idempotency)
                existing_hash = self.duplicate_detector.compute_hash(dest_path)
                source_hash = self.duplicate_detector.compute_hash(filepath)
                
                if existing_hash == source_hash:
                    self.stats['skipped_duplicate'] += 1
                    return ProcessingResult(
                        source_path=filepath,
                        destination_path=dest_path,
                        status='skipped_duplicate',
                        message=f"Already exists at destination (same content)"
                    )
                else:
                    # Different content, need unique name
                    counter = 1
                    base_dest = dest_path
                    while dest_path.exists():
                        stem = base_dest.stem
                        suffix = base_dest.suffix
                        dest_path = base_dest.parent / f"{stem}_{counter}{suffix}"
                        counter += 1
            
            # Perform the operation
            version_set = False
            if self.config.dry_run:
                action = "Would move" if self.config.move_files else "Would copy"
                self._log(f"  [DRY RUN] {action}: {filepath}")
                self._log(f"            To: {dest_path}")
                if need_filename_update:
                    self._log(f"            Set OriginalFileName: {original_filename}")
                if not metadata.has_datetime and dt_source:
                    self._log(f"            Set DateTimeOriginal: {dt} (from {dt_source})")
                if location_to_set:
                    self._log(f"            Set GPS: {location_to_set}")
                self._log(f"            Set Version: {self.version}")
            else:
                # Save original file timestamps before any operations
                # We want to preserve these even after metadata modifications
                original_atime, original_mtime = self.metadata_handler.get_file_timestamps(filepath)
                
                # Create a working copy or move the file
                if self.config.move_files:
                    success = self.metadata_handler.move_file_with_metadata(filepath, dest_path)
                else:
                    success = self.metadata_handler.copy_file_with_metadata(filepath, dest_path)
                
                if not success:
                    self.stats['errors'] += 1
                    return ProcessingResult(
                        source_path=filepath,
                        destination_path=None,
                        status='error',
                        message="Failed to copy/move file"
                    )
                
                # Update metadata on the destination file
                working_file = dest_path
                
                # Set OriginalFileName and AlternateFileName if needed
                if need_filename_update:
                    current_name = filepath.name
                    self.metadata_handler.set_original_filename(
                        working_file,
                        original_filename,
                        current_name if current_name != original_filename else None
                    )
                
                # Set DateTimeOriginal if it wasn't in metadata
                if not metadata.has_datetime and dt:
                    self.metadata_handler.set_datetime_original(
                        working_file, dt,
                        inferred=dt_inferred,
                        inference_source=dt_source
                    )
                
                # Set GPS coordinates if needed
                if location_to_set:
                    self.metadata_handler.set_gps_coordinates(
                        working_file,
                        location_to_set[0],
                        location_to_set[1]
                    )
                
                # Set the tool version that processed this file
                self.metadata_handler.set_processed_version(working_file, self.version)
                version_set = True
                
                # Restore original file timestamps after all metadata operations
                # This ensures FileModifyDate matches the original file
                self.metadata_handler.set_file_timestamps(working_file, original_atime, original_mtime)
                
                # Register the processed file in our registry for idempotency
                # This prevents re-processing the same file within the same run
                self._processed_files_registry[original_filename] = working_file
                if filepath.name != original_filename:
                    self._processed_files_registry[filepath.name] = working_file
            
            self.stats['processed'] += 1
            
            return ProcessingResult(
                source_path=filepath,
                destination_path=dest_path,
                status='success',
                message="Processed successfully",
                datetime_used=dt,
                datetime_source=dt_source,
                original_filename=original_filename,
                original_filename_set=need_filename_update,
                location_set=location_to_set is not None,
                version_set=version_set
            )
            
        except Exception as e:
            self.stats['errors'] += 1
            return ProcessingResult(
                source_path=filepath,
                destination_path=None,
                status='error',
                message=f"Error: {str(e)}"
            )
    
    def _result_to_file_record(self, result: ProcessingResult) -> FileRecord:
        """Convert a ProcessingResult to a FileRecord for reporting."""
        # Map status to report status
        if result.status == 'success':
            status = 'imported'
            skip_reason = None
            error_message = None
        elif result.status.startswith('skipped'):
            status = 'skipped'
            # Extract skip reason from status
            skip_reasons_map = {
                'skipped_duplicate': 'duplicate',
                'skipped_no_datetime': 'no datetime in metadata or filename',
                'skipped_no_location': 'no GPS location provided',
            }
            skip_reason = skip_reasons_map.get(result.status, result.message)
            error_message = None
        else:  # error
            status = 'error'
            skip_reason = None
            error_message = result.message
        
        return FileRecord(
            source_path=str(result.source_path.absolute()),
            destination_path=str(result.destination_path.absolute()) if result.destination_path else None,
            status=status,
            skip_reason=skip_reason,
            error_message=error_message,
            original_filename=result.original_filename,
            datetime_used=result.datetime_used.isoformat() if result.datetime_used else None,
            datetime_source=result.datetime_source,
            gps_set=result.location_set,
            version_set=result.version_set,
        )
    
    def run(self, save_report: bool = True) -> Tuple[List[ProcessingResult], Optional[ImportReport]]:
        """
        Run the full organization process.
        
        Args:
            save_report: If True, save reports to report_dir
        
        Returns:
            Tuple of (list of ProcessingResult, ImportReport or None)
        """
        # Validate configuration
        errors = self.config.validate()
        if errors:
            for error in errors:
                print(f"Configuration error: {error}")
            return [], None
        
        # Initialize report
        report = ImportReport(
            run_timestamp=datetime.now().isoformat(),
            tool_version=self.version,
            source_path=str(self.config.source_path.absolute()),
            destination_path=str(self.config.destination_path.absolute()),
            dry_run=self.config.dry_run,
            move_mode=self.config.move_files,
            folder_pattern=self.config.folder_pattern,
            filename_pattern=self.config.filename_pattern,
        )
        
        # Set up logging
        log_file = None
        if save_report and not self.config.dry_run:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = self.report_dir / f"import_{timestamp}.log"
        
        with ImportLogger(log_file=log_file, verbose=self.config.verbose) as logger:
            # Print operation mode
            mode = "DRY RUN - " if self.config.dry_run else ""
            action = "Moving" if self.config.move_files else "Copying"
            logger.info(f"\n{mode}{action} files from {self.config.source_path} to {self.config.destination_path}")
            logger.info(f"Tool version: {self.version}")
            logger.info(f"Folder pattern: {self.config.folder_pattern}")
            logger.info(f"Filename pattern: {self.config.filename_pattern}")
            logger.info("")
            
            # Build registry of already-processed files from destination
            # This uses XMP:OriginalFileName for idempotent duplicate detection
            if self.config.destination_path.exists():
                logger.verbose_info("Building processed files registry from destination...")
                count = self._build_processed_files_registry()
                logger.verbose_info(f"Found {count} previously processed files")
            
            # Scan source files
            files = self.scan_source_files()
            logger.info(f"Found {len(files)} media files to process\n")
            
            if not files:
                logger.info("No files to process.")
                return [], report
            
            # Process each file
            results = []
            for i, filepath in enumerate(files, 1):
                logger.progress(i, len(files), filepath.name)
                result = self.process_file(filepath)
                results.append(result)
                
                # Add to report
                file_record = self._result_to_file_record(result)
                report.add_file(file_record)
                
                # Log result
                if result.status == 'success':
                    logger.file_imported(filepath, result.destination_path)
                elif result.status.startswith('skipped'):
                    logger.file_skipped(filepath, result.message, result.destination_path)
                elif result.status == 'error':
                    logger.file_error(filepath, result.message)
            
            # Print summary
            logger.section("Summary")
            logger.info(f"  Total files scanned: {self.stats['total_files']}")
            logger.info(f"  Successfully processed: {self.stats['processed']}")
            logger.info(f"  Skipped (duplicates): {self.stats['skipped_duplicate']}")
            logger.info(f"  Skipped (no datetime): {self.stats['skipped_no_datetime']}")
            logger.info(f"  Skipped (no location): {self.stats['skipped_no_location']}")
            logger.info(f"  Errors: {self.stats['errors']}")
            
            if self.config.dry_run:
                logger.info("\n[DRY RUN] No files were actually modified.")
        
        # Save reports
        if save_report and not self.config.dry_run and results:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_gen = ReportGenerator(report)
            report_paths = report_gen.save_all(self.report_dir, f"import_{timestamp}")
            
            print(f"\nReports saved to: {self.report_dir}")
            for fmt, path in report_paths.items():
                print(f"  - {path.name}")
        
        return results, report