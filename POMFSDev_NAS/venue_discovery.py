import requests
from bs4 import BeautifulSoup
import re
import urllib.parse

def search_instagram_id(venue_name):
    """
    Searches for the Instagram ID of a venue using Naver Search.
    (DuckDuckGo blocked 403, using Naver as fallback)
    """
    base_url = "https://search.naver.com/search.naver"
    
    # Try multiple query variations
    # Naver works well with Korean/English mix, but let's try standard specific queries
    queries = [
        f"{venue_name} instagram",
        f"{venue_name} official instagram"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }
    
    found_id = None
    
    for q in queries:
        if found_id: break
        
        try:
            print(f"Searching (Naver): {q}")
            resp = requests.get(base_url, params={'query': q}, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Naver search results structure can vary.
                # Simplest way: Look for all <a> tags with href containing instagram.com
                links = soup.find_all('a')
                
                for link in links:
                    href = link.get('href', '')
                    
                    # Pattern verification
                    match = re.search(r'instagram\.com/([a-zA-Z0-9._]+)', href)
                    if match:
                        candidate = match.group(1)
                        print(f"Found candidate: {candidate}")
                        
                        dummy_words = ['p', 'reel', 'stories', 'explore', 'accounts', 'about', 'developer', 'help']
                        if candidate not in dummy_words:
                            found_id = candidate
                            break 
                            
        except Exception as e:
            print(f"Error searching for {venue_name}: {e}")
            
    return found_id

if __name__ == "__main__":
    # Test
    print("Found ID:", search_instagram_id("Cairo Jazz Club 610"))
