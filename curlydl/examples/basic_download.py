"""
Basic example demonstrating simple usage of curlyDL
"""
import os
import time
import logging
from src import DownloadManager
from src.metadata import DownloadState

def format_size(size_bytes: float) -> str:
    """Format size in bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def format_speed(speed_bytes: float) -> str:
    """Format speed in bytes/second to human readable format"""
    return f"{format_size(speed_bytes)}/s"

def format_time(seconds: float) -> str:
    """Format time in seconds to human readable format"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.0f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("download.log"),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)

    # Create downloads directory if it doesn't exist
    os.makedirs("downloads", exist_ok=True)

    # Initialize the download manager with custom settings
    manager = DownloadManager(
        max_workers=4,  # Use 4 threads for parallel downloads
        user_agent="curlyDL/1.0",  # Custom user agent
        min_free_space=1024 * 1024 * 100,  # Require at least 100MB free space
        log_file="download.log"  # Enable logging to file
    )

    # URL to download
    url = "https://raw.githubusercontent.com/torvalds/linux/master/README"
    output_path = "downloads/linux_readme.txt"
    
    logger.info(f"Starting download from {url}")
    logger.info(f"Output path: {output_path}")
    
    try:
        # Start download
        download_id = manager.start_download(url, output_path)
        
        # Monitor download progress with enhanced statistics
        previous_bytes = 0
        start_time = time.time()
        
        while True:
            # Get comprehensive download statistics
            stats = manager.get_download_stats(download_id)
            state = stats["state"]
            progress = stats["progress"]
            speed_stats = stats["speed"]
            bytes_downloaded = stats["bytes_downloaded"]
            
            # Calculate speed and ETA
            current_speed = speed_stats["current_speed"]
            average_speed = speed_stats["average_speed"]
            peak_speed = speed_stats["peak_speed"]
            
            # Format status line
            status_parts = [
                f"Progress: {progress:.1f}%",
                f"Speed: {format_speed(current_speed)}",
                f"Avg: {format_speed(average_speed)}",
                f"Peak: {format_speed(peak_speed)}",
            ]
            
            # Add ETA if we have valid speed
            if average_speed > 0 and progress < 100:
                bytes_remaining = (bytes_downloaded / (progress / 100)) - bytes_downloaded
                eta = bytes_remaining / average_speed
                status_parts.append(f"ETA: {format_time(eta)}")
            
            # Add state
            status_parts.append(f"State: {state.value}")
            
            # Print status line
            print("\r" + " | ".join(status_parts), end="", flush=True)
            
            # Check if download is complete, failed, or cancelled
            if state in (DownloadState.COMPLETE, DownloadState.FAILED, DownloadState.CANCELLED):
                break
            
            # Short sleep to prevent excessive CPU usage
            time.sleep(0.1)
        
        print()  # New line after progress
        
        # Check final state
        if state == DownloadState.COMPLETE:
            total_time = time.time() - start_time
            average_speed = bytes_downloaded / total_time
            
            logger.info("Download completed successfully")
            print(f"\nDownload complete!")
            print(f"Total size: {format_size(bytes_downloaded)}")
            print(f"Time taken: {format_time(total_time)}")
            print(f"Average speed: {format_speed(average_speed)}")
        else:
            logger.error(f"Download {state.value}")
            print(f"\nDownload {state.value}!")
        
    except KeyboardInterrupt:
        logger.info("Download cancelled by user")
        print("\nDownload cancelled by user")
        manager.cancel_download(download_id)
    except Exception as e:
        logger.error(f"Download failed: {str(e)}", exc_info=True)
        print(f"\nError: {str(e)}")
    finally:
        # Ensure proper cleanup
        manager.cleanup()

if __name__ == "__main__":
    main()
