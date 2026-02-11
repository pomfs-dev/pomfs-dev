"""
Reanalyze API Blueprint
Provides endpoints for batch reanalysis of scraped_data/ images
Uses background thread to prevent connection timeout issues
"""
import os
import json
import time
import threading
from flask import Blueprint, render_template, request, jsonify
from reanalyze_utils import (
    scan_scraped_data, 
    get_available_dates, 
    get_accounts_for_date,
    get_reanalysis_batch,
    read_ocr_text,
    has_ocr_text
)
from db_utils import get_neon_connection, upsert_scraped_post
from geocoder import geocode_location
from gcs_uploader import upload_image_to_gcs
from db_helpers import save_to_dev_db

reanalyze_bp = Blueprint('reanalyze', __name__)

_reanalysis_state = {
    'running': False,
    'status': 'idle',
    'progress': 0,
    'current': 0,
    'total': 0,
    'stats': {
        'processed': 0,
        'events_detected': 0,
        'skipped_analyzed': 0,
        'skipped_no_ocr': 0,
        'errors': 0
    },
    'message': '',
    'error': None,
    'started_at': None,
    'completed_at': None
}
_reanalysis_lock = threading.Lock()

_ocr_state = {
    'running': False,
    'status': 'idle',
    'progress': 0,
    'current': 0,
    'total': 0,
    'stats': {
        'ocr_success': 0,
        'ocr_failed': 0,
        'skipped': 0
    },
    'message': '',
    'error': None,
    'started_at': None,
    'completed_at': None
}
_ocr_lock = threading.Lock()


def get_analyzed_shortcodes() -> set:
    """Get set of shortcodes already analyzed in Neon DB (with event_name)."""
    try:
        conn = get_neon_connection()
        cur = conn.cursor()
        cur.execute("SELECT shortcode FROM scraped_posts WHERE event_name IS NOT NULL")
        shortcodes = {row[0] for row in cur.fetchall()}
        conn.close()
        return shortcodes
    except Exception as e:
        print(f"[Reanalyze] Error fetching analyzed shortcodes: {e}")
        return set()


