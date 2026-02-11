"""
Google Geocoding API를 사용하여 장소명/주소를 좌표로 변환하는 모듈.

3단계 검색 전략:
1단계: event_location (상세 주소) → 성공률 95%+
2단계: event_venue + ", Seoul, South Korea" → 성공률 70-80%
3단계: 실패 시 NULL 반환 (캐러셀에만 표시)
"""

import os
import requests
from typing import Optional, Tuple, Dict, Any

GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY')
GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

DEFAULT_CITY = "Seoul, South Korea"


def geocode_location(
    location: Optional[str] = None,
    venue: Optional[str] = None,
    default_city: str = DEFAULT_CITY
) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """
    장소 정보를 좌표로 변환 (3단계 검색 전략).
    
    Args:
        location: 상세 주소 (예: "서울특별시 용산구 이태원로27가길 42 3층")
        venue: 장소명 (예: "Club Soap", "Shape Seoul")
        default_city: 장소명 검색 시 추가할 기본 도시 (기본값: "Seoul, South Korea")
    
    Returns:
        Tuple of (latitude, longitude, formatted_address, place_id)
        실패 시 모든 값이 None
    """
    if not GOOGLE_PLACES_API_KEY:
        print("[Geocoder] Error: GOOGLE_PLACES_API_KEY not set")
        return (None, None, None, None)
    
    # 1단계: 상세 주소로 검색
    if location and location.strip():
        print(f"[Geocoder] 1단계: 상세 주소 검색 - '{location}'")
        result = _geocode_query(location.strip())
        if result:
            print(f"[Geocoder] 성공: {result[2]}")
            return result
        print("[Geocoder] 1단계 실패, 2단계 시도...")
    
    # 2단계: 장소명 + 도시로 검색
    if venue and venue.strip():
        query = f"{venue.strip()}, {default_city}"
        print(f"[Geocoder] 2단계: 장소명+도시 검색 - '{query}'")
        result = _geocode_query(query)
        if result:
            print(f"[Geocoder] 성공: {result[2]}")
            return result
        print("[Geocoder] 2단계 실패")
    
    # 3단계: 실패
    print("[Geocoder] 모든 검색 실패 - 좌표 없이 저장됨")
    return (None, None, None, None)


def _geocode_query(query: str) -> Optional[Tuple[float, float, str, str]]:
    """
    Google Geocoding API 호출.
    
    Args:
        query: 검색할 주소 또는 장소명
    
    Returns:
        Tuple of (latitude, longitude, formatted_address, place_id) or None
    """
    try:
        params = {
            "address": query,
            "region": "KR",
            "language": "ko",
            "components": "country:KR",
            "key": GOOGLE_PLACES_API_KEY
        }
        
        response = requests.get(GEOCODING_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        status = data.get("status")
        
        if status == "OK" and data.get("results"):
            result = data["results"][0]
            geo = result["geometry"]["location"]
            
            # partial_match 경고
            if result.get("partial_match"):
                print(f"[Geocoder] Warning: partial_match - 정확도가 낮을 수 있음")
            
            return (
                geo["lat"],
                geo["lng"],
                result.get("formatted_address", ""),
                result.get("place_id", "")
            )
        
        elif status == "ZERO_RESULTS":
            print(f"[Geocoder] ZERO_RESULTS: '{query}' 검색 결과 없음")
        elif status == "OVER_QUERY_LIMIT":
            print("[Geocoder] Error: API 할당량 초과")
        elif status == "REQUEST_DENIED":
            print("[Geocoder] Error: API 요청 거부 - API 키 확인 필요")
        elif status == "INVALID_REQUEST":
            print(f"[Geocoder] Error: 잘못된 요청 - '{query}'")
        else:
            print(f"[Geocoder] Error: 알 수 없는 상태 - {status}")
        
        return None
        
    except requests.exceptions.Timeout:
        print(f"[Geocoder] Error: 요청 시간 초과 - '{query}'")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[Geocoder] Error: 네트워크 오류 - {e}")
        return None
    except Exception as e:
        print(f"[Geocoder] Error: 예외 발생 - {e}")
        return None


def geocode_batch(
    items: list,
    location_key: str = "location",
    venue_key: str = "venue",
    default_city: str = DEFAULT_CITY
) -> list:
    """
    여러 항목에 대해 일괄 Geocoding 수행.
    
    Args:
        items: 딕셔너리 리스트 (각 항목에 location, venue 키 포함)
        location_key: 상세 주소 필드명
        venue_key: 장소명 필드명
        default_city: 기본 도시
    
    Returns:
        각 항목에 latitude, longitude, formatted_address, place_id가 추가된 리스트
    """
    results = []
    
    for i, item in enumerate(items):
        location = item.get(location_key)
        venue = item.get(venue_key)
        
        print(f"[Geocoder] 배치 처리 {i+1}/{len(items)}")
        
        lat, lng, formatted_addr, place_id = geocode_location(
            location=location,
            venue=venue,
            default_city=default_city
        )
        
        result = item.copy()
        result["latitude"] = lat
        result["longitude"] = lng
        result["formatted_address"] = formatted_addr
        result["place_id"] = place_id
        results.append(result)
    
    return results


# 테스트용 함수
def test_geocoding():
    """Geocoding 기능 테스트."""
    test_cases = [
        # 1단계: 상세 주소
        {"location": "서울특별시 용산구 이태원로27가길 42", "venue": None},
        # 2단계: 장소명 + 도시
        {"location": None, "venue": "Shape Seoul"},
        # 실패 케이스
        {"location": None, "venue": None},
    ]
    
    print("=" * 60)
    print("Geocoding 테스트 시작")
    print("=" * 60)
    
    for i, case in enumerate(test_cases):
        print(f"\n테스트 {i+1}: location='{case['location']}', venue='{case['venue']}'")
        result = geocode_location(
            location=case["location"],
            venue=case["venue"]
        )
        print(f"결과: lat={result[0]}, lng={result[1]}")
        print(f"주소: {result[2]}")
        print("-" * 40)
    
    print("\n테스트 완료")


if __name__ == "__main__":
    test_geocoding()
