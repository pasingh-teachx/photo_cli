# Photo Organizer CLI

A powerful EXIF metadata-based photo and video organizer tool that helps you import, deduplicate, analyze, and organize your media files with pristine metadata.

## Features

- **EXIF/Metadata-based organization**: Uses only embedded metadata dates, not filesystem dates
- **Idempotent operations**: Safe to re-run - won't create duplicates
- **Duplicate detection**: Content-based SHA256 hashing to skip exact duplicates
- **Original filename preservation**: Stores original and alternate filenames in XMP metadata
- **WhatsApp support**: Extracts dates from WhatsApp-style filenames
- **Location management**: Prompts for GPS coordinates when missing (with batch override option)
- **Customizable output**: Configurable folder structure and filename patterns
- **Dry run mode**: Preview changes before applying them
- **Non-destructive**: Preserves all original metadata

## Installation

```bash
cd photo_cli
pip install -e .
```

### Dependencies

This tool requires `exiftool` to be installed on your system:

```bash
# Ubuntu/Debian
sudo apt-get install libimage-exiftool-perl

# macOS
brew install exiftool

# Windows
# Download from https://exiftool.org/
```

## Usage

### Basic Usage

```bash
# Import photos from source to destination (copy mode, interactive)
photo-organizer /path/to/source /path/to/destination

# Dry run - preview changes without modifying files
photo-organizer /path/to/source /path/to/destination --dry-run

# Move files instead of copying
photo-organizer /path/to/source /path/to/destination --move

# Skip GPS coordinate prompts
photo-organizer /path/to/source /path/to/destination --skip-location

# Batch set GPS coordinates for all files
photo-organizer /path/to/source /path/to/destination --location "37.7749,-122.4194"
```

### Customizing Output Structure

```bash
# Custom folder pattern (default: {year}-{month:02d}-{month_name_short})
photo-organizer /source /dest --folder-pattern "{year}/{month:02d}-{month_name}"

# Custom filename pattern (default: {year}-{month:02d}-{day:02d}_{hour:02d}-{min:02d}-{sec:02d}-{original_name})
photo-organizer /source /dest --filename-pattern "{year}{month:02d}{day:02d}_{original_name}"
```

### Available Pattern Variables

- `{year}` - 4-digit year (e.g., 2025)
- `{month}` - Month number (1-12)
- `{month:02d}` - Zero-padded month (01-12)
- `{month_name}` - Full month name (January)
- `{month_name_short}` - Short month name (Jan)
- `{day}` - Day of month (1-31)
- `{day:02d}` - Zero-padded day (01-31)
- `{hour}` - Hour (0-23)
- `{hour:02d}` - Zero-padded hour (00-23)
- `{min}` - Minute (0-59)
- `{min:02d}` - Zero-padded minute (00-59)
- `{sec}` - Second (0-59)
- `{sec:02d}` - Zero-padded second (00-59)
- `{original_name}` - Original filename (without extension)
- `{ext}` - File extension (lowercase)

## Metadata Handling

### Original Filename Tracking

- `XMP:OriginalFileName` - Stores the first known filename of the file
- `XMP:AlternateFileName` - Stores the current filename if it differs from original

### WhatsApp Files

The tool recognizes WhatsApp filename patterns:
- `WhatsApp Image 2024-10-01 at 10.06.47 AM.jpeg` - Full datetime extracted
- `WhatsApp Video 2025-02-03 at 2.38.55 AM.mp4` - Full datetime extracted
- `IMG-20241001-WA0001.jpg` - Date only, time inferred from metadata
- `VID-20241001-WA0001.mp4` - Date only, time inferred from metadata

### Date/Time Inference

For WhatsApp files with date-only filenames, the tool:
1. Checks all available metadata dates (including system dates)
2. If a date within 1-2 days is found, uses that time
3. Marks the datetime as inferred with `XMP:DateTimeInferred=true`
4. Stores the source in `XMP:DateTimeInferenceSource`
5. If no match found, prompts user for time input

## License

MIT License