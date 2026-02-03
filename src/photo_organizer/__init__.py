"""
Photo Organizer - EXIF metadata-based photo and video organizer.
"""

__version__ = "1.0.0"
__author__ = "Photo Organizer Team"

from .organizer import PhotoOrganizer
from .config import OrganizerConfig

__all__ = ["PhotoOrganizer", "OrganizerConfig", "__version__"]
