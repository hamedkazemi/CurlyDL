"""
Custom exceptions for metadata operations
"""

class MetadataError(Exception):
    """Base exception for metadata-related errors"""
    pass

class MetadataStorageError(MetadataError):
    """Exception raised when metadata storage operations fail"""
    pass

class MetadataLoadError(MetadataError):
    """Exception raised when metadata loading operations fail"""
    pass

class MetadataValidationError(MetadataError):
    """Exception raised when metadata validation fails"""
    pass

class MetadataStateError(MetadataError):
    """Exception raised when invalid state transitions are attempted"""
    pass
