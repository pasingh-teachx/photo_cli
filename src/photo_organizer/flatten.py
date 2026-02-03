"""
Flatten skipped folders utility.
"""

import shutil
from pathlib import Path
from typing import Dict, Set


def flatten_skipped_folders(
    source_dir: Path,
    destination_dir: Path,
    move_files: bool = False,
    dry_run: bool = False,
    verbose: bool = False
) -> None:
    """
    Flatten skipped folders into a single destination directory.

    Args:
        source_dir: Directory containing skipped folders (e.g., destination/skipped/)
        destination_dir: Directory to flatten files into
        move_files: If True, move files instead of copying
        dry_run: If True, only preview changes
        verbose: If True, print detailed progress
    """
    if not source_dir.exists():
        raise ValueError(f"Source directory does not exist: {source_dir}")

    if dry_run:
        print(f"[DRY RUN] Would flatten {source_dir} to {destination_dir}")
    else:
        destination_dir.mkdir(parents=True, exist_ok=True)

    # Track used filenames to handle conflicts
    used_names: Dict[str, int] = {}
    processed_files = 0
    skipped_files = 0

    # Walk through all files in source directory recursively
    for filepath in source_dir.rglob('*'):
        if not filepath.is_file():
            continue

        # Get relative path from source_dir
        try:
            relative_path = filepath.relative_to(source_dir)
        except ValueError:
            # Shouldn't happen, but skip if it does
            if verbose:
                print(f"Warning: Could not get relative path for {filepath}")
            continue

        # Create a flattened filename from the relative path
        # Replace path separators with underscores and handle conflicts
        flat_name = _create_unique_filename(str(relative_path), used_names)

        destination_file = destination_dir / flat_name

        if dry_run:
            print(f"[DRY RUN] Would {'move' if move_files else 'copy'}: {filepath} -> {destination_file}")
        else:
            try:
                if move_files:
                    shutil.move(str(filepath), str(destination_file))
                else:
                    shutil.copy2(str(filepath), str(destination_file))
                processed_files += 1
                if verbose:
                    print(f"{'Moved' if move_files else 'Copied'}: {filepath} -> {destination_file}")
            except Exception as e:
                print(f"Error processing {filepath}: {e}")
                skipped_files += 1

    action = "would be" if dry_run else "were"
    print(f"\nFlatten complete: {processed_files} files {action} processed")
    if skipped_files > 0:
        print(f"{skipped_files} files were skipped due to errors")


def _create_unique_filename(relative_path_str: str, used_names: Dict[str, int]) -> str:
    """
    Create a unique filename from a relative path string.

    Args:
        relative_path_str: The relative path as a string (e.g., "subfolder/file.txt")
        used_names: Dictionary tracking used filenames and their counters

    Returns:
        A unique filename
    """
    # Replace path separators with underscores
    # This handles both forward and backward slashes
    filename = relative_path_str.replace('/', '_').replace('\\', '_')

    # Handle filename conflicts
    base_name = filename
    counter = used_names.get(base_name, 0)

    if counter == 0:
        # First time seeing this name
        used_names[base_name] = 1
        return base_name
    else:
        # Find an available numbered name
        while True:
            candidate = _add_number_suffix(base_name, counter)
            if candidate not in used_names:
                used_names[candidate] = 1
                used_names[base_name] = counter + 1
                return candidate
            counter += 1


def _add_number_suffix(filename: str, number: int) -> str:
    """
    Add a number suffix to a filename before the extension.

    Args:
        filename: Original filename
        number: Number to add

    Returns:
        Filename with number suffix
    """
    if '.' in filename:
        name_part, ext = filename.rsplit('.', 1)
        return f"{name_part}_{number}.{ext}"
    else:
        return f"{filename}_{number}"