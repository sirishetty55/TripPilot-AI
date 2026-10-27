"""
Location Resolution & Destination Classification Service for TripPilot AI.
Provides token-aware, country-code grounded location classification without
naive substring matching bugs (e.g. prevents 'Pudukkottai' containing 'uk'
from being falsely marked as international, and correctly identifies 'Luxembourg').
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Set
from config import BASE_DIR

@dataclass
class LocationInfo:
    query: str
    canonical_name: str
    country_code: str  # ISO 3166-1 alpha-2 code e.g. 'IN', 'LU', 'CH', 'FR'
    country_name: str
    is_island: bool = False
    is_ambiguous: bool = False
    confidence: float = 1.0

    @property
    def is_international(self) -> bool:
        return self.country_code != "IN" and self.country_code != "UNKNOWN"

@dataclass
class RouteClassification:
    origin: str
    destination: str
    origin_country: str
    dest_country: str
    is_overseas: Optional[bool]
    route_category: str  # 'domestic_mainland', 'international', 'island', 'unknown'
    description: str

# 1. ISO 3166-1 Country Mapping (names, codes, aliases)
COUNTRIES: Dict[str, Tuple[str, str]] = {
    # Code: (Canonical Country Name, Regex Pattern for exact word matches)
    "IN": ("India", r"\b(india|bharat|hindustan)\b"),
    "LU": ("Luxembourg", r"\b(luxembourg|luxemburg)\b"),
    "CH": ("Switzerland", r"\b(switzerland|swiss|helvetia|suisse|schweiz)\b"),
    "FR": ("France", r"\b(france|french)\b"),
    "DE": ("Germany", r"\b(germany|deutschland)\b"),
    "IT": ("Italy", r"\b(italy|italia)\b"),
    "ES": ("Spain", r"\b(spain|espana)\b"),
    "GB": ("United Kingdom", r"\b(uk|united kingdom|great britain|britain|england|scotland|wales)\b"),
    "US": ("United States", r"\b(usa|united states|america)\b"),
    "CA": ("Canada", r"\b(canada)\b"),
    "AU": ("Australia", r"\b(australia)\b"),
    "NZ": ("New Zealand", r"\b(new zealand)\b"),
    "JP": ("Japan", r"\b(japan|nippon)\b"),
    "SG": ("Singapore", r"\b(singapore)\b"),
    "TH": ("Thailand", r"\b(thailand|siam)\b"),
    "ID": ("Indonesia", r"\b(indonesia)\b"),
    "MY": ("Malaysia", r"\b(malaysia)\b"),
    "VN": ("Vietnam", r"\b(vietnam)\b"),
    "AE": ("United Arab Emirates", r"\b(uae|united arab emirates|dubai|abu dhabi)\b"),
    "QA": ("Qatar", r"\b(qatar)\b"),
    "OM": ("Oman", r"\b(oman)\b"),
    "TR": ("Turkey", r"\b(turkey|turkiye)\b"),
    "EG": ("Egypt", r"\b(egypt)\b"),
    "ZA": ("South Africa", r"\b(south africa)\b"),
    "MV": ("Maldives", r"\b(maldives|maldive)\b"),
    "MU": ("Mauritius", r"\b(mauritius)\b"),
    "SC": ("Seychelles", r"\b(seychelles)\b"),
    "LK": ("Sri Lanka", r"\b(sri lanka|ceylon)\b"),
    "NP": ("Nepal", r"\b(nepal)\b"),
    "BT": ("Bhutan", r"\b(bhutan)\b"),
    "NL": ("Netherlands", r"\b(netherlands|holland)\b"),
    "BE": ("Belgium", r"\b(belgium|belgique)\b"),
    "AT": ("Austria", r"\b(austria|osterreich)\b"),
    "SE": ("Sweden", r"\b(sweden)\b"),
    "NO": ("Norway", r"\b(norway)\b"),
    "DK": ("Denmark", r"\b(denmark)\b"),
    "FI": ("Finland", r"\b(finland)\b"),
    "IS": ("Iceland", r"\b(iceland)\b"),
    "GR": ("Greece", r"\b(greece|hellas)\b"),
    "PT": ("Portugal", r"\b(portugal)\b"),
    "CZ": ("Czech Republic", r"\b(czech republic|czechia|prague)\b"),
    "HU": ("Hungary", r"\b(hungary)\b"),
    "PL": ("Poland", r"\b(poland)\b"),
    "IE": ("Ireland", r"\b(ireland)\b"),
    "MX": ("Mexico", r"\b(mexico)\b"),
    "BR": ("Brazil", r"\b(brazil|brasil)\b"),
    "AR": ("Argentina", r"\b(argentina)\b"),
    "PE": ("Peru", r"\b(peru)\b"),
    "KR": ("South Korea", r"\b(south korea|korea)\b"),
    "CN": ("China", r"\b(china)\b"),
    "HK": ("Hong Kong", r"\b(hong kong)\b"),
}

# 2. Major World Cities & Regions mapped to ISO Country Code
WORLD_CITIES: Dict[str, Tuple[str, str, bool]] = {
    # lowercase city name: (Country Code, Canonical Name, is_island)
    "luxembourg": ("LU", "Luxembourg City", False),
    "luxembourg city": ("LU", "Luxembourg City", False),
    "zurich": ("CH", "Zurich", False),
    "geneva": ("CH", "Geneva", False),
    "interlaken": ("CH", "Interlaken", False),
    "lucerne": ("CH", "Lucerne", False),
    "zermatt": ("CH", "Zermatt", False),
    "basel": ("CH", "Basel", False),
    "bern": ("CH", "Bern", False),
    "grindelwald": ("CH", "Grindelwald", False),
    "lausanne": ("CH", "Lausanne", False),
    "paris": ("FR", "Paris", False),
    "nice": ("FR", "Nice", False),
    "lyon": ("FR", "Lyon", False),
    "marseille": ("FR", "Marseille", False),
    "chamonix": ("FR", "Chamonix", False),
    "london": ("GB", "London", False),
    "edinburgh": ("GB", "Edinburgh", False),
    "manchester": ("GB", "Manchester", False),
    "dublin": ("IE", "Dublin", False),
    "rome": ("IT", "Rome", False),
    "florence": ("IT", "Florence", False),
    "venice": ("IT", "Venice", False),
    "milan": ("IT", "Milan", False),
    "amalfi": ("IT", "Amalfi", False),
    "barcelona": ("ES", "Barcelona", False),
    "madrid": ("ES", "Madrid", False),
    "seville": ("ES", "Seville", False),
    "berlin": ("DE", "Berlin", False),
    "munich": ("DE", "Munich", False),
    "frankfurt": ("DE", "Frankfurt", False),
    "amsterdam": ("NL", "Amsterdam", False),
    "vienna": ("AT", "Vienna", False),
    "salzburg": ("AT", "Salzburg", False),
    "innsbruck": ("AT", "Innsbruck", False),
    "hallstatt": ("AT", "Hallstatt", False),
    "brussels": ("BE", "Brussels", False),
    "prague": ("CZ", "Prague", False),
    "budapest": ("HU", "Budapest", False),
    "athens": ("GR", "Athens", False),
    "santorini": ("GR", "Santorini", True),
    "mykonos": ("GR", "Mykonos", True),
    "crete": ("GR", "Crete", True),
    "lisbon": ("PT", "Lisbon", False),
    "porto": ("PT", "Porto", False),
    "new york": ("US", "New York", False),
    "nyc": ("US", "New York", False),
    "san francisco": ("US", "San Francisco", False),
    "los angeles": ("US", "Los Angeles", False),
    "las vegas": ("US", "Las Vegas", False),
    "miami": ("US", "Miami", False),
    "chicago": ("US", "Chicago", False),
    "hawaii": ("US", "Hawaii", True),
    "honolulu": ("US", "Honolulu", True),
    "maui": ("US", "Maui", True),
    "tokyo": ("JP", "Tokyo", False),
    "kyoto": ("JP", "Kyoto", False),
    "osaka": ("JP", "Osaka", False),
    "hokkaido": ("JP", "Hokkaido", True),
    "seoul": ("KR", "Seoul", False),
    "singapore": ("SG", "Singapore", True),
    "bangkok": ("TH", "Bangkok", False),
    "phuket": ("TH", "Phuket", True),
    "krabi": ("TH", "Krabi", False),
    "koh samui": ("TH", "Koh Samui", True),
    "chiang mai": ("TH", "Chiang Mai", False),
    "bali": ("ID", "Bali", True),
    "jakarta": ("ID", "Jakarta", True),
    "kuala lumpur": ("MY", "Kuala Lumpur", False),
    "penang": ("MY", "Penang", True),
    "langkawi": ("MY", "Langkawi", True),
    "hanoi": ("VN", "Hanoi", False),
    "da nang": ("VN", "Da Nang", False),
    "ho chi minh": ("VN", "Ho Chi Minh City", False),
    "dubai": ("AE", "Dubai", False),
    "abu dhabi": ("AE", "Abu Dhabi", False),
    "doha": ("QA", "Doha", False),
    "muscat": ("OM", "Muscat", False),
    "istanbul": ("TR", "Istanbul", False),
    "cairo": ("EG", "Cairo", False),
    "cape town": ("ZA", "Cape Town", False),
    "sydney": ("AU", "Sydney", False),
    "melbourne": ("AU", "Melbourne", False),
    "auckland": ("NZ", "Auckland", True),
    "queenstown": ("NZ", "Queenstown", True),
    "male": ("MV", "Male", True),
    "colombo": ("LK", "Colombo", True),
    "kathmandu": ("NP", "Kathmandu", False),
    "pokhara": ("NP", "Pokhara", False),
}

# 3. Comprehensive Indian Cities, Towns & Districts mapped to 'IN'
INDIAN_LOCATIONS: Dict[str, Tuple[str, bool]] = {
    # Name lowercase: (Canonical Name, is_island)
    "pudukkottai": ("Pudukkottai, Tamil Nadu", False),
    "pudukottai": ("Pudukkottai, Tamil Nadu", False),
    "goa": ("Goa", False),
    "panaji": ("Panaji, Goa", False),
    "candolim": ("Candolim, Goa", False),
    "calangute": ("Calangute, Goa", False),
    "baga": ("Baga, Goa", False),
    "margao": ("Margao, Goa", False),
    "jaipur": ("Jaipur, Rajasthan", False),
    "udaipur": ("Udaipur, Rajasthan", False),
    "jodhpur": ("Jodhpur, Rajasthan", False),
    "jaisalmer": ("Jaisalmer, Rajasthan", False),
    "pushkar": ("Pushkar, Rajasthan", False),
    "kerala": ("Kerala", False),
    "kochi": ("Kochi, Kerala", False),
    "cochin": ("Kochi, Kerala", False),
    "alleppey": ("Alleppey, Kerala", False),
    "alappuzha": ("Alappuzha, Kerala", False),
    "munnar": ("Munnar, Kerala", False),
    "wayanad": ("Wayanad, Kerala", False),
    "trivandrum": ("Thiruvananthapuram, Kerala", False),
    "thiruvananthapuram": ("Thiruvananthapuram, Kerala", False),
    "kovalam": ("Kovalam, Kerala", False),
    "varkala": ("Varkala, Kerala", False),
    "manali": ("Manali, Himachal Pradesh", False),
    "shimla": ("Shimla, Himachal Pradesh", False),
    "dharamshala": ("Dharamshala, Himachal Pradesh", False),
    "dharamsala": ("Dharamshala, Himachal Pradesh", False),
    "kullu": ("Kullu, Himachal Pradesh", False),
    "spiti": ("Spiti Valley, Himachal Pradesh", False),
    "kasol": ("Kasol, Himachal Pradesh", False),
    "mumbai": ("Mumbai, Maharashtra", False),
    "bombay": ("Mumbai, Maharashtra", False),
    "pune": ("Pune, Maharashtra", False),
    "lonavala": ("Lonavala, Maharashtra", False),
    "mahabaleshwar": ("Mahabaleshwar, Maharashtra", False),
    "nagpur": ("Nagpur, Maharashtra", False),
    "delhi": ("New Delhi", False),
    "new delhi": ("New Delhi", False),
    "ncr": ("Delhi NCR", False),
    "bengaluru": ("Bengaluru, Karnataka", False),
    "bangalore": ("Bengaluru, Karnataka", False),
    "mysore": ("Mysuru, Karnataka", False),
    "mysuru": ("Mysuru, Karnataka", False),
    "coorg": ("Coorg, Karnataka", False),
    "kodagu": ("Coorg, Karnataka", False),
    "hampi": ("Hampi, Karnataka", False),
    "gokarna": ("Gokarna, Karnataka", False),
    "mangalore": ("Mangaluru, Karnataka", False),
    "mangaluru": ("Mangaluru, Karnataka", False),
    "chennai": ("Chennai, Tamil Nadu", False),
    "madras": ("Chennai, Tamil Nadu", False),
    "madurai": ("Madurai, Tamil Nadu", False),
    "coimbatore": ("Coimbatore, Tamil Nadu", False),
    "ooty": ("Ooty, Tamil Nadu", False),
    "kodaikanal": ("Kodaikanal, Tamil Nadu", False),
    "rameswaram": ("Rameswaram, Tamil Nadu", False),
    "kanyakumari": ("Kanyakumari, Tamil Nadu", False),
    "pondicherry": ("Puducherry", False),
    "puducherry": ("Puducherry", False),
    "kolkata": ("Kolkata, West Bengal", False),
    "calcutta": ("Kolkata, West Bengal", False),
    "darjeeling": ("Darjeeling, West Bengal", False),
    "kalimpong": ("Kalimpong, West Bengal", False),
    "hyderabad": ("Hyderabad, Telangana", False),
    "ahmedabad": ("Ahmedabad, Gujarat", False),
    "surat": ("Surat, Gujarat", False),
    "rann of kutch": ("Kutch, Gujarat", False),
    "varanasi": ("Varanasi, Uttar Pradesh", False),
    "agra": ("Agra, Uttar Pradesh", False),
    "lucknow": ("Lucknow, Uttar Pradesh", False),
    "rishikesh": ("Rishikesh, Uttarakhand", False),
    "haridwar": ("Haridwar, Uttarakhand", False),
    "dehradun": ("Dehradun, Uttarakhand", False),
    "mussoorie": ("Mussoorie, Uttarakhand", False),
    "nainital": ("Nainital, Uttarakhand", False),
    "amritsar": ("Amritsar, Punjab", False),
    "chandigarh": ("Chandigarh", False),
    "srinagar": ("Srinagar, Jammu & Kashmir", False),
    "gulmarg": ("Gulmarg, Jammu & Kashmir", False),
    "leh": ("Leh, Ladakh", False),
    "ladakh": ("Ladakh", False),
    "gangtok": ("Gangtok, Sikkim", False),
    "shillong": ("Shillong, Meghalaya", False),
    "kaziranga": ("Kaziranga, Assam", False),
    "guwahati": ("Guwahati, Assam", False),
    "puri": ("Puri, Odisha", False),
    "bhubaneswar": ("Bhubaneswar, Odisha", False),
    # Indian Island destinations (require flight/ship from mainland)
    "andaman": ("Andaman & Nicobar Islands", True),
    "port blair": ("Port Blair, Andaman", True),
    "havelock": ("Havelock Island, Andaman", True),
    "neil island": ("Neil Island, Andaman", True),
    "lakshadweep": ("Lakshadweep Islands", True),
    "agatti": ("Agatti, Lakshadweep", True),
    "kavaratti": ("Kavaratti, Lakshadweep", True),
}

def resolve_location(query: str, default_country: str = "IN") -> LocationInfo:
    """
    Resolves an input location query into a structured LocationInfo object.
    Matches exact tokens/words to prevent naive substring bugs.
    """
    clean = query.strip()
    clean_lower = clean.lower()

    if not clean:
        return LocationInfo(
            query=query,
            canonical_name="Unknown",
            country_code="UNKNOWN",
            country_name="Unknown",
            is_ambiguous=True,
            confidence=0.0
        )

    # 1. Exact match in Indian locations
    if clean_lower in INDIAN_LOCATIONS:
        canonical, is_island = INDIAN_LOCATIONS[clean_lower]
        return LocationInfo(
            query=query,
            canonical_name=canonical,
            country_code="IN",
            country_name="India",
            is_island=is_island,
            confidence=1.0
        )

    # 2. Exact match in World cities
    if clean_lower in WORLD_CITIES:
        code, canonical, is_island = WORLD_CITIES[clean_lower]
        c_name = COUNTRIES.get(code, ("International", ""))[0]
        return LocationInfo(
            query=query,
            canonical_name=canonical,
            country_code=code,
            country_name=c_name,
            is_island=is_island,
            confidence=1.0
        )

    # 3. Check for exact country name match (using regex word boundaries)
    for code, (c_name, pattern) in COUNTRIES.items():
        if re.search(pattern, clean_lower, re.IGNORECASE):
            # Special check: If user typed e.g. "Pudukkottai" (which contains "uk"),
            # pattern r"\b(uk|...)\b" would NOT match because "uk" is surrounded by 'd' and 'k'!
            is_isl = code in ("MV", "MU", "SC", "SG", "IS", "NZ")
            return LocationInfo(
                query=query,
                canonical_name=c_name,
                country_code=code,
                country_name=c_name,
                is_island=is_isl,
                confidence=0.95
            )

    # 4. Partial token check for Indian multi-word locations
    # e.g. "North Goa", "South Goa", "Pudukkottai district", "Old Jaipur"
    for loc_key, (canonical, is_island) in INDIAN_LOCATIONS.items():
        if re.search(rf"\b{re.escape(loc_key)}\b", clean_lower):
            return LocationInfo(
                query=query,
                canonical_name=canonical,
                country_code="IN",
                country_name="India",
                is_island=is_island,
                confidence=0.9
            )

    # 5. Partial token check for world cities
    # e.g. "Central Zurich", "Greater London", "Downtown Paris", "Canton of Luxembourg"
    for city_key, (code, canonical, is_island) in WORLD_CITIES.items():
        if re.search(rf"\b{re.escape(city_key)}\b", clean_lower):
            c_name = COUNTRIES.get(code, ("International", ""))[0]
            return LocationInfo(
                query=query,
                canonical_name=canonical,
                country_code=code,
                country_name=c_name,
                is_island=is_island,
                confidence=0.9
            )

    # 6. Unresolved / Ambiguous location
    return LocationInfo(
        query=query,
        canonical_name=clean.title(),
        country_code="UNKNOWN",
        country_name="Unknown Destination",
        is_ambiguous=True,
        confidence=0.0
    )


def classify_route(
    origin_query: str,
    dest_query: str,
    default_origin_country: str = "IN"
) -> RouteClassification:
    """
    Classifies a travel route by comparing resolved origin and destination countries.
    Returns RouteClassification with:
    - 'domestic_mainland'
    - 'international'
    - 'island'
    - 'unknown'
    """
    origin_clean = origin_query.strip() if origin_query else ""
    dest_clean = dest_query.strip() if dest_query else ""

    dest_info = resolve_location(dest_clean)
    
    # If origin query provided, resolve it; otherwise assume default origin country
    if origin_clean:
        origin_info = resolve_location(origin_clean, default_country=default_origin_country)
    else:
        origin_info = LocationInfo(
            query="Default Origin",
            canonical_name="Default Origin",
            country_code=default_origin_country,
            country_name=COUNTRIES.get(default_origin_country, ("India", ""))[0],
            confidence=1.0
        )

    # Handle unknown destination
    if dest_info.country_code == "UNKNOWN":
        return RouteClassification(
            origin=origin_clean or origin_info.canonical_name,
            destination=dest_clean,
            origin_country=origin_info.country_code,
            dest_country="UNKNOWN",
            is_overseas=None,
            route_category="unknown",
            description=f"Destination '{dest_clean}' could not be reliably classified. Please specify city and country."
        )

    # Compare origin country with destination country
    if origin_info.country_code != "UNKNOWN" and origin_info.country_code == dest_info.country_code:
        # Same Country
        if dest_info.is_island or origin_info.is_island:
            return RouteClassification(
                origin=origin_clean or origin_info.canonical_name,
                destination=dest_info.canonical_name,
                origin_country=origin_info.country_code,
                dest_country=dest_info.country_code,
                is_overseas=True,
                route_category="island",
                description=f"Domestic island route within {dest_info.country_name}. Requires air or maritime transit."
            )
        else:
            return RouteClassification(
                origin=origin_clean or origin_info.canonical_name,
                destination=dest_info.canonical_name,
                origin_country=origin_info.country_code,
                dest_country=dest_info.country_code,
                is_overseas=False,
                route_category="domestic_mainland",
                description=f"Domestic mainland route within {dest_info.country_name}. Multi-modal overland transit viable."
            )
    else:
        # Cross-Border / International
        if dest_info.is_island:
            return RouteClassification(
                origin=origin_clean or origin_info.canonical_name,
                destination=dest_info.canonical_name,
                origin_country=origin_info.country_code,
                dest_country=dest_info.country_code,
                is_overseas=True,
                route_category="island",
                description=f"International island route from {origin_info.country_name} to {dest_info.country_name}. Requires flights and maritime transfers."
            )
        else:
            return RouteClassification(
                origin=origin_clean or origin_info.canonical_name,
                destination=dest_info.canonical_name,
                origin_country=origin_info.country_code,
                dest_country=dest_info.country_code,
                is_overseas=True,
                route_category="international",
                description=f"International cross-border route ({origin_info.country_name} -> {dest_info.country_name}). Requires air travel."
            )


class LocationService:
    """Convenience class wrapper for LocationService operations."""
    def __init__(self, origin_country_code: str = "IN"):
        self.origin_country_code = origin_country_code

    def resolve(self, destination: str) -> LocationInfo:
        return resolve_location(destination, default_country=self.origin_country_code)

    def classify(self, destination: str, origin: str = "") -> RouteClassification:
        return classify_route(origin, destination, default_origin_country=self.origin_country_code)
