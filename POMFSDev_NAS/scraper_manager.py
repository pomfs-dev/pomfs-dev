import os
import time
import random
from datetime import datetime, timedelta

class ScraperManager:
    """
    Manages scraping operations with automatic fallback and error recovery.
    
    Tiers:
    1. Apify Cloud (Fast, Reliable)
    2. Local Instagrapi (Backup)
    3. Selenium (Last Resort - Placeholder)
    
    Circuit Breaker:
    - Tracks consecutive Tier 1 failures.
    - If >= 3 failures, blocks Tier 1 for 10 minutes.
    """
    
    # Class-level state for Circuit Breaker
    _apify_failures = 0
    _circuit_open_until = None
    
    def __init__(self, apify_token=None):
        self.apify_token = apify_token or os.environ.get("APIFY_TOKEN")
        self.apify_client = None
        self.local_scraper = None
        
    def _is_circuit_open(self):
        """Check if Apify circuit is open (blocked)."""
        if ScraperManager._circuit_open_until:
            if datetime.now() < ScraperManager._circuit_open_until:
                return True
            else:
                # Reset after cooldown
                print("[ScraperManager] 🟢 Circuit Breaker reset. Retrying Apify.")
                ScraperManager._circuit_open_until = None
                ScraperManager._apify_failures = 0
        return False

    def _record_failure(self, tier="apify"):
        if tier == "apify":
            ScraperManager._apify_failures += 1
            print(f"[ScraperManager] ⚠️ Apify Failure Count: {ScraperManager._apify_failures}/3")
            if ScraperManager._apify_failures >= 3:
                cooldown_min = 10
                ScraperManager._circuit_open_until = datetime.now() + timedelta(minutes=cooldown_min)
                print(f"[ScraperManager] 🔴 Circuit Breaker ACTIVATED. Apify blocked for {cooldown_min} minutes.")

    def _record_success(self, tier="apify"):
        if tier == "apify":
            ScraperManager._apify_failures = 0

    def _get_apify_scraper(self):
        if self._is_circuit_open():
            return None
            
        if not self.apify_client and self.apify_token:
            try:
                from scraper_apify import ApifyScraper
                self.apify_client = ApifyScraper(token=self.apify_token)
            except ImportError:
                print("[ScraperManager] Failed to import ApifyScraper")
        return self.apify_client

    def _get_local_scraper(self):
        if not self.local_scraper:
            try:
                from scraper import InstagramScraper
                self.local_scraper = InstagramScraper()
            except ImportError:
                print("[ScraperManager] Failed to import InstagramScraper")
        return self.local_scraper

    def fetch_posts(self, username, limit=3, output_dir=None, progress_callback=None):
        """
        Attempts to fetch posts using available scrapers in order of priority.
        """
        def report(msg, log_msg=None, type='info'):
            if progress_callback:
                progress_callback(msg, log_msg or msg, type)
            print(f"[ScraperManager] {msg}")

        # Tier 1: Apify
        apify = self._get_apify_scraper()
        if apify:
            try:
                report(f"Tier 1: Apify 스크래핑 시도 ({username})...", "Apify Cloud 연결 시도", "api")
                # Using list() to consume generator and ensure completion before returning
                # Note: lambda wrapper might be needed if signatures mismatch
                posts = list(apify.get_recent_posts_iter(username, limit, output_dir, lambda m, l: report(m, l, 'info')))
                
                if posts:
                    report(f"✅ Apify 수집 성공: {len(posts)}개", "Apify 수집 완료", "success")
                    self._record_success("apify")
                    return posts
                else:
                    report("⚠️ Apify 수집 결과 없음, Tier 2 전환...", "Apify 결과 0개 -> Fallback", "warning")
                    # Empty result might not be a failure (just no posts), but we fallback just in case
            except Exception as e:
                self._record_failure("apify")
                report(f"❌ Apify 실패: {e}", f"Apify 에러: {e} -> Tier 2 전환", "error")
        elif self._is_circuit_open():
            report("⛔ Apify Circuit Open (Skipping Tier 1)", "Apify 일시 차단 중 (Circuit Breaker)", "warning")
        
        # Tier 2: Local Instagrapi
        report(f"Tier 2: 로컬 스크래퍼 전환 ({username})...", "로컬 Instagrapi 준비 중", "warning")
        
        # Random cool-down before local fallback
        delay = random.uniform(5, 10)
        report(f"⏳ 안전을 위해 {delay:.1f}초 대기...", f"Cool-down: {delay:.1f}s", "info")
        time.sleep(delay)
        
        local = self._get_local_scraper()
        if local:
            try:
                # scraper.py expects progress_callback(msg, log_msg)
                def local_cb(msg, log_msg):
                    report(msg, log_msg, 'info')
                    
                posts = list(local.get_recent_posts_iter(username, limit, output_dir, local_cb))
                if posts:
                     report(f"✅ 로컬 수집 성공: {len(posts)}개", "로컬 수집 완료", "success")
                     return posts
            except Exception as e:
                report(f"❌ 로컬 스크래핑 실패: {e}", f"로컬 에러: {e}", "error")
                
                # Tier 3: Selenium (Placeholder for now)
                # If we had it, we would call it here.
                # report("Tier 3: Selenium fallback...", "Selenium 시도", "warning")
                
                raise e # Re-raise if all available tiers fail
        else:
            raise Exception("No scraping backends available")