def _run_reanalysis(date_filter, username_filter, skip_analyzed):
    """Background thread function for reanalysis."""
    global _reanalysis_state
    
    try:
        from analyzer import MistralAnalyzer
        mistral_key = os.environ.get('MISTRAL_API_KEY') or os.environ.get('MISTRAL_API')
        if not mistral_key:
            with _reanalysis_lock:
                _reanalysis_state['running'] = False
                _reanalysis_state['status'] = 'error'
                _reanalysis_state['error'] = 'MISTRAL_API_KEY not configured'
            return
        
        analyzer = MistralAnalyzer(api_key=mistral_key)
        
        with _reanalysis_lock:
            _reanalysis_state['status'] = 'initializing'
            _reanalysis_state['message'] = 'Analyzer initialized'
        
        analyzed_shortcodes = get_analyzed_shortcodes() if skip_analyzed else set()
        
        scan_result = scan_scraped_data(date_filter, username_filter)
        total_images = len(scan_result['images'])
        
        with _reanalysis_lock:
            _reanalysis_state['status'] = 'processing'
            _reanalysis_state['total'] = total_images
            _reanalysis_state['message'] = f'Found {total_images} images'
        
        stats = {
            'processed': 0,
            'events_detected': 0,
            'skipped_analyzed': 0,
            'skipped_no_ocr': 0,
            'errors': 0
        }
        
        def update_progress(i):
            with _reanalysis_lock:
                _reanalysis_state['current'] = i + 1
                _reanalysis_state['progress'] = round((i + 1) / total_images * 100, 1) if total_images > 0 else 100
                _reanalysis_state['stats'] = stats.copy()
        
        if total_images == 0:
            with _reanalysis_lock:
                _reanalysis_state['running'] = False
                _reanalysis_state['status'] = 'completed'
                _reanalysis_state['progress'] = 100
                _reanalysis_state['message'] = 'No images to process'
                _reanalysis_state['completed_at'] = time.time()
            return
        
        for i, img in enumerate(scan_result['images']):
            with _reanalysis_lock:
                if not _reanalysis_state['running']:
                    _reanalysis_state['status'] = 'cancelled'
                    _reanalysis_state['message'] = 'Cancelled by user'
                    return
            
            shortcode = img['shortcode']
            
            if skip_analyzed and shortcode in analyzed_shortcodes:
                stats['skipped_analyzed'] += 1
                update_progress(i)
                continue
            
            ocr_text = read_ocr_text(img['path'])
            if not ocr_text:
                stats['skipped_no_ocr'] += 1
                update_progress(i)
                continue
            
            try:
                analysis_result = analyzer.parse_info(ocr_text)
                
                if analysis_result and analysis_result.get('is_event_poster'):
                    post_data = {
                        'shortcode': shortcode,
                        'caption': '',
                        'url': f"https://instagram.com/p/{shortcode}/",
                        'image_filepath': img['path'],
                        'date': img['date']
                    }
                    
                    dates_list = analysis_result.get('dates', [])
                    event_date = dates_list[0] if dates_list else None
                    artist = analysis_result.get('artist', '')
                    artists_list = [artist] if artist and artist != 'Various' else []
                    
                    venue = analysis_result.get('venue')
                    location = analysis_result.get('location')
                    country = analysis_result.get('country', 'KR')
                    
                    analyzed_data = {
                        'event_name': analysis_result.get('title'),
                        'venue': venue,
                        'artists': artists_list,
                        'event_date': event_date,
                        'event_time': analysis_result.get('time'),
                        'event_location': location,
                        'event_country': country
                    }
                    
                    upsert_scraped_post(img['username'], post_data, analyzed_data)
                    
                    try:
                        gcs_url = None
                        if os.path.exists(img['path']):
                            gcs_url = upload_image_to_gcs(img['path'], shortcode)
                        
                        lat, lng, formatted_addr, place_id = None, None, None, None
                        if venue or location:
                            lat, lng, formatted_addr, place_id = geocode_location(location, venue)
                        
                        if analyzed_data.get('event_name') and event_date:
                            import json
                            save_to_dev_db(
                                venue_name=venue,
                                event_name=analyzed_data['event_name'],
                                event_date=event_date,
                                event_dates_json=json.dumps([event_date]) if event_date else None,
                                content=ocr_text[:500] if ocr_text else None,
                                image_url=gcs_url,
                                artists_json=json.dumps(artists_list) if artists_list else None,
                                instagram_id=shortcode,
                                instagram_post_url=post_data['url'],
                                event_location=location,
                                is_draft=False,
                                latitude=lat,
                                longitude=lng,
                                formatted_address=formatted_addr,
                                place_id=place_id,
                                event_time=analyzed_data.get('event_time'),
                                event_country=country
                            )
                    except Exception as pub_err:
                        print(f"[Reanalyze] Publishing error for {shortcode}: {pub_err}")
                    
                    stats['events_detected'] += 1
                
                stats['processed'] += 1
                
            except Exception as e:
                stats['errors'] += 1
                print(f"[Reanalyze] Error analyzing {shortcode}: {e}")
            
            update_progress(i)
            time.sleep(0.1)
        
        with _reanalysis_lock:
            _reanalysis_state['running'] = False
            _reanalysis_state['status'] = 'completed'
            _reanalysis_state['progress'] = 100
            _reanalysis_state['stats'] = stats.copy()
            _reanalysis_state['message'] = f"Completed: {stats['events_detected']} events detected"
            _reanalysis_state['completed_at'] = time.time()
            
    except Exception as e:
        with _reanalysis_lock:
            _reanalysis_state['running'] = False
            _reanalysis_state['status'] = 'error'
            _reanalysis_state['error'] = str(e)
        print(f"[Reanalyze] Fatal error: {e}")


@reanalyze_bp.route('/reanalyze')
def reanalyze_page():
    """Render the reanalyze UI page."""
    dates = get_available_dates()
    return render_template('reanalyze.html', dates=dates)


@reanalyze_bp.route('/api/reanalyze/accounts')
def get_accounts():
    """Get accounts for a specific date."""
    date = request.args.get('date', '')
    if not date:
        return jsonify({'accounts': []})
    
    accounts = get_accounts_for_date(date)
    return jsonify({'accounts': accounts})


