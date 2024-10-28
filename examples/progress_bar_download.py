"""
Example demonstrating curlyDL with tqdm progress bars
"""
import os
import time
from tqdm import tqdm
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

def download_with_progress(url: str, output_path: str) -> bool:
    """
    Download a file with a progress bar
    
    Args:
        url (str): URL to download from
        output_path (str): Where to save the file
        
    Returns:
        bool: True if download was successful, False otherwise
    """
    manager = DownloadManager()
    
    try:
        # Start download
        download_id = manager.start_download(url, output_path)
        
        # Get initial stats
        stats = manager.get_download_stats(download_id)
        bytes_downloaded = stats["bytes_downloaded"]
        
        # Initialize progress bar with custom format
        pbar = tqdm(
            total=100,
            desc=os.path.basename(output_path),
            unit='%',
            bar_format='{desc}: {percentage:.2f}%|{bar}| {n:.2f}/{total:.2f} '
                      '[{elapsed}<{remaining}, {rate_fmt}{postfix}]',
            mininterval=0.01,  # Update at most every 10ms
            maxinterval=0.01,  # Force update every 10ms
        )
        
        # Track last progress to avoid unnecessary updates
        last_progress = -1
        
        # Monitor progress
        while True:
            # Get current stats
            stats = manager.get_download_stats(download_id)
            state = stats["state"]
            current_progress = stats["progress"]
            speed_stats = stats["speed"]
            bytes_downloaded = stats["bytes_downloaded"]
            
            # Update progress bar only when progress changes
            if current_progress > last_progress:
                # Round progress to 2 decimal places
                pbar.n = round(current_progress, 2)
                
                # Update postfix with speed and state
                current_speed = speed_stats["current_speed"]
                postfix = f", {format_speed(current_speed)}, {state.value}"
                pbar.set_postfix_str(postfix)
                
                pbar.refresh()
                last_progress = current_progress
            
            # Check if download is complete, failed, or cancelled
            if state in (DownloadState.COMPLETE, DownloadState.FAILED, DownloadState.CANCELLED):
                break
            
            # Very short sleep to prevent excessive CPU usage
            time.sleep(0.01)  # 10ms sleep
        
        # Ensure progress bar shows completion
        if state == DownloadState.COMPLETE:
            pbar.n = 100
            pbar.set_postfix_str(f", {format_size(bytes_downloaded)}, complete")
            pbar.refresh()
        else:
            pbar.set_postfix_str(f", {state.value}")
            pbar.refresh()
        
        pbar.close()
        
        return state == DownloadState.COMPLETE
        
    except KeyboardInterrupt:
        print(f"\nDownload cancelled: {os.path.basename(output_path)}")
        if 'download_id' in locals():
            manager.cancel_download(download_id)
        return False
    except Exception as e:
        print(f"\nError downloading {os.path.basename(output_path)}: {e}")
        return False
    finally:
        # Ensure proper cleanup
        manager.cleanup()

def main():
    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)
    
    # Files to download
    downloads = [
        {
            "url": "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.11.5.tar.xz",
            "output": "downloads/linux-6.11.5.tar.xz"
        },
        {
            "url": "https://raw.githubusercontent.com/torvalds/linux/master/COPYING",
            "output": "downloads/license.txt"
        },
        {
            "url": "https://raw.githubusercontent.com/torvalds/linux/master/CREDITS",
            "output": "downloads/credits.txt"
        }
    ]
    
    print("Starting downloads...\n")
    
    # Download each file
    successful = 0
    for download in downloads:
        if download_with_progress(download["url"], download["output"]):
            successful += 1
    
    print(f"\nCompleted {successful} of {len(downloads)} downloads")

if __name__ == "__main__":
    main()
