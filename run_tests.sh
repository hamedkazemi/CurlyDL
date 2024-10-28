#!/bin/bash

# Run unit tests
echo "Running unit tests..."
python3 -m unittest discover tests/

# Run basic example
echo -e "\nRunning basic download example..."
python3 examples/basic_download.py

# Run advanced example
echo -e "\nRunning advanced download example..."
python3 examples/advanced_download.py
