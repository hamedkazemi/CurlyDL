"""
Advanced example demonstrating parallel downloads with progress tracking,
speed calculation, error recovery, and download queue management
"""
import os
import time
import hashlib
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from src import DownloadManager

class Priority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3

@dataclass
class DownloadItem:
    url: str
    output_path: str
    priority: Priority = Priority.NORMAL
    expected_hash: Optional[str] = None
    max_speed: Optional[int] = None  # Speed limit in bytes/second
    description: Optional[str] = None

class DownloadTracker:
    def __init__(self, download_manager, download_id, url, max_speed=None, description=None):
        self.download_manager = download_manager
        self.download_id = download_id
        self.url = url
        self.max_speed = max_speed
        self.description = description or os.path.basename(url)
        self.last_progress = -1
        self.start_time = time.time()
        self.last_bytes = 0
        self.last_time = self.start_time
        self.speed_history = deque(maxlen=10)  # Keep last 10 speed measurements
        self.total_size = None
        self.start_bytes = 0
        self.total_time = 0
    
    def format_size(self, size):
        """Format size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def calculate_speed(self, current_bytes):
        """Calculate current download speed with averaging"""
        current_time = time.time()
        time_diff = current_time - self.last_time
        if time_diff >= 0.1:  # Update speed every 100ms
            bytes_diff = current_bytes - self.last_bytes
            speed = bytes_diff / time_diff
            
            # Apply speed limit if set
            if self.max_speed and speed > self.max_speed:
                time.sleep((bytes_diff / self.max_speed) - time_diff)
                speed = self.max_speed
            
            self.speed_history.append(speed)
            self.last_bytes = current_bytes
            self.last_time = current_time
            
            # Calculate average speed
            return sum(self.speed_history) / len(self.speed_history)
        return None

    def calculate_average_speed(self):
        """Calculate overall average download speed"""
        if self.total_time > 0:
            return (self.last_bytes - self.start_bytes) / self.total_time
        return 0

    def estimate_time_remaining(self, progress, speed):
        """Estimate remaining download time"""
        if progress > 0 and speed > 0 and self.total_size:
            remaining_bytes = self.total_size * (100 - progress) / 100
            seconds = remaining_bytes / speed
            if seconds < 60:
                return f"{seconds:.0f}s"
            elif seconds < 3600:
                return f"{seconds/60:.1f}m"
            else:
                return f"{seconds/3600:.1f}h"
        return "???"
    
    def track_progress(self):
        """Track and display download progress"""
        try:
            current_progress = self.download_manager.get_progress(self.download_id)
            if int(current_progress) != int(self.last_progress):
                # Get current speed
                speed = self.calculate_speed(self.last_bytes)
                speed_str = f" ({self.format_size(speed)}/s)" if speed else ""
                
                # Get total size if not already stored
                if self.total_size is None:
                    try:
                        with open(f"downloads_metadata/{self.download_id}.json", 'r') as f:
                            import json
                            metadata = json.load(f)
                            self.total_size = metadata.get('total_size', 0)
                    except:
                        pass

                # Format size info
                size_info = f" of {self.format_size(self.total_size)}" if self.total_size else ""
                
                # Calculate time remaining
                time_remaining = f" - {self.estimate_time_remaining(current_progress, speed)}" if speed else ""
                
                # Build status line with description
                status = f"{self.description}: {current_progress:.1f}%{size_info}{speed_str}{time_remaining}"
                
                # Add timestamp and priority indicator
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] {status}")
                
                self.last_progress = current_progress
                
                # Update total time
                self.total_time = time.time() - self.start_time
                
            return not self.download_manager.is_complete(self.download_id)
        except Exception as e:
            print(f"Error tracking progress: {str(e)}")
            return False

class DownloadQueue:
    def __init__(self, download_manager, max_concurrent=4):
        self.download_manager = download_manager
        self.max_concurrent = max_concurrent
        self.queue = []
        self.active = []
        self.completed = []
        self.failed = []
    
    def add(self, item: DownloadItem):
        """Add item to queue"""
        self.queue.append(item)
        # Sort queue by priority
        self.queue.sort(key=lambda x: x.priority.value, reverse=True)
    
    def process_queue(self):
        """Process download queue"""
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = []
            
            while self.queue or futures:
                # Start new downloads if slots available
                while self.queue and len(futures) < self.max_concurrent:
                    item = self.queue.pop(0)
                    future = executor.submit(
                        download_file,
                        self.download_manager,
                        item.url,
                        item.output_path,
                        item.expected_hash,
                        item.max_speed,
                        item.description
                    )
                    futures.append((future, item))
                    self.active.append(item)
                
                # Check completed downloads
                for future, item in futures[:]:
                    if future.done():
                        futures.remove((future, item))
                        self.active.remove(item)
                        if future.result():
                            self.completed.append(item)
                        else:
                            self.failed.append(item)
                
                time.sleep(0.1)

def calculate_file_hash(filepath, algorithm='sha256'):
    """Calculate file hash using specified algorithm"""
    hasher = getattr(hashlib, algorithm)()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def verify_file(filepath, expected_hash=None):
    """Verify downloaded file"""
    if not os.path.exists(filepath):
        print(f"Error: File not found - {filepath}")
        return False
        
    file_size = os.path.getsize(filepath)
    file_hash = calculate_file_hash(filepath)
    
    print(f"\nFile verification:")
    print(f"Path: {filepath}")
    print(f"Size: {file_size:,} bytes")
    print(f"SHA256: {file_hash}")
    
    if expected_hash and file_hash != expected_hash:
        print("Warning: Hash mismatch!")
        return False
    return True

def download_file(download_manager, url, output_path, expected_hash=None, max_speed=None, description=None):
    """Handle individual file download with retries"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            if retry_count > 0:
                print(f"\nRetrying download ({retry_count}/{max_retries}): {description or url}")
                # Wait longer for each retry
                time.sleep(retry_count * 2)
            else:
                print(f"\nStarting download: {description or url}")
                
            download_id = download_manager.start_download(url, output_path)
            tracker = DownloadTracker(download_manager, download_id, url, max_speed, description)
            
            while tracker.track_progress():
                time.sleep(0.1)
            
            if verify_file(output_path, expected_hash):
                avg_speed = tracker.calculate_average_speed()
                print(f"\nDownload complete: {description or url}")
                print(f"Average speed: {tracker.format_size(avg_speed)}/s")
                print(f"Total time: {tracker.total_time:.1f}s")
                return True
                
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                print(f"\nError: File not found - {url}")
            elif "SSL" in error_msg:
                print(f"\nError: SSL certificate verification failed - {url}")
            elif "timeout" in error_msg.lower():
                print(f"\nError: Connection timeout - {url}")
            else:
                print(f"\nError downloading {url}: {error_msg}")
            
            retry_count += 1
            if retry_count < max_retries:
                continue
            
        return False

