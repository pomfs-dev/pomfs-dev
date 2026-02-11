import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import urllib.parse

def search_google_selenium(venue_name, city=None, country=None):
    """
    Searches Google for the venue's Instagram ID using Selenium (Undetected).
    Query: "{venue_name} {city} {country} instagram"
    """
    print(f"Initializing Selenium (Undetected) for Deep Search: {venue_name}")
    
    # Headless mode allows detection. Using headed mode for better success rate.
    # chrome_options = Options() # Standard options
    chrome_options = uc.ChromeOptions() # Use uc options
    
    # chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # UA is handled better by uc, but safe to keep if needed, though uc randomizes/fixes it.
    # chrome_options.add_argument("--lang=en-US")
    # Small window to be less intrusive
    # chrome_options.add_argument("--window-size=1024,768") 

    driver = None
    try:
        # uc.Chrome downloads driver automatically if needed
        driver = uc.Chrome(options=chrome_options, use_subprocess=True) 
        driver.set_window_size(1024, 768)
        
        # Construct Query
        query_parts = [venue_name]
        if city and city != '-': query_parts.append(city)
        if country and country != '-': query_parts.append(country)
        query_parts.append("instagram")
        
        query = " ".join(query_parts)
        print(f"Deep Search Query: {query}")
        
        driver.get("https://www.google.com")
        
        # Simple wait for body to ensure load
        time.sleep(1)
        
        # Find search box
        # Google input name is usually 'q'
        search_box = driver.find_element(By.NAME, "q")
        search_box.send_keys(query)
        search_box.send_keys(Keys.RETURN)
        
        # Wait for results (optimize speed)
        try:
             # Wait up to 5 seconds for results to appear
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.g, div.MjjYud, div#search"))
            )
        except:
            pass # Timeout, proceed to parse whatever is there
        
        # Check for CAPTCHA/Consent page (basic check)
        if "sorry" in driver.current_url or "consent" in driver.current_url:
            print("Warning: Google CAPTCHA or Consent page detected.")
        
        # Parse Results with Robust Selectors
        possible_selectors = [
            "div.g a", 
            "div.MjjYud a", 
            "div#search a",
            "a" # Fallback to all links if specific containers fail, filtered by href later
        ]
        
        links = []
        for selector in possible_selectors:
            found = driver.find_elements(By.CSS_SELECTOR, selector)
            if found:
                print(f"Selector '{selector}' found {len(found)} links.")
                links.extend(found)
        
        # Remove duplicates based on element ID or href
        unique_links = []
        seen_hrefs = set()
        
        for link in links:
            try:
                href = link.get_attribute("href")
                if href and href not in seen_hrefs:
                    seen_hrefs.add(href)
                    unique_links.append(link)
            except:
                continue
                
        found_id = None
        for link in unique_links:
            href = link.get_attribute("href")
            
            if href and "instagram.com" in href:
                # Extract ID
                match = re.search(r'instagram\.com/([a-zA-Z0-9._]+)', href)
                if match:
                    candidate = match.group(1)
                    
                    # Filter dummy words
                    dummy = ['p', 'reel', 'stories', 'explore', 'accounts', 'about', 'developer', 'help', 'creators']
                    if candidate.lower() not in dummy:
                        print(f"Found Candidate: {candidate} in {href}")
                        found_id = candidate
                        break
        
        return found_id

    except Exception as e:
        print(f"Selenium Search Error: {e}")
        return None
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    # Test
    print(search_google_selenium("Electric Garden Cairo", "Cairo", "Egypt"))
