#!/usr/bin/env python3
"""Verify that all required environment variables are set."""
import os
import sys

REQUIRED_VARS = [
    'DEPLOY_KEY',
    'DATABASE_URL',
    'BINANCE_API_KEY',
    'BINANCE_API_SECRET'
]

def main():
    """Check for required environment variables."""
    missing = []
    for var in REQUIRED_VARS:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    print("All required environment variables are set.")
    sys.exit(0)

if __name__ == '__main__':
    main()
