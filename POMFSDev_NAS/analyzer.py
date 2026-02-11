import os
import re
import base64
import unicodedata
import time
import threading
from mistralai import Mistral
from datetime import datetime

# Global rate limiter for Mistral API (1 request per second)
_mistral_rate_lock = threading.Lock()
_mistral_last_request_time = 0

def _wait_for_rate_limit():
    """Ensure at least 1 second between Mistral API calls."""
    global _mistral_last_request_time
    with _mistral_rate_lock:
        current_time = time.time()
        time_since_last = current_time - _mistral_last_request_time
        if time_since_last < 1.0:
            wait_time = 1.0 - time_since_last
            time.sleep(wait_time)
        _mistral_last_request_time = time.time()

# Smart Year Inference Helper
def infer_year_for_month(event_month):
    """
    Infer the most likely year for an event based on the event month.
    Events are typically promoted 1-4 months in advance.
    
    Special handling for year boundary transitions only:
    - Early year (Jan-Mar) + late year event (Oct-Dec) → last year
    - Late year (Oct-Dec) + early year event (Jan-Mar) → next year
    - All other cases → current year
    
    Examples (assuming current month is January = 1):
    - December (12): early year + late event → last year (2025) ✓
    - November (11): early year + late event → last year (2025) ✓
    - October (10): early year + late event → last year (2025) ✓
    - August (8): not late event → this year (2026) ✓
    - April (4): not late event → this year (2026) ✓
    
    Examples (assuming current month is December = 12):
    - January (1): late year + early event → next year (2027) ✓
    - February (2): late year + early event → next year (2027) ✓
    - March (3): late year + early event → next year (2027) ✓
    - September (9): not early event → this year (2026) ✓
    """
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    is_early_year = current_month <= 3
    is_late_year = current_month >= 10
    is_early_event = event_month <= 3
    is_late_event = event_month >= 10
    
    if is_early_year and is_late_event:
        return current_year - 1
    elif is_late_year and is_early_event:
        return current_year + 1
    else:
        return current_year

# Common Date Parsing Logic
def parse_date_info(text):
    """
    Extracts date, venue, artist, and title info using regex and heuristics.
    Shared by both analyzers.
    """
    text = unicodedata.normalize('NFKC', text)
    
    info = {
        "is_event_poster": False,
        "dates": [],
        "venue": "",
        "artist": "",
        "title": "",
        "raw_text": text
    }
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        info['title'] = lines[0]

    full_dates = []
    
    for m in re.finditer(r'(202[4-9])[\.\/-](\d{1,2})[\.\/-](\d{1,2})', text):
        full_dates.append(f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}")
        
    for m in re.finditer(r'(?<!\d)(\d{1,2})[\.\/-](\d{1,2})(?!\d)', text):
         mo, da = int(m.group(1)), int(m.group(2))
         if 1 <= mo <= 12 and 1 <= da <= 31:
             inferred_year = infer_year_for_month(mo)
             full_dates.append(f"{inferred_year}-{str(mo).zfill(2)}-{str(da).zfill(2)}")

    for m in re.finditer(r'(\d{1,2})월\s*(\d{1,2})일', text):
         mo, da = int(m.group(1)), int(m.group(2))
         if 1 <= mo <= 12 and 1 <= da <= 31:
             inferred_year = infer_year_for_month(mo)
             full_dates.append(f"{inferred_year}-{str(mo).zfill(2)}-{str(da).zfill(2)}")
             
    for m in re.finditer(r'(?<!\d)(\d{1,2})1(\d{2})(?!\d)', text):
         mo, da = int(m.group(1)), int(m.group(2))
         if 1 <= mo <= 12 and 1 <= da <= 31:
              inferred_year = infer_year_for_month(mo)
              full_dates.append(f"{inferred_year}-{str(mo).zfill(2)}-{str(da).zfill(2)}")
              
    info["dates"] = list(dict.fromkeys(full_dates))

    # 3. Venue Extraction
    venue_header_match = re.search(r'(?:VENUE|Venue|Location|Place|会場).*', text, re.IGNORECASE)
    if venue_header_match:
        start_idx = text.find(venue_header_match.group(0)) + len(venue_header_match.group(0))
        post_header_text = text[start_idx:]
        
        lines = post_header_text.split('\n')
        possible_venues = []
        for line in lines:
            line = line.strip()
            if not line: continue
            
            bullet_match = re.match(r'(?:•|‣|-)\s*(.*)', line)
            if bullet_match:
                b_content = bullet_match.group(1).strip()
                if '‣' in b_content:
                    parts = b_content.split('‣')
                    val = parts[1].strip() if len(parts) > 1 else b_content
                    possible_venues.append(val)
                elif ':' in b_content:
                    parts = b_content.split(':')
                    possible_venues.append(parts[1].strip())
                else:
                    if not re.search(r'\d{4}', b_content) and 'JPY' not in b_content:
                        possible_venues.append(b_content)
            elif '「' in line or '」' in line:
                break
        
        if possible_venues:
            info['venue'] = ", ".join(possible_venues)
    
    if not info['venue']:
         v_match = re.search(r'(?:VENUE|Venue|Location|Place)\s*(?:‣|:|\||-)\s*(.*)', text, re.IGNORECASE)
         if v_match:
             val = v_match.group(1).strip()
             if len(val) > 1 and val not in ["会場", "Location"]:
                 info['venue'] = val

    # 4. Artist Extraction
    artist_match = re.search(r'(?:ARTIST|Artist|Lineup|Band|Cast|出演)\s*(?:‣|:|\||-)\s*(.*)', text, re.IGNORECASE)
    if artist_match:
        info['artist'] = artist_match.group(1).strip()
    
    # 5. Determine if this is an event poster (fallback heuristic)
    # Be generous: dates OR venue OR event keywords → event poster
    event_keywords = [
        '공연', '라이브', '파티', '콘서트', '페스티벌', '클럽', 'DJ', '이벤트',
        'LIVE', 'PARTY', 'CONCERT', 'FESTIVAL', 'GIG', 'SHOW', '출연',
        'ライブ', 'イベント', '入場', 'TICKET', '티켓', '예매', 'ADV', 'DOOR',
        'LINE UP', 'LINEUP', 'GUEST', 'OPENING', 'HEADLINER'
    ]
    
    has_event_keyword = any(kw.lower() in text.lower() for kw in event_keywords)
    
    if info['dates'] or info['venue'] or has_event_keyword:
        info['is_event_poster'] = True
        
    return info


