# curlydl

WIP: A robust, feature-rich download manager for Python with support for parallel downloads, speed limiting, and progress tracking.

## Features

### Core Features
- Parallel downloads with configurable worker count
- Progress tracking with real-time speed calculation
- Download resume capability
- File integrity verification with checksums
- Error handling with automatic retries
- Speed limiting per download

### Advanced Features
- Priority-based download queue
- Concurrent download limiting
- Detailed progress tracking with:
  - Download speed averaging
  - Time remaining estimation
  - File size formatting
  - Progress percentage
- Metadata persistence for download state
- Graceful interrupt handling
- Automatic cleanup of partial downloads

## Requirements

### System Dependencies
- Python 3.10 or higher
- libcurl development files

#### Ubuntu/Debian:
```bash
sudo apt-get install libcurl4-openssl-dev
```

#### CentOS/RHEL:
```bash
sudo yum install libcurl-devel
```

#### Arch Linux:
```bash
sudo pacman -S curl
```

#### macOS:
```bash
brew install curl
```

#### Windows:
Windows users need to install the appropriate version of libcurl. We recommend using the Windows binaries from the [curl website](https://curl.se/windows/).

## Installation

Install using pip:
```bash
pip install curlydl
```

## Quick Start

```python
from curlydl import DownloadManager

# Initialize download manager
manager = DownloadManager()

# Start a simple download
manager.start_download(
    url="https://example.com/file.zip",
    output_path="file.zip"
)

# Start a download with speed limit
manager.start_download(
    url="https://example.com/large-file.zip",
    output_path="large-file.zip",
    max_speed=100 * 1024  # 100KB/s
)
```

## Usage

### Basic Usage

```python
from curlydl import DownloadManager

# Initialize download manager
manager = DownloadManager(max_workers=4)

# Start a download
download_id = manager.start_download(
    url="https://example.com/file.zip",
    output_path="downloads/file.zip"
)

# Check progress
progress = manager.get_progress(download_id)
print(f"Download progress: {progress}%")

# Verify completion
is_complete = manager.is_complete(download_id)
```

### Advanced Usage

1. Priority-based Queue:
```python
from curlydl import DownloadQueue, DownloadItem, Priority

queue = DownloadQueue(max_concurrent=2)

# Add high-priority download
queue.add(DownloadItem(
    url="https://example.com/important.zip",
    output_path="downloads/important.zip",
    priority=Priority.HIGH
))

# Add normal priority download with speed limit
queue.add(DownloadItem(
    url="https://example.com/file.zip",
    output_path="downloads/file.zip",
    priority=Priority.NORMAL,
    max_speed=50 * 1024  # 50KB/s limit
))
```

2. Progress Tracking:
```python
from curlydl import DownloadManager

manager = DownloadManager()
download_id = manager.start_download(
    url="https://example.com/file.zip",
    output_path="file.zip"
)

# Monitor progress
while not manager.is_complete(download_id):
    progress = manager.get_progress(download_id)
    speed = manager.get_download_stats(download_id)
    speed = speed['speed']['current_speed']
    print(f"Progress: {progress:.1f}% - Speed: {speed/1024:.1f} KB/s")
```

### Real-World Examples

1. Downloading Multiple Files with Different Priorities:
```python
from curlydl import DownloadQueue, DownloadItem, Priority

queue = DownloadQueue(max_concurrent=2)

# High priority system updates
queue.add(DownloadItem(
    url="https://example.com/security-patch.zip",
    output_path="security-patch.zip",
    priority=Priority.HIGH
))

# Normal priority application files
queue.add(DownloadItem(
    url="https://example.com/app-data.zip",
    output_path="app-data.zip",
    priority=Priority.NORMAL
))

# Low priority optional content with speed limit
queue.add(DownloadItem(
    url="https://example.com/optional-content.zip",
    output_path="optional-content.zip",
    priority=Priority.LOW,
    max_speed=100 * 1024  # Limit to 100KB/s
))

# Process queue
queue.process_queue()
```

2. Download with Progress Callback:
```python
from curlydl import DownloadManager

def progress_callback(download_id, progress, speed):
    print(f"Download {download_id}: {progress:.1f}% ({speed/1024:.1f} KB/s)")

manager = DownloadManager(progress_callback=progress_callback)
manager.start_download(
    url="https://example.com/file.zip",
    output_path="file.zip"
)
```

3. Batch Download with Error Recovery:
```python
from curlydl import DownloadQueue, DownloadItem
import os

def download_batch(urls, output_dir):
    queue = DownloadQueue(max_concurrent=3)
    
    for url in urls:
        filename = os.path.basename(url)
        queue.add(DownloadItem(
            url=url,
            output_path=f"{output_dir}/{filename}"
        ))
    
    try:
        queue.process_queue()
        print(f"Successfully completed: {len(queue.completed)}")
        if queue.failed:
            print("Failed downloads:")
            for item in queue.failed:
                print(f"- {item.url}")
    except KeyboardInterrupt:
        print("Downloads interrupted")
```

### Example Output

When running downloads, you'll see detailed progress information:
```
[20:24:53] security-patch.zip: 45.2% of 54.8KB (50.0KB/s) - 1.2s remaining
[20:24:54] app-data.zip: 78.9% of 102.6KB (unlimited) - 3.5s remaining
[20:24:55] optional-content.zip: 12.5% of 1.5MB (100.0KB/s) - 15.0s remaining
```

## Error Handling

curlydl provides comprehensive error handling:

1. Automatic Retries:
- Failed downloads are automatically retried with exponential backoff
- Configurable retry count and delay

2. Detailed Error Messages:
- File not found (404)
- SSL certificate errors
- Connection timeouts
- Write errors

3. Error Recovery:
- Partial downloads are automatically resumed
- Corrupt files are detected and re-downloaded
- Interrupted downloads can be resumed

## Troubleshooting

### Common Issues

1. SSL Certificate Errors:
```python
# Disable SSL verification (not recommended for production)
manager = DownloadManager(verify_ssl=False)
```

2. Timeout Issues:
```python
# Increase timeout duration
manager = DownloadManager(timeout=300)  # 5 minutes
```

3. Speed Limit Not Working:
```python
# Ensure speed is in bytes per second
max_speed = 100 * 1024  # 100 KB/s
```

### Debug Mode

Enable debug mode for detailed logging:
```python
from curlydl import DownloadManager
import logging

logging.basicConfig(level=logging.DEBUG)
manager = DownloadManager(debug=True)
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
