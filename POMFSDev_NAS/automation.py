import os
import json
import time
import unicodedata
import re
import pandas as pd
from db_config import get_db_connection
from db_utils import save_scraped_post, upsert_scraped_post
import gc

def extract_username(raw_input):
    """Extract clean Instagram username from URL or raw input."""
    if not raw_input:
        return ""
    raw_input = raw_input.strip()
    
    # Handle Instagram URLs
    if 'instagram.com' in raw_input:
        match = re.search(r'instagram\.com/([^/?]+)', raw_input)
        if match:
            return match.group(1).lstrip('@')
    
    # Remove @ prefix if present
    if raw_input.startswith('@'):
        return raw_input[1:]
    
    return raw_input

# Import your modules - assuming they are in the same directory
try:
    from scraper import InstagramScraper
    from analyzer import ImageAnalyzer, MistralAnalyzer
except ImportError as e:
    print(f"[Automation] Import Error: {e}")

import random

# Singleton for ImageAnalyzer# Global singleton
_SHARED_ANALYZER = None
import os

# Configuration environment or hardcoded key for now (User provided: uZvXeDEhoRV0iul5YS2d17xm6ZHfzvEy)
# Ideally this should be in an env var or config file.
# For simplicity/speed, I'll put it here or read from env.
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "uZvXeDEhoRV0iul5YS2d17xm6ZHfzvEy")

def get_shared_analyzer():
    global _SHARED_ANALYZER
    if _SHARED_ANALYZER is None:
        if MISTRAL_API_KEY:
            try:
                print(f"[Automation] Initializing MistralAnalyzer with key ending in ...{MISTRAL_API_KEY[-4:]}")
                from analyzer import MistralAnalyzer
                _SHARED_ANALYZER = MistralAnalyzer(api_key=MISTRAL_API_KEY)
                print("[Automation] ✅ Using Mistral OCR Engine")
            except Exception as e:
                print(f"[Automation] ⚠️ Failed to init Mistral: {e}")
                raise RuntimeError("Mistral API is required but failed to initialize") from e
        else:
            raise RuntimeError("MISTRAL_API_KEY is required but not set")
            
    return _SHARED_ANALYZER

