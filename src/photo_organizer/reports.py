"""
Reporting and logging functionality for photo organizer operations.

Generates detailed logs and summary reports of import operations.
"""

import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, TextIO
from dataclasses import dataclass, field, asdict


@dataclass
class FileRecord:
    """Record of a single file's processing result."""
    source_path: str
    destination_path: Optional[str]
    status: str  # 'imported', 'skipped', 'error'
    skip_reason: Optional[str] = None
    error_message: Optional[str] = None
    original_filename: Optional[str] = None
    datetime_used: Optional[str] = None
    datetime_source: Optional[str] = None
    gps_set: bool = False
    version_set: bool = False


@dataclass  
class ImportReport:
    """Complete report of an import operation."""
    run_timestamp: str
    tool_version: str
    source_path: str
    destination_path: str
    dry_run: bool
    move_mode: bool
    folder_pattern: str
    filename_pattern: str
    
    # Statistics
    total_files: int = 0
    imported_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    
    # Detailed records
    files: List[FileRecord] = field(default_factory=list)
    
    # Skip reason breakdown
    skip_reasons: Dict[str, int] = field(default_factory=dict)
    
    def add_file(self, record: FileRecord):
        """Add a file record to the report."""
        self.files.append(record)
        self.total_files += 1
        
        if record.status == 'imported':
            self.imported_count += 1
        elif record.status == 'skipped':
            self.skipped_count += 1
            reason = record.skip_reason or 'unknown'
            self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1
        elif record.status == 'error':
            self.error_count += 1
    
    def get_imported_files(self) -> List[FileRecord]:
        """Get list of successfully imported files."""
        return [f for f in self.files if f.status == 'imported']
    
    def get_skipped_files(self) -> List[FileRecord]:
        """Get list of skipped files."""
        return [f for f in self.files if f.status == 'skipped']
    
    def get_error_files(self) -> List[FileRecord]:
        """Get list of files with errors."""
        return [f for f in self.files if f.status == 'error']


