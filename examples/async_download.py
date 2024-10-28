"""
Example demonstrating async usage of curlyDL with asyncio
"""
import os
import asyncio
from src import DownloadManager

async def monitor_download(manager, download_id, filename):
    """Monitor download progress asynchronously"""
    last_progress = -1
    while not manager.is_complete(download_id):
        progress = manager.get_progress(download_id)
        if int(progress) != int(last_progress):
            print(f"{filename}: {progress:.1f}%")
            last_progress = progress
        await asyncio.sleep(0.1)
    print(f"{filename}: Complete!")

async def download_file(manager, url, output_path):
    """Download a file asynchronously"""
    filename = os.path.basename(output_path)
    try:
        print(f"Starting download: {filename}")
        download_id = manager.start_download(url, output_path)
        await monitor_download(manager, download_id, filename)
        return True
    except Exception as e:
        print(f"Error downloading {filename}: {e}")
        return False

async def main():
    # Initialize download manager
    manager = DownloadManager()

    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)

    # List of files to download
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

    try:
        # Create download tasks
        tasks = [
            download_file(manager, item["url"], item["output"])
            for item in downloads
        ]

        # Wait for all downloads to complete
        results = await asyncio.gather(*tasks)

        # Print summary
        successful = sum(1 for r in results if r)
        print(f"\nCompleted {successful} of {len(downloads)} downloads")

    except KeyboardInterrupt:
        print("\nDownloads cancelled")
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
