"""
Tests for the reporting module.
"""

import pytest
import json
import csv
import io
import tempfile
from pathlib import Path
from datetime import datetime

from photo_organizer.reports import (
    FileRecord, ImportReport, ReportGenerator, ImportLogger
)


class TestFileRecord:
    """Tests for FileRecord dataclass."""
    
    def test_create_imported_record(self):
        """Test creating a record for an imported file."""
        record = FileRecord(
            source_path='/source/photo.jpg',
            destination_path='/dest/2025/01/photo.jpg',
            status='imported',
            original_filename='photo.jpg',
            datetime_used='2025-01-15T14:30:00',
            datetime_source='EXIF:DateTimeOriginal',
            gps_set=False,
            version_set=True,
        )
        assert record.status == 'imported'
        assert record.skip_reason is None
        assert record.error_message is None
    
    def test_create_skipped_record(self):
        """Test creating a record for a skipped file."""
        record = FileRecord(
            source_path='/source/photo.jpg',
            destination_path='/dest/existing.jpg',
            status='skipped',
            skip_reason='duplicate',
        )
        assert record.status == 'skipped'
        assert record.skip_reason == 'duplicate'
    
    def test_create_error_record(self):
        """Test creating a record for a file with error."""
        record = FileRecord(
            source_path='/source/photo.jpg',
            destination_path=None,
            status='error',
            error_message='Permission denied',
        )
        assert record.status == 'error'
        assert record.error_message == 'Permission denied'


class TestImportReport:
    """Tests for ImportReport dataclass."""
    
    def test_empty_report(self):
        """Test creating an empty report."""
        report = ImportReport(
            run_timestamp='2025-01-15T14:30:00',
            tool_version='1.0.0',
            source_path='/source',
            destination_path='/dest',
            dry_run=False,
            move_mode=False,
            folder_pattern='{year}/{month:02d}',
            filename_pattern='{original_name}',
        )
        
        assert report.total_files == 0
        assert report.imported_count == 0
        assert report.skipped_count == 0
        assert report.error_count == 0
    
    def test_add_imported_file(self):
        """Test adding an imported file to the report."""
        report = ImportReport(
            run_timestamp='2025-01-15T14:30:00',
            tool_version='1.0.0',
            source_path='/source',
            destination_path='/dest',
            dry_run=False,
            move_mode=False,
            folder_pattern='{year}/{month:02d}',
            filename_pattern='{original_name}',
        )
        
        record = FileRecord(
            source_path='/source/photo.jpg',
            destination_path='/dest/2025/01/photo.jpg',
            status='imported',
        )
        report.add_file(record)
        
        assert report.total_files == 1
        assert report.imported_count == 1
        assert report.skipped_count == 0
    
    def test_add_skipped_file(self):
        """Test adding a skipped file to the report."""
        report = ImportReport(
            run_timestamp='2025-01-15T14:30:00',
            tool_version='1.0.0',
            source_path='/source',
            destination_path='/dest',
            dry_run=False,
            move_mode=False,
            folder_pattern='{year}/{month:02d}',
            filename_pattern='{original_name}',
        )
        
        record = FileRecord(
            source_path='/source/photo.jpg',
            destination_path=None,
            status='skipped',
            skip_reason='no datetime',
        )
        report.add_file(record)
        
        assert report.total_files == 1
        assert report.skipped_count == 1
        assert report.skip_reasons['no datetime'] == 1
    
    def test_skip_reasons_breakdown(self):
        """Test that skip reasons are tracked separately."""
        report = ImportReport(
            run_timestamp='2025-01-15T14:30:00',
            tool_version='1.0.0',
            source_path='/source',
            destination_path='/dest',
            dry_run=False,
            move_mode=False,
            folder_pattern='{year}/{month:02d}',
            filename_pattern='{original_name}',
        )
        
        # Add files with different skip reasons
        for _ in range(3):
            report.add_file(FileRecord(
                source_path='/source/photo.jpg',
                destination_path=None,
                status='skipped',
                skip_reason='duplicate',
            ))
        
        for _ in range(2):
            report.add_file(FileRecord(
                source_path='/source/photo.jpg',
                destination_path=None,
                status='skipped',
                skip_reason='no datetime',
            ))
        
        assert report.skip_reasons['duplicate'] == 3
        assert report.skip_reasons['no datetime'] == 2
    
    def test_get_filtered_files(self):
        """Test getting files by status."""
        report = ImportReport(
            run_timestamp='2025-01-15T14:30:00',
            tool_version='1.0.0',
            source_path='/source',
            destination_path='/dest',
            dry_run=False,
            move_mode=False,
            folder_pattern='{year}/{month:02d}',
            filename_pattern='{original_name}',
        )
        
        report.add_file(FileRecord(source_path='/s/a.jpg', destination_path='/d/a.jpg', status='imported'))
        report.add_file(FileRecord(source_path='/s/b.jpg', destination_path=None, status='skipped', skip_reason='dup'))
        report.add_file(FileRecord(source_path='/s/c.jpg', destination_path='/d/c.jpg', status='imported'))
        report.add_file(FileRecord(source_path='/s/d.jpg', destination_path=None, status='error', error_message='fail'))
        
        assert len(report.get_imported_files()) == 2
        assert len(report.get_skipped_files()) == 1
        assert len(report.get_error_files()) == 1


