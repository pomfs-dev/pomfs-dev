from instagrapi import Client
import os
import shutil
import time

class InstagramScraper:
    def __init__(self, download_path='downloads'):
        self.download_path = download_path
        self.cl = Client()
        self.session_file = "session.json"
        
        # Try to load session
        if os.path.exists(self.session_file):
            try:
                print(f"[Scraper] Loading session from {self.session_file}...")
                self.cl.load_settings(self.session_file)
                # Verify session valid? 
                # Doing a lightweight call to check
                # self.cl.get_timeline_feed(amount=1)
                print("[Scraper] Session loaded.")
            except Exception as e:
                print(f"[Scraper] Warning: Could not load session: {e}")
        else:
            print(f"[Scraper] Warning: {self.session_file} not found. You may need to run login_interactive.py first.")

    def get_recent_posts(self, username, limit=5):
        """
        Wrapper for get_recent_posts_iter to return list for backward compatibility.
        """
        return list(self.get_recent_posts_iter(username, limit))

    def get_recent_posts_iter(self, username, limit=5, output_dir=None, progress_callback=None):
        """
        Generator that yields progress (count, post_data) tuple using Instagrapi.
        
        Args:
            progress_callback: Optional function(message, log_message) for progress updates
        """
        try:
            print(f"Fetching posts for {username} (Mobile API)...")
            
            # Resolve User ID
            try:
                user_id = self.cl.user_id_from_username(username)
            except Exception as e:
                print(f"Error resolving username {username}: {e}")
                # Fallback for instagrapi 2.x TypeError or GQL issues
                try:
                    print(f"Attempting V1 fallback for {username}...")
                    user_id = self.cl.user_info_by_username_v1(username).pk
                except Exception as v1_e:
                    print(f"V1 fallback failed: {v1_e}")
                    raise e
            
            # Fetch Medias with robust error handling
            medias = []
            try:
                medias = self.cl.user_medias(user_id, amount=limit)
            except Exception as e:
                print(f"Warning: Failed to fetch medias for {username}: {e}")
                # Try simple pagination or public call fallback if provided?
                # For now just log and continue empty
                if "validation" in str(e).lower():
                    print("This is a data schema mismatch (Pydantic ValidationError). Instagram sent unexpected data.")
                elif "data" in str(e).lower() and "keyerror" in str(e).lower():
                     print("This is likely a soft-block (KeyError: 'data').")

            if output_dir:
                target_dir = output_dir
            else:
                target_dir = os.path.join(self.download_path, username)
                
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
                
            count = 0
            for media in medias:
                if count >= limit: break
                
                # Filter for images/albums
                # 1=Photo, 2=Video, 8=Album
                if media.media_type == 2: 
                    print(f"Skipping video {media.pk}...")
                    continue
                
                print(f"Processing media {media.pk} (Type: {media.media_type})...")
                
                # Download
                try:
                    # Instagrapi downloads to path using media.pk usually
                    # photo_download returns path
                    # We want to save to target_dir
                    
                    # Generate filename timestamp based
                    timestamp = int(media.taken_at.timestamp())
                    filename_base = f"{timestamp}_UTC"
                    
                    paths = []
                    path = None
                    if media.media_type == 1:
                         p = self.cl.photo_download(media.pk, folder=target_dir)
                         if p: 
                             paths = [p]
                             path = p
                    elif media.media_type == 8:
                         # Album - Iterate resources and download ONLY images
                         paths = []
                         # Check if resources are populated
                         if hasattr(media, 'resources') and media.resources:
                             for resource in media.resources:
                                 if resource.media_type == 1: # Photo
                                      # Use photo_download with resource pk
                                      # Note: instagrapi might need resource pk or media pk?
                                      # self.cl.photo_download takes media_pk.
                                      # For resources, they have their own pk.
                                      try:
                                          p = self.cl.photo_download(resource.pk, folder=target_dir)
                                          if p: paths.append(p)
                                      except Exception as e:
                                          print(f"Error downloading resource {resource.pk}: {e}")
                             
                             if paths:
                                 path = paths[0]
                         else:
                             # Fallback if no resources (rare) or simpler album
                             # Try default download but beware of videos
                             # Just skip if tricky to extract partial?
                             # Or use album_download and delete mp4?
                             # Let's try album_download and filter paths
                             temp_paths = self.cl.album_download(media.pk, folder=target_dir)
                             for tp in temp_paths:
                                 # Convert Path to str
                                 tp_str = str(tp)
                                 if tp_str.lower().endswith('.mp4'):
                                     try:
                                         os.remove(tp_str)
                                         print(f"Removed video: {tp_str}")
                                     except: pass
                                 else:
                                     paths.append(tp)
                             if paths: path = paths[0]
                    
                    if not path:
                         print("No image path returned.")
                         continue
                    
                    filename = os.path.basename(path)
                    
                    # Construct post info
                    post_info = {
                        "shortcode": media.code,
                        "date": media.taken_at.isoformat() if media.taken_at else "",
                        "caption": media.caption_text,
                        "url": f"https://www.instagram.com/p/{media.code}/",
                        "image_filepath": os.path.join(output_dir if output_dir else username, filename),
                        "all_image_filenames": [p.name if hasattr(p, 'name') else os.path.basename(str(p)) for p in paths]
                    }
                    
                    yield (count + 1, post_info)
                    count += 1
                    
                except Exception as e:
                    print(f"Error downloading media {media.pk}: {e}")
            
        except Exception as e:
            # Handle specific Instagrapi errors
            error_msg = str(e)
            if "login_required" in error_msg or "LoginRequired" in str(type(e)):
                 print(f"CRITICAL: Session expired or login required for {username}.")
                 # We can't easily raise a custom exception that automation.py understands without importing it,
                 # but we can raise a generic Exception with a clear message.
                 raise Exception("Login Required: Please run 'login_interactive.py' to refresh session.")
            
            print(f"Scrape error: {e}")
            raise e

if __name__ == "__main__":
    # Test
    scraper = InstagramScraper()
    # for p in scraper.get_recent_posts_iter("theroofseoul_", 1):
    #     print(p)
