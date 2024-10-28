"""
Data models for download metadata
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import time

class DownloadState(Enum):
    """Possible states of a download"""
    INITIALIZING = "initializing"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def to_json(self) -> str:
        """Convert enum to JSON-serializable string"""
        return self.value

    @classmethod
    def from_json(cls, value: str) -> 'DownloadState':
        """Create enum from JSON string"""
        return cls(value)

@dataclass
class SegmentInfo:
    """Information about a download segment"""
    start: int
    end: int
    status: str
    attempts: int = 0
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SegmentInfo':
        """Create from dictionary"""
        return cls(**data)

@dataclass
class SpeedStats:
    """Download speed statistics"""
    current_speed: float = 0.0
    average_speed: float = 0.0
    peak_speed: float = 0.0
    speeds: List[float] = field(default_factory=list)  # Will store last 10 speed measurements
    last_update: float = field(default_factory=lambda: time.time())
    last_bytes: int = 0

    def add_speed(self, speed: float) -> None:
        """Add a speed measurement, maintaining a maximum of 10 entries"""
        self.speeds.append(speed)
        if len(self.speeds) > 10:
            self.speeds.pop(0)
        self.average_speed = sum(self.speeds) / len(self.speeds)
        self.peak_speed = max(self.peak_speed, speed)
        self.current_speed = speed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'current_speed': self.current_speed,
            'average_speed': self.average_speed,
            'peak_speed': self.peak_speed,
            'speeds': list(self.speeds),  # Convert to list to ensure JSON serialization
            'last_update': self.last_update,
            'last_bytes': self.last_bytes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpeedStats':
        """Create from dictionary"""
        if isinstance(data, cls):
            return data
        return cls(
            current_speed=float(data.get('current_speed', 0.0)),
            average_speed=float(data.get('average_speed', 0.0)),
            peak_speed=float(data.get('peak_speed', 0.0)),
            speeds=list(data.get('speeds', [])),
            last_update=float(data.get('last_update', time.time())),
            last_bytes=int(data.get('last_bytes', 0))
        )

@dataclass
class DownloadMetadata:
    """Complete metadata for a download"""
    url: str
    output_path: str
    total_size: int
    downloaded_bytes: int
    state: DownloadState
    segments: List[SegmentInfo] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resume_supported: bool = False
    error_count: int = 0
    last_error: Optional[str] = None
    speed_stats: SpeedStats = field(default_factory=SpeedStats)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'url': self.url,
            'output_path': self.output_path,
            'total_size': self.total_size,
            'downloaded_bytes': self.downloaded_bytes,
            'state': self.state.to_json(),
            'segments': [segment.to_dict() for segment in self.segments],
            'created_at': self.created_at,
            'last_updated': self.last_updated,
            'resume_supported': self.resume_supported,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'speed_stats': self.speed_stats.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DownloadMetadata':
        """Create from dictionary"""
        # Handle nested objects
        state = DownloadState.from_json(data['state'])
        segments = [SegmentInfo.from_dict(s) for s in data.get('segments', [])]
        speed_stats = SpeedStats.from_dict(data.get('speed_stats', {}))

        # Create instance with processed data
        return cls(
            url=data['url'],
            output_path=data['output_path'],
            total_size=int(data['total_size']),
            downloaded_bytes=int(data['downloaded_bytes']),
            state=state,
            segments=segments,
            created_at=data.get('created_at', datetime.now(timezone.utc).isoformat()),
            last_updated=data.get('last_updated', datetime.now(timezone.utc).isoformat()),
            resume_supported=bool(data.get('resume_supported', False)),
            error_count=int(data.get('error_count', 0)),
            last_error=data.get('last_error'),
            speed_stats=speed_stats
        )