@reanalyze_bp.route('/api/reanalyze/scan')
def scan_endpoint():
    """Scan scraped_data and return statistics."""
    date_filter = request.args.get('date', None)
    username_filter = request.args.get('username', None)
    
    result = scan_scraped_data(date_filter, username_filter)
    
    analyzed_shortcodes = get_analyzed_shortcodes()
    already_analyzed = sum(1 for img in result['images'] 
                          if img['shortcode'] in analyzed_shortcodes)
    
    return jsonify({
        'total_images': result['total_images'],
        'ocr_completed': result['ocr_completed'],
        'ocr_pending': result['ocr_pending'],
        'already_analyzed': already_analyzed,
        'ready_for_analysis': result['total_images'] - already_analyzed,
        'dates': result['dates'][:10],
        'accounts_count': len(result['accounts'])
    })


@reanalyze_bp.route('/api/reanalyze/start', methods=['POST', 'GET'])
def start_reanalysis():
    """Start batch reanalysis in background thread."""
    global _reanalysis_state
    
    with _reanalysis_lock:
        if _reanalysis_state['running']:
            return jsonify({
                'success': False,
                'error': 'Reanalysis already running',
                'status': _reanalysis_state['status']
            })
    
    date_filter = request.args.get('date', None)
    username_filter = request.args.get('username', None)
    skip_analyzed = request.args.get('skip_analyzed', 'true').lower() == 'true'
    
    with _reanalysis_lock:
        _reanalysis_state = {
            'running': True,
            'status': 'starting',
            'progress': 0,
            'current': 0,
            'total': 0,
            'stats': {
                'processed': 0,
                'events_detected': 0,
                'skipped_analyzed': 0,
                'skipped_no_ocr': 0,
                'errors': 0
            },
            'message': 'Starting reanalysis...',
            'error': None,
            'started_at': time.time(),
            'completed_at': None
        }
    
    thread = threading.Thread(
        target=_run_reanalysis,
        args=(date_filter, username_filter, skip_analyzed),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Reanalysis started in background'
    })


@reanalyze_bp.route('/api/reanalyze/status')
def get_status():
    """Get current reanalysis status."""
    with _reanalysis_lock:
        return jsonify(_reanalysis_state.copy())


@reanalyze_bp.route('/api/reanalyze/stop', methods=['POST', 'GET'])
def stop_reanalysis():
    """Stop the running reanalysis."""
    global _reanalysis_state
    
    with _reanalysis_lock:
        if not _reanalysis_state['running']:
            return jsonify({
                'success': False,
                'message': 'No reanalysis is running'
            })
        
        _reanalysis_state['running'] = False
    
    return jsonify({
        'success': True,
        'message': 'Stop signal sent'
    })


