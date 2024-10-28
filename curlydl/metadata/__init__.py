"""
Metadata package for managing download metadata
"""
from .models import (
    DownloadState,
    SegmentInfo,
    SpeedStats,
    DownloadMetadata
)
from .exceptions import (
    MetadataError,
    MetadataStorageError,
    MetadataLoadError,
    MetadataValidationError,
    MetadataStateError
)
from .manager import MetadataManager

__all__ = [
    # Models
    'DownloadState',
    'SegmentInfo',
    'SpeedStats',
    'DownloadMetadata',
    
    # Exceptions
    'MetadataError',
    'MetadataStorageError',
    'MetadataLoadError',
    'MetadataValidationError',
    'MetadataStateError',
    
    # Manager
    'MetadataManager'
]