def run_full_scrape_process(raw_username, limit=3, limit_type="posts", known_venue_name=None, auto_save_db=True, progress_callback=None):
    """
    Background process to scrape, analyze, and optionally AUTO-SAVE Instagram posts.
    Returns the result dictionary (success, saved_count, details) or raises Exception.
    
    progress_callback: function(message, percent, log=None, log_type='info')
    """
    def report(msg, pct, log=None, log_type='info'):
        if progress_callback:
            progress_callback(msg, pct, log or msg, log_type)
        print(f"[Automation] {msg}")

    report(f"Starting scrape for {raw_username} (Venue: {known_venue_name})...", 10)
    
    try:
        # Lazy import to avoid circular dep issues if any
        from db_helpers import save_single_event
        
        username = extract_username(raw_username)

        # 1. Scraper Manager Init
        try:
            from scraper_manager import ScraperManager
            scraper_mgr = ScraperManager()
        except ImportError:
            raise RuntimeError("Could not import ScraperManager")

        # 1. Scrape
        scrape_start_time = time.time()
        report(f"📥 {username} 스크래핑 시작 (최대 {limit}개)...", 15, f"계정 '{username}'에서 게시물 수집 시작", "info")
        all_posts_data = []

        # Define base output directory with date: scraped_data/YYYY-MM-DD
        from datetime import datetime
        today_str = datetime.now().strftime('%Y-%m-%d')
        base_output_dir = os.path.join("scraped_data", today_str)
        os.makedirs(base_output_dir, exist_ok=True)
            
        # Target dir for images: scraped_data/YYYY-MM-DD/username
        targets_dir = os.path.join(base_output_dir, username)
        
        # Callback adapter for ScraperManager
        def manager_progress(msg, log_msg, log_type):
            # Map manager progress to global progress (15-55%)
            # We don't have exact percent from manager, so we keep it static or pulse
            report(msg, 30, log_msg, log_type)
        
        try:
            # Fetch posts using Manager (Auto Fallback)
            # Returns list of (count, post_data) tuples
            scraped_items = scraper_mgr.fetch_posts(username, limit=limit, output_dir=targets_dir, progress_callback=manager_progress)
            
            count = 0
            for i, post in scraped_items:
                count += 1
                report(f"Processing media {count}/{len(scraped_items)}...", 30 + int((count/len(scraped_items))*25), f"게시물 {count} 데이터 처리 중", "info")
                
                is_video = post.get('is_video', False)
                if post.get('image_filepath'):
                    filename_prefix = os.path.splitext(os.path.basename(post['image_filepath']))[0]
                else:
                    filename_prefix = f"{post['shortcode']}_video"
                
                post_data = {
                    "filename_prefix": filename_prefix, 
                    "caption": post['caption'] or "",
                    "extracted_texts": [],
                    "shortcode": post['shortcode'],
                    "post_date": str(post['date']) if post.get('date') else "",
                    "all_image_filenames": post.get('all_image_filenames', []),
                    "is_video": is_video,
                }
                if post['caption']:
                    post_data["caption"] = unicodedata.normalize('NFKC', post['caption'])
                all_posts_data.append(post_data)
                
                # Save to Neon DB (initial save, will be updated with analysis later)
                try:
                    upsert_scraped_post(username, post)
                    report(f"Saved {count}", 30 + int((count/len(scraped_items))*25), f"✅ 게시물 {count} Neon DB 저장 완료", "success")
                except Exception as db_err:
                    print(f"[DB Save Error] {db_err}")
                    
        except Exception as e:
            report(f"Scrape failed: {e}", 50, f"스크래핑 치명적 오류: {e}", "error")
            if not all_posts_data:
                raise e
            
        scrape_end_time = time.time()
        total_scrape_duration = scrape_end_time - scrape_start_time
        avg_scrape_time = total_scrape_duration / max(len(all_posts_data), 1)
        
        report(f"📊 스크래핑 완료: {len(all_posts_data)}개 게시물", 55, f"수집 완료! (총 {total_scrape_duration:.1f}초, 평균 {avg_scrape_time:.1f}초/게시물)", "success")
        
        # 2. Analyze
        report("🤖 AI 분석 초기화 중...", 60, "Mistral API 연결 중...", "api")
        mistral_key = os.environ.get("MISTRAL_API_KEY")
        if mistral_key:
            analyzer = MistralAnalyzer(api_key=mistral_key)
        else:
            # Use Singleton to prevent Memory Leak / OOM
            analyzer = get_shared_analyzer()
            
        # Define base output directory with date: scraped_data/YYYY-MM-DD
        from datetime import datetime
        today_str = datetime.now().strftime('%Y-%m-%d')
        base_output_dir = os.path.join("scraped_data", today_str)
        os.makedirs(base_output_dir, exist_ok=True)
            
        # Target dir for images: scraped_data/YYYY-MM-DD/username
        targets_dir = os.path.join(base_output_dir, username)
        
        # NOTE: If we want to support checking PREVIOUSLY scraped data, we might need a broader search.
        # But for new scrapes, this structure is cleaner.
        # The user wants "scraped_data inside collected date folders".
        
        if not all_posts_data:
            report("No posts found to analyze.", 100)
            return {"success": True, "message": "No posts found", "saved_count": 0, "scraped_count": 0}

        all_results = []
        saved_db_count = 0
        
        # Pre-fetch Venue ID if known
        known_venue_id = None
        if known_venue_name:
            conn = get_db_connection()
            curr = conn.execute("SELECT id FROM venues WHERE venueName = ?", (known_venue_name,))
            row = curr.fetchone()
            if row:
                known_venue_id = row['id']
            conn.close()
        
        total_posts = len(all_posts_data)
        
        analysis_start_time = time.time()
        
        # Helper for parallel processing
        def process_single_post(idx, p_data):
            try:
                is_video = p_data.get('is_video', False)
                extracted_text_from_images = ""
                existing_valid_images = []
                
                # For video posts, skip image processing and use caption only
                if is_video:
                    print(f"[Automation] Video post {p_data['shortcode']} - analyzing caption only")
                else:
                    # Find image(s)
                    if not os.path.exists(targets_dir): return None

                    image_files_for_post = []
                    if "all_image_filenames" in p_data and p_data["all_image_filenames"]:
                         image_files_for_post = p_data["all_image_filenames"]
                    else:
                         image_files_for_post = [f for f in os.listdir(targets_dir) if f.startswith(p_data["filename_prefix"]) and f.endswith(('.jpg', '.png'))]
                    
                    if not image_files_for_post:
                        return None
                    
                    # OCR All Images
                    valid_extensions = ('.jpg', '.jpeg', '.png', '.heic', '.webp')
                    
                    for f in image_files_for_post:
                        if f.lower().endswith(valid_extensions):
                            existing_valid_images.append(f)
                    
                    if not existing_valid_images:
                        return None
                    
                    # OCR each image and save individual OCR text files
                    for img_file in existing_valid_images:
                        fpath = os.path.join(targets_dir, img_file)
                        ocr_text_single_image = ""
                        
                        if fpath and os.path.exists(fpath):
                            # Try OCR with retry on failure
                            max_retries = 2
                            for attempt in range(max_retries):
                                try:
                                    ocr_text_single_image = analyzer.extract_text(fpath)
                                    if ocr_text_single_image:
                                        break
                                except Exception as ocr_err:
                                    print(f"[OCR] Attempt {attempt+1} failed for {img_file}: {ocr_err}")
                                    if attempt < max_retries - 1:
                                        import time
                                        time.sleep(1)
                        
                        # Save individual OCR text file for each image
                        ocr_txt_path = os.path.join(targets_dir, os.path.splitext(img_file)[0] + "_ocr.txt")
                        try:
                            with open(ocr_txt_path, 'w', encoding='utf-8') as f:
                                f.write(ocr_text_single_image if ocr_text_single_image else "")
                            if ocr_text_single_image:
                                print(f"[OCR] Saved: {ocr_txt_path} ({len(ocr_text_single_image)} chars)")
                        except Exception as save_err:
                            print(f"[OCR] Failed to save {ocr_txt_path}: {save_err}")
                        
                        if ocr_text_single_image:
                            extracted_text_from_images += f"\n--- {img_file} ---\n{ocr_text_single_image}"
                
                p_data['extracted_texts'] = [extracted_text_from_images]
                
                caption_text = p_data["caption"]
                
                # For video posts, caption must exist for analysis
                if is_video and not caption_text:
                    print(f"[Automation] Video post {p_data['shortcode']} has no caption, skipping")
                    return None
                
                combined_text = (caption_text or "") + "\n" + extracted_text_from_images
                
                # Parse Information
                parsed = analyzer.parse_info(combined_text)
                    
                # Check if this is an event poster (AI auto-detection)
                is_event_poster = parsed.get('is_event_poster', False)
                
                final_dates = parsed.get('dates', [])
                final_dates = list(dict.fromkeys(final_dates))
                
                final_title = parsed.get('title', "")
                final_venue = known_venue_name if known_venue_name else parsed.get('venue', "")
                final_venue_id = known_venue_id
                final_location = parsed.get('location', "")
                
                final_artist = parsed.get('artist', "")
                if not final_artist and username:
                    final_artist = username
                
                # Set filename from the first valid image for database storage
                filename = existing_valid_images[0] if existing_valid_images else None
                    
                # Auto-Save to DB Logic - Only save if is_event_poster=True
                db_status = "Skipped"
                
                # If AI determines this is NOT an event poster, skip saving
                if not is_event_poster:
                    db_status = "Skipped (Not Event)"
                    print(f"[Automation] ⏭️ Skipped: Not an event poster")
                # EVENT DETECTION LOGIC (v2.0.0 - OR 조건 완화):
                # 조건 1: 공연명만 있어도 이벤트 (title alone)
                # 조건 2: 공연명 + 날짜 (title + dates)
                # 조건 3: 장소 + 날짜 (venue + dates)
                else:
                    has_title = bool(final_title)
                    has_venue = bool(final_venue_id or final_venue)
                    has_dates = bool(final_dates)
                    
                    # OR 로직: 하나라도 만족하면 이벤트로 저장
                    is_valid_event = has_title or (has_venue and has_dates)
                    
                    # For video posts, we don't require filename (no image to upload)
                    can_save = is_valid_event and (filename or is_video)
                    
                    if can_save:
                        # Only proceed with saving if is_event_poster=True AND dates exist
                        # Events without dates are marked "Ready to Review" for manual date input
                        if auto_save_db and final_dates:
                            for d_str in final_dates:
                                event_payload = {
                                    'venue_id': final_venue_id if final_venue_id else 'NEW',
                                    'new_venue': final_venue if not final_venue_id else None,
                                    'artist_id': 'NEW',
                                    'new_artist': final_artist,
                                    'event_name': final_title or f"{final_artist} Live",
                                    'event_date': d_str,
                                    'event_time': parsed.get('time', ''),
                                    'event_location': final_location,
                                    'event_country': parsed.get('country', 'KR'),
                                    'content': caption_text[:3000] if caption_text else "",
                                    'filename': filename,
                                    'image_src_folder': os.path.abspath(targets_dir),
                                    'shortcode': p_data.get('shortcode', '')
                                }
                                
                                if save_single_event(event_payload):
                                    db_status = "Saved"
                                elif db_status != "Saved":
                                    db_status = "Duplicate"
                        elif not final_dates:
                            # Event detected but no dates - needs manual review
                            db_status = "Ready to Review (No Date)"
                            print(f"[Automation] 📋 Event detected but no dates found - marking for review")
                        else:
                            db_status = "Ready to Review"
                    else:
                        db_status = "Skipped (No Valid Event Data)"
                
                # Update scraped_posts with analyzed data
                analyzed_data = {
                    'event_name': final_title or (f"{final_artist} Live" if final_artist else None),
                    'venue': final_venue,
                    'artists': [final_artist] if final_artist else [],
                    'event_date': final_dates[0] if final_dates else None,
                    'event_time': parsed.get('time', '')
                }
                
                post_for_update = {
                    'shortcode': p_data.get('shortcode', ''),
                    'caption': caption_text,
                    'url': None,
                    'image_filepath': os.path.abspath(os.path.join(targets_dir, filename)) if filename else None,
                    'date': p_data.get('post_date', '')
                }
                
                try:
                    upsert_scraped_post(username, post_for_update, analyzed_data)
                    print(f"[Automation] ✅ Post {p_data.get('shortcode', '')} analysis data saved to Neon DB")
                except Exception as upd_err:
                    print(f"[DB Update Error] {upd_err}")
                
                return {
                    "filename": filename,
                    "image_path": os.path.abspath(os.path.join(targets_dir, filename)) if filename else None,
                    "dates_found": final_dates,
                    "inferred_venue": final_venue,
                    "inferred_location": final_location,
                    "inferred_artist": final_artist,
                    "caption": caption_text,
                    "event_name": final_title,
                    "shortcode": p_data.get('shortcode', ''),
                    "post_date": p_data.get('post_date', ''),
                    "db_status": db_status,
                    "is_event_poster": is_event_poster
                }
            except Exception as e:
                print(f"Error processing post {idx}: {e}")
                return None

        # SEQUENTIAL EXECUTION WITH RATE LIMITING (Mistral API: 1 req/sec)
        report(f"🔬 AI 분석 시작 ({total_posts}개 게시물)...", 60, f"순차 처리 (API 제한: 1 req/sec)", "api")
        
        try:
            for idx, p_data in enumerate(all_posts_data):
                # Rate limiting: 1 request per second
                if idx > 0:
                    time.sleep(1.0)
                
                try:
                    res = process_single_post(idx, p_data)
                    if res:
                        all_results.append(res)
                        if res['db_status'] == "Saved":
                            saved_db_count += 1
                except Exception as e:
                    print(f"Error processing post {idx}: {e}")
                
                # Update Progress (60% -> 95%)
                completed_count = idx + 1
                current_pct = 60 + int((completed_count / total_posts) * 35)
                report(f"Analyzing {completed_count}/{total_posts}...", current_pct, f"🔍 게시물 {idx+1} OCR 및 정보 추출 완료", "api")
                        
        except Exception as e:
            report(f"Sequential execution failed: {e}", 60)
            raise e
            
        analysis_end_time = time.time()
        total_analysis_duration = analysis_end_time - analysis_start_time
        avg_analysis_time = total_analysis_duration / max(len(all_posts_data), 1)

        # 3. Save CSV
        df = pd.DataFrame(all_results)
        # Save CSV in scraped_data/YYYY-MM-DD/
        csv_path = os.path.join(base_output_dir, f"{username}_results.csv")
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        # Cleanup
        del scraper
        gc.collect()
        
        # Calculate skip count (posts skipped specifically because not event posters)
        skip_count = len([r for r in all_results if r.get('db_status') == 'Skipped (Not Event)'])
        
        report(f"Analysis complete. Saving results...", 90)
        print(f"[Automation] SUCCESS. Saved {saved_db_count} events to DB, skipped {skip_count} (not event posters).")
        
        return {
            "success": True, 
            "saved_count": saved_db_count, 
            "skip_count": skip_count,
            "scraped_count": len(all_posts_data),
            "csv_path": csv_path,
            "details": all_results,
            "stats": {
                "total_posts": len(all_posts_data),
                "total_scrape_sec": round(total_scrape_duration, 2),
                "avg_scrape_sec": round(avg_scrape_time, 2),
                "total_analysis_sec": round(total_analysis_duration, 2),
                "avg_analysis_sec": round(avg_analysis_time, 2)
            }
        }
        
    except Exception as e:
        print(f"[Automation] ERROR: {e}")
        # Return error structure instead of crashing thread if possible, but caller expects dict or raise
        raise e
