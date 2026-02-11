import os
import requests
import time
from apify_client import ApifyClient
from datetime import datetime

class ApifyScraper:
    """
    Instagram scraper using Apify cloud service.
    No local login required - uses Apify's Instagram Scraper actor.
    """
    
    def __init__(self, token, download_path='downloads'):
        self.token = token
        self.download_path = download_path
        self.client = ApifyClient(token)
        print("[ApifyScraper] Initialized with Apify token")
    
    def get_recent_posts(self, username, limit=5):
        """Wrapper for backward compatibility."""
        return list(self.get_recent_posts_iter(username, limit))
    
    def get_recent_posts_iter(self, username, limit=5, output_dir=None, progress_callback=None):
        """
        Generator that yields (count, post_data) tuple using Apify Instagram Scraper.
        Compatible with InstagramScraper interface.
        
        Args:
            progress_callback: Optional function(message, log_message) for progress updates
        """
        def report(msg, log_msg=None):
            if progress_callback:
                progress_callback(msg, log_msg or msg)
            print(f"[ApifyScraper] {msg}")
        
        report(f"Fetching posts for {username} via Apify...")
        
        if output_dir:
            target_dir = output_dir
        else:
            target_dir = os.path.join(self.download_path, username)
        
        os.makedirs(target_dir, exist_ok=True)
        
        try:
            run_input = {
                "directUrls": [f"https://www.instagram.com/{username}/"],
                "resultsType": "posts",
                "resultsLimit": limit,
            }
            
            report(f"🔄 Apify 클라우드에서 {username} 데이터 수집 중...", f"Apify 서버 요청 중 (최대 1-2분 소요)")
            run = self.client.actor("apify/instagram-scraper").call(run_input=run_input)
            
            report(f"📦 수집 완료! 데이터 다운로드 중...", f"Apify 응답 수신, 데이터 처리 시작")
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            report(f"✅ {len(items)}개 게시물 발견", f"총 {len(items)}개 게시물 데이터 수신")
            
            if not items:
                print(f"[ApifyScraper] WARNING: No posts found for {username}. Profile may be private or empty.")
                return
            
            count = 0
            for item in items:
                if count >= limit:
                    break
                
                shortcode = item.get('shortCode', '')
                caption = item.get('caption', '') or ''
                timestamp = item.get('timestamp', '')
                is_video = item.get('type') == 'Video'
                
                # Parse timestamp
                post_date = None
                if timestamp:
                    try:
                        post_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except:
                        post_date = datetime.now()
                else:
                    post_date = datetime.now()
                
                downloaded_paths = []
                
                # Skip image download for videos, but keep caption
                if is_video:
                    print(f"[ApifyScraper] Video post {shortcode} - skipping image download, keeping caption")
                else:
                    # Get image URLs
                    image_urls = []
                    if item.get('displayUrl'):
                        image_urls.append(item['displayUrl'])
                    
                    # For albums/sidecars
                    if item.get('images'):
                        image_urls = item['images']
                    elif item.get('childPosts'):
                        for child in item['childPosts']:
                            if child.get('displayUrl'):
                                image_urls.append(child['displayUrl'])
                    
                    # Download images
                    for idx, img_url in enumerate(image_urls[:10]):
                        try:
                            filename = f"{shortcode}_{idx}.jpg"
                            filepath = os.path.join(target_dir, filename)
                            
                            response = requests.get(img_url, timeout=30)
                            if response.status_code == 200:
                                with open(filepath, 'wb') as f:
                                    f.write(response.content)
                                downloaded_paths.append(filepath)
                                print(f"[ApifyScraper] Downloaded: {filename}")
                        except Exception as e:
                            print(f"[ApifyScraper] Failed to download image: {e}")
                    
                    if not downloaded_paths:
                        print(f"[ApifyScraper] No images downloaded for {shortcode}, skipping")
                        continue
                
                count += 1
                post_data = {
                    'shortcode': shortcode,
                    'caption': caption,
                    'date': post_date.isoformat() if post_date else '',
                    'url': f"https://www.instagram.com/p/{shortcode}/",
                    'image_filepath': downloaded_paths[0] if downloaded_paths else '',
                    'all_image_filenames': [os.path.basename(p) for p in downloaded_paths],
                    'is_video': is_video,
                }
                
                report(f"📸 게시물 {count}/{limit} 다운로드 완료", f"게시물 {count}: {shortcode} 이미지 저장 완료")
                yield (count, post_data)
                
        except Exception as e:
            print(f"[ApifyScraper] ERROR: {e}")
            raise