class TestReportGenerator:
    """Tests for ReportGenerator."""
    
    @pytest.fixture
    def sample_report(self):
        """Create a sample report for testing."""
        report = ImportReport(
            run_timestamp='2025-01-15T14:30:00',
            tool_version='1.0.0',
            source_path='/source',
            destination_path='/dest',
            dry_run=False,
            move_mode=False,
            folder_pattern='{year}/{month:02d}',
            filename_pattern='{original_name}',
        )
        
        report.add_file(FileRecord(
            source_path='/source/photo1.jpg',
            destination_path='/dest/2025/01/photo1.jpg',
            status='imported',
            datetime_used='2025-01-15T14:30:00',
            datetime_source='EXIF:DateTimeOriginal',
        ))
        report.add_file(FileRecord(
            source_path='/source/photo2.jpg',
            destination_path='/dest/existing.jpg',
            status='skipped',
            skip_reason='duplicate',
        ))
        report.add_file(FileRecord(
            source_path='/source/photo3.jpg',
            destination_path=None,
            status='error',
            error_message='Read error',
        ))
        
        return report
    
    def test_write_summary(self, sample_report):
        """Test generating summary report."""
        gen = ReportGenerator(sample_report)
        output = io.StringIO()
        gen.write_summary(output)
        
        content = output.getvalue()
        assert 'PHOTO ORGANIZER IMPORT REPORT' in content
        assert '1.0.0' in content
        assert 'Total Files Scanned:    3' in content
        assert 'Successfully Imported:  1' in content
        assert 'Skipped:                1' in content
        assert 'Errors:                 1' in content
        assert 'duplicate' in content
    
    def test_write_json(self, sample_report):
        """Test generating JSON report."""
        gen = ReportGenerator(sample_report)
        output = io.StringIO()
        gen.write_json(output)
        
        data = json.loads(output.getvalue())
        assert data['tool_version'] == '1.0.0'
        assert data['statistics']['total_files'] == 3
        assert data['statistics']['imported_count'] == 1
        assert len(data['files']) == 3
    
    def test_write_csv(self, sample_report):
        """Test generating CSV report."""
        gen = ReportGenerator(sample_report)
        output = io.StringIO()
        gen.write_csv(output)
        
        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)
        
        assert len(rows) == 3
        assert rows[0]['status'] == 'imported'
        assert rows[1]['status'] == 'skipped'
        assert rows[2]['status'] == 'error'
    
    def test_save_all(self, sample_report):
        """Test saving all report formats."""
        gen = ReportGenerator(sample_report)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = gen.save_all(Path(tmpdir), 'test_report')
            
            assert (Path(tmpdir) / 'test_report.txt').exists()
            assert (Path(tmpdir) / 'test_report.json').exists()
            assert (Path(tmpdir) / 'test_report.csv').exists()
            
            assert 'summary' in paths
            assert 'json' in paths
            assert 'csv' in paths


class TestImportLogger:
    """Tests for ImportLogger."""
    
    def test_logger_to_console_only(self, capsys):
        """Test logger output to console."""
        with ImportLogger(verbose=True) as logger:
            logger.info("Test message")
            logger.verbose_info("Verbose message")
        
        captured = capsys.readouterr()
        assert "Test message" in captured.out
        assert "Verbose message" in captured.out
    
    def test_logger_verbose_disabled(self, capsys):
        """Test that verbose messages are hidden when verbose=False."""
        with ImportLogger(verbose=False) as logger:
            logger.info("Normal message")
            logger.verbose_info("Verbose message")
        
        captured = capsys.readouterr()
        assert "Normal message" in captured.out
        assert "Verbose message" not in captured.out
    
    def test_logger_to_file(self):
        """Test logger output to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / 'test.log'
            
            with ImportLogger(log_file=log_file, verbose=True) as logger:
                logger.info("File message")
                logger.verbose_info("Verbose file message")
            
            content = log_file.read_text()
            assert "File message" in content
            assert "Verbose file message" in content
    
    def test_logger_file_imported(self, capsys):
        """Test logging imported file."""
        with ImportLogger(verbose=True) as logger:
            logger.file_imported(
                Path('/source/photo.jpg'),
                Path('/dest/2025/01/photo.jpg')
            )
        
        captured = capsys.readouterr()
        assert '✓' in captured.out
        assert 'photo.jpg' in captured.out
    
    def test_logger_file_skipped(self, capsys):
        """Test logging skipped file."""
        with ImportLogger(verbose=True) as logger:
            logger.file_skipped(
                Path('/source/photo.jpg'),
                'duplicate',
                Path('/dest/existing.jpg')
            )
        
        captured = capsys.readouterr()
        assert '⊘' in captured.out
        assert 'duplicate' in captured.out
    
    def test_logger_file_error(self, capsys):
        """Test logging error file."""
        with ImportLogger(verbose=True) as logger:
            logger.file_error(
                Path('/source/photo.jpg'),
                'Permission denied'
            )
        
        captured = capsys.readouterr()
        assert '✗' in captured.out
        assert 'Permission denied' in captured.out
