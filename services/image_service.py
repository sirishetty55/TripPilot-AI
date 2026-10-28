"""
Dynamic Destination & Landmark Image Retrieval Service for TripPilot AI.
Fetches real photographs from Wikimedia Commons / Wikipedia PageImages API,
with optional Unsplash API and Pexels API support when keys are configured.
Includes two-tier caching (in-memory + SQLite), attribution metadata, and alt text.
"""

import json
import os
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Tuple
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen
from config import BASE_DIR, DATABASE_PATH

@dataclass
class DestinationPhoto:
    image_url: str
    thumb_url: str
    alt_text: str
    attribution_text: str
    attribution_url: str
    provider: str
    is_exact_match: bool = True

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "DestinationPhoto":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# In-memory session cache: query_key -> DestinationPhoto
_MEMORY_IMAGE_CACHE: Dict[str, DestinationPhoto] = {}

def _init_image_cache_table():
    """Initializes SQLite cache table for retrieved images."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_cache (
                cache_key TEXT PRIMARY KEY,
                image_url TEXT NOT NULL,
                thumb_url TEXT NOT NULL,
                alt_text TEXT,
                attribution_text TEXT,
                attribution_url TEXT,
                provider TEXT,
                is_exact_match INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass

def _get_from_sqlite_cache(cache_key: str) -> Optional[DestinationPhoto]:
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT image_url, thumb_url, alt_text, attribution_text, attribution_url, provider, is_exact_match FROM image_cache WHERE cache_key = ?", (cache_key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return DestinationPhoto(
                image_url=row[0],
                thumb_url=row[1],
                alt_text=row[2],
                attribution_text=row[3],
                attribution_url=row[4],
                provider=row[5],
                is_exact_match=bool(row[6])
            )
    except Exception:
        pass
    return None

def _save_to_sqlite_cache(cache_key: str, photo: DestinationPhoto):
    try:
        _init_image_cache_table()
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT OR REPLACE INTO image_cache (
                cache_key, image_url, thumb_url, alt_text, attribution_text,
                attribution_url, provider, is_exact_match, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cache_key, photo.image_url, photo.thumb_url, photo.alt_text,
            photo.attribution_text, photo.attribution_url, photo.provider,
            1 if photo.is_exact_match else 0, now
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _fetch_from_wikimedia(query: str, search_context: str = "", index: int = 0) -> Optional[DestinationPhoto]:
    """
    Fetches real photograph from Wikimedia / Wikipedia PageImages API.
    Provides attribution and description under Creative Commons / Public Domain.
    index: used to paginate results so multiple calls for the same destination return different images.
    """
    search_term = f'"{query}" {search_context}'.strip() if search_context else query.strip()
    params = urlencode({
        "action": "query",
        "generator": "search",
        "gsrsearch": search_term,
        "gsrnamespace": 0,
        "gsrlimit": max(5, index + 3),
        "gsroffset": index,
        "prop": "pageimages|info",
        "piprop": "thumbnail|original",
        "pithumbsize": 800,
        "inprop": "url",
        "format": "json"
    })
    
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    headers = {
        "User-Agent": "TripPilotAI/1.0 (https://trippilot.edu; educational travel assistant)"
    }
    
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return None
            
        page_list = list(pages.values())
        valid_pages = [
            p for p in page_list
            if p.get("thumbnail", {}).get("source") or p.get("original", {}).get("source")
        ]
        if not valid_pages:
            return None
            
        selected_page = valid_pages[index % len(valid_pages)]
        thumb = selected_page.get("thumbnail", {}).get("source", "")
        original = selected_page.get("original", {}).get("source", thumb)
        title = selected_page.get("title", query)
        page_url = selected_page.get("fullurl", f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}")
        
        if thumb or original:
            img_url = original if original else thumb
            return DestinationPhoto(
                image_url=img_url,
                thumb_url=thumb if thumb else img_url,
                alt_text=f"Photograph of {title} in {search_context or query}",
                attribution_text=f"Wikimedia Commons / Wikipedia: {title}",
                attribution_url=page_url,
                provider="Wikimedia Commons",
                is_exact_match=True
            )
    except Exception:
        pass
    return None


UNWANTED_PHOTO_TERMS = (
    "portrait", "man in", "woman in", "portrait of", "person", "selfie",
    "male model", "female model", "guy standing", "man standing", "woman standing",
    "close up of person", "headshot", "facial expression", "posing", "fashion model",
    "portrait photography"
)

def _fetch_from_unsplash(query: str, access_key: str, page: int = 1, category: str = "attraction") -> Optional[DestinationPhoto]:
    """Fetches high-resolution photo from official Unsplash API, filtering out unrelated portraits/people."""
    if not access_key:
        return None
    params = urlencode({
        "query": query,
        "orientation": "landscape",
        "per_page": 5,
        "page": max(1, page),
        "client_id": access_key
    })
    url = f"https://api.unsplash.com/search/photos?{params}"
    req = Request(url, headers={"User-Agent": "TripPilotAI/1.0"})
    try:
        with urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results", [])
        for item in results:
            description = (item.get("description") or item.get("alt_description") or "").lower()
            # Filter out person/portrait photos for attractions, hotels, and cuisine
            if any(term in description for term in UNWANTED_PHOTO_TERMS):
                continue
            urls = item.get("urls", {})
            user = item.get("user", {})
            user_name = user.get("name", "Unsplash Contributor")
            user_link = user.get("links", {}).get("html", "https://unsplash.com")
            display_desc = item.get("description") or item.get("alt_description") or f"Photo of {query}"
            return DestinationPhoto(
                image_url=urls.get("regular", urls.get("small", "")),
                thumb_url=urls.get("small", ""),
                alt_text=str(display_desc),
                attribution_text=f"Photo by {user_name} on Unsplash",
                attribution_url=f"{user_link}?utm_source=TripPilotAI&utm_medium=referral",
                provider="Unsplash",
                is_exact_match=True
            )
    except Exception:
        pass
    return None


FORBIDDEN_PHOTO_TERMS = (
    "wine and other products", "products", "other products", "local products",
    "souvenirs", "shopping", "electricity", "utilities", "electricity and utilities",
    "tourist information", "practical information", "public holidays", "public holiday",
    "stay safe", "stay healthy", "districts", "regions", "cities", "other destinations",
    "the year in"
)

def get_destination_photo(
    name: str,
    destination: str = "",
    category: str = "attraction",
    index: int = 0
) -> DestinationPhoto:
    """
    Main entrypoint to retrieve genuine destination photographs.
    index: pass different values (0, 1, 2…) for different cards at the same destination
           so they get different images rather than the same fallback photo.
    Checks memory cache -> SQLite persistent cache -> Unsplash API (if configured) -> Wikimedia API.
    Returns DestinationPhoto with full attribution metadata and alt text.
    """
    clean_name = name.strip()
    clean_dest = destination.strip()
    folded_name = clean_name.lower()

    # Reject non-attraction/utility/shopping terms from image fetching
    if any(bad in folded_name for bad in FORBIDDEN_PHOTO_TERMS):
        return DestinationPhoto(
            image_url="",
            thumb_url="",
            alt_text=f"Reference for {clean_name}",
            attribution_text="",
            attribution_url="",
            provider="None",
            is_exact_match=False
        )

    cache_key = f"{clean_name.casefold()}|{clean_dest.casefold()}|{category.casefold()}|{index}"

    # 1. In-memory cache
    if cache_key in _MEMORY_IMAGE_CACHE:
        return _MEMORY_IMAGE_CACHE[cache_key]

    # 2. SQLite persistent cache
    cached = _get_from_sqlite_cache(cache_key)
    if cached:
        _MEMORY_IMAGE_CACHE[cache_key] = cached
        return cached

    photo: Optional[DestinationPhoto] = None

    # 3. Check for Unsplash Access Key
    unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
    if unsplash_key:
        cat_lower = category.lower()
        if "hotel" in cat_lower or "stay" in cat_lower or "accommodation" in cat_lower:
            u_query = f"{clean_name} hotel resort"
        elif "food" in cat_lower or "dining" in cat_lower or "cuisine" in cat_lower:
            u_query = f"{clean_name} food dish"
        elif "beach" in cat_lower:
            u_query = f"{clean_name} beach {clean_dest}".strip()
        else:
            u_query = f"{clean_name} {clean_dest}".strip()
        photo = _fetch_from_unsplash(u_query, unsplash_key, page=index + 1, category=category)

    # 4. Wikimedia Commons / Wikipedia API (Default primary provider)
    if not photo or not photo.image_url:
        # First attempt: exact landmark + destination
        photo = _fetch_from_wikimedia(clean_name, clean_dest, index=index)

    # 5. Fallback attempt: only for index 0 to avoid repeating identical photo across every card
    if not photo or not photo.image_url:
        if clean_dest and clean_name.lower() != clean_dest.lower() and index == 0:
            dest_photo = _fetch_from_wikimedia(clean_dest, index=0)
            if dest_photo and dest_photo.image_url:
                photo = DestinationPhoto(
                    image_url=dest_photo.image_url,
                    thumb_url=dest_photo.thumb_url,
                    alt_text=f"Destination scenery of {clean_dest} ({clean_name})",
                    attribution_text=dest_photo.attribution_text,
                    attribution_url=dest_photo.attribution_url,
                    provider=dest_photo.provider,
                    is_exact_match=False
                )

    # 6. If no exact/unique image found, return neutral honest placeholder (no fabricated URL or duplicate)
    if not photo or not photo.image_url:
        photo = DestinationPhoto(
            image_url="",
            thumb_url="",
            alt_text=f"Travel reference for {clean_name}",
            attribution_text="",
            attribution_url="",
            provider="None",
            is_exact_match=False
        )

    # Save to both caches
    _MEMORY_IMAGE_CACHE[cache_key] = photo
    if photo.image_url:
        _save_to_sqlite_cache(cache_key, photo)

    return photo

