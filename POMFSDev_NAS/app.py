from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, send_from_directory
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
import os
import glob
import pandas as pd
import json
import shutil


def find_local_image(username, shortcode):
    """
    Dynamically find local image path for a scraped post.
    Searches scraped_data/*/username/shortcode*.jpg pattern.
    Returns relative path if found, None otherwise.
    """
    if not username or not shortcode:
        return None
    pattern = f"scraped_data/*/{username}/{shortcode}*.jpg"
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    pattern_png = f"scraped_data/*/{username}/{shortcode}*.png"
    matches_png = glob.glob(pattern_png)
    if matches_png:
        return matches_png[0]
    return None
from db_config import get_db_connection
from venue_discovery import search_instagram_id
from db_utils import init_scraped_posts_table, save_scraped_post, get_scraped_posts, delete_all_scraped_posts, get_collection_stats_by_usernames
import math
# from utils import send_email_notification  # Will implement later

app = Flask(__name__)

# Register Reanalyze Blueprint
from reanalyze_routes import reanalyze_bp
app.register_blueprint(reanalyze_bp)

# Initialize Neon DB tables on startup
try:
    init_scraped_posts_table()
except Exception as e:
    print(f"[Warning] Could not initialize Neon DB tables: {e}")
app.secret_key = 'super_secret_key_for_testing'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Import ENV from config
from db_config import ENV

@app.context_processor
def inject_env():
    return dict(env=ENV)

@app.route('/admin/reset_db', methods=['POST'])
def admin_reset_db():
    if ENV != 'TEST':
        return jsonify({'success': False, 'message': 'Only allowed in TEST mode'}), 403
    
    try:
        from init_test_db import init_test_db
        init_test_db()
        return jsonify({'success': True, 'message': 'Test DB Reset Successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/')
def index():
    conn = get_db_connection()
    stats = {
        'venues': conn.execute('SELECT COUNT(*) FROM venues').fetchone()[0],
        'artists': conn.execute("SELECT COUNT(*) FROM users WHERE role = 'artist'").fetchone()[0] if ENV!='TEST' else 0, # Simplify for test
        'events': conn.execute('SELECT COUNT(*) FROM posts').fetchone()[0]
    }
    
    # Fetch recent 5 events from posts table
    # Simplify query for Test DB (SQLite)
    # eventDates is TEXT: [{"date":"2025-..."}]
    recent_events = conn.execute('''
        SELECT 
            p.eventName, 
            p.eventDates,
            v.venueName, 
            p.performingArtists as artistName
        FROM posts p
        LEFT JOIN venues v ON p.venueId = v.id
        ORDER BY p.id DESC
        LIMIT 5
    ''').fetchall()
    
    # Process JSON dates for display
    processed_events = []
    for r in recent_events:
        d_str = r['eventDates']
        try:
            d_json = json.loads(d_str)
            date_display = d_json[0]['date'] if d_json else "No Date"
        except:
            date_display = d_str
            
        processed_events.append({
            'eventName': r['eventName'],
            'eventDate': date_display,
            'venueName': r['venueName'],
            'artistName': r['artistName']
        })
    
    conn.close()
    return render_template('index.html', stats=stats, recent_events=processed_events)

@app.route('/docs')
def docs():
    return render_template('codebase_audit.html')

@app.route('/events')
def events():
    conn = get_db_connection()
    all_events_rows = conn.execute('''
        SELECT 
            p.id,
            p.eventName, 
            p.eventDates,
            v.venueName, 
            p.performingArtists as artistName
        FROM posts p
        LEFT JOIN venues v ON p.venueId = v.id
        ORDER BY p.id DESC
    ''').fetchall()
    
    processed_events = []
    for r in all_events_rows:
        d_str = r['eventDates']
        try:
            d_json = json.loads(d_str)
            date_display = d_json[0]['date'] if d_json else "No Date"
        except:
            date_display = d_str
            
        processed_events.append({
            'id': r['id'],
            'eventName': r['eventName'],
            'eventDate': date_display,
            'venueName': r['venueName'],
            'artistName': r['artistName']
        })

    conn.close()
    return render_template('events.html', events=processed_events)

@app.route('/registered')
def registered():
    """View all registered events from MusicFeedPlatform Development Database."""
    from db_helpers import get_all_registered_events
    events = get_all_registered_events()
    return render_template('registered.html', events=events)

@app.route('/api/registered/publish', methods=['POST'])
def api_publish_events():
    """Publish selected draft events (set is_draft = false)."""
    from db_helpers import publish_events
    
    data = request.json
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'success': False, 'error': 'No IDs provided'}), 400
    
    try:
        published = publish_events(ids)
        return jsonify({'success': True, 'published': published})
    except Exception as e:
        print(f"[API] Publish events error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/registered/delete', methods=['POST'])
def api_delete_events():
    """Delete selected draft events."""
    from db_helpers import delete_events
    
    data = request.json
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'success': False, 'error': 'No IDs provided'}), 400
    
    try:
        deleted = delete_events(ids)
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        print(f"[API] Delete events error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/review')
def review():
    """Review page to view scraped posts from Neon DB."""
    try:
        username_filter = request.args.get('username', '')
        limit = int(request.args.get('limit', 50))
        
        effective_limit = None if limit == 0 else limit
        posts = get_scraped_posts(username=username_filter if username_filter else None, limit=effective_limit)
        
        for post in posts:
            local_path = find_local_image(post.get('source_username'), post.get('shortcode'))
            post['local_image_path'] = local_path
        
        all_posts = get_scraped_posts(limit=500)
        usernames = sorted(set(p['source_username'] for p in all_posts if p.get('source_username')))
        
        return render_template('review.html', 
                             posts=posts, 
                             usernames=usernames,
                             selected_username=username_filter,
                             limit=limit)
    except Exception as e:
        flash(f'데이터 로드 오류: {e}', 'error')
        return render_template('review.html', posts=[], usernames=[], selected_username='', limit=50)


@app.route('/scraped_data/<path:filepath>')
def serve_scraped_image(filepath):
    """Serve images from scraped_data folder."""
    return send_from_directory('scraped_data', filepath)

@app.route('/api/review/delete-all-scraped', methods=['POST'])
def api_delete_all_scraped():
    """Delete all scraped posts from Neon DB."""
    try:
        deleted_count = delete_all_scraped_posts()
        return jsonify({'success': True, 'deleted': deleted_count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/review/upload-to-dev-db', methods=['POST'])
def api_upload_to_dev_db():
    """Upload selected scraped posts to MusicFeedPlatform Development DB."""
    from db_helpers import save_to_dev_db
    from db_utils import get_neon_connection
    from psycopg2.extras import RealDictCursor
    import json
    
    data = request.json
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'success': False, 'error': 'No IDs provided'}), 400
    
    try:
        conn = get_neon_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(f"SELECT * FROM scraped_posts WHERE id IN ({placeholders})", ids)
        posts = cur.fetchall()
        
        cur.close()
        conn.close()
        
        uploaded = 0
        skipped = 0
        
        for post in posts:
            event_name = post.get('event_name')
            venue_name = post.get('event_venue') or ''
            artists = post.get('performing_artists') or []
            instagram_id = post.get('source_username') or post.get('user_id') or 'unknown'
            
            if not event_name:
                artist_name = artists[0] if artists else instagram_id
                if artist_name:
                    event_name = f"{artist_name} Live"
                    if venue_name:
                        event_name += f" at {venue_name}"
                elif venue_name:
                    event_name = f"Event at {venue_name}"
                else:
                    event_name = f"@{instagram_id} Event"
            content = post.get('content') or ''
            image_url = post.get('image_url') or ''
            
            event_dates = post.get('event_dates')
            event_date = None
            event_dates_json = '[]'
            
            if event_dates:
                if isinstance(event_dates, list) and len(event_dates) > 0:
                    event_date = event_dates[0].get('date') if isinstance(event_dates[0], dict) else None
                    event_dates_json = json.dumps(event_dates)
                elif isinstance(event_dates, str):
                    try:
                        parsed = json.loads(event_dates)
                        if parsed and len(parsed) > 0:
                            event_date = parsed[0].get('date')
                        event_dates_json = event_dates
                    except:
                        pass
            
            artists_json = json.dumps(artists) if isinstance(artists, list) else '[]'
            
            event_time = post.get('event_time') or ''
            event_country = post.get('event_country') or ''
            event_location = post.get('event_location') or ''
            instagram_post_url = post.get('instagram_link') or post.get('instagram_url') or ''
            
            result = save_to_dev_db(
                venue_name=venue_name,
                event_name=event_name,
                event_date=event_date,
                event_dates_json=event_dates_json,
                content=content,
                image_url=image_url,
                artists_json=artists_json,
                instagram_id=instagram_id,
                instagram_post_url=instagram_post_url,
                event_location=event_location,
                event_time=event_time,
                event_country=event_country
            )
            
            if result:
                uploaded += 1
            else:
                skipped += 1
        
        return jsonify({
            'success': True, 
            'uploaded': uploaded,
            'skipped': skipped
        })
        
    except Exception as e:
        print(f"[API] Upload to Dev DB error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('파일이 없습니다.', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        image_folder = request.form.get('image_folder', '').strip()
        
        if file.filename == '':
            flash('선택된 파일이 없습니다.', 'error')
            return redirect(request.url)
        
        if file:
            # Handle .xlsx for Batch Collection (Target List)
            if file.filename.endswith(('.xlsx', '.xls')):
                try:
                    os.makedirs('DB', exist_ok=True) # Ensure DB directory exists
                    target_path = os.path.join('DB', 'batch_targets.xlsx')
                    file.save(target_path)
                    
                    # Quick validation check
                    df = pd.read_excel(target_path, nrows=1)
                    
                    # Flexible column matching
                    possible_cols = ['userName', 'username', 'User Name', 'Username', 'IG ID', 'instagram_id']
                    found_col = None
                    for col in df.columns:
                        if col in possible_cols:
                            found_col = col
                            break
                    
                    if found_col:
                        # Normalize column for batch_collection route
                        # We might need to rewrite the file or just handle it in batch_collection
                        # Let's just handle it here by ensuring we know it's valid.
                        # Actually, batch_collection expects 'userName', so let's normalize the file if needed.
                        if found_col != 'userName':
                             df = pd.read_excel(target_path)
                             df.rename(columns={found_col: 'userName'}, inplace=True)
                             df.to_excel(target_path, index=False)
                             
                        flash('대상 목록이 업로드되었습니다. 일괄 처리 페이지로 이동합니다.', 'success')
                        return redirect(url_for('batch_collection'))
                    else:
                        flash('인스타그램 ID 컬럼(userName, username 등)이 없는 엑셀 파일입니다.', 'warning')
                        return redirect(request.url)
                except Exception as e:
                     flash(f'엑셀 처리 오류: {e}', 'error')
                     return redirect(request.url)

            # Handle CSV/JSON for Review (Old Logic)
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)
            
            # Parse CSV
            try:
                df = pd.read_csv(filepath)
                required_cols = ['filename', 'caption']
                for col in required_cols:
                    if col not in df.columns:
                        df[col] = ''
                
                # Fill NaN values with empty string to avoid TypeError
                df = df.fillna('')
                
                if 'dates_found' in df.columns:
                    df['dates_found'] = df['dates_found'].apply(lambda x: eval(x) if isinstance(x, str) and x.startswith('[') else [])
                else:
                    df['dates_found'] = []

                rows = df.to_dict('records')
                
                conn = get_db_connection()
                venues = conn.execute('SELECT * FROM venues').fetchall()
                users = conn.execute('SELECT * FROM users').fetchall()
                conn.close()
                
                return render_template('matching.html', rows=rows, filename=file.filename, venues=venues, users=users, image_folder=image_folder)
                
            except Exception as e:
                flash(f'파일 분석 중 오류 발생: {e}', 'error')
                return redirect(request.url)
            
    return render_template('upload.html')

@app.route('/batch_collection', methods=['GET', 'POST'])
def batch_collection():
    excel_path = os.path.join('DB', 'batch_targets.xlsx')

    # Handle Upload or Delete
    if request.method == 'POST':
        # Check for Delete capability
        if 'action' in request.form and request.form['action'] == 'delete':
            if os.path.exists(excel_path):
                os.remove(excel_path)
                flash('리스트가 삭제되었습니다.', 'success')
            return redirect(url_for('batch_collection'))

        if 'file' not in request.files:
            flash('파일이 없습니다.', 'error')
            return redirect(request.url)
        # ... (rest of upload logic)
        file = request.files['file']
        if file.filename == '':
            flash('파일을 선택해주세요.', 'error')
            return redirect(request.url)
        
        if file:
            try:
                # Save file
                file.save(excel_path)
                
                # Normalize Columns
                df = pd.read_excel(excel_path)
                possible_cols = ['username', 'User Name', '아이디', 'Account']
                found_col = None
                for col in df.columns:
                    if col == 'userName':
                        found_col = 'userName'
                        break
                    if col in possible_cols:
                        found_col = col
                        break
                
                if found_col:
                     if found_col != 'userName':
                         df.rename(columns={found_col: 'userName'}, inplace=True)
                         df.to_excel(excel_path, index=False)
                     flash('리스트가 업로드되었습니다.', 'success')
                else:
                     flash('엑셀 파일에 "userName" 또는 "username" 컬럼이 필요합니다.', 'warning')
                     # We don't delete the file, but user might see empty list or old list if read fails?
                     # Actually if read fails or col missing, we might want to not show data?
                     # For now, let's just warn.
                
                return redirect(url_for('batch_collection'))
            except Exception as e:
                flash(f'업로드 오류: {e}', 'error')
                return redirect(request.url)

    # Handle View
    try:
        rows = []
        page = int(request.args.get('page', 1))
        per_page = 50
        total_pages = 0
        total_rows = 0
        collection_stats = {}

        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path)
            
            # Ensure columns exist
            for col in ['userName', 'fullName']:
                if col not in df.columns:
                    df[col] = ''
            
            total_rows = len(df)
            total_pages = math.ceil(total_rows / per_page)
            
            start = (page - 1) * per_page
            end = start + per_page
            sliced_df = df.iloc[start:end].copy()
            
            sliced_df = sliced_df.fillna('')
            rows = sliced_df.to_dict('records')
            
            # Get collection stats for usernames on this page
            usernames = [row.get('userName', '').strip() for row in rows if row.get('userName', '').strip()]
            if usernames:
                try:
                    collection_stats = get_collection_stats_by_usernames(usernames)
                except Exception as e:
                    print(f"[Warning] Could not get collection stats: {e}")
        
        return render_template('batch_collection.html',
                               rows=rows,
                               page=page,
                               total_pages=total_pages,
                               total_rows=total_rows,
                               collection_stats=collection_stats)
                               
    except Exception as e:
        flash(f'일괄 처리 페이지 로드 오류: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/api/batch_accounts', methods=['GET'])
