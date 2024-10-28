"""
Example demonstrating curlyDL with tqdm progress bars
"""
import os
from tqdm import tqdm
from src import DownloadManager

def download_with_progress(url, output_path):
    """Download a file with a progress bar"""
    manager = DownloadManager()
    
    try:
        # Start download
        download_id = manager.start_download(url, output_path)
        
        # Initialize progress bar
        pbar = tqdm(
            total=100,
            desc=os.path.basename(output_path),
            unit='%',
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
        )
        
        # Track last progress to avoid unnecessary updates
        last_progress = -1
        
        # Monitor progress
        while not manager.is_complete(download_id):
            current_progress = manager.get_progress(download_id)
            # Update progress bar only when progress changes
            if int(current_progress) > int(last_progress):
                pbar.n = int(current_progress)
                pbar.refresh()
                last_progress = current_progress
        
        # Ensure progress bar shows completion
        pbar.n = 100
        pbar.refresh()
        pbar.close()
        
        return True
        
    except KeyboardInterrupt:
        print(f"\nDownload cancelled: {os.path.basename(output_path)}")
        return False
    except Exception as e:
        print(f"\nError downloading {os.path.basename(output_path)}: {e}")
        return False

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