class MistralAnalyzer:
    def __init__(self, api_key):
        print("Initializing Mistral OCR...")
        self.client = Mistral(api_key=api_key)
        
    def extract_text(self, image_path):
        if not os.path.exists(image_path):
            return ""
        try:
            with open(image_path, "rb") as image_file:
                 base64_img = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Rate limiting: 1 request per second
            _wait_for_rate_limit()
            
            response = self.client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{base64_img}"
                }
            )
            markdown_text = "\n".join([page.markdown for page in response.pages])
            return markdown_text
        except Exception as e:
            print(f"Error with Mistral OCR: {e}")
            return ""

    def parse_info(self, text):
        """
        Uses Mistral LLM to semantically extract structured data from the OCR text.
        """
        if not text:
             return parse_date_info(text) # Fallback

        print("[MistralAnalyzer] extracting structured info via LLM...")
        try:
            # Rate limiting: 1 request per second
            _wait_for_rate_limit()
            
            now = datetime.now()
            current_month = now.month
            current_year = now.year
            
            prompt = f"""
            Analyze the text below and extract event information into a JSON object.
            
            DETERMINE if this is an event/performance/party poster. Be GENEROUS in classification:
            
            IS an event poster if ANY of these are present:
            - Date information (날짜, 일시, 月, 日, specific dates like 1/23, 01.23)
            - Event keywords: 공연, 라이브, 파티, 콘서트, 페스티벌, 클럽, DJ, 이벤트, LIVE, PARTY, CONCERT, FESTIVAL, GIG, SHOW, 출연, ライブ, イベント
            - Venue/location names (클럽, 홀, 바, 라운지, Club, Hall, Bar, Lounge)
            - Ticket/entry info (입장료, 티켓, 예매, ADV, DOOR, ¥, ₩)
            - Artist/performer names or lineups
            
            NOT an event poster ONLY if it's clearly:
            - Personal selfie/daily life photo with no event info
            - Food/restaurant review without event
            - Product advertisement
            - Travel photo without performance info
            
            When in doubt, set is_event_poster to TRUE.
            
            Fields required:
            - "is_event_poster": true if this contains ANY event-related information (date, venue, artist, ticket info). Be generous!
            - "dates": List of dates in "YYYY-MM-DD" format. If year is missing, use these rules:
              * Current date is {current_year}-{str(current_month).zfill(2)}
              * Default to current year ({current_year}) for most cases
              * Only exception: year boundary transitions
                - If current month is Jan-Mar and event is Oct-Dec → use last year ({current_year - 1})
                - If current month is Oct-Dec and event is Jan-Mar → use next year ({current_year + 1})
              Empty list if no date found.
            - "time": Event start time in "HH:MM" 24-hour format (e.g. "19:00", "21:30"). Convert from any format:
              * "7PM" → "19:00", "9:30PM" → "21:30", "오후 7시" → "19:00"
              * If only OPEN/DOOR time shown, use that. If multiple times, use earliest.
              * Empty string if no time found.
            - "venue": Name of the venue (e.g. "Club Soap", "Rolling Hall", "Mudance"). Short venue name, NOT full address. Empty if not found.
            - "location": Full address if available (e.g. "서울특별시 용산구 이태원로27가길 42 3층"). Empty if no address.
            - "country": Country code based on venue/location (e.g. "KR" for Korea, "JP" for Japan, "US" for USA). Infer from:
              * Korean addresses (서울, 부산, 대구, etc.) → "KR"
              * Japanese addresses (東京, 大阪, etc.) or yen (¥) → "JP"
              * English addresses with US cities/states → "US"
              * Default to "KR" if Korean text detected.
            - "artist": Name of the artist or "Various" if multiple. Empty if not found.
            - "title": Event title or main text from poster. Extract even partial info.
            
            Text:
            {text[:3000]}
            
            Return ONLY the JSON object.
            """
            
            chat_response = self.client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            import json
            content = chat_response.choices[0].message.content
            data = json.loads(content)
            
            # Normalize to match expected interface
            info = {
                "is_event_poster": data.get('is_event_poster', False),
                "dates": data.get('dates', []),
                "time": data.get('time', ''),
                "venue": data.get('venue', ''),
                "location": data.get('location', ''),
                "country": data.get('country', 'KR'),
                "artist": data.get('artist', ''),
                "title": data.get('title', ''),
                "raw_text": text
            }
            return info
            
        except Exception as e:
            print(f"[MistralAnalyzer] LLM Parse Error: {e}. Fallback to regex.")
            return parse_date_info(text)


# Backward Compatibility - MistralAnalyzer is now the default
ImageAnalyzer = MistralAnalyzer
