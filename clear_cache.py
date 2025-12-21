#!/usr/bin/env python3
"""
Clear Python Cache Files
Removes all .pyc files and __pycache__ directories to force fresh imports
"""

from pathlib import Path
import shutil


def clear_all_cache():
    """Clear all Python cache files and directories"""
    current_dir = Path(__file__).parent

    deleted_files = 0
    deleted_dirs = 0

    print("Clearing Python cache files...")

    # Find and delete all .pyc files
    for pyc_file in current_dir.rglob('*.pyc'):
        try:
            pyc_file.unlink()
            deleted_files += 1
            print(f"  Deleted: {pyc_file.relative_to(current_dir)}")
        except Exception as e:
            print(f"  Failed to delete {pyc_file}: {e}")

    # Find and delete all __pycache__ directories
    for pycache_dir in current_dir.rglob('__pycache__'):
        try:
            shutil.rmtree(pycache_dir)
            deleted_dirs += 1
            print(f"  Removed: {pycache_dir.relative_to(current_dir)}")
        except Exception as e:
            print(f"  Failed to remove {pycache_dir}: {e}")

    print()
    print(f"✓ Cache clearing complete!")
    print(f"  Files deleted: {deleted_files}")
    print(f"  Directories removed: {deleted_dirs}")
    print()
    print("All Python modules will be freshly imported on next run.")


if __name__ == "__main__":
    clear_all_cache()