def _run_ocr_missing(date_filter, username_filter):
    """Background OCR processing for images missing OCR text."""
    global _ocr_state
    
    try:
        from analyzer import MistralAnalyzer
        mistral_key = os.environ.get('MISTRAL_API_KEY') or os.environ.get('MISTRAL_API')
        if not mistral_key:
            with _ocr_lock:
                _ocr_state['running'] = False
                _ocr_state['status'] = 'error'
                _ocr_state['error'] = 'MISTRAL_API_KEY not configured'
            print("[OCR] MISTRAL_API_KEY not configured")
            return
        
        analyzer = MistralAnalyzer(api_key=mistral_key)
        print("[OCR] Initialized MistralAnalyzer for batch OCR")
    except Exception as e:
        with _ocr_lock:
            _ocr_state['running'] = False
            _ocr_state['status'] = 'error'
            _ocr_state['error'] = f'Failed to initialize analyzer: {e}'
        print(f"[OCR] Failed to initialize analyzer: {e}")
        return
    
    try:
        scan_result = scan_scraped_data(date_filter, username_filter)
        
        images_needing_ocr = [img for img in scan_result['images'] if not has_ocr_text(img['path'])]
        total_images = len(images_needing_ocr)
        
        with _ocr_lock:
            _ocr_state['total'] = total_images
            _ocr_state['message'] = f'Found {total_images} images without OCR'
        
        if total_images == 0:
            with _ocr_lock:
                _ocr_state['running'] = False
                _ocr_state['status'] = 'completed'
                _ocr_state['progress'] = 100
                _ocr_state['message'] = 'No images need OCR'
                _ocr_state['completed_at'] = time.time()
            return
        
        with _ocr_lock:
            _ocr_state['status'] = 'processing'
            _ocr_state['message'] = f'Processing {total_images} images...'
        
        stats = {
            'ocr_success': 0,
            'ocr_failed': 0,
            'skipped': 0
        }
        
        def update_ocr_progress(i):
            with _ocr_lock:
                _ocr_state['current'] = i + 1
                _ocr_state['progress'] = round((i + 1) / total_images * 100, 1) if total_images > 0 else 100
                _ocr_state['stats'] = stats.copy()
        
        for i, img in enumerate(images_needing_ocr):
            with _ocr_lock:
                if not _ocr_state['running']:
                    _ocr_state['status'] = 'cancelled'
                    _ocr_state['message'] = 'Cancelled by user'
                    return
            
            img_path = img['path']
            
            if not os.path.exists(img_path):
                stats['skipped'] += 1
                update_ocr_progress(i)
                continue
            
            try:
                ocr_text = analyzer.extract_text(img_path)
                
                ocr_txt_path = os.path.splitext(img_path)[0] + "_ocr.txt"
                with open(ocr_txt_path, 'w', encoding='utf-8') as f:
                    f.write(ocr_text if ocr_text else "")
                
                if ocr_text:
                    stats['ocr_success'] += 1
                    print(f"[OCR] Success: {img['shortcode']} ({len(ocr_text)} chars)")
                else:
                    stats['ocr_failed'] += 1
                    
            except Exception as e:
                stats['ocr_failed'] += 1
                print(f"[OCR] Error for {img['shortcode']}: {e}")
            
            update_ocr_progress(i)
            time.sleep(0.5)
        
        with _ocr_lock:
            _ocr_state['running'] = False
            _ocr_state['status'] = 'completed'
            _ocr_state['progress'] = 100
            _ocr_state['message'] = f'Completed: {stats["ocr_success"]} success, {stats["ocr_failed"]} failed'
            _ocr_state['completed_at'] = time.time()
        
        print(f"[OCR] Batch completed: {stats}")
        
    except Exception as e:
        with _ocr_lock:
            _ocr_state['running'] = False
            _ocr_state['status'] = 'error'
            _ocr_state['error'] = str(e)
        print(f"[OCR] Fatal error: {e}")


@reanalyze_bp.route('/api/reanalyze/ocr-missing/start', methods=['POST', 'GET'])
def start_ocr_missing():
    """Start batch OCR for images without OCR text."""
    global _ocr_state
    
    with _ocr_lock:
        if _ocr_state['running']:
            return jsonify({
                'success': False,
                'error': 'OCR already running',
                'status': _ocr_state['status']
            })
    
    date_filter = request.args.get('date', None)
    username_filter = request.args.get('username', None)
    
    with _ocr_lock:
        _ocr_state = {
            'running': True,
            'status': 'starting',
            'progress': 0,
            'current': 0,
            'total': 0,
            'stats': {
                'ocr_success': 0,
                'ocr_failed': 0,
                'skipped': 0
            },
            'message': 'Starting OCR batch...',
            'error': None,
            'started_at': time.time(),
            'completed_at': None
        }
    
    thread = threading.Thread(
        target=_run_ocr_missing,
        args=(date_filter, username_filter),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'OCR batch started in background'
    })


@reanalyze_bp.route('/api/reanalyze/ocr-missing/status')
def get_ocr_status():
    """Get current OCR batch status."""
    with _ocr_lock:
        return jsonify(_ocr_state.copy())


@reanalyze_bp.route('/api/reanalyze/ocr-missing/stop', methods=['POST', 'GET'])
def stop_ocr_missing():
    """Stop the running OCR batch."""
    global _ocr_state
    
    with _ocr_lock:
        if not _ocr_state['running']:
            return jsonify({
                'success': False,
                'message': 'No OCR batch is running'
            })
        
        _ocr_state['running'] = False
    
    return jsonify({
        'success': True,
        'message': 'Stop signal sent'
    })
