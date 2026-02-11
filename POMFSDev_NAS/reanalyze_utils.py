"""
Reanalyze Utilities for scraped_data/ folder processing
Scans local images, checks OCR status, and prepares for batch reanalysis
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime


SCRAPED_DATA_DIR = "scraped_data"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def extract_shortcode_from_filename(filename: str) -> Optional[str]:
    """Extract Instagram shortcode from image filename.
    
    Format: {shortcode}_{index}.jpg
    Example: DTWSuQ-D-C4_0.jpg -> DTWSuQ-D-C4
    """
    base = os.path.splitext(filename)[0]
    match = re.match(r'^(.+)_\d+$', base)
    if match:
        return match.group(1)
    return base


def get_ocr_text_path(image_path: str) -> str:
    """Get the corresponding OCR text file path for an image."""
    base = os.path.splitext(image_path)[0]
    return f"{base}_ocr.txt"


def has_ocr_text(image_path: str) -> bool:
    """Check if OCR text file exists for an image."""
    return os.path.exists(get_ocr_text_path(image_path))


def read_ocr_text(image_path: str) -> Optional[str]:
    """Read OCR text content if exists."""
    ocr_path = get_ocr_text_path(image_path)
    if os.path.exists(ocr_path):
        try:
            with open(ocr_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"[ReanalyzeUtils] Error reading OCR file {ocr_path}: {e}")
    return None


def scan_scraped_data(date_filter: Optional[str] = None, 
                      username_filter: Optional[str] = None) -> Dict:
    """Scan scraped_data folder and return statistics.
    
    Args:
        date_filter: Optional date string (YYYY-MM-DD) to filter
        username_filter: Optional username to filter
        
    Returns:
        Dict with scan results and statistics
    """
    result = {
        'dates': [],
        'accounts': [],
        'total_images': 0,
        'ocr_completed': 0,
        'ocr_pending': 0,
        'images': []
    }
    
    if not os.path.exists(SCRAPED_DATA_DIR):
        return result
    
    dates = sorted([d for d in os.listdir(SCRAPED_DATA_DIR) 
                   if os.path.isdir(os.path.join(SCRAPED_DATA_DIR, d))],
                  reverse=True)
    
    if date_filter:
        dates = [d for d in dates if d == date_filter]
    
    result['dates'] = dates
    all_accounts = set()
    
    for date_dir in dates:
        date_path = os.path.join(SCRAPED_DATA_DIR, date_dir)
        
        for username in os.listdir(date_path):
            if username_filter and username != username_filter:
                continue
                
            user_path = os.path.join(date_path, username)
            if not os.path.isdir(user_path):
                continue
                
            all_accounts.add(username)
            
            for filename in os.listdir(user_path):
                ext = os.path.splitext(filename)[1].lower()
                if ext not in IMAGE_EXTENSIONS:
                    continue
                    
                image_path = os.path.join(user_path, filename)
                shortcode = extract_shortcode_from_filename(filename)
                ocr_exists = has_ocr_text(image_path)
                
                result['total_images'] += 1
                if ocr_exists:
                    result['ocr_completed'] += 1
                else:
                    result['ocr_pending'] += 1
                
                result['images'].append({
                    'path': image_path,
                    'shortcode': shortcode,
                    'username': username,
                    'date': date_dir,
                    'filename': filename,
                    'has_ocr': ocr_exists
                })
    
    result['accounts'] = sorted(list(all_accounts))
    return result


def get_available_dates() -> List[str]:
    """Get list of available date folders in scraped_data."""
    if not os.path.exists(SCRAPED_DATA_DIR):
        return []
    
    return sorted([d for d in os.listdir(SCRAPED_DATA_DIR)
                   if os.path.isdir(os.path.join(SCRAPED_DATA_DIR, d))],
                  reverse=True)


def get_accounts_for_date(date_str: str) -> List[str]:
    """Get list of account folders for a specific date."""
    date_path = os.path.join(SCRAPED_DATA_DIR, date_str)
    if not os.path.exists(date_path):
        return []
    
    return sorted([d for d in os.listdir(date_path)
                   if os.path.isdir(os.path.join(date_path, d))])


def get_reanalysis_batch(date_filter: Optional[str] = None,
                         username_filter: Optional[str] = None,
                         skip_analyzed: bool = True,
                         analyzed_shortcodes: Optional[set] = None,
                         limit: int = 50) -> List[Dict]:
    """Get a batch of images ready for reanalysis.
    
    Args:
        date_filter: Optional date to filter
        username_filter: Optional username to filter  
        skip_analyzed: Skip images already in analyzed_shortcodes
        analyzed_shortcodes: Set of shortcodes already analyzed in DB
        limit: Maximum batch size
        
    Returns:
        List of image dicts ready for analysis
    """
    scan_result = scan_scraped_data(date_filter, username_filter)
    
    if analyzed_shortcodes is None:
        analyzed_shortcodes = set()
    
    batch = []
    for img in scan_result['images']:
        if skip_analyzed and img['shortcode'] in analyzed_shortcodes:
            continue
        
        batch.append(img)
        if len(batch) >= limit:
            break
    
    return batch


if __name__ == "__main__":
    print("=== Scanning scraped_data/ ===")
    result = scan_scraped_data()
    print(f"Dates: {result['dates'][:5]}...")
    print(f"Total accounts: {len(result['accounts'])}")
    print(f"Total images: {result['total_images']}")
    print(f"OCR completed: {result['ocr_completed']}")
    print(f"OCR pending: {result['ocr_pending']}")
    
    if result['images']:
        print(f"\nSample image: {result['images'][0]}")
