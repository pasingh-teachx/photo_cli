# ExifTool config file for photo_organizer custom XMP tags
#
# This config defines a custom XMP namespace for storing metadata
# related to photo organization (original filenames, inferred dates, etc.)

%Image::ExifTool::UserDefined = (
    # Define new XMP namespace
    'Image::ExifTool::XMP::Main' => {
        photoOrganizer => {
            SubDirectory => {
                TagTable => 'Image::ExifTool::UserDefined::photoOrganizer',
            },
        },
    },
);

# Define the tag table for our custom namespace
%Image::ExifTool::UserDefined::photoOrganizer = (
    GROUPS => { 0 => 'XMP', 1 => 'XMP-photoOrganizer', 2 => 'Other' },
    NAMESPACE => { 'photoOrganizer' => 'http://ns.photo-organizer.local/1.0/' },
    WRITABLE => 'string',
    
    # Original filename before any renaming
    OriginalFileName => { Writable => 'string' },
    
    # Alternate filename (source filename if different from original)
    AlternateFileName => { Writable => 'string' },
    
    # Flag indicating datetime was inferred (not from original EXIF)
    DateTimeInferred => { Writable => 'string' },
    
    # Source of datetime inference (e.g., 'filename', 'File:FileModifyDate')
    DateTimeInferenceSource => { Writable => 'string' },
    
    # Flag indicating location was manually set
    LocationManuallySet => { Writable => 'string' },
    
    # Version of photo-organizer that processed this file
    ProcessedByVersion => { Writable => 'string' },
);

1;  # Required for Perl config files