def main():
    # Initialize download manager and queue
    download_manager = DownloadManager(max_workers=4)
    queue = DownloadQueue(download_manager, max_concurrent=2)
    
    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)
    
    # Add downloads to queue with different priorities and descriptions
    queue.add(DownloadItem(
        # Debian small package for testing speed limiting
        url="http://ftp.debian.org/debian/pool/main/h/hello/hello_2.10-2_amd64.deb",
        output_path="downloads/hello_debian.deb",
        priority=Priority.HIGH,
        description="Debian Hello Package (Speed Limited)",
        max_speed=50 * 1024  # Limit to 50KB/s
    ))
    
    queue.add(DownloadItem(
        url="https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.11.5.tar.xz",
        output_path="downloads/linux-6.11.5.tar.xz",
        priority=Priority.NORMAL,
        description="Linux README"
    ))
    
    queue.add(DownloadItem(
        url="https://raw.githubusercontent.com/torvalds/linux/master/COPYING",
        output_path="downloads/linux_license.txt",
        priority=Priority.NORMAL,
        description="Linux License"
    ))
    
    queue.add(DownloadItem(
        url="https://raw.githubusercontent.com/torvalds/linux/master/CREDITS",
        output_path="downloads/linux_credits.txt",
        priority=Priority.LOW,
        description="Linux Credits"
    ))
    
    print("Starting download queue...")
    print("Press Ctrl+C to interrupt downloads\n")
    print("Note: First download is speed-limited to 50KB/s for demonstration\n")
    
    try:
        queue.process_queue()
        
        print("\nQueue processing complete!")
        print(f"Successfully completed: {len(queue.completed)}")
        print(f"Failed: {len(queue.failed)}")
        
        if queue.failed:
            print("\nFailed downloads:")
            for item in queue.failed:
                print(f"- {item.description or item.url}")
        
        if queue.completed:
            print("\nCompleted downloads:")
            for item in queue.completed:
                size = os.path.getsize(item.output_path)
                print(f"- {item.description}: {size:,} bytes")
        
    except KeyboardInterrupt:
        print("\nDownloads interrupted by user")
        # Clean up partial downloads
        for item in queue.active:
            if os.path.exists(item.output_path):
                try:
                    os.remove(item.output_path)
                    print(f"Cleaned up partial download: {item.output_path}")
                except:
                    pass

if __name__ == "__main__":
    main()