class ReportGenerator:
    """Generates reports in various formats."""
    
    def __init__(self, report: ImportReport):
        self.report = report
    
    def write_summary(self, output: TextIO):
        """Write a human-readable summary to the output stream."""
        r = self.report
        
        output.write("=" * 70 + "\n")
        output.write("PHOTO ORGANIZER IMPORT REPORT\n")
        output.write("=" * 70 + "\n\n")
        
        # Run info
        output.write(f"Run Time:        {r.run_timestamp}\n")
        output.write(f"Tool Version:    {r.tool_version}\n")
        output.write(f"Mode:            {'DRY RUN' if r.dry_run else 'LIVE'}\n")
        output.write(f"Operation:       {'Move' if r.move_mode else 'Copy'}\n\n")
        
        # Paths
        output.write(f"Source:          {r.source_path}\n")
        output.write(f"Destination:     {r.destination_path}\n")
        output.write(f"Folder Pattern:  {r.folder_pattern}\n")
        output.write(f"Filename Pattern: {r.filename_pattern}\n\n")
        
        # Statistics
        output.write("-" * 70 + "\n")
        output.write("STATISTICS\n")
        output.write("-" * 70 + "\n")
        output.write(f"Total Files Scanned:    {r.total_files}\n")
        output.write(f"Successfully Imported:  {r.imported_count}\n")
        output.write(f"Skipped:                {r.skipped_count}\n")
        output.write(f"Errors:                 {r.error_count}\n\n")
        
        # Skip reasons breakdown
        if r.skip_reasons:
            output.write("Skip Reasons:\n")
            for reason, count in sorted(r.skip_reasons.items(), key=lambda x: -x[1]):
                output.write(f"  - {reason}: {count}\n")
            output.write("\n")
        
        # Imported files
        imported = self.report.get_imported_files()
        if imported:
            output.write("-" * 70 + "\n")
            output.write(f"IMPORTED FILES ({len(imported)})\n")
            output.write("-" * 70 + "\n")
            for f in imported:
                output.write(f"\n  Source:      {f.source_path}\n")
                output.write(f"  Destination: {f.destination_path}\n")
                if f.datetime_used:
                    output.write(f"  DateTime:    {f.datetime_used} (from {f.datetime_source})\n")
                if f.gps_set:
                    output.write(f"  GPS:         Set\n")
        
        # Skipped files
        skipped = self.report.get_skipped_files()
        if skipped:
            output.write("\n" + "-" * 70 + "\n")
            output.write(f"SKIPPED FILES ({len(skipped)})\n")
            output.write("-" * 70 + "\n")
            for f in skipped:
                output.write(f"\n  Source:      {f.source_path}\n")
                output.write(f"  Reason:      {f.skip_reason}\n")
                if f.destination_path:
                    output.write(f"  Existing at: {f.destination_path}\n")
        
        # Error files
        errors = self.report.get_error_files()
        if errors:
            output.write("\n" + "-" * 70 + "\n")
            output.write(f"ERRORS ({len(errors)})\n")
            output.write("-" * 70 + "\n")
            for f in errors:
                output.write(f"\n  Source:  {f.source_path}\n")
                output.write(f"  Error:   {f.error_message}\n")
        
        output.write("\n" + "=" * 70 + "\n")
        output.write("END OF REPORT\n")
        output.write("=" * 70 + "\n")
    
    def write_json(self, output: TextIO):
        """Write report as JSON."""
        data = {
            'run_timestamp': self.report.run_timestamp,
            'tool_version': self.report.tool_version,
            'source_path': self.report.source_path,
            'destination_path': self.report.destination_path,
            'dry_run': self.report.dry_run,
            'move_mode': self.report.move_mode,
            'folder_pattern': self.report.folder_pattern,
            'filename_pattern': self.report.filename_pattern,
            'statistics': {
                'total_files': self.report.total_files,
                'imported_count': self.report.imported_count,
                'skipped_count': self.report.skipped_count,
                'error_count': self.report.error_count,
                'skip_reasons': self.report.skip_reasons,
            },
            'files': [asdict(f) for f in self.report.files]
        }
        json.dump(data, output, indent=2)
    
    def write_csv(self, output: TextIO):
        """Write file records as CSV."""
        fieldnames = [
            'status', 'source_path', 'destination_path', 
            'skip_reason', 'error_message', 'original_filename',
            'datetime_used', 'datetime_source', 'gps_set', 'version_set'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for record in self.report.files:
            writer.writerow(asdict(record))
    
    def save_all(self, output_dir: Path, base_name: Optional[str] = None):
        """
        Save report in all formats to the specified directory.
        
        Args:
            output_dir: Directory to save reports
            base_name: Base name for report files (default: timestamp-based)
        
        Returns:
            Dict of format -> filepath for generated reports
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if base_name is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = f"import_report_{timestamp}"
        
        paths = {}
        
        # Summary report (text)
        summary_path = output_dir / f"{base_name}.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            self.write_summary(f)
        paths['summary'] = summary_path
        
        # JSON report
        json_path = output_dir / f"{base_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            self.write_json(f)
        paths['json'] = json_path
        
        # CSV report
        csv_path = output_dir / f"{base_name}.csv"
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            self.write_csv(f)
        paths['csv'] = csv_path
        
        return paths


class ImportLogger:
    """
    Logger that tracks import operations in real-time.
    
    Can write to both console and log file simultaneously.
    """
    
    def __init__(self, log_file: Optional[Path] = None, verbose: bool = False):
        """
        Initialize the logger.
        
        Args:
            log_file: Optional path to log file
            verbose: If True, print verbose messages to console
        """
        self.verbose = verbose
        self.log_file = log_file
        self._file_handle: Optional[TextIO] = None
        
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            self._file_handle = open(log_file, 'w', encoding='utf-8')
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def close(self):
        """Close the log file if open."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
    
    def _write(self, message: str, console: bool = True, file: bool = True):
        """Write message to console and/or file."""
        if console:
            print(message)
        if file and self._file_handle:
            self._file_handle.write(message + '\n')
            self._file_handle.flush()
    
    def info(self, message: str):
        """Log an info message."""
        self._write(message)
    
    def verbose_info(self, message: str):
        """Log a verbose message (only shown if verbose mode is on)."""
        if self.verbose:
            self._write(message)
        elif self._file_handle:
            self._write(message, console=False, file=True)
    
    def warning(self, message: str):
        """Log a warning message."""
        self._write(f"WARNING: {message}")
    
    def error(self, message: str):
        """Log an error message."""
        self._write(f"ERROR: {message}")
    
    def file_imported(self, source: Path, destination: Path):
        """Log a successful import."""
        self.info(f"  ✓ {source.name}")
        self.verbose_info(f"    -> {destination}")
    
    def file_skipped(self, source: Path, reason: str, existing: Optional[Path] = None):
        """Log a skipped file."""
        self.info(f"  ⊘ {source.name}")
        self.info(f"    Skipped: {reason}")
        if existing:
            self.verbose_info(f"    Existing: {existing}")
    
    def file_error(self, source: Path, error: str):
        """Log a file error."""
        self.info(f"  ✗ {source.name}")
        self.info(f"    Error: {error}")
    
    def section(self, title: str):
        """Log a section header."""
        self._write(f"\n{'='*60}")
        self._write(title)
        self._write('='*60)
    
    def progress(self, current: int, total: int, filename: str):
        """Log progress."""
        self._write(f"[{current}/{total}] {filename}")
