"""
Basic example demonstrating simple usage of curlyDL
"""
from src import DownloadManager

def main():
    # Initialize the download manager
    manager = DownloadManager()

    # URL to download
    url = "https://raw.githubusercontent.com/torvalds/linux/master/README"
    output_path = "downloads/linux_readme.txt"
    
    print(f"Downloading {url}")
    print(f"Output: {output_path}")
    
    try:
        # Start download and wait for completion
        download_id = manager.start_download(url, output_path)
        
        # Simple progress monitoring
        while not manager.is_complete(download_id):
            progress = manager.get_progress(download_id)
            print(f"\rProgress: {progress:.1f}%", end="", flush=True)
        
        print("\nDownload complete!")
        
    except KeyboardInterrupt:
        print("\nDownload cancelled")
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    main()