def api_batch_accounts():
    excel_path = os.path.join('DB', 'batch_targets.xlsx')
    
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        
        if not os.path.exists(excel_path):
            return jsonify([])
        
        df = pd.read_excel(excel_path)
        
        for col in ['userName', 'fullName']:
            if col not in df.columns:
                df[col] = ''
        
        df = df.fillna('')
        
        start = (page - 1) * limit
        end = start + limit
        sliced_df = df.iloc[start:end].copy()
        
        return jsonify(sliced_df.to_dict('records'))
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/batch_collection_status', methods=['GET'])
def api_batch_collection_status():
    """Get collection status for batch accounts. Supports page parameter for page-specific stats."""
    excel_path = os.path.join('DB', 'batch_targets.xlsx')
    page = request.args.get('page', type=int)
    limit = request.args.get('limit', 50, type=int)
    
    try:
        if not os.path.exists(excel_path):
            return jsonify({'total': 0, 'collected': 0, 'uncollected': 0, 'first_uncollected_index': 0, 'first_uncollected_global': 0})
        
        df = pd.read_excel(excel_path)
        if 'userName' not in df.columns:
            return jsonify({'total': 0, 'collected': 0, 'uncollected': 0, 'first_uncollected_index': 0, 'first_uncollected_global': 0})
        
        all_usernames = [str(u).strip() for u in df['userName'].tolist() if str(u).strip()]
        total_count = len(all_usernames)
        
        if total_count == 0:
            return jsonify({'total': 0, 'collected': 0, 'uncollected': 0, 'first_uncollected_index': 0, 'first_uncollected_global': 0})
        
        # Get collection stats for all usernames
        collection_stats = get_collection_stats_by_usernames(all_usernames)
        
        # Calculate global stats
        global_collected = sum(1 for u in all_usernames if u in collection_stats and collection_stats[u]['post_count'] > 0)
        
        # Find global first uncollected index (1-based)
        first_uncollected_global = 0
        for i, username in enumerate(all_usernames):
            if not (username in collection_stats and collection_stats[username]['post_count'] > 0):
                first_uncollected_global = i + 1
                break
        if first_uncollected_global == 0:
            first_uncollected_global = total_count + 1
        
        # If page is specified, calculate page-specific stats
        if page is not None and page >= 1:
            start_idx = (page - 1) * limit
            end_idx = min(start_idx + limit, total_count)
            page_usernames = all_usernames[start_idx:end_idx]
            
            page_total = len(page_usernames)
            page_collected = sum(1 for u in page_usernames if u in collection_stats and collection_stats[u]['post_count'] > 0)
            page_uncollected = page_total - page_collected
            
            # Find first uncollected on this page (1-based index within page)
            first_uncollected_on_page = 0
            for i, username in enumerate(page_usernames):
                if not (username in collection_stats and collection_stats[username]['post_count'] > 0):
                    first_uncollected_on_page = i + 1  # 1-based within page
                    break
            
            # Global index of first uncollected on this page
            first_uncollected_global_on_page = start_idx + first_uncollected_on_page if first_uncollected_on_page > 0 else 0
            
            return jsonify({
                'total': total_count,
                'collected': global_collected,
                'page': page,
                'page_total': page_total,
                'page_collected': page_collected,
                'page_uncollected': page_uncollected,
                'first_uncollected_on_page': first_uncollected_on_page,
                'first_uncollected_global_on_page': first_uncollected_global_on_page,
                'first_uncollected_global': first_uncollected_global
            })
        
        # No page specified - return global stats
        return jsonify({
            'total': total_count,
            'collected': global_collected,
            'uncollected': total_count - global_collected,
            'first_uncollected_index': first_uncollected_global,
            'first_uncollected_global': first_uncollected_global
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/collection_stats', methods=['POST'])
def api_collection_stats():
    """Get collection stats for specific usernames."""
    try:
        data = request.get_json()
        usernames = data.get('usernames', [])
        
        if not usernames:
            return jsonify({})
        
        stats = get_collection_stats_by_usernames(usernames)
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save', methods=['POST'])
def save_data():
    from utils import send_email_notification
    from db_helpers import save_single_event
    try:
        data = request.form
        image_src_folder = data.get('image_folder_path', '')
        
        idx = 0
        saved_count = 0
        
        while f'filename_{idx}' in data:
            event_data = {
                'filename': data.get(f'filename_{idx}'),
                'event_date': data.get(f'date_{idx}'),
                'event_name': data.get(f'eventName_{idx}'),
                'content': data.get(f'content_{idx}'),
                'venue_id': data.get(f'venueId_{idx}'),
                'new_venue': data.get(f'new_venue_{idx}'),
                'artist_id': data.get(f'artistId_{idx}'),
                'new_artist': data.get(f'new_artist_{idx}'),
                'image_src_folder': image_src_folder
            }
            
            if save_single_event(event_data):
                saved_count += 1
            
            idx += 1
            
        if saved_count > 0:
            send_email_notification(saved_count)
        
        flash(f'성공적으로 {saved_count}건의 공연 정보가 저장되었습니다.', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        flash(f'저장 중 오류 발생: {e}', 'error')
        return redirect(url_for('upload_file'))

@app.route('/delete_all', methods=['POST'])
def delete_all():
    # 1. Clear DB
    conn = get_db_connection()
    try:
        if ENV == 'TEST':
             conn.execute('DELETE FROM posts')
             conn.execute('DELETE FROM venueEvents')
             conn.execute('DELETE FROM venues')
             # Reset AutoIncrement?
             conn.execute('DELETE FROM sqlite_sequence WHERE name="posts"')
             conn.execute('DELETE FROM sqlite_sequence WHERE name="venues"')
             conn.execute('DELETE FROM sqlite_sequence WHERE name="venueEvents"')
        else:
            # Production Tables
            conn.execute('DELETE FROM venue_event_artists')
            conn.execute('DELETE FROM venue_events')
            conn.execute('DELETE FROM users WHERE role != "admin"') # Safety?
            # Creating venue_event_artists if not exists in prod for safety not needed here.
            # Just keep legacy behavior for non-TEST if that was working, or update if we migrated logic.
            # Assuming PROD matches db_schema_performance.json but legacy code used venue_event_artists
            conn.execute('DELETE FROM venues')
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f'삭제 중 오류 발생: {e}', 'error')
    finally:
        conn.close()
    
    # 2. Clear Images
    static_images_dir = 'static/images'
    if os.path.exists(static_images_dir):
        shutil.rmtree(static_images_dir)
        os.makedirs(static_images_dir)
        
    flash('모든 데이터와 이미지가 초기화되었습니다.', 'success')
    return redirect(url_for('index'))

@app.route('/scrape', methods=['GET', 'POST'])
def scrape_instagram():
    """
    Standard route to render the UI.
    """
    return render_template('scrape.html')

# @app.route('/scrape_stream')
def scrape_stream_legacy():
    from flask import Response, stream_with_context
    raw_username = request.args.get('username')
    limit = int(request.args.get('limit', 3))
    
    def generate():
        import json
        import time
        import unicodedata # Added for caption normalization
        from automation import extract_username
        
        try:
            if not raw_username:
                yield f"data: {json.dumps({'error': 'No username provided'})}\n\n"
                return

            username = extract_username(raw_username)
            yield f"data: {json.dumps({'progress': 5, 'message': f'Connecting to Instagram for {username}...'})}\n\n"
            
            # 1. Scrape Setup
            from scraper import InstagramScraper
            scraper = InstagramScraper()
            
            yield f"data: {json.dumps({'progress': 10, 'message': 'Starting download...'})}\n\n"
            
            # Scrape Loop
            # Store post data including shortcode for later analysis
            all_posts_data = [] # To store post info including shortcode
            # scraper yields (count, post_dict)
            for i, post in scraper.get_recent_posts_iter(username, limit=limit):
                # post is a dictionary now
                post_data = {
                    "filename_prefix": os.path.splitext(os.path.basename(post['image_filepath']))[0], 
                    "caption": post['caption'] or "",
                    "extracted_texts": [], # Will be filled by analyzer
                    "shortcode": post['shortcode'],
                    "post_date": post['date'].strftime('%Y-%m-%d %H:%M') if post['date'] else ""
                }
                if post['caption']:
                    post_data["caption"] = unicodedata.normalize('NFKC', post['caption'])
                all_posts_data.append(post_data)
                
                # Save to Neon DB
                try:
                    save_scraped_post(username, post)
                    yield f"data: {json.dumps({'progress': 10 + int(((i) / limit) * 40), 'message': f'Downloaded & saved post {i}/{limit} to DB'})}\n\n"
                except Exception as db_err:
                    print(f"[DB Save Error] {db_err}")
                    yield f"data: {json.dumps({'progress': 10 + int(((i) / limit) * 40), 'message': f'Downloaded post {i}/{limit} (DB save failed)'})}\n\n"
            
            yield f"data: {json.dumps({'progress': 50, 'message': 'Download complete. Starting analysis...'})}\n\n"
            
            # 2. Analyze Setup
            from analyzer import ImageAnalyzer, MistralAnalyzer
            mistral_key = os.environ.get("MISTRAL_API_KEY")
            if mistral_key:
                analyzer = MistralAnalyzer(api_key=mistral_key)
                yield f"data: {json.dumps({'progress': 52, 'message': 'Mistral OCR Engine initialized.'})}\n\n"
            else:
                analyzer = ImageAnalyzer()
                yield f"data: {json.dumps({'progress': 52, 'message': 'EasyOCR Engine initialized.'})}\n\n"
                
            targets_dir = username
            if not os.path.exists(targets_dir):
                 yield f"data: {json.dumps({'error': 'Target directory not found'})}\n\n"
                 return
                 
            # Process each post data
            all_results = []
            total_posts = len(all_posts_data)
            
            if total_posts == 0:
                yield f"data: {json.dumps({'progress': 100, 'message': 'No posts found to analyze.'})}\n\n"
            
            for idx, p_data in enumerate(all_posts_data):
                # Find the actual image file based on filename_prefix
                image_files_for_post = [f for f in os.listdir(targets_dir) if f.startswith(p_data["filename_prefix"]) and f.endswith(('.jpg', '.png'))]
                
                if not image_files_for_post:
                    yield f"data: {json.dumps({'progress': 50 + int(((idx + 1) / total_posts) * 40), 'message': f'No image found for post {idx+1}. Skipping.'})}\n\n"
                    continue

                # Assuming one image per post for now, or take the first one
                filename = image_files_for_post[0]
                filepath = os.path.join(targets_dir, filename)
                
                # 50% to 90%
                pct = 50 + int(((idx + 1) / total_posts) * 40)
                yield f"data: {json.dumps({'progress': pct, 'message': f'Analyzing post {idx+1}/{total_posts} : {filename}'})}\n\n"
                
                extracted_text = analyzer.extract_text(filepath)
                
                txt_path = os.path.join(targets_dir, os.path.splitext(filename)[0] + "_ocr.txt")
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(extracted_text)
                    
                # 1. Parse OCR
                parsed_ocr = analyzer.parse_info(extracted_text)
                
                # 2. Parse Caption (from stored post_data)
                caption_text = p_data["caption"]
                parsed_cap = {"dates": [], "venue": "", "artist": "", "title": ""}
                if caption_text:
                    parsed_cap = analyzer.parse_info(caption_text)
                
                # 3. Merge Strategies (Priority: Caption > OCR)
                final_dates = parsed_cap['dates'] + parsed_ocr['dates']
                final_dates = list(dict.fromkeys(final_dates)) # Dedupe preserving order
                
                # Prefer caption title if available, else OCR title
                final_title = parsed_cap.get('title') or parsed_ocr.get('title') or ""
                
                # Prefer caption venue if available
                final_venue = parsed_cap.get('venue') or parsed_ocr.get('venue') or ""
                
                # Prefer caption artist if available
                final_artist = parsed_cap.get('artist') or parsed_ocr.get('artist') or ""
                
                # Fallback: Use username as artist if nothing found
                if not final_artist and username:
                    final_artist = username

                # --- NEW: Known Venue Lookup Fallback ---
                # If venue is still empty, check against known venues in DB
                if not final_venue:
                    try:
                        conn = get_db_connection()
                        known_venues = conn.execute("SELECT venueName FROM venues").fetchall()
                        conn.close()
                        
                        # Search in Caption first, then OCR
                        search_text = (caption_text + " " + extracted_text).lower()
                        
                        for v in known_venues:
                            v_name = v['venueName']
                            # Simple substring check (case-insensitive)
                            if v_name.lower() in search_text:
                                final_venue = v_name
                                break
                    except Exception as e:
                        print(f"Error in venue lookup: {e}")
                # ----------------------------------------

                all_results.append({
                    "filename": filename,
                    "extracted_text": extracted_text, # This comes from analyzer.extract_text(filepath)
                    "dates_found": final_dates,      # This comes from the merge logic
                    "caption": caption_text,         # This comes from p_data["caption"]
                    "inferred_venue": final_venue,
                    "inferred_artist": final_artist,
                    "event_name": final_title,
                    "shortcode": p_data["shortcode"],
                    "post_date": p_data["post_date"] # This is the new field from p_data
                })
            
            # 3. Finalize
            yield f"data: {json.dumps({'progress': 95, 'message': 'Saving results...'})}\n\n"
            
            df = pd.DataFrame(all_results)
            csv_path = f"{username}_results.csv"
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            
            # Need to pass data to matching page. 
            # Since this is a stream, we can't render_template.
            # We must tell client to redirect with necessary params.
            # But redirecting with params like rows/db data via GET is bad.
            # Better approach: Save result to a temp location or just load it in the next request.
            # Or simplified: Client redirects to /upload logic but points to the generated CSV?
            # Let's create a wrapper route: /load_result?csv=...
            
            yield f"data: {json.dumps({'progress': 100, 'message': 'Done!', 'redirect': f'/load_result?csv_path={csv_path}'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/load_result')
def load_result():
    """
    Helper to load generated CSV and render matching page.
    """
    csv_path = request.args.get('csv_path')
    print(f"[DEBUG] load_result called with csv_path: {csv_path}")
    
    # Check if path exists as is (absolute or relative)
    if not csv_path or not os.path.exists(csv_path):
        # Fallback: Search in scraped_data RECURSIVELY if filename only
        found = False
        if csv_path:
             target_name = os.path.basename(csv_path)
             scraped_root = 'scraped_data'
             if os.path.exists(scraped_root):
                 for root, dirs, files in os.walk(scraped_root):
                     if target_name in files:
                         csv_path = os.path.join(root, target_name)
                         found = True
                         break
        
        if not found:
             print(f"[DEBUG] load_result: File not found: {csv_path} (Fallback search also failed)")
             flash(f'결과 파일을 찾을 수 없습니다: {csv_path}', 'error')
             return redirect(url_for('scrape_instagram'))

    try:
        print(f"[DEBUG] load_result: Reading CSV...")
        df = pd.read_csv(csv_path)
        required_cols = ['filename', 'caption']
        for col in required_cols:
            if col not in df.columns:
                df[col] = ''
        
        df = df.fillna('')
        
        if 'dates_found' in df.columns:
            df['dates_found'] = df['dates_found'].apply(lambda x: eval(x) if isinstance(x, str) and x.startswith('[') else [])
        else:
            df['dates_found'] = []

        rows = df.to_dict('records')
        
        print(f"[DEBUG] load_result: DB Connection...")
        conn = get_db_connection()
        venues = conn.execute('SELECT * FROM venues').fetchall()
        users = conn.execute('SELECT * FROM users').fetchall()
        conn.close()
        
        # Infer image folder from CSV path 
        # New structure: scraped_data/username/
        # csv is at scraped_data/username_results.csv
        # username can be derived from filename
        
        basename = os.path.basename(csv_path)
        username = basename.replace('_results.csv', '')
        
        # Use absolute path to be safe
        base_dir = os.path.dirname(os.path.abspath(csv_path))
        image_folder_path = os.path.join(base_dir, username)
        
        print(f"[DEBUG] load_result: Rendering matching.html...")
        return render_template('matching.html', rows=rows, filename=csv_path, venues=venues, users=users, image_folder=image_folder_path)
        
    except Exception as e:
        print(f"[DEBUG] load_result: Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        flash(f'결과 로드 중 오류: {e}', 'error')
        return redirect(url_for('scrape_instagram'))


@app.route('/discovery', methods=['GET', 'POST'])
def venue_discovery():
    try:
        # File paths
        upload_dir = 'DB'
        target_filename = 'user_uploaded_venues.xlsx'
        excel_path = os.path.join(upload_dir, target_filename)
        
        # Handle File Upload
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('파일이 없습니다.', 'error')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                flash('파일을 선택해주세요.', 'error')
                return redirect(request.url)
            if file and file.filename.endswith(('.xlsx', '.xls')):
                file.save(excel_path)
                flash('파일이 업로드되었습니다. 분석을 시작합니다.', 'success')
                return redirect(url_for('venue_discovery'))
            else:
                flash('엑셀 파일(.xlsx, .xls)만 업로드 가능합니다.', 'error')
                return redirect(request.url)

        # Pagination logic
        page = int(request.args.get('page', 1))
        per_page = 50
        
        # Check if file exists
        if not os.path.exists(excel_path):
            # Render template with "No Data" state
            return render_template('venue_discovery.html', 
                                   rows=[], 
                                   page=1, 
                                   total_pages=0,
                                   total_rows=0,
                                   no_file=True)
            
        df = pd.read_excel(excel_path)
        
        # Normalize columns if needed (Optional robustness)
        # We need: venue_name, country, city, main_genre
        # Map if slightly different? For now assume strict or give feedback.
        required_cols = ['venue_name'] # Minimal requirement
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
             # Try fallback mapping or error
             # e.g. 'Venue' -> 'venue_name'
             rename_map = {
                 'Venue': 'venue_name', 'Name': 'venue_name', '이름': 'venue_name',
                 'Country': 'country', '국가': 'country',
                 'City': 'city', '도시': 'city',
                 'Genre': 'main_genre', '장르': 'main_genre'
             }
             df.rename(columns=rename_map, inplace=True)
             
        # Create missing columns with empty string
        for col in ['country', 'city', 'main_genre', 'instagram_id']:
            if col not in df.columns:
                df[col] = ''
        
        # --- Persistence: Load Saved IDs ---
        json_path = os.path.join('DB', 'venue_instagram_map.json')
        saved_map = {}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    saved_map = json.load(f)
            except:
                pass # Ignore load error
        # -----------------------------------
        
        # Pagination logic
        total_rows = len(df)
        total_pages = math.ceil(total_rows / per_page)
        
        # Slice dataframe
        start = (page - 1) * per_page
        end = start + per_page
        sliced_df = df.iloc[start:end].copy() # Ensure copy to modify
        
        # Inject Saved IDs
        def get_saved_id(row):
            # Prioritize saved ID if exists, otherwise keep existing excel value or None
            # Actually, user wants to find IDs. If Excel has it, great.
            # But the map is the source of "Found by App".
            # Let's fallback: Map > Excel > None
            saved = saved_map.get(row['venue_name'], None)
            if saved: return saved
            return row['instagram_id'] if pd.notna(row['instagram_id']) else None
            
        sliced_df['instagram_id'] = sliced_df.apply(get_saved_id, axis=1)
        sliced_df = sliced_df.fillna('') # Clean NaNs for JSON serialization
        
        # Convert to dict
        rows = sliced_df.to_dict('records')
        
        return render_template('venue_discovery.html', 
                               rows=rows, 
                               page=page, 
                               total_pages=total_pages,
                               total_rows=total_rows,
                               no_file=False)
                               
    except Exception as e:
        flash(f'오류 발생: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/api/search_venue')
def api_search_venue():
    venue_name = request.args.get('venue_name')
    if not venue_name:
        return {'error': 'No venue name provided'}, 400
        
    # Check persistence first (optional caching optimization)
    # But user might want to re-search, so let's allow re-searching.
    # ...
        
    found_id = search_instagram_id(venue_name)
    
    if found_id:
        # --- Persistence: Save ID ---
        try:
            json_path = os.path.join('DB', 'venue_instagram_map.json')
            saved_map = {}
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        saved_map = json.load(f)
                except:
                    pass
            
            saved_map[venue_name] = found_id
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(saved_map, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving to JSON: {e}")
        # ----------------------------
        
        return {'success': True, 'instagram_id': found_id}
    else:
        return {'success': False, 'message': 'Not found'}

@app.route('/api/reset_discovery', methods=['POST'])
def api_reset_discovery():
    try:
        data = request.json
        scope = data.get('scope', 'all')
        
        json_path = os.path.join('DB', 'venue_instagram_map.json')
        excel_path = os.path.join('DB', 'user_uploaded_venues.xlsx')
        
        if scope == 'all':
            # 1. Reset Findings (JSON)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=4, ensure_ascii=False)
                
            # 2. Reset Source List (Excel) - Because user expects "List content to disappear"
            if os.path.exists(excel_path):
                os.remove(excel_path)
                
            return {'success': True, 'message': 'All discovery data and list reset.'}
            
        elif scope == 'single':
            venue_name = data.get('venue_name')
            if not venue_name:
                return {'error': 'Venue name required for single reset'}, 400
                
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    saved_map = json.load(f)
                
                if venue_name in saved_map:
                    del saved_map[venue_name]
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(saved_map, f, indent=4, ensure_ascii=False)
            return {'success': True, 'message': f'Reset data for {venue_name}'}
            
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/api/reset_excel', methods=['POST'])
def api_reset_excel():
    try:
        upload_dir = 'DB'
        target_filename = 'user_uploaded_venues.xlsx'
        excel_path = os.path.join(upload_dir, target_filename)
        
        if os.path.exists(excel_path):
            os.remove(excel_path)
            return {'success': True, 'message': 'Excel file deleted'}
        else:
            return {'success': True, 'message': 'File already gone'}
            
    except Exception as e:
        return {'error': str(e)}, 500



@app.route('/api/search_venue_google')
def api_search_venue_google():
    from selenium_search import search_google_selenium
    
    venue_name = request.args.get('venue_name')
    city = request.args.get('city', '')
    country = request.args.get('country', '')
    
    if not venue_name:
        return {'error': 'No venue name provided'}, 400
        
    print(f"Requesting Deep Search for: {venue_name} ({city}, {country})")
    
    found_id = search_google_selenium(venue_name, city, country)
    
    if found_id:
        # --- Persistence: Save ID ---
        try:
            json_path = os.path.join('DB', 'venue_instagram_map.json')
            saved_map = {}
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        saved_map = json.load(f)
                except:
                    pass
            
            saved_map[venue_name] = found_id
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(saved_map, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving to JSON: {e}")
        # ----------------------------
        
        return {'success': True, 'instagram_id': found_id}
    else:
        return {'success': False, 'message': 'Not found in Deep Search'}

@app.route('/api/save_manual_id', methods=['POST'])
def api_save_manual_id():
    try:
        data = request.json
        venue_name = data.get('venue_name')
        instagram_id = data.get('instagram_id')
        
        if not venue_name or not instagram_id:
            return {'success': False, 'error': 'Missing fields'}, 400
            
        # --- Persistence: Save ID ---
        json_path = os.path.join('DB', 'venue_instagram_map.json')
        saved_map = {}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    saved_map = json.load(f)
            except:
                pass
        
        saved_map[venue_name] = instagram_id
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(saved_map, f, indent=4, ensure_ascii=False)
        # ----------------------------

        return {'success': True, 'message': 'Saved manually'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500

@app.route('/api/discovery/scrape_venue', methods=['POST'])
def api_discovery_scrape_venue():
    """Scrape and analyze posts for a discovered venue Instagram ID.
    Uses the full pipeline: Apify → OCR → LLM → GCS → Geocoding → MusicFeed DB
    """
    import threading
    from automation import run_full_scrape_process
    
    data = request.json
    instagram_id = data.get('instagram_id')
    venue_name = data.get('venue_name')
    limit = data.get('limit', 5)
    
    if not instagram_id:
        return jsonify({'success': False, 'error': 'No Instagram ID provided'}), 400
    
    def task(username, venue, lim):
        try:
            result = run_full_scrape_process(
                raw_username=username,
                limit=lim,
                limit_type="posts",
                known_venue_name=venue,
                auto_save_db=True
            )
            print(f"[Discovery] Completed scrape for {username}: saved={result.get('saved_count', 0)}")
        except Exception as e:
            print(f"[Discovery] Scrape failed for {username}: {e}")
    
    thread = threading.Thread(target=task, args=(instagram_id, venue_name, limit))
    thread.start()
    
    return jsonify({
        'success': True,
        'message': f'Started scraping {instagram_id} with full pipeline'
    })

@app.route('/api/discovery/batch_scrape', methods=['POST'])
def api_discovery_batch_scrape():
    """Batch scrape all discovered venues with Instagram IDs.
    Uses the full pipeline for each venue.
    """
    import threading
    from automation import run_full_scrape_process
    
    data = request.json
    limit_per_venue = data.get('limit', 3)
    
    json_path = os.path.join('DB', 'venue_instagram_map.json')
    if not os.path.exists(json_path):
        return jsonify({'success': False, 'error': 'No discovered venues found'}), 400
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            venue_map = json.load(f)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to load venues: {e}'}), 500
    
    if not venue_map:
        return jsonify({'success': False, 'error': 'No venues with Instagram IDs'}), 400
    
    def batch_task(venues, lim):
        for venue_name, instagram_id in venues.items():
            try:
                print(f"[Discovery Batch] Processing {venue_name} ({instagram_id})...")
                result = run_full_scrape_process(
                    raw_username=instagram_id,
                    limit=lim,
                    limit_type="posts",
                    known_venue_name=venue_name,
                    auto_save_db=True
                )
                print(f"[Discovery Batch] {venue_name}: saved={result.get('saved_count', 0)}")
            except Exception as e:
                print(f"[Discovery Batch] Failed for {venue_name}: {e}")
    
    thread = threading.Thread(target=batch_task, args=(venue_map.copy(), limit_per_venue))
    thread.start()
    
    return jsonify({
        'success': True,
        'message': f'Started batch scraping {len(venue_map)} venues',
        'total_venues': len(venue_map)
    })

@app.route('/api/add_manual_venue', methods=['POST'])
def api_add_manual_venue():
    try:
        data = request.json
        venue_name = data.get('venue_name')
        city = data.get('city', '')
        country = data.get('country', '')
        
        if not venue_name:
            return {'success': False, 'error': 'Venue Name is required'}, 400
            
        target_filename = 'user_uploaded_venues.xlsx'
        upload_dir = 'DB'
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            
        excel_path = os.path.join(upload_dir, target_filename)
        
        new_data = {
            'venue_name': [venue_name],
            'city': [city],
            'country': [country],
            'main_genre': ['Manual Input'],
            'instagram_id': [None]
        }
        new_df = pd.DataFrame(new_data)
        
        if os.path.exists(excel_path):
            existing_df = pd.read_excel(excel_path)
            # Normalize columns if needed to avoid mismatch
            for col in ['venue_name', 'city', 'country', 'main_genre', 'instagram_id']:
                if col not in existing_df.columns:
                    existing_df[col] = ''
            
            # Prepend new row
            updated_df = pd.concat([new_df, existing_df], ignore_index=True)
        else:
            updated_df = new_df
            
        updated_df.to_excel(excel_path, index=False)
        
        return {'success': True, 'message': 'Added to list'}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}, 500

@app.route('/api/scrape_background', methods=['POST'])
def api_scrape_background():
    import threading
    from automation import run_full_scrape_process
    
    data = request.json
    username = data.get('username')
    limit = data.get('limit', 3)
    
    if not username:
        return {'error': 'No username provided'}, 400
        
    def task(u, l):
        try:
            run_full_scrape_process(u, limit=l)
        except Exception as e:
            print(f"Background scrape failed for {u}: {e}")
            
    thread = threading.Thread(target=task, args=(username, limit))
    thread.start()
    
    return {'success': True, 'message': 'Started background scraping'}

# --- Real-Time Progress Store ---
# Simple in-memory storage: { task_id: { status: 'running', progress: 0, logs: [], result: None } }
TASK_STORE = {}

# --- Batch Session Store ---
# Stores the current batch collection session state for page navigation persistence
BATCH_SESSION = {
    'active': False,
    'session_id': None,
    'status': None,  # 'running', 'completed', 'stopped'
    'start_page': 1,
    'total_accounts': 0,
    'completed_count': 0,
    'task_ids': [],  # List of active task IDs
    'started_at': None,
    'logs': []
}

@app.route('/api/batch_session', methods=['POST'])
def api_batch_session():
    """Manage batch session state."""
    import uuid
    from datetime import datetime
    
    data = request.json
    action = data.get('action')
    
    if action == 'start':
        BATCH_SESSION['active'] = True
        BATCH_SESSION['session_id'] = str(uuid.uuid4())
        BATCH_SESSION['status'] = 'running'
        BATCH_SESSION['start_page'] = data.get('page', 1)
        BATCH_SESSION['total_accounts'] = data.get('total_accounts', 0)
        BATCH_SESSION['completed_count'] = 0
        BATCH_SESSION['task_ids'] = []
        BATCH_SESSION['started_at'] = datetime.now().isoformat()
        BATCH_SESSION['logs'] = [f"Batch started at page {BATCH_SESSION['start_page']}"]
        
        return jsonify({'success': True, 'session_id': BATCH_SESSION['session_id']})
    
    elif action == 'update':
        if BATCH_SESSION['active']:
            if 'completed_count' in data:
                BATCH_SESSION['completed_count'] = data['completed_count']
            if 'task_id' in data:
                if data['task_id'] not in BATCH_SESSION['task_ids']:
                    BATCH_SESSION['task_ids'].append(data['task_id'])
            if 'log' in data:
                BATCH_SESSION['logs'].append(data['log'])
        return jsonify({'success': True})
    
    elif action == 'stop':
        BATCH_SESSION['active'] = False
        BATCH_SESSION['status'] = 'stopped'
        return jsonify({'success': True})
    
    elif action == 'complete':
        BATCH_SESSION['active'] = False
        BATCH_SESSION['status'] = 'completed'
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Invalid action'}), 400

@app.route('/api/batch_session/active', methods=['GET'])
def api_batch_session_active():
    """Get current active batch session status."""
    if not BATCH_SESSION['active']:
        return jsonify({'active': False})
    
    # Get status of all active tasks
    running_tasks = []
    for task_id in BATCH_SESSION['task_ids']:
        if task_id in TASK_STORE:
            task = TASK_STORE[task_id]
            if task['status'] == 'running':
                running_tasks.append({
                    'task_id': task_id,
                    'progress': task['progress'],
                    'logs': task['logs'][-3:] if task['logs'] else []
                })
    
    return jsonify({
        'active': True,
        'session_id': BATCH_SESSION['session_id'],
        'status': BATCH_SESSION['status'],
        'start_page': BATCH_SESSION['start_page'],
        'total_accounts': BATCH_SESSION['total_accounts'],
        'completed_count': BATCH_SESSION['completed_count'],
        'running_tasks': running_tasks,
        'logs': BATCH_SESSION['logs'][-10:] if BATCH_SESSION['logs'] else []
    })

@app.route('/api/auto_process_async', methods=['POST'])
def api_auto_process_async():
    """
    Async version of auto_process_venue. Returns a task_id immediately.
    """
    import threading
    import uuid
    from automation import run_full_scrape_process
    
    data = request.json
    venue_name = data.get('venue_name')
    instagram_id = data.get('instagram_id')
    limit = int(data.get('limit', 3))
    
    if not instagram_id:
        return {'success': False, 'error': 'Missing instagram_id'}, 400
        
    task_id = str(uuid.uuid4())
    TASK_STORE[task_id] = {
        'status': 'queue',
        'progress': 0,
        'logs': [f"Task queued for {instagram_id}"],
        'result': None
    }
    
    def task_worker(tid, uid, l_val, v_name):
        def progress_callback(msg, pct, log=None, log_type='info'):
            if tid in TASK_STORE:
                TASK_STORE[tid]['progress'] = pct
                TASK_STORE[tid]['logs'].append(log or msg)
        
        try:
            TASK_STORE[tid]['status'] = 'running'
            progress_callback(f"Worker started for {uid}...", 0)
            
            result = run_full_scrape_process(
                uid, 
                limit=l_val, 
                limit_type="posts", 
                known_venue_name=v_name, 
                auto_save_db=False,
                progress_callback=progress_callback
            )
            
            TASK_STORE[tid]['status'] = 'completed'
            TASK_STORE[tid]['progress'] = 100
            TASK_STORE[tid]['result'] = result
            TASK_STORE[tid]['logs'].append("Process successfully finished.")
            
        except Exception as e:
            print(f"Async task failed: {e}")
            import traceback
            traceback.print_exc()
            TASK_STORE[tid]['status'] = 'error'
            TASK_STORE[tid]['logs'].append(f"Error: {str(e)}")
            TASK_STORE[tid]['result'] = {'success': False, 'message': str(e)}

    # Start Thread
    thread = threading.Thread(target=task_worker, args=(task_id, instagram_id, limit, venue_name))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'task_id': task_id})

@app.route('/api/save_event_manual', methods=['POST'])
def api_save_event_manual():
    from db_helpers import save_single_event
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
        
    # Data is expected to match the event_payload structure
    # We might need to ensure 'image_src_folder' is valid if processing from scratch, 
    # but here we just trust the reviewed data to be sufficient for save_single_event
    
    # [Fix] Handle absolute image_path from frontend for Manual Save
    if 'image_path' in data and data['image_path']:
        import os
        data['image_src_folder'] = os.path.dirname(data['image_path'])
        if 'filename' not in data or not data['filename']:
            data['filename'] = os.path.basename(data['image_path'])

    try:
        success = save_single_event(data)
        if success:
             return jsonify({'success': True})
        else:
             return jsonify({'success': False, 'error': 'Database save failed (Duplicate or Error)'}), 500
    except Exception as e:
        print(f"Manual save error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task_status/<task_id>', methods=['GET'])
def api_task_status(task_id):
    task = TASK_STORE.get(task_id)
    if not task:
        return jsonify({'success': False, 'error': 'Task not found'}), 404
    return jsonify(task)

# Keep the synchronous route for backward compatibility if needed, 
# or just redirect logic? For now, we keep it but the UI will switch to async.
@app.route('/api/auto_process_venue', methods=['POST'])
def api_auto_process_venue():
    # ... (existing synchronous logic if we want to keep it, or deprecate)
    # The existing logic is fine to keep, but let's encourage async.
    # For now, I will modify this to just forward to async if desired?
    # No, let's keep it separate to avoid breaking other potential calls.
    # Just copying the minimal logic for safety or leave as is.
    # Actually, to save space/confusion, I'll just append the Async routes 
    # and leave this one as legacy or alternative.
    """
    Legacy Synchronous route
    """
    from automation import run_full_scrape_process
    # ... (rest of function as is)
    # I will just insert the new routes BEFORE this one or after.
    # The tool replacement will handle it.
    pass
    # Re-writing the existing function just to satisfy the replace block match if needed
    # But I can just inserting BEFORE it.
    pass
    """
    Orchestrator for the "Full Auto" pipeline.
    Search -> (Frontend) -> This API -> Scrape -> Analyze -> Save DB
    """
    from automation import run_full_scrape_process
    
    data = request.json
    venue_name = data.get('venue_name')
    instagram_id = data.get('instagram_id')
    
    if not instagram_id:
        return {'success': False, 'error': 'Missing instagram_id'}, 400
        
    try:
        # Run SYNCHRONOUSLY for this MVP request or use a very short limit
        # The user wants to see it happen in sequence.
        # However, 3 posts scrape + OCR + Mistral might take 30-60sec.
        # Nginx/Flask might timeout if too long.
        # But let's try synchronous first as user asked for "Sequential".
        
        # Limit from request
        limit = int(data.get('limit', 3))

        # Run automation with auto_save_db=False to require manual review
        result = run_full_scrape_process(
            instagram_id, 
            limit=limit, 
            limit_type="posts", 
            known_venue_name=venue_name, 
            auto_save_db=True
        )
        
        if result.get('status') == 'success' or result.get('success') is True:
            return jsonify({
                'status': 'success',
                'success': True,
                'message': f"Scraped {instagram_id}. Saved {result.get('saved_count', 0)} events.",
                'saved_count': result.get('saved_count', 0),
                'scraped_count': result.get('scraped_count', 0),
                'csv_path': result.get('csv_path'),
                'details': result.get('details', []) # Return full details for Review Modal
            })
        else:
            return jsonify({
                'status': 'error',
                'message': result.get('message', 'Unknown error during processing'),
                'details': result
            }), 500
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Auto process failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 200
@app.route('/scrape_stream')
def scrape_stream():
    from flask import Response, stream_with_context
    raw_username = request.args.get('username')
    limit = int(request.args.get('limit', 3))
    
    def generate():
        import json
        import time
        import threading
        import queue
        from automation import extract_username
        from automation import run_full_scrape_process
        
        if not raw_username:
            yield f"data: {json.dumps({'error': 'No username provided'})}\n\n"
            return
            
        username = extract_username(raw_username)
        
        # Initial Message
        yield f"data: {json.dumps({'progress': 5, 'message': f'Connecting to Instagram for {username}...'})}\n\n"
        
        q = queue.Queue()
        
        def worker():
            try:
                def progress_cb(msg, pct, log=None, log_type='info'):
                    data = {'progress': pct, 'message': msg}
                    if log:
                        data['log'] = log
                        data['log_type'] = log_type
                    q.put(data)
                    
                result = run_full_scrape_process(
                    username, 
                    limit=limit, 
                    limit_type="posts",
                    auto_save_db=True,
                    progress_callback=progress_cb
                )
                q.put({'done': True, 'result': result})
            except Exception as e:
                import traceback
                traceback.print_exc()
                q.put({'error': str(e)})
                
        t = threading.Thread(target=worker)
        t.start()
        
        # Wait loop
        while True:
            try:
                # Wait for data with timeout to keep connection alive
                data = q.get(timeout=1.0)
                
                if 'error' in data:
                    yield f"data: {json.dumps({'error': data['error']})}\n\n"
                    break
                    
                if 'done' in data:
                    res = data['result']
                    # Final success message
                    yield f"data: {json.dumps({'progress': 100, 'message': 'Analysis Complete! Preparing results...'})}\n\n"
                    
                    # Extract result data for client
                    saved_count = res.get('saved_count', 0) if res else 0
                    skip_count = res.get('skip_count', 0) if res else 0
                    scraped_count = res.get('scraped_count', 0) if res else 0
                    details = res.get('details', []) if res else []
                    
                    # Send complete result with all data
                    yield f"data: {json.dumps({'progress': 100, 'message': 'Done!', 'complete': True, 'saved_count': saved_count, 'skip_count': skip_count, 'scraped_count': scraped_count, 'details': details, 'redirect': '/review'})}\n\n"
                    break
                    
                if 'progress' in data:
                    yield f"data: {json.dumps(data)}\n\n"
                    
            except queue.Empty:
                if not t.is_alive():
                    # Thread died silently?
                    yield f"data: {json.dumps({'error': 'Process terminated unexpectedly'})}\n\n"
                    break
                # Keep alive comment
                yield ": keep-alive\n\n"
                
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/load_image')
def load_image():
    """
    Serve a local image file given its absolute path.
    Usage: <img src="/load_image?path=/absolute/path/to/image.jpg">
    """
    image_path = request.args.get('path')
    if not image_path:
        return "Missing path", 400

    # Basic security check: ensure it's a file
    if not os.path.isfile(image_path):
         return "File not found", 404

    # Optimize: send_file handles mime type guessing
    return send_file(image_path)

# --- Migration Tool Routes ---
@app.route('/migration')
def migration_page():
    return render_template('migration.html')

@app.route('/api/run_migration_stream')
def run_migration_stream():
    from flask import Response, stream_with_context
    import json
    import sqlite3
    # Lazy import to avoid dependency hard-lock
    try:
        import psycopg2
    except ImportError:
        return jsonify({'error': 'psycopg2 not installed'}), 500
    
    db_url_arg = request.args.get('db_url')
    
    def generate():
        NEON_DB_URL = db_url_arg or os.environ.get("NEON_DB_URL") or os.environ.get("DATABASE_URL")
        
        if not NEON_DB_URL:
             yield f"data: {json.dumps({'message': '[Error] No Database URL provided.', 'type': 'error'})}\n\n"
             yield f"data: {json.dumps({'done': True, 'success': False})}\n\n"
             return

        yield f"data: {json.dumps({'message': 'Connecting to databases...', 'type': 'info'})}\n\n"
        
        try:
            # 1. Connect Local
            local_conn = sqlite3.connect('pomfs.db')
            local_conn.row_factory = sqlite3.Row
            
            # 2. Connect Remote
            pg_conn = psycopg2.connect(NEON_DB_URL)
            
            # 3. Migrate Venues
            yield f"data: {json.dumps({'message': '--- Migrating Venues ---', 'type': 'info'})}\n\n"
            
            l_cur = local_conn.cursor()
            p_cur = pg_conn.cursor()
            
            l_cur.execute("SELECT * FROM venues")
            venues = l_cur.fetchall()
            venue_map = {}
            
            for v in venues:
                name = v['venueName']
                local_id = v['id']
                
                p_cur.execute('SELECT id FROM venues WHERE "venueName" = %s', (name,))
                exists = p_cur.fetchone()
                
                if exists:
                    remote_id = exists[0]
                    # yield f"data: {json.dumps({'message': f'[Skip] Venue {name} exists.'})}\n\n"
                else:
                    yield f"data: {json.dumps({'message': f'[Insert] Venue {name}...', 'type': 'info'})}\n\n"
                    p_cur.execute('INSERT INTO venues ("venueName", status) VALUES (%s, %s) RETURNING id', (name, 'active'))
                    remote_id = p_cur.fetchone()[0]
                
                venue_map[local_id] = remote_id
            
            pg_conn.commit()
            yield f"data: {json.dumps({'message': f'Venues migrated. Count: {len(venue_map)}', 'type': 'success'})}\n\n"
            
            # 4. Migrate Posts
            yield f"data: {json.dumps({'message': '--- Migrating Posts ---', 'type': 'info'})}\n\n"
            
            l_cur.execute("SELECT * FROM posts")
            posts = l_cur.fetchall()
            
            migrated = 0
            skipped = 0
            
            for p in posts:
                l_vid = p['venueId']
                r_vid = venue_map.get(l_vid)
                
                if not r_vid:
                    event_name = p["eventName"]
                    yield f"data: {json.dumps({'message': f'[Warn] Skipped post {event_name} (Unknown Venue)', 'type': 'warn'})}\n\n"
                    continue
                
                # Check Duplicates
                p_cur.execute('SELECT id FROM posts WHERE "venueId" = %s AND "eventName" = %s', (r_vid, p['eventName']))
                if p_cur.fetchone():
                    skipped += 1
                    continue
                
                # Insert
                try:
                    p_cur.execute(
                        """
                        INSERT INTO posts (
                            "userId", category, subcategory, 
                            "venueId", "eventName", "eventDates", 
                            content, "imageUrl", "performingArtists", 
                            "isDraft", "createdAt"
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            'admin_migration', 
                            p['category'], 
                            p['subcategory'], 
                            r_vid, 
                            p['eventName'], 
                            p['eventDates'], 
                            p['content'], 
                            p['imageUrl'], 
                            p['performingArtists'], 
                            p['isDraft']
                        )
                    )
                    migrated += 1
                    
                    if migrated % 5 == 0:
                        yield f"data: {json.dumps({'message': f'Migrated {migrated} posts...', 'type': 'info'})}\n\n"
                        
                except Exception as e:
                    event_name = p["eventName"]
                    yield f"data: {json.dumps({'message': f'[Error] Failed post {event_name}: {e}', 'type': 'error'})}\n\n"
                    pg_conn.rollback()
            
            pg_conn.commit()
            yield f"data: {json.dumps({'message': f'Migration result: {migrated} imported, {skipped} skipped.', 'type': 'success'})}\n\n"
            yield f"data: {json.dumps({'done': True, 'success': True})}\n\n"
            
            local_conn.close()
            pg_conn.close()

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'message': f'[Critical Error] {str(e)}', 'type': 'error'})}\n\n"
            yield f"data: {json.dumps({'done': True, 'success': False})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

# --- Marketing Tool Routes ---
@app.route('/marketing')
def marketing_page():
    return render_template('marketing.html')

@app.route('/api/marketing/generate', methods=['POST'])
def marketing_generate():
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    style = data.get('style') # unused for now
    
    if not start_date or not end_date:
        return jsonify({'success': False, 'message': 'Date range required'})
    
    try:
        import sqlite3
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get all active posts
        # We fetch more fields to help generator
        cur.execute('''
            SELECT p.id, p.eventName, p.eventDates, p.imageUrl, p.performingArtists, v.venueName, p.content 
            FROM posts p
            LEFT JOIN venues v ON p.venueId = v.id
            WHERE p.isDraft = 1 
            ORDER BY p.createdAt DESC
        ''')
        rows = cur.fetchall()
        conn.close()
        
        # Filter by Date Range (Python side)
        valid_events = []
        from datetime import datetime
        
        fmt = "%Y-%m-%d"
        s_dt = datetime.strptime(start_date, fmt)
        e_dt = datetime.strptime(end_date, fmt)
        
        import json
        
        for r in rows:
            try:
                dates = json.loads(r['eventDates']) # List of {date: "YYYY-MM-DD", ...} or just strings? 
                # Our schema uses [{"date":...}]
                
                matched_date = None
                for d_obj in dates:
                    d_str = d_obj.get('date') if isinstance(d_obj, dict) else str(d_obj)
                    if not d_str: continue
                    
                    try:
                        d_val = datetime.strptime(d_str, fmt)
                        if s_dt <= d_val <= e_dt:
                            matched_date = d_str
                            break
                    except:
                        pass
                
                if matched_date:
                    # Parse image path
                    # imageUrl might be: "/static/images/..." or absolute path
                    # We need absolute path for Pillow if possible, or relative to cwd
                    img_path = r['imageUrl']
                    # logic to resolve path
                    if img_path and img_path.startswith('/static/'):
                         # Convert web path to fs path
                         # /static/images/foo.jpg -> static/images/foo.jpg
                         img_path = img_path.lstrip('/')
                    elif img_path and img_path.startswith('http'):
                        pass # keep as URL
                    # Fallback for absolute paths stored in DB
                    
                    valid_events.append({
                        'eventName': r['eventName'],
                        'venueName': r['venueName'],
                        'date': matched_date,
                        'image_path': img_path,
                        'performers': r['performingArtists'] # JSON string
                    })
            except Exception as e:
                print(f"Skipping row {r['id']}: {e}")
                continue
        
        if not valid_events:
            return jsonify({'success': False, 'message': 'No events found in this date range.'})
            
        # Call Generator
        from marketing_generator import MarketingGenerator
        api_key = os.environ.get("MISTRAL_API_KEY")
        gen = MarketingGenerator(api_key)
        
        # 1. Generate Image
        output_filename = f"marketing_result_{int(datetime.now().timestamp())}.jpg"
        output_rel_path = os.path.join('static', 'temp_gen')
        os.makedirs(output_rel_path, exist_ok=True)
        final_path = os.path.join(output_rel_path, output_filename)
        
        gen.generate_image(valid_events, final_path)
        
        # 2. Generate Caption
        caption = gen.generate_caption(valid_events)
        
        return jsonify({
            'success': True,
            'image_url': f"/{final_path}", # Web path
            'caption': caption
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/posts')
def api_get_posts():
    """Get scraped posts from Neon DB."""
    try:
        username = request.args.get('username')
        limit = int(request.args.get('limit', 50))
        
        posts = get_scraped_posts(username=username, limit=limit)
        
        result = []
        for p in posts:
            result.append({
                'id': p['id'],
                'username': p['username'],
                'shortcode': p['shortcode'],
                'post_date': p['post_date'].isoformat() if p['post_date'] else None,
                'caption': p['caption'][:200] + '...' if p['caption'] and len(p['caption']) > 200 else p['caption'],
                'post_url': p['post_url'],
                'created_at': p['created_at'].isoformat() if p['created_at'] else None
            })
        
        return jsonify({
            'success': True,
            'count': len(result),
            'posts': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/test_tool')
def test_tool_page():
    """Test tool page for map/carousel testing with existing scraped data."""
    return render_template('test_tool.html')

@app.route('/api/test/scraped_folders')
def api_test_scraped_folders():
    """Get list of dates and accounts from scraped_data folder."""
    import os
    scraped_path = 'scraped_data'
    result = {'dates': [], 'folders': {}}
    
    if not os.path.exists(scraped_path):
        return jsonify({'success': True, **result})
    
    dates = sorted([d for d in os.listdir(scraped_path) 
                   if os.path.isdir(os.path.join(scraped_path, d))], reverse=True)
    result['dates'] = dates
    
    for date in dates:
        date_path = os.path.join(scraped_path, date)
        accounts = sorted([a for a in os.listdir(date_path) 
                          if os.path.isdir(os.path.join(date_path, a))])
        result['folders'][date] = accounts
    
    return jsonify({'success': True, **result})

@app.route('/api/test/images/<date>/<username>')
def api_test_images(date, username):
    """Get list of images for a specific account."""
    import os
    folder_path = os.path.join('scraped_data', date, username)
    
    if not os.path.exists(folder_path):
        return jsonify({'success': False, 'error': 'Folder not found'}), 404
    
    images = []
    for f in sorted(os.listdir(folder_path)):
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            shortcode = f.rsplit('_', 1)[0] if '_' in f else f.rsplit('.', 1)[0]
            images.append({
                'filename': f,
                'path': os.path.join(folder_path, f),
                'shortcode': shortcode
            })
    
    return jsonify({'success': True, 'images': images})

@app.route('/api/test/get_event_data/<shortcode>')
def api_test_get_event_data(shortcode):
    """Get event data from Neon DB scraped_posts by shortcode."""
    from db_utils import get_neon_connection
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = get_neon_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute('''
            SELECT event_name, event_venue, event_location, event_date, event_time,
                   event_country, latitude, longitude, formatted_address,
                   performing_artists, content, source_username, shortcode
            FROM scraped_posts
            WHERE shortcode = %s
        ''', (shortcode,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': 'Data not found', 'shortcode': shortcode})
        
        event_date_str = None
        if row.get('event_date'):
            try:
                event_date_str = row['event_date'].strftime('%Y-%m-%d')
            except:
                event_date_str = str(row['event_date'])[:10]
        
        artists_raw = row.get('performing_artists')
        artists = []
        if artists_raw:
            if isinstance(artists_raw, list):
                artists = artists_raw
            elif isinstance(artists_raw, str):
                import json
                try:
                    artists = json.loads(artists_raw)
                except:
                    artists = [a.strip() for a in artists_raw.split(',') if a.strip()]
        
        return jsonify({
            'success': True,
            'data': {
                'event_name': row.get('event_name') or '',
                'event_venue': row.get('event_venue') or '',
                'event_location': row.get('event_location') or '',
                'event_date': event_date_str,
                'event_time': row.get('event_time') or '',
                'event_country': row.get('event_country') or 'KR',
                'latitude': float(row['latitude']) if row.get('latitude') else None,
                'longitude': float(row['longitude']) if row.get('longitude') else None,
                'formatted_address': row.get('formatted_address') or '',
                'artists': artists,
                'content': row.get('content') or '',
                'source_username': row.get('source_username') or ''
            }
        })
        
    except Exception as e:
        print(f"[API] get_event_data error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test/account_events/<date>/<username>')
def api_test_account_events(date, username):
    """Get analyzed events for a specific account from Neon DB.
    
    Returns list of events and auto-fills first event data.
    Note: date parameter reserved for future filtering, currently unused.
    """
    from db_utils import get_account_events
    import json as json_module
    
    def parse_event_date(event_dates):
        """Parse event_dates field which can be list, JSON string, or list of dicts."""
        if not event_dates:
            return None
        
        try:
            if isinstance(event_dates, str):
                event_dates = json_module.loads(event_dates)
            
            if isinstance(event_dates, list) and len(event_dates) > 0:
                first_date = event_dates[0]
                if isinstance(first_date, dict):
                    return first_date.get('date') or first_date.get('value')
                elif isinstance(first_date, str):
                    if len(first_date) >= 10:
                        return first_date[:10]
                    return first_date
            return None
        except:
            return None
    
    def parse_artists(artists_raw):
        """Parse artists field which can be list or JSON string."""
        if not artists_raw:
            return []
        
        if isinstance(artists_raw, list):
            return artists_raw
        
        if isinstance(artists_raw, str):
            try:
                return json_module.loads(artists_raw)
            except:
                return [a.strip() for a in artists_raw.split(',') if a.strip()]
        return []
    
    try:
        events = get_account_events(username, events_only=False)
        
        events_list = []
        first_event = None
        
        for event in events:
            has_event_data = bool(event.get('event_name')) or (
                bool(event.get('event_venue')) and bool(event.get('event_dates'))
            )
            
            event_data = {
                'shortcode': event.get('shortcode'),
                'event_name': event.get('event_name') or '',
                'event_venue': event.get('event_venue') or '',
                'is_event': has_event_data,
                'has_data': bool(event.get('event_name') or event.get('event_venue'))
            }
            events_list.append(event_data)
            
            if first_event is None and has_event_data:
                location = event.get('event_location') or event.get('formatted_address') or ''
                lat = event.get('latitude')
                lng = event.get('longitude')
                
                first_event = {
                    'shortcode': event.get('shortcode'),
                    'event_name': event.get('event_name') or '',
                    'event_venue': event.get('event_venue') or '',
                    'event_location': location,
                    'event_date': parse_event_date(event.get('event_dates')),
                    'event_time': event.get('event_time') or '',
                    'event_country': event.get('event_country') or 'KR',
                    'latitude': float(lat) if lat else None,
                    'longitude': float(lng) if lng else None,
                    'artists': parse_artists(event.get('performing_artists')),
                    'content': event.get('content') or ''
                }
        
        return jsonify({
            'success': True,
            'account': username,
            'total': len(events_list),
            'events_count': len([e for e in events_list if e['is_event']]),
            'events': events_list,
            'first_event': first_event
        })
        
    except Exception as e:
        print(f"[API] account_events error: {e}")
        return jsonify({'success': False, 'error': str(e), 'events': [], 'first_event': None})

@app.route('/api/test/country_samples')
def api_test_country_samples():
    """Get random sample data for different countries for map testing."""
    import random
    
    samples = {
        'KR': [
            {'event_name': 'TECHNO NIGHT Vol.3', 'event_venue': '클럽 믹스', 'event_location': '서울 강남구 역삼동 123-45', 'latitude': 37.5012, 'longitude': 127.0396},
            {'event_name': 'HOUSE MUSIC FESTIVAL', 'event_venue': '클럽 옥타곤', 'event_location': '서울 강남구 논현동 50-3', 'latitude': 37.5110, 'longitude': 127.0340},
            {'event_name': 'UNDERGROUND SESSION', 'event_venue': '클럽 볼트', 'event_location': '서울 마포구 서교동 395-166', 'latitude': 37.5560, 'longitude': 126.9220},
            {'event_name': 'DEEP HOUSE PARTY', 'event_venue': '클럽 아레나', 'event_location': '서울 용산구 이태원동 116-10', 'latitude': 37.5347, 'longitude': 126.9945},
            {'event_name': 'EDM FESTIVAL KOREA', 'event_venue': '올림픽공원', 'event_location': '서울 송파구 올림픽로 424', 'latitude': 37.5209, 'longitude': 127.1214}
        ],
        'JP': [
            {'event_name': 'TOKYO UNDERGROUND', 'event_venue': 'WOMB', 'event_location': '東京都渋谷区円山町2-16', 'latitude': 35.6580, 'longitude': 139.6922},
            {'event_name': 'SHIBUYA BEATS', 'event_venue': 'Contact Tokyo', 'event_location': '東京都渋谷区道玄坂2-10-12', 'latitude': 35.6575, 'longitude': 139.6968},
            {'event_name': 'OSAKA NIGHT FEVER', 'event_venue': 'NOON + CAFE', 'event_location': '大阪府大阪市中央区西心斎橋2-4-28', 'latitude': 34.6700, 'longitude': 135.4980},
            {'event_name': 'KYOTO ELECTRONIC', 'event_venue': 'Metro', 'event_location': '京都府京都市左京区川端二条東', 'latitude': 35.0116, 'longitude': 135.7680},
            {'event_name': 'FUKUOKA DANCE', 'event_venue': 'Kieth Flack', 'event_location': '福岡県福岡市中央区舞鶴1-8-28', 'latitude': 33.5902, 'longitude': 130.3990}
        ],
        'US': [
            {'event_name': 'LA HOUSE PARTY', 'event_venue': 'Sound Nightclub', 'event_location': '1642 N Las Palmas Ave, Los Angeles, CA', 'latitude': 34.1015, 'longitude': -118.3292},
            {'event_name': 'NYC UNDERGROUND', 'event_venue': 'Basement', 'event_location': '240 W 52nd St, New York, NY', 'latitude': 40.7625, 'longitude': -73.9850},
            {'event_name': 'MIAMI BEACH FESTIVAL', 'event_venue': 'Club Space', 'event_location': '34 NE 11th St, Miami, FL', 'latitude': 25.7857, 'longitude': -80.1920},
            {'event_name': 'CHICAGO DANCE', 'event_venue': 'Spybar', 'event_location': '646 N Franklin St, Chicago, IL', 'latitude': 41.8935, 'longitude': -87.6355},
            {'event_name': 'SF TECHNO NIGHT', 'event_venue': 'Public Works', 'event_location': '161 Erie St, San Francisco, CA', 'latitude': 37.7690, 'longitude': -122.4195}
        ]
    }
    
    country = request.args.get('country', 'KR')
    random_pick = request.args.get('random', 'false').lower() == 'true'
    
    if country not in samples:
        return jsonify({'success': False, 'error': f'Unknown country: {country}'}), 400
    
    if random_pick:
        sample = random.choice(samples[country])
        return jsonify({'success': True, 'sample': sample, 'country': country})
    else:
        return jsonify({'success': True, 'samples': samples[country], 'country': country})

@app.route('/api/test/upload_and_save', methods=['POST'])
def api_test_upload_and_save():
    """Upload image to GCS and save test event to MusicFeedPlatform DB."""
    from gcs_uploader import upload_image_to_gcs
    from db_helpers import save_to_dev_db
    import json
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    image_path = data.get('image_path')
    if not image_path or not os.path.exists(image_path):
        return jsonify({'success': False, 'error': 'Image file not found'}), 400
    
    try:
        gcs_url = upload_image_to_gcs(image_path)
        if not gcs_url:
            return jsonify({'success': False, 'error': 'GCS upload failed'}), 500
        
        artists = data.get('artists', [])
        artists_json = json.dumps(artists) if isinstance(artists, list) else '[]'
        
        result = save_to_dev_db(
            venue_name=data.get('event_venue', ''),
            event_name=data.get('event_name', 'Test Event'),
            event_date=data.get('event_date'),
            event_dates_json='[]',
            content=data.get('content', ''),
            image_url=gcs_url,
            artists_json=artists_json,
            event_location=data.get('event_location', ''),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            formatted_address=data.get('formatted_address', ''),
            event_time=data.get('event_time', ''),
            event_country=data.get('event_country', '')
        )
        
        if result:
            return jsonify({'success': True, 'image_url': gcs_url})
        else:
            return jsonify({'success': False, 'error': 'DB save failed'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test/list_test_data')
def api_test_list_test_data():
    """Get list of pomfs_ai test events from MusicFeedPlatform DB."""
    from db_helpers import get_dev_db_connection
    
    try:
        conn = get_dev_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        cur.execute('''
            SELECT id, event_name, event_venue, event_date, event_country, 
                   image_url, created_at
            FROM posts
            WHERE category = 'pomfs_ai' AND genre = 'pomfs_ai'
            ORDER BY created_at DESC
        ''')
        
        rows = cur.fetchall()
        events = []
        for row in rows:
            events.append({
                'id': row[0],
                'event_name': row[1] or '',
                'event_venue': row[2] or '',
                'event_date': row[3].isoformat() if row[3] else None,
                'event_country': row[4] or '',
                'image_url': row[5] or '',
                'created_at': row[6].isoformat() if row[6] else None
            })
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'count': len(events), 'events': events})
        
    except Exception as e:
        print(f"[API] list_test_data error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test/clear_all', methods=['POST'])
def api_test_clear_all():
    """Delete all pomfs_ai test events from MusicFeedPlatform DB."""
    from db_helpers import get_dev_db_connection
    
    try:
        conn = get_dev_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        cur.execute('''
            DELETE FROM posts
            WHERE category = 'pomfs_ai' AND genre = 'pomfs_ai'
        ''')
        
        deleted_count = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[API] Cleared all test data: {deleted_count} events deleted")
        return jsonify({'success': True, 'deleted': deleted_count})
        
    except Exception as e:
        print(f"[API] clear_all error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test/delete_selected', methods=['POST'])
def api_test_delete_selected():
    """Delete selected test events from MusicFeedPlatform DB (pomfs_ai only)."""
    from db_helpers import get_dev_db_connection
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
    
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'success': False, 'error': 'No IDs provided'}), 400
    
    if not all(isinstance(i, int) for i in ids):
        return jsonify({'success': False, 'error': 'Invalid ID format'}), 400
    
    try:
        conn = get_dev_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(f'''
            DELETE FROM posts 
            WHERE id IN ({placeholders})
            AND category = 'pomfs_ai' AND genre = 'pomfs_ai'
        ''', ids)
        
        deleted_count = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[API] Deleted selected test events: {deleted_count}")
        return jsonify({'success': True, 'deleted': deleted_count})
    except Exception as e:
        print(f"[API] delete_selected error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ DEV_NOTES Update with Email Notification ============
# Admin API Key for protected endpoints (set via environment variable)
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', 'pomfs-admin-2026')

def check_admin_api_key():
    """Validate admin API key from request header or query param"""
    api_key = request.headers.get('X-Admin-Key') or request.args.get('admin_key')
    return api_key == ADMIN_API_KEY

@app.route('/api/dev_notes', methods=['GET'])
def get_dev_notes():
    """Get current DEV_NOTES.md content (read-only, no auth required)"""
    try:
        with open('DEV_NOTES.md', 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dev_notes', methods=['POST'])
def update_dev_notes():
    """Update DEV_NOTES.md and send email notification (admin auth required)"""
    if not check_admin_api_key():
        return jsonify({'success': False, 'error': 'Unauthorized: Invalid or missing admin key'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON body'}), 400
        
        content = data.get('content')
        if content is None:
            return jsonify({'success': False, 'error': 'Missing required field: content'}), 400
        
        changes_summary = data.get('changes_summary', '')
        send_notification = data.get('send_notification', True)
        
        with open('DEV_NOTES.md', 'w', encoding='utf-8') as f:
            f.write(content)
        
        email_result = None
        email_error_msg = None
        if send_notification:
            try:
                from replitmail import send_dev_notes_update_notification
                email_result = send_dev_notes_update_notification(changes_summary)
            except Exception as email_error:
                print(f"[API] Email notification failed: {email_error}")
                email_error_msg = str(email_error)
        
        response = {
            'success': True, 
            'message': 'DEV_NOTES.md updated successfully',
            'email_sent': email_result is not None and email_error_msg is None
        }
        if email_error_msg:
            response['email_error'] = email_error_msg
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dev_notes/test_email', methods=['POST'])
def test_dev_notes_email():
    """Test email notification for DEV_NOTES updates (admin auth required)"""
    if not check_admin_api_key():
        return jsonify({'success': False, 'error': 'Unauthorized: Invalid or missing admin key'}), 401
    
    try:
        from replitmail import send_dev_notes_update_notification
        result = send_dev_notes_update_notification("테스트 이메일 발송입니다.")
        if result:
            return jsonify({'success': True, 'result': result})
        else:
            return jsonify({'success': False, 'error': 'Email send returned None'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Disable reloader to prevent server restarts when UC touches files
    app.run(host='0.0.0.0', debug=True, port=5000, use_reloader=False)
