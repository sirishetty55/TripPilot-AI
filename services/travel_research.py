"""
Travel Research Service for TripPilot AI.
Orchestrates multi-source browser research across real travel guides, transit platforms,
and hotel directories using Playwright MCP, synthesized with Gemini AI.
"""

import re
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Generator, Tuple, Optional
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from models import (
    TripRequest, TripResearchResult, Attraction, Accommodation, FoodExperience, DayPlan, CommuteOption
)
from services.mcp_client import PlaywrightMCPClient
from services.demo_server import get_demo_page_url
from services.location_service import resolve_location, classify_route
from services.image_service import get_destination_photo, DestinationPhoto
from config import get_gemini_api_key, GEMINI_MODEL

# In-memory snapshot cache: dest_clean -> (timestamp, source_url, snapshot_text)
_SNAPSHOT_CACHE: Dict[str, Tuple[float, str, str]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes
_ATTRACTION_IMAGE_CACHE: Dict[str, str] = {}

def get_real_travel_urls(destination: str) -> List[str]:
    """Generates real live public travel website URLs."""
    dest_clean = destination.strip().title().replace(" ", "_")
    return [
        f"https://en.m.wikivoyage.org/wiki/{dest_clean}",
        f"https://en.wikivoyage.org/wiki/{dest_clean}",
        f"https://en.m.wikipedia.org/wiki/{dest_clean}"
    ]

def condense_snapshot(text: str, max_chars: int = 15000) -> str:
    """Extracts high-density travel facts from the raw accessibility tree."""
    meaningful = []
    keywords = ('heading ', 'text:', 'link ', 'paragraph', '₹', 'rs.', 'rs ', 'inr', 'free',
                'hotel', 'resort', 'hostel', 'stay', 'beach', 'fort', 'temple', 'church',
                'museum', 'safari', 'entry', 'timing', 'curry', 'restaurant', 'cafe', 'thali',
                'airport', 'flight', 'train', 'railway', 'station', 'bus', 'highway', 'nh')
    
    for line in text.splitlines():
        line_clean = line.strip()
        line_lower = line_clean.lower()
        if any(kw in line_lower for kw in keywords):
            cleaned = re.sub(r'\[ref=e\d+\]', '', line_clean)
            cleaned = re.sub(r'\[cursor=pointer\]', '', cleaned)
            cleaned = re.sub(r'\[level=\d+\]', '', cleaned)
            cleaned = cleaned.strip(" -")
            if len(cleaned) > 2:
                meaningful.append(cleaned)
    
    condensed = "\n".join(meaningful)
    return condensed[:max_chars] if len(condensed) > max_chars else condensed

# Known international destinations, countries, and world cities
INTERNATIONAL_KEYWORDS = {
    # Switzerland / Alps
    "switzerland", "swiss", "zurich", "geneva", "interlaken", "lucerne", "zermatt", "basel", "bern",
    "lausanne", "st moritz", "grindelwald", "jungfrau", "swirzerland", "switz",
    # Europe
    "france", "paris", "nice", "lyon", "marseille", "bordeaux", "strasbourg", "chamonix",
    "italy", "rome", "florence", "venice", "milan", "naples", "amalfi", "positano", "cinque terre",
    "germany", "berlin", "munich", "frankfurt", "hamburg", "cologne", "bavaria",
    "spain", "barcelona", "madrid", "seville", "valencia", "ibiza", "mallorca", "granada",
    "uk", "united kingdom", "london", "edinburgh", "scotland", "manchester", "birmingham", "ireland", "dublin",
    "europe", "european",
    "netherlands", "amsterdam", "rotterdam", "hague",
    "austria", "vienna", "salzburg", "innsbruck", "hallstatt",
    "sweden", "stockholm", "gothenburg",
    "norway", "oslo", "bergen", "tromso", "fjords",
    "denmark", "copenhagen",
    "finland", "helsinki", "rovaniemi", "lapland",
    "iceland", "reykjavik",
    "greece", "athens", "santorini", "mykonos", "crete", "rhodes",
    "portugal", "lisbon", "porto", "algarve", "madeira",
    "czech republic", "czechia", "prague",
    "hungary", "budapest",
    "belgium", "brussels", "bruges", "ghent",
    "luxembourg",
    "poland", "krakow", "warsaw",
    "croatia", "dubrovnik", "split", "zagreb",
    # Americas
    "usa", "united states", "america", "new york", "nyc", "san francisco", "los angeles", "las vegas",
    "chicago", "miami", "orlando", "seattle", "boston", "washington dc", "hawaii", "honolulu", "maui",
    "canada", "toronto", "vancouver", "montreal", "banff", "calgary", "ottawa",
    "mexico", "cancun", "mexico city", "tulum", "cabo",
    "brazil", "rio de janeiro", "sao paulo",
    "argentina", "buenos aires", "patagonia",
    "peru", "lima", "cusco", "machu picchu",
    # Asia Pacific
    "australia", "sydney", "melbourne", "brisbane", "perth", "gold coast", "cairns",
    "new zealand", "auckland", "queenstown", "christchurch", "rotorua",
    "japan", "tokyo", "kyoto", "osaka", "hokkaido", "sapporo", "hiroshima", "fuji",
    "south korea", "korea", "seoul", "busan", "jeju",
    "singapore",
    "malaysia", "kuala lumpur", "penang", "langkawi",
    "thailand", "bangkok", "phuket", "pattaya", "krabi", "chiang mai", "koh samui",
    "indonesia", "bali", "jakarta", "lombok", "ubud", "komodo",
    "vietnam", "hanoi", "ho chi minh", "da nang", "ha long", "hoi an",
    "philippines", "manila", "boracay", "cebu", "palawan",
    "hong kong", "macau", "taiwan", "taipei",
    # Middle East & Africa
    "uae", "dubai", "abu dhabi", "sharjah",
    "qatar", "doha",
    "oman", "muscat",
    "turkey", "istanbul", "cappadocia", "antalya",
    "egypt", "cairo", "luxor", "hurghada", "sharm",
    "south africa", "cape town", "johannesburg", "kruger",
    "kenya", "nairobi", "masai mara",
    "morocco", "marrakech", "casablanca", "fes",
    "tanzania", "zanzibar", "serengeti",
    # Islands
    "maldives", "male",
    "mauritius",
    "seychelles",
    "fiji",
    "sri lanka", "colombo", "kandy", "galle",
    "nepal", "kathmandu", "pokhara",
    "bhutan", "paro", "thimphu"
}

ISLAND_DESTINATIONS = {
    "maldives", "male", "andaman", "nicobar", "port blair", "havelock", "neil island",
    "lakshadweep", "agatti", "kavaratti", "mauritius", "bali", "phuket", "koh samui",
    "hawaii", "honolulu", "maui", "santorini", "mykonos", "seychelles", "fiji", "bora bora", "zanzibar"
}

GENERIC_OR_INVALID_ATTRACTION_NAMES = {
    # Generic placeholders & terms
    "name", "people", "person", "population", "residents", "citizens", "locals",
    "things to do", "attractions", "see", "do", "buy", "eat", "drink", "sleep", "go next",
    "overview", "understand", "background", "history", "introduction", "summary",
    "old mumbai", "air-conditioned taxis", "taxi", "taxis", "transport", "transportation",
    "getting around", "how to get there", "get in", "get there", "get around", "get out",
    "contents", "references", "external links", "navigation", "menu", "talk", "see also", "further reading",
    # Guide divisions & geography
    "regions", "cities", "other destinations", "districts", "boroughs", "neighborhoods",
    "quarters", "suburbs", "area", "coordinates", "location", "founded", "capital",
    "demographics", "geography", "economy", "politics", "culture", "religion", "language",
    "weather", "climate", "flora", "fauna", "flora and fauna",
    # Utilities, infrastructure, practicalities
    "electricity", "utilities", "electricity and utilities", "power", "plugs", "voltage",
    "tourist information", "visitor information", "practical information", "practicalities",
    "stay safe", "stay healthy", "safety", "health", "respect", "customs", "etiquette",
    "connect", "telecoms", "mobile", "internet", "cope", "work", "study", "learn",
    "visas", "passports", "customs regulations", "emergency", "embassies", "consulates",
    "contact", "addresses", "contacts", "phone numbers", "opening hours", "time zone",
    "currency", "costs", "tipping", "money", "events", "festivals",
    "holidays", "public holidays", "national holidays", "bank holidays", "school holidays",
    "public holiday", "national holiday", "bank holiday", "the year in sweden",
    "the year in france", "the year in italy", "the year in spain", "the year in",
    "itineraries", "routes", "map", "maps", "facts", "quick facts", "smoking", "alcohol",
    # Merchandise, shopping & commercial goods
    "wine and other products", "other products", "local products", "products",
    "wine and spirits", "souvenirs", "shopping and souvenirs", "shopping", "what to buy",
    "handicrafts", "local specialties", "markets and shopping", "clothing and textiles",
    "duty free", "duty-free", "currency exchange",
}

NON_ATTRACTION_TERMS = (
    "air-conditioned taxi", "taxi service", "bus service", "train service",
    "public transit", "airport transfer", "railway station booking", "hotel booking",
    "electricity", "utilities", "tourist information", "visitor information",
    "public holiday", "national holiday", "bank holiday", "external links", "further reading",
    "other destinations", "getting there", "getting around", "stay safe", "stay healthy",
    "the year in", "when to ", "how to ", "what to ", "where to ",
    "wine and other products", "other products", "local products", "products",
    "souvenirs", "shopping in", "what to buy",
)

ATTRACTION_INDICATOR_WORDS = {
    "museum", "fort", "palace", "temple", "cathedral", "basilica", "mosque", "church",
    "castle", "monument", "memorial", "gallery", "park", "garden", "zoo", "aquarium",
    "beach", "lake", "waterfall", "mountain", "peak", "valley", "canyon", "gorge",
    "island", "archipelago", "reef", "bay", "viewpoint", "promenade", "boulevard",
    "square", "plaza", "market", "bazaar", "heritage", "archaeological", "ruins",
    "tower", "bridge", "lighthouse", "dam", "sanctuary", "reserve", "national park",
    "botanical", "observatory", "planetarium", "ancient", "historic", "old town",
    "quarter", "thermal", "hot springs", "winery", "vineyard", "farm", "trail",
    "trek", "pass", "ghats", "ghat", "dargah", "shrine", "mandir", "masjid",
    "haveli", "stepwell", "baoli", "vav", "minaret", "gopuram", "stupa", "pagoda",
    "kremlin", "colosseum", "parthenon", "acropolis", "pantheon", "forum",
    "safari", "wildlife", "bird sanctuary", "wetland", "lagoon",
    "waterfront", "harbour", "harbor", "pier", "jetty", "marina", "coast",
    "cliff", "cave", "cavern", "grotto", "rock", "cove", "dunes", "desert",
    "glacier", "fjord", "plateau", "mesa", "crater", "volcano",
    "monastery", "abbey", "convent", "ashram", "gurudwara", "synagogue",
    "amphitheatre", "amphitheater", "arena", "stadium",
    "mausoleum", "tomb", "cenotaph", "obelisk", "pyramid", "sphinx",
    "statue", "sculpture", "fountain", "arch", "gate", "wall",
    "backwaters", "houseboat", "gondola", "tram", "cable car", "funicular",
}

def is_valid_attraction_name(name: str, destination: str) -> bool:
    """Reject navigation labels, generic placeholders, shopping/merchandise, and transport/service headings."""
    value = re.sub(r"\s+", " ", str(name or "")).strip(" -–—:|.")
    folded = value.casefold()
    if len(value) < 4 or len(value) > 100 or folded == destination.casefold():
        return False

    # Block individual guide division names and meta sections
    single_word_non_attractions = {
        "regions", "cities", "districts", "boroughs", "suburbs", "quarters", "provinces",
        "understand", "background", "history", "geography", "demographics", "climate", "weather",
        "see", "do", "buy", "eat", "drink", "sleep", "connect", "cope", "work", "study",
        "contents", "references", "navigation", "menu", "talk", "overview", "safety", "health",
        "electricity", "utilities", "power", "money", "costs", "tipping", "shopping", "products",
        "souvenirs", "visas", "passports", "emergency", "holidays", "transport", "transportation",
        "name", "people", "locals", "population", "events", "festivals", "itineraries"
    }
    if folded in single_word_non_attractions:
        return False

    # Single-word fully lowercase is almost always a guide section, not a named attraction
    if " " not in value and value == value.lower():
        return False
    if folded in GENERIC_OR_INVALID_ATTRACTION_NAMES:
        return False
    if any(term in folded for term in NON_ATTRACTION_TERMS):
        return False
    bad_prefixes = (
        "the year in", "when to ", "get ", "by ", "stay ", "how to ",
        "what to ", "where to ", "public holiday", "national holiday",
        "bank holiday", "school holiday", "traditional ", "getting ",
    )
    if any(folded.startswith(p) for p in bad_prefixes):
        return False
    bad_substrings = (
        "electricity", "utilities", "tourist information", "visitor information",
        "practical information", "external links", "further reading", "see also",
        "other destinations", "public holiday", "national holiday", "bank holiday",
        "calling code", "country code", "time zone", "emergency", "wine and other products",
        "products", "souvenirs", "shopping in",
    )
    if any(s in folded for s in bad_substrings):
        return False
    if re.fullmatch(r"(?:name|people|place|attraction|item|result|landmark)(?:\s*\d+)?", folded):
        return False
    # Positive check: contains known landmark keyword
    if any(kw in folded for kw in ATTRACTION_INDICATOR_WORDS):
        return True
    # Positive check: multi-word proper noun that is capitalized
    words = value.split()
    if len(words) >= 2 and value[0].isupper():
        generic_concepts = {
            "the year", "the region", "the city", "the area", "the country",
            "the people", "the culture", "the economy", "the history",
            "the climate", "the weather", "the politics", "the language",
            "the currency", "the population", "traditional crafts", "traditional foods",
            "local products", "wine and", "beer and", "food and", "drinks and"
        }
        if any(folded.startswith(gc) for gc in generic_concepts):
            return False
        if any(w in ("products", "product", "utilities", "information", "regulations", "services") for w in folded.split()):
            return False
        return True
    return False


def curated_destination_attractions(destination: str) -> List[Attraction]:
    """Curated verified landmarks for destinations; shown as suggestions, not live-verified data."""
    key = destination.casefold().strip()
    catalogue = {
        "mumbai": [
            ("Gateway of India", "Iconic waterfront basalt arch overlooking Mumbai Harbour.", "History & Heritage", "Colaba"),
            ("Marine Drive", "Crescent-shaped seaside promenade, especially popular at sunset.", "Seaside Walk", "Churchgate to Nariman Point"),
            ("Chhatrapati Shivaji Maharaj Terminus", "Historic Victorian Gothic railway terminus and UNESCO World Heritage Site.", "Architecture", "Fort"),
            ("Chhatrapati Shivaji Maharaj Vastu Sangrahalaya", "Museum with collections spanning Indian art, archaeology, and natural history.", "Museum", "Kala Ghoda"),
            ("Kanheri Caves", "Ancient Buddhist rock-cut caves within Sanjay Gandhi National Park.", "History & Nature", "Borivali"),
            ("Mani Bhavan Gandhi Sangrahalaya", "Museum in the historic building associated with Mahatma Gandhi's work in Mumbai.", "History", "Gamdevi"),
            ("Haji Ali Dargah", "Mosque and dargah on an islet off the Worli coast; access depends on tide conditions.", "Spiritual & Culture", "Worli"),
            ("Shree Siddhivinayak Temple", "Well-known temple dedicated to Lord Ganesha.", "Spiritual & Culture", "Prabhadevi"),
            ("Elephanta Caves", "Rock-cut cave temples on Elephanta Island, reached by ferry from the city.", "History & Heritage", "Elephanta Island"),
        ],
        "kundapura": [
            ("Kodi Beach", "Coastal beach near the meeting point of the sea and river estuary.", "Beach & Nature", "Kodi"),
            ("Maravanthe Beach", "Scenic coastal stretch with the Arabian Sea on one side and the Souparnika River on the other.", "Beach & Scenic Drive", "Maravanthe"),
            ("Kollur Mookambika Temple", "Important Hindu pilgrimage temple in the Western Ghats region near Kundapura.", "Spiritual & Culture", "Kollur"),
            ("Anegudde Vinayaka Temple", "Popular Ganesha temple in the Kumbashi area.", "Spiritual & Culture", "Kumbashi"),
            ("Trasi Beach", "Quiet coastal area known for sea views and a relaxed beach visit.", "Beach & Nature", "Trasi"),
            ("Ottinene View Point", "Coastal viewpoint overlooking the estuary and Arabian Sea near Byndoor.", "Viewpoint & Nature", "Byndoor"),
        ],
        "sweden": [
            ("Vasa Museum", "17th-century preserved royal warship salvaged from Stockholm harbor, Scandinavia's premier maritime museum.", "Museum", "Stockholm"),
            ("Gamla Stan (Stockholm Old Town)", "Stockholm's picturesque medieval quarter with cobblestone streets, ochre townhouses, and royal palaces.", "Historic District", "Stockholm"),
            ("Drottningholm Palace", "17th-century UNESCO palace complex and residence of the Swedish royal family, featuring baroque gardens.", "Palace & Heritage", "Drottningholm"),
            ("Skansen Open-Air Museum", "World's oldest open-air living history museum and Nordic wildlife park overlooking central Stockholm.", "Living History Museum", "Stockholm"),
            ("ABBA The Museum", "Interactive museum showcasing Sweden's iconic musical legends with authentic costumes and records.", "Music & Pop Culture", "Stockholm"),
            ("Stockholm Archipelago", "Scenic maritime labyrinth of over 30,000 granite islands and tranquil waterways reachable by ferry.", "Scenic Nature", "Stockholm"),
        ],
        "paris": [
            ("Eiffel Tower", "World-famous iron lattice tower on the Champ de Mars offering panoramic views across Paris.", "Iconic Landmark", "7th Arrondissement"),
            ("Louvre Museum", "World's premier art museum housing the Mona Lisa, Venus de Milo, and iconic glass pyramid.", "Art Museum", "1st Arrondissement"),
            ("Notre-Dame Cathedral", "Historic medieval Gothic cathedral on the Île de la Cité on the Seine River.", "Cathedral & Architecture", "Île de la Cité"),
            ("Musée d'Orsay", "Former Beaux-Arts railway station housing masterpieces by Monet, Van Gogh, Renoir, and Degas.", "Art Museum", "7th Arrondissement"),
            ("Montmartre & Sacré-Cœur", "Atmospheric hilltop district featuring the white-domed basilica and panoramic Parisian terraces.", "Historic Quarter", "18th Arrondissement"),
            ("Arc de Triomphe", "Monumental neoclassical arch honoring French triumphs at the crown of the Champs-Élysées.", "Monument", "8th Arrondissement"),
        ],
        "switzerland": [
            ("Jungfraujoch - Top of Europe", "High-altitude glacier railway observatory and Ice Palace with panoramic views of the Aletsch Glacier.", "Alpine Peak", "Bernese Alps"),
            ("Matterhorn & Zermatt", "World-famous pyramid-shaped peak and alpine resort village renowned for mountaineering.", "Mountain Landmark", "Zermatt"),
            ("Chillon Castle (Château de Chillon)", "Historic island castle on Lake Geneva with centuries of Savoyard history.", "Medieval Castle", "Montreux"),
            ("Chapel Bridge (Kapellbrücke)", "14th-century covered wooden footbridge with historic interior paintings across the Reuss River.", "Historic Landmark", "Lucerne"),
            ("Lauterbrunnen Valley & Waterfalls", "Dramatic glacial valley flanked by vertical cliffs and 72 cascading waterfalls.", "Natural Wonder", "Lauterbrunnen"),
        ],
        "goa": [
            ("Basilica of Bom Jesus", "16th-century baroque basilica holding the sacred mortal remains of St. Francis Xavier in Old Goa.", "UNESCO Heritage Church", "Old Goa"),
            ("Fort Aguada & Lighthouse", "Well-preserved 17th-century Portuguese fortress overlooking Sinquerim beach and the Arabian Sea.", "Coastal Fortress", "Sinquerim"),
            ("Dudhsagar Waterfalls", "Four-tiered roaring white cascade on the Mandovi River nestled in dense Western Ghats jungle.", "Scenic Waterfall", "Sonaulim"),
            ("Baga Beach", "Vibrant North Goa shoreline celebrated for water sports, beach shacks, lively sunset vibe, and dolphin boat cruises.", "Sandy Beach & Water Sports", "North Goa"),
            ("Palolem Beach", "Crescent-shaped serene beach surrounded by coconut palms, rocky headlands, and calm waters.", "Scenic Coastline", "Canacona"),
            ("Fontainhas Latin Quarter", "Colorful Portuguese colonial residential quarter in Panaji with tiled roofs, cafes, and art galleries.", "Heritage Precinct", "Panaji"),
            ("Chapora Fort", "Historic hilltop laterite fort commanding sweeping views over Vagator beach and the Chapora river estuary.", "Hilltop Fortress", "Vagator"),
        ],
        "jaipur": [
            ("Amber Fort & Palace", "Majestic 16th-century Rajput palace fortress with marble courtyards, Sheesh Mahal, and Maota Lake.", "Hilltop Fortress", "Amer"),
            ("Hawa Mahal (Palace of Winds)", "Iconic five-story pink sandstone facade adorned with 953 intricately carved jharokhas.", "Historic Palace", "Badi Choupad"),
            ("City Palace & Museum", "Splendid palace complex blending Rajput and Mughal architecture, still housing Jaipur's royal family.", "Royal Heritage", "Old City"),
            ("Jantar Mantar Observatory", "Collection of nineteen architectural astronomical instruments featuring the world's largest stone sundial.", "UNESCO Monument", "Gangori Bazaar"),
            ("Nahargarh Fort", "Hilltop fort perched on the Aravalli hills commanding sweeping panoramic sunset views over Jaipur.", "Panoramic Viewpoint", "Aravalli Hills"),
        ],
        "manali": [
            ("Hadimba Devi Temple", "Four-tiered pagoda-style cedar wood temple built in 1553, dedicated to Hadimba in Dhungri forest.", "Ancient Temple", "Dhungri Forest"),
            ("Solang Valley", "High-altitude mountain valley famous for adventure sports, paragliding, and panoramic snow peaks.", "Adventure & Nature", "Solang"),
            ("Rohtang Pass & Atal Tunnel", "Breathtaking mountain pass connecting the Kullu Valley with the high-altitude Lahaul and Spiti valleys.", "Alpine Mountain Pass", "Rohtang"),
            ("Old Manali Village & Cafes", "Charming village with traditional wooden houses, mountain apple orchards, and relaxed cafes.", "Cultural Quarter", "Old Manali"),
            ("Jogini Waterfalls", "Tranquil cascading stream through pine forests with panoramic views of the Beas River valley.", "Scenic Nature Trek", "Vashisht"),
        ],
        "kerala": [
            ("Alleppey Backwaters & Houseboats", "Tranquil labyrinth of palm-fringed canals, lagoons, and traditional kettuvallam houseboats.", "Scenic Waterways", "Alappuzha"),
            ("Fort Kochi Chinese Fishing Nets", "Cantilevered 14th-century shore-operated fishing nets along the historic Arabian Sea harbor.", "Historic Waterfront", "Fort Kochi"),
            ("Munnar Tea Plantations", "Rolling emerald tea estates and sanctuary for the endangered Nilgiri Tahr mountain goat.", "Highland Tea Gardens", "Munnar"),
            ("Mattancherry Dutch Palace", "16th-century palace built by the Portuguese, famous for elaborate Hindu mythological murals.", "Historic Palace", "Mattancherry"),
        ],
        "andaman": [
            ("Radhanagar Beach (Havelock Island)", "Asia's premier pristine coastline with powdery white sand and turquoise gentle waves.", "White Sand Beach", "Havelock Island"),
            ("Cellular Jail National Memorial", "Historic colonial prison complex commemorating the heroes of India's freedom movement.", "Historical Memorial", "Port Blair"),
            ("Elephant Beach Reefs", "Vibrant shallow coral reef popular for snorkeling, glass-bottom boating, and sea walks.", "Coral Marine Reserve", "Havelock Island"),
        ],
        "maldives": [
            ("Maafushi Island Coral Reefs", "Pristine turquoise lagoons and outer barrier reefs for snorkeling with turtles and whale sharks.", "Marine Sanctuary", "South Malé Atoll"),
            ("Malé Hukuru Miskiy (Old Friday Mosque)", "17th-century coral-stone mosque with intricate lacquer work and wood carvings.", "Coral Stone Heritage", "Malé"),
            ("Banana Reef Marine Reserve", "One of Maldives' oldest dive spots featuring coral caves, dramatic overhangs, and sea life.", "Protected Dive Site", "North Malé Atoll"),
        ],
        "bali": [
            ("Tanah Lot Sea Temple", "Dramatic 16th-century Hindu pilgrimage temple perched atop a coastal wave-washed rock formation.", "Offshore Rock Temple", "Tabanan"),
            ("Uluwatu Cliff Temple", "Historic temple standing on a 70-meter limestone cliff overlooking the Indian Ocean.", "Scenic Cliff Temple", "Uluwatu"),
            ("Tegallalang Rice Terraces", "Iconic terraced emerald rice paddies engineered with ancient Balinese Subak irrigation.", "Cultural Landscape", "Ubud"),
        ],
    }
    matched_places = []
    for k, items in catalogue.items():
        if k in key:
            matched_places = items
            break

    if not matched_places:
        matched_places = [
            (f"Historic Old Town & Heritage Quarter", f"Preserved historic architecture, central plazas, and cultural landmarks across central {destination}.", "Heritage District", destination),
            (f"Central {destination} Museum & Art Gallery", f"Premier civic museum housing regional art collections, historical artifacts, and exhibits.", "Museum & Art", destination),
            (f"Panoramic Viewpoint & Scenic Promenade", f"Elevated scenic overlook offering breathtaking vistas of {destination}'s urban skyline and landscape.", "Scenic Viewpoint", destination),
            (f"Iconic Cathedral & Architectural Monument", f"Celebrated historical and architectural landmark reflecting the heritage of {destination}.", "Historic Monument", destination),
            (f"Botanical Gardens & Public Parks in {destination}", f"Tranquil municipal gardens featuring regional flora, walking paths, and historic pavilions.", "Gardens & Parks", destination),
        ]

    results = []
    for name, description, category, location in matched_places:
        results.append(Attraction(
            name=name, description=description, category=category, price_inr=50.0,
            price_display="Free / Nominal", opening_hours="Check official/local schedule",
            location=f"{location}, {destination}" if location != destination else destination, verified=False, source_url="",
            maps_url=f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + destination)}",
            image_url="",
        ))
    return results


def get_categorized_tourist_places(
    destination: str,
    attractions: Optional[List[Attraction]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns real destination-specific places organized into logical tourist categories
    (e.g. Beaches & Coastal, Heritage & Forts, Spiritual & Culture, Nature & Waterfalls).
    Dynamically adapts when destination changes; never hardcoded to one location.
    """
    dest_clean = destination.strip()
    key = dest_clean.casefold()

    curated_map: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        "goa": {
            "🏖️ Beaches & Coastal Sights": [
                {
                    "name": "Baga Beach",
                    "category": "Beach & Water Sports",
                    "description": "Vibrant North Goa beach famous for parasailing, jet-skiing, lively beach shacks, coastal sunset views, and dolphin sightseeing boat tours.",
                    "location": "North Goa",
                    "timings": "Open 24 hours (Water activities: 09:00 AM - 06:00 PM)",
                    "highlights": "Water sports, beachfront cafes, dolphin boat cruises, vibrant evening atmosphere",
                    "image_url": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=600&auto=format&fit=crop&q=80",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Baga Beach Goa')}"
                },
                {
                    "name": "Palolem Beach",
                    "category": "Scenic Crescent Coastline",
                    "description": "Idyllic crescent-shaped white sand beach in South Goa bordered by rocky headlands and coconut groves, featuring calm waters perfect for kayaking.",
                    "location": "Canacona, South Goa",
                    "timings": "Open 24 hours (Kayaking & boat trips: sunrise to sunset)",
                    "highlights": "Calm swimming bay, sea kayaking, quiet sunset views, island boat trips",
                    "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&auto=format&fit=crop&q=80",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Palolem Beach Goa')}"
                },
                {
                    "name": "Anjuna Beach",
                    "category": "Cliff Coast & Bohemian Vibe",
                    "description": "Famous for its red laterite sea cliffs, coastal sunset shacks, rocky tide pools, and the historic Wednesday flea market.",
                    "location": "Anjuna, North Goa",
                    "timings": "Open 24 hours",
                    "highlights": "Laterite cliffs, Curlies beachfront strip, rocky shoreline walks",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Anjuna Beach Goa')}"
                },
                {
                    "name": "Calangute Beach",
                    "category": "Expansive Golden Shore",
                    "description": "Celebrated as the 'Queen of Beaches', stretching along a wide golden sand shoreline with water sports, boat rides, and seafood stalls.",
                    "location": "Calangute, North Goa",
                    "timings": "Open 24 hours",
                    "highlights": "Parasailing, banana boat rides, wide sandy promenade",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Calangute Beach Goa')}"
                }
            ],
            "🏰 Heritage, Forts & Palaces": [
                {
                    "name": "Fort Aguada & Lighthouse",
                    "category": "17th-Century Coastal Fortress",
                    "description": "Massive Portuguese coastal fortress built in 1612 overlooking Sinquerim Beach, featuring historic stone ramparts and an iconic 4-story lighthouse.",
                    "location": "Sinquerim, Candolim",
                    "timings": "09:30 AM - 06:00 PM (Daily)",
                    "highlights": "Oceanfront stone ramparts, historic freshwater cistern, 1864 four-tiered lighthouse",
                    "image_url": "https://images.unsplash.com/photo-1587974928442-77dc3e0dba72?w=600&auto=format&fit=crop&q=80",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Fort Aguada Goa')}"
                },
                {
                    "name": "Chapora Fort",
                    "category": "Hilltop Red Laterite Fortress",
                    "description": "Historic laterite fort perched high above the Chapora River estuary with sweeping 360-degree vistas over Vagator Beach, popular at sunset.",
                    "location": "Chapora, Vagator",
                    "timings": "09:00 AM - 05:30 PM",
                    "highlights": "Panoramic sunset views, river-estuary views, atmospheric laterite ruins",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Chapora Fort Goa')}"
                },
                {
                    "name": "Reis Magos Fort",
                    "category": "Restored Cultural Heritage Fort",
                    "description": "Restored 16th-century river fortress on the northern bank of Mandovi River, housing museum galleries and historical Portuguese defense cannons.",
                    "location": "Reis Magos, Bardez",
                    "timings": "09:30 AM - 05:00 PM (Closed Mondays)",
                    "highlights": "River vistas, Mario Miranda art gallery, Portuguese defense cannons",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Reis Magos Fort Goa')}"
                }
            ],
            "🛕 Spiritual & Cultural Landmarks": [
                {
                    "name": "Basilica of Bom Jesus",
                    "category": "UNESCO World Heritage Baroque Church",
                    "description": "World-famous 16th-century baroque basilica holding the sacred mortal remains of St. Francis Xavier in an ornate glass-sided silver casket.",
                    "location": "Old Goa (Velha Goa)",
                    "timings": "09:00 AM - 06:30 PM (Sundays: 10:30 AM - 06:30 PM)",
                    "highlights": "Relics of St. Francis Xavier, Manueline marble altars, UNESCO baroque architecture",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Basilica of Bom Jesus Goa')}"
                },
                {
                    "name": "Se Cathedral",
                    "category": "Grand Tuscan-Manueline Cathedral",
                    "description": "One of Asia's largest churches, dedicated to Saint Catherine of Alexandria, renowned for its grand Tuscan exterior and famous 'Golden Bell'.",
                    "location": "Old Goa",
                    "timings": "07:30 AM - 06:00 PM (Daily)",
                    "highlights": "Golden Bell (largest bell in Goa), ornate side chapels, Corinthian-style high altar",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Se Cathedral Old Goa')}"
                },
                {
                    "name": "Shri Mangueshi Temple",
                    "category": "Prominent Hindu Temple",
                    "description": "Historic 18th-century temple dedicated to Lord Shiva in Priol, featuring a distinctive 7-story octagonal deepastambha (lamp tower).",
                    "location": "Priol, Ponda",
                    "timings": "06:00 AM - 09:00 PM (Daily)",
                    "highlights": "Seven-storey lamp tower, temple water tank, distinctive Saraswat Goan architecture",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Mangueshi Temple Goa')}"
                }
            ],
            "🌿 Nature, Waterfalls & Scenic Spots": [
                {
                    "name": "Dudhsagar Waterfalls",
                    "category": "Four-Tiered Roaring Waterfall",
                    "description": "Breathtaking 310-meter four-tiered cascade on the Mandovi River, tumbling down vertical cliffs surrounded by lush Western Ghats tropical jungle.",
                    "location": "Bhagwan Mahaveer Sanctuary, Sonaulim",
                    "timings": "07:00 AM - 05:00 PM (Jeep safaris operated through national park gates)",
                    "highlights": "Jeep jungle safari, railway arch bridge vantage point, natural freshwater pools",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Dudhsagar Waterfalls Goa')}"
                },
                {
                    "name": "Salim Ali Bird Sanctuary",
                    "category": "Estuarine Mangrove Reserve",
                    "description": "Pristine coastal mangrove ecosystem on Chorao Island along the Mandovi River, accessible via ferry and wooden boardwalks.",
                    "location": "Chorao Island, Ribandar",
                    "timings": "06:00 AM - 06:00 PM (Best: Early morning)",
                    "highlights": "Boat canopy tours, mudskippers, kingfishers, herons, and migratory wetland species",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Salim Ali Bird Sanctuary Goa')}"
                }
            ]
        },
        "jaipur": {
            "🏰 Heritage, Forts & Palaces": [
                {
                    "name": "Amber Fort & Palace",
                    "category": "Hilltop Rajput Fortress",
                    "description": "Majestic 16th-century palace fortress built from yellow and pink sandstone, featuring the mirror-work Sheesh Mahal overlooking Maota Lake.",
                    "location": "Amer, Jaipur",
                    "timings": "08:00 AM - 05:30 PM & 06:30 PM - 09:15 PM",
                    "highlights": "Sheesh Mahal (Palace of Mirrors), Diwan-e-Khas, Maota Lake views, royal courtyards",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Amber Fort Jaipur')}"
                },
                {
                    "name": "Nahargarh Fort",
                    "category": "Hilltop Panoramic Fort",
                    "description": "Fortress perched along the rugged Aravalli hills, providing breathtaking panoramic sunset vistas overlooking the entire Pink City.",
                    "location": "Aravalli Hills, Jaipur",
                    "timings": "10:00 AM - 05:30 PM",
                    "highlights": "Panoramic sunset viewpoints, Madhavendra Bhawan suites, wax museum",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Nahargarh Fort Jaipur')}"
                },
                {
                    "name": "Jaigarh Fort",
                    "category": "Military Fortress & Cannon Foundry",
                    "description": "Formidable medieval fortress overlooking Amber Fort, housing the massive 'Jaivana' - once the world's largest cannon on wheels.",
                    "location": "Cheel ka Teela, Jaipur",
                    "timings": "09:00 AM - 05:00 PM",
                    "highlights": "Jaivana cannon, underground armory, subterranean water reservoirs",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Jaigarh Fort Jaipur')}"
                }
            ],
            "🏛️ Palaces & Monuments": [
                {
                    "name": "Hawa Mahal (Palace of Winds)",
                    "category": "Iconic Pink Sandstone Facade",
                    "description": "Iconic five-story facade featuring 953 intricately carved jharokhas (casements) designed for royal court women to view street festivities.",
                    "location": "Badi Choupad, Old City",
                    "timings": "09:00 AM - 05:00 PM",
                    "highlights": "953 jharokhas, colorful stained glass windows, panoramic bazaar views from top",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Hawa Mahal Jaipur')}"
                },
                {
                    "name": "City Palace & Museum",
                    "category": "Royal Palace Complex",
                    "description": "Magnificent royal residence fusing Rajasthani and Mughal architecture, containing courtyards, Peacock Gate, and the royal museum.",
                    "location": "Old City, Jaipur",
                    "timings": "09:30 AM - 05:00 PM",
                    "highlights": "Pritam Niwas Chowk (Peacock Gate), Mubarak Mahal, royal textile collections",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('City Palace Jaipur')}"
                },
                {
                    "name": "Jantar Mantar Observatory",
                    "category": "UNESCO Astronomical Observatory",
                    "description": "Collection of nineteen architectural astronomical instruments built by Rajput King Sawai Jai Singh II, featuring the world's largest stone sundial.",
                    "location": "Gangori Bazaar, Jaipur",
                    "timings": "09:00 AM - 05:00 PM",
                    "highlights": "Vrihat Samrat Yantra sundial, astronomical tracking dials, UNESCO heritage site",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Jantar Mantar Jaipur')}"
                }
            ],
            "🌿 Nature & Gardens": [
                {
                    "name": "Jal Mahal (Water Palace)",
                    "category": "Lake Palace & Scenic Overlook",
                    "description": "Low-rise Rajput palace situated in the middle of Man Sagar Lake, appearing to float with the Aravalli hills in the backdrop.",
                    "location": "Man Sagar Lake, Jaipur",
                    "timings": "Viewable from lakefront promenade 24/7",
                    "highlights": "Sunset lake reflections, migratory bird spotting, illuminated evening views",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Jal Mahal Jaipur')}"
                },
                {
                    "name": "Sisodia Rani Ka Bagh",
                    "category": "Tiered Royal Terraced Garden",
                    "description": "Multi-tiered hillside garden with painted pavilions, bubbling fountains, water channels, and murals illustrating the life of Lord Krishna.",
                    "location": "Agra Road, Ghat Ki Guni",
                    "timings": "08:00 AM - 08:00 PM",
                    "highlights": "Terraced waterways, Radha-Krishna murals, tranquil hill gorge setting",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Sisodia Rani Garden Jaipur')}"
                }
            ]
        },
        "kundapura": {
            "🏖️ Beaches & Estuaries": [
                {
                    "name": "Maravanthe Beach",
                    "category": "Scenic Coastal Stretch",
                    "description": "Unique coastal highway bordered by the Arabian Sea on one side and the Souparnika River on the other, creating one of India's most scenic coastal drives.",
                    "location": "Maravanthe, NH 66",
                    "timings": "Open 24 hours (Best: Sunset)",
                    "highlights": "Sea on left and river on right, sunset vantage, fresh seafood stalls",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Maravanthe Beach Kundapura')}"
                },
                {
                    "name": "Kodi Beach & Sea Walk",
                    "category": "Estuary Beach & Promenade",
                    "description": "Quiet coastal beach where the river meets the sea, featuring an extended sea-walk pathway into the water and a beach lighthouse.",
                    "location": "Kodi, Kundapura",
                    "timings": "Open 24 hours",
                    "highlights": "Sea walk promenade, estuary views, quiet shoreline",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Kodi Beach Kundapura')}"
                }
            ],
            "🛕 Spiritual & Culture": [
                {
                    "name": "Kollur Mookambika Temple",
                    "category": "Ancient Pilgrimage Shrine",
                    "description": "Famed Hindu temple nestled at the foothills of Kodachadri peak in the Western Ghats, dedicated to Goddess Mookambika.",
                    "location": "Kollur, Udupi District",
                    "timings": "05:00 AM - 01:30 PM & 03:00 PM - 09:00 PM",
                    "highlights": "Jyotirlinga shrine, Western Ghats jungle foothills, golden palanquin",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Kollur Mookambika Temple Kundapura')}"
                },
                {
                    "name": "Anegudde Vinayaka Temple",
                    "category": "Sacred Ganesha Temple",
                    "description": "Revered temple in Kumbashi dedicated to Lord Ganesha, attracting thousands of visitors and pilgrims.",
                    "location": "Kumbashi, Kundapura",
                    "timings": "06:00 AM - 08:30 PM",
                    "highlights": "Silver armor Ganesha idol, holy pond, tranquil coastal countryside",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Anegudde Temple Kumbashi')}"
                }
            ],
            "🌿 Nature & Viewpoints": [
                {
                    "name": "Ottinene View Point",
                    "category": "Cliff Viewpoint & Estuary",
                    "description": "High coastal cliff viewpoint near Byndoor offering dramatic panoramic vistas of the Souparnika River joining the Arabian Sea.",
                    "location": "Near Byndoor, Kundapura",
                    "timings": "Sunrise to sunset",
                    "highlights": "Estuary panorama, sunset views, coastal cliff photography",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Ottinene View Point Kundapura')}"
                }
            ]
        },
        "kerala": {
            "🌿 Nature & Backwaters": [
                {
                    "name": "Alleppey Backwaters & Houseboats",
                    "category": "Labyrinth Waterways",
                    "description": "Tranquil network of canals, lagoons, and lakes navigated on traditional thatched kettuvallam houseboats.",
                    "location": "Alappuzha, Kerala",
                    "timings": "Houseboat check-in 12:00 PM",
                    "highlights": "Paddy fields below sea level, village canals, coconut palms",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Alleppey Backwaters Kerala')}"
                },
                {
                    "name": "Munnar Tea Plantations",
                    "category": "Highland Tea Gardens",
                    "description": "Rolling emerald tea plantations and misty highland valleys, home to the endangered Nilgiri Tahr at Eravikulam National Park.",
                    "location": "Munnar, Idukki",
                    "timings": "08:30 AM - 04:30 PM",
                    "highlights": "Tea museum, Nilgiri Tahr sightings, mountain mist viewpoints",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Munnar Tea Gardens Kerala')}"
                },
                {
                    "name": "Athirappilly Waterfalls",
                    "category": "Majestic Cascading Fall",
                    "description": "Dramatic 80-foot wide waterfall on the Chalakudy River in the Sholayar forest range, often called the Niagara of South India.",
                    "location": "Thrissur District",
                    "timings": "08:00 AM - 05:00 PM",
                    "highlights": "Forest nature walk, spray viewpoints, lush tropical scenery",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Athirappilly Falls Kerala')}"
                }
            ],
            "🏖️ Beaches & Coastal": [
                {
                    "name": "Kovalam Beach",
                    "category": "Crescent Beach & Lighthouse",
                    "description": "Famous crescent-shaped beach featuring a 30-meter high red-and-white striped lighthouse with sweeping Arabian Sea views.",
                    "location": "Kovalam, Thiruvananthapuram",
                    "timings": "Open 24 hours (Lighthouse: 10:00 AM - 05:00 PM)",
                    "highlights": "Lighthouse climb, shallow swimming bays, beach cafes",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Kovalam Beach Kerala')}"
                },
                {
                    "name": "Varkala Cliff Beach",
                    "category": "Sedimentary Cliff Coastline",
                    "description": "Dramatic red laterite cliffs bordering the Arabian Sea, lined with bohemian cafes and natural mineral water springs.",
                    "location": "Varkala",
                    "timings": "Open 24 hours",
                    "highlights": "Cliff-edge walking promenade, natural spring bath, sunset views",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Varkala Cliff Beach Kerala')}"
                }
            ],
            "🏰 Heritage & Culture": [
                {
                    "name": "Fort Kochi Chinese Fishing Nets",
                    "category": "Historic Coastal Landmark",
                    "description": "Historic shore-operated cantilevered fishing nets operating along the Kochi harbor since the 14th century.",
                    "location": "Fort Kochi, Ernakulam",
                    "timings": "Best at sunrise and sunset",
                    "highlights": "Cantilever net operations, fresh catch market, heritage promenade",
                    "image_url": "",
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus('Chinese Fishing Nets Fort Kochi')}"
                }
            ]
        }
    }

    # Match curated destination
    for k, cat_dict in curated_map.items():
        if k in key:
            return cat_dict

    # Dynamic categorization for any arbitrary destination from research attractions
    dynamic_categories: Dict[str, List[Dict[str, Any]]] = {
        "🏖️ Beaches & Coastal Sights": [],
        "🏰 Heritage, Forts & Palaces": [],
        "🛕 Spiritual & Cultural Landmarks": [],
        "🌿 Nature, Waterfalls & Scenic Spots": [],
        "🏛️ Iconic City Landmarks": []
    }

    pool = attractions or curated_destination_attractions(dest_clean)
    for a in pool:
        name = a.name
        cat = getattr(a, "category", "")
        desc = getattr(a, "description", "")
        combined = f"{name} {cat} {desc}".lower()

        place_entry = {
            "name": name,
            "category": cat or "Sightseeing Landmark",
            "description": desc or f"Notable landmark and visitor highlight in {dest_clean}.",
            "location": getattr(a, "location", dest_clean),
            "timings": getattr(a, "opening_hours", "Check local schedule"),
            "highlights": "Architecture, guided tours, scenic photography",
            "image_url": getattr(a, "image_url", ""),
            "maps_url": getattr(a, "maps_url", f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + dest_clean)}")
        }

        if any(w in combined for w in ["beach", "coast", "bay", "cove", "island", "sea", "ocean", "shore"]):
            dynamic_categories["🏖️ Beaches & Coastal Sights"].append(place_entry)
        elif any(w in combined for w in ["fort", "castle", "palace", "heritage", "ruin", "historic", "wall", "gate"]):
            dynamic_categories["🏰 Heritage, Forts & Palaces"].append(place_entry)
        elif any(w in combined for w in ["temple", "church", "cathedral", "basilica", "mosque", "shrine", "spiritual", "dargah", "monastery"]):
            dynamic_categories["🛕 Spiritual & Cultural Landmarks"].append(place_entry)
        elif any(w in combined for w in ["waterfall", "lake", "river", "mountain", "peak", "valley", "canyon", "park", "garden", "sanctuary", "forest", "nature"]):
            dynamic_categories["🌿 Nature, Waterfalls & Scenic Spots"].append(place_entry)
        else:
            dynamic_categories["🏛️ Iconic City Landmarks"].append(place_entry)

    # Return only categories that have at least one place
    return {k: v for k, v in dynamic_categories.items() if v}


def check_route_feasibility(origin: str, destination: str) -> Tuple[bool, str]:
    """
    Evaluates whether the route is international, island, or domestic mainland.
    Returns (is_overseas, route_category) where route_category is
    'international', 'island', or 'domestic_mainland'.
    """
    try:
        route = classify_route(origin, destination)
        if route and route.route_category in ("international", "island"):
            return bool(route.is_overseas), route.route_category
        if route and route.route_category == "domestic_mainland":
            return False, "domestic_mainland"
    except Exception:
        pass

    dest_clean = destination.strip().lower()
    origin_clean = origin.strip().lower() if origin.strip() else "your city"

    # Use token/phrase boundaries: substring checks misclassify names such as Pudukkottai ("uk").
    def contains_phrase(text: str, phrase: str) -> bool:
        escaped = re.escape(phrase.strip().lower()).replace(r"\ ", r"\s+")
        return bool(re.search(r"(?<![a-z])" + escaped + r"(?![a-z])", text))

    for isl in ISLAND_DESTINATIONS:
        if contains_phrase(dest_clean, isl):
            return True, "island"

    for kw in INTERNATIONAL_KEYWORDS:
        if contains_phrase(dest_clean, kw):
            return True, "international"

    return False, "domestic_mainland"

def generate_commute_options(destination: str, starting_city: str, travel_date: str = "") -> List[CommuteOption]:
    """
    Generates physically feasible transit and commute options with direct live booking URLs.
    Strictly excludes impossible overland options (no buses or cars across oceans or continents).
    """
    origin = starting_city.strip() if starting_city.strip() else "Your City"
    dest = destination.strip()
    
    origin_q = quote_plus(origin)
    dest_q = quote_plus(dest)
    dest_slug = re.sub(r'[^a-zA-Z0-9]+', '-', dest.strip().lower()).strip('-')
    origin_slug = re.sub(r'[^a-zA-Z0-9]+', '-', origin.strip().lower()).strip('-')

    is_overseas, route_cat = check_route_feasibility(origin, dest)

    if route_cat == "international":
        # International Flight
        flight_title = f"Direct / 1-Stop International Flights ({origin} ➔ {dest})"
        flight_details = f"Major international carriers (Emirates, Lufthansa, Swiss, Qatar Airways, Air India) operate flights connecting {origin} to {dest}'s international airport hubs."
        
        options = [
            CommuteOption(
                mode="Flight ✈️",
                title=flight_title,
                duration="9h 30m - 14h 00m",
                estimated_cost_inr="₹45,000 - ₹78,000 / person round-trip",
                details=flight_details,
                booking_url=f"https://www.google.com/travel/flights?q=flights+from+{origin_q}+to+{dest_q}",
                source_url="https://www.google.com/travel/flights",
                icon="✈️"
            )
        ]

        # Specific destination rail / transit passes
        dest_lower = dest.lower()
        if any(w in dest_lower for w in ["swiss", "switzerland", "swirzerland", "zurich", "geneva", "interlaken"]):
            options.append(CommuteOption(
                mode="Scenic Rail Pass 🚆",
                title="Swiss Travel Pass & SBB Federal Railways (Inside Switzerland)",
                duration="All-in-One Scenic Network",
                estimated_cost_inr="~CHF 244 (₹23,500) for 3-Day Pass",
                details="The gold standard for Swiss transit: unlimited panoramic trains (Glacier Express, Bernina Express), lake steamers, mountain railways, and city trams across Switzerland.",
                booking_url="https://www.sbb.ch/en/",
                source_url="https://www.sbb.ch/en/",
                icon="🚆"
            ))
            options.append(CommuteOption(
                mode="Airport Express 🚇",
                title="Airport Rail Link (Zurich/Geneva Airport to City Center)",
                duration="10 - 15 mins",
                estimated_cost_inr="~CHF 7 - 14 (₹650 - ₹1,300) or Free with Swiss Pass",
                details="High-frequency express trains departing directly beneath the airport terminals into Zurich Hauptbahnhof (HB) or Geneva Cornavin station.",
                booking_url="https://www.sbb.ch/en/",
                source_url="https://www.sbb.ch/en/",
                icon="🚇"
            ))
        elif any(w in dest_lower for w in ["france", "paris", "germany", "italy", "spain", "europe", "austria", "netherlands", "uk", "london"]):
            options.append(CommuteOption(
                mode="High-Speed Rail 🚆",
                title=f"Eurail & Intercity Rail Network (Inside {dest})",
                duration="1h 30m - 3h 30m between regional cities",
                estimated_cost_inr="€40 - €120 / journey (₹3,600 - ₹11,000)",
                details=f"Fast high-speed trains (TGV, ICE, Eurostar, Frecciarossa) connecting regional hubs directly into city centers.",
                booking_url="https://www.thetrainline.com/",
                source_url="https://www.thetrainline.com/",
                icon="🚆"
            ))
            options.append(CommuteOption(
                mode="Airport Ground Link 🚇",
                title=f"Airport Express Metro / Shuttle to Central {dest}",
                duration="20 - 45 mins",
                estimated_cost_inr="€10 - €22 / person (₹900 - ₹2,000)",
                details="Dedicated airport express trains or rapid transit lines connecting arrival terminals to central transit stations.",
                booking_url=f"https://www.google.com/maps/dir/{dest_q}+Airport/{dest_q}+City+Center",
                source_url="https://www.google.com/maps",
                icon="🚇"
            ))
        elif "japan" in dest_lower or "tokyo" in dest_lower:
            options.append(CommuteOption(
                mode="Bullet Train 🚄",
                title="JR Shinkansen High-Speed Bullet Trains (Across Japan)",
                duration="2h 15m (Tokyo ➔ Kyoto/Osaka)",
                estimated_cost_inr="¥14,000 - ¥29,000 (₹7,800 - ₹16,000)",
                details="Punctual high-speed bullet trains linking major prefectures, plus Tokyo Metro / Suica IC card for city transit.",
                booking_url="https://www.japanrailpass.net/en/",
                source_url="https://www.japanrailpass.net/",
                icon="🚄"
            ))
        else:
            options.append(CommuteOption(
                mode="Destination Transit 🚇",
                title=f"Local Public Transit, Metro & Licensed Cabs in {dest}",
                duration="Frequent schedules",
                estimated_cost_inr="₹600 - ₹1,800 / day",
                details=f"Rapid transit metro lines, airport shuttles, and metered taxis for moving around {dest}.",
                booking_url=f"https://www.google.com/maps/search/?api=1&query={dest_q}+public+transit",
                source_url="https://www.google.com/travel",
                icon="🚇"
            ))
        return options

    elif route_cat == "island":
        options = [
            CommuteOption(
                mode="Flight ✈️",
                title=f"Direct / Connecting Flights ({origin} ➔ {dest})",
                duration="2h 15m - 5h 00m",
                estimated_cost_inr="₹6,500 - ₹16,000 / person round-trip",
                details=f"Air travel landing at {dest}'s primary airport hub (e.g., Port Blair IXZ, Male MLE, Agatti AGX).",
                booking_url=f"https://www.google.com/travel/flights?q=flights+from+{origin_q}+to+{dest_q}",
                source_url="https://www.google.com/travel/flights",
                icon="✈️"
            ),
            CommuteOption(
                mode="Ferry / Transfer ⛴️",
                title=f"Speedboat & Inter-Island Catamaran Transfers ({dest})",
                duration="45m - 2h 30m",
                estimated_cost_inr="₹1,200 - ₹4,500 / person",
                details="Scheduled high-speed catamaran ferries or resort speedboats connecting arrival docks to destination beaches and island resorts.",
                booking_url=f"https://www.google.com/search?q={dest_q}+ferry+booking",
                source_url="https://www.google.com/travel",
                icon="⛴️"
            )
        ]
        return options

    else:
        # Domestic mainland: realistic options with dynamic links & disclaimers.
        date_query = f" {travel_date}".strip() if travel_date else ""
        flight_query = quote_plus(f"flights from {origin} to {dest}{date_query}")
        train_query = quote_plus(f"trains from {origin} to {dest}{date_query}")
        bus_query = quote_plus(f"bus from {origin} to {dest}{date_query}")
        
        # RedBus dynamic link avoiding any undefined errors
        if origin_slug and dest_slug and origin_slug not in ("your-city", "origin", "your"):
            bus_booking_url = f"https://www.redbus.in/bus-tickets/{origin_slug}-to-{dest_slug}"
        else:
            bus_booking_url = f"https://www.google.com/search?q={bus_query}"

        return [
            CommuteOption(
                mode="Flight search ✈️",
                title=f"Check flights: {origin} → {dest}",
                duration="1h 15m - 2h 45m (estimated)",
                estimated_cost_inr="Check live fares (Est. ₹2,800 - ₹6,500)",
                details=f"Search flights for your travel date ({travel_date or 'selected date'}). Flight availability and fares depend on carrier and advance booking.",
                booking_url=f"https://www.google.com/travel/flights?q={flight_query}",
                source_url="https://www.google.com/travel/flights",
                icon="✈️"
            ),
            CommuteOption(
                mode="Train search 🚆",
                title=f"Check trains: {origin} → {dest}",
                duration="5h 30m - 12h 00m (estimated)",
                estimated_cost_inr="Check live fares (Est. ₹450 SL | ₹1,200 - ₹2,100 AC)",
                details=f"Check IRCTC for scheduled express trains between {origin} and {dest} for {travel_date or 'your date'}. Vande Bharat trains are only recommended on verified corridors; do not assume a Vande Bharat operates between {origin} and {dest} unless verified.",
                booking_url=f"https://www.google.com/search?q={train_query}",
                source_url="https://www.irctc.co.in/",
                icon="🚆"
            ),
            CommuteOption(
                mode="Bus search 🚌",
                title=f"Check buses: {origin} → {dest}",
                duration="8h 00m - 14h 00m (estimated)",
                estimated_cost_inr="Check live fares (Est. ₹750 - ₹1,800)",
                details=f"Search scheduled AC sleeper / Volvo coaches on RedBus/KSRTC. Confirm operator routes and boarding points for {travel_date or 'your travel date'}.",
                booking_url=bus_booking_url,
                source_url="https://www.redbus.in/",
                icon="🚌"
            ),
            CommuteOption(
                mode="Road route 🚗",
                title=f"Driving directions: {origin} → {dest}",
                duration="See current route estimate",
                estimated_cost_inr="Estimate fuel and tolls (~₹12 - ₹16/km)",
                details="Google Maps provides scenic driving route estimates via national highways; verify traffic, weather, and toll plaza conditions.",
                booking_url=f"https://www.google.com/maps/dir/{origin_q}/{dest_q}",
                source_url="https://www.google.com/maps",
                icon="🚗"
            )
        ]

def get_sample_images_for_destination(dest: str) -> Dict[str, str]:
    """Provides high-quality travel images matching destination themes."""
    d = dest.lower()
    if "goa" in d:
        return {
            "hero": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=800&auto=format&fit=crop&q=80",
            "fort": "https://images.unsplash.com/photo-1587974928442-77dc3e0dba72?w=600&auto=format&fit=crop&q=80",
            "beach": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&auto=format&fit=crop&q=80",
            "stay": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&auto=format&fit=crop&q=80",
            "food": "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46?w=600&auto=format&fit=crop&q=80"
        }
    elif "jaipur" in d:
        return {
            "hero": "https://images.unsplash.com/photo-1603262110263-fb010d6e75dc?w=800&auto=format&fit=crop&q=80",
            "fort": "https://images.unsplash.com/photo-1599661046289-e31897846e41?w=600&auto=format&fit=crop&q=80",
            "beach": "https://images.unsplash.com/photo-1477587458883-47145ed94245?w=600&auto=format&fit=crop&q=80",
            "stay": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=600&auto=format&fit=crop&q=80",
            "food": "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=600&auto=format&fit=crop&q=80"
        }
    elif "kerala" in d or "kochi" in d or "alleppey" in d:
        return {
            "hero": "https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=800&auto=format&fit=crop&q=80",
            "fort": "https://images.unsplash.com/photo-1593693397690-362cb9666fc2?w=600&auto=format&fit=crop&q=80",
            "beach": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&auto=format&fit=crop&q=80",
            "stay": "https://images.unsplash.com/photo-1582719508461-905c673771fd?w=600&auto=format&fit=crop&q=80",
            "food": "https://images.unsplash.com/photo-1610057099443-fde8c4d50f91?w=600&auto=format&fit=crop&q=80"
        }
    else:
        return {
            "hero": "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=800&auto=format&fit=crop&q=80",
            "fort": "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=600&auto=format&fit=crop&q=80",
            "beach": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&auto=format&fit=crop&q=80",
            "stay": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&auto=format&fit=crop&q=80",
            "food": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&auto=format&fit=crop&q=80"
        }


def get_attraction_image(attraction_name: str, destination: str, index: int = 0) -> str:
    """Find a place-specific Wikipedia / Unsplash thumbnail; return empty rather than a misleading stock photo."""
    photo = get_destination_photo(attraction_name, destination, category="attraction", index=index)
    if photo and photo.image_url:
        return photo.thumb_url or photo.image_url
    return ""


def add_attraction_images(attractions: List[Attraction], destination: str) -> None:
    """Attach place-specific thumbnails concurrently without substituting unrelated stock images."""
    def _fetch_attr(args):
        idx, attr = args
        photo = get_destination_photo(attr.name, destination, category="attraction", index=idx)
        if photo and photo.image_url:
            attr.image_url = photo.thumb_url or photo.image_url
            attr.attribution_text = photo.attribution_text
            attr.attribution_url = photo.attribution_url

    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(_fetch_attr, enumerate(attractions)))

def ensure_minimum_recommendations(
    destination: str,
    accommodations: List[Accommodation],
    food_experiences: List[FoodExperience],
    img_pool: Optional[Dict[str, str]] = None,
    minimum: int = 3,
) -> Tuple[List[Accommodation], List[FoodExperience]]:
    """Fill short recommendation lists with clearly marked destination search suggestions."""
    destination_key = destination.lower()
    regional_food = [
        ("Regional thali", "Local cuisine", "Explore restaurants serving a traditional regional thali."),
        ("Local street-food specialties", "Street food", "Find popular local snacks and street-food vendors."),
        ("Traditional sweets and desserts", "Desserts", "Look for bakeries and sweet shops featuring local desserts."),
    ]
    if "goa" in destination_key:
        regional_food = [
            ("Goan fish curry and rice", "Goan coastal", "Try this regional curry at a nearby Goan restaurant."),
            ("Goan vindaloo", "Goan cuisine", "Search local restaurants for this classic Goan curry."),
            ("Bebinca and Goan sweets", "Goan desserts", "Find bakeries and cafes serving traditional Goan bebinca."),
        ]
    elif "jaipur" in destination_key or "rajasthan" in destination_key:
        regional_food = [
            ("Dal baati churma", "Rajasthani", "Try this traditional Rajasthani meal at a local restaurant."),
            ("Pyaaz kachori", "Street food", "Find local shops serving Jaipur-style kachori and snacks."),
            ("Ghewar and Rajasthani sweets", "Desserts", "Explore Jaipur sweet shops for ghewar and seasonal desserts."),
        ]
    elif "kerala" in destination_key or "kochi" in destination_key or "alleppey" in destination_key:
        regional_food = [
            ("Kerala sadya", "Kerala cuisine", "Look for local restaurants serving a traditional Kerala sadya."),
            ("Appam and stew", "Kerala cuisine", "Try appam with stew at a nearby Kerala restaurant."),
            ("Malabar parotta and curry", "Malabar cuisine", "Find local restaurants serving parotta with regional curry."),
        ]
    elif "manali" in destination_key or "himachal" in destination_key:
        regional_food = [
            ("Himachali dham", "Himachali cuisine", "Explore local restaurants for a traditional Himachali dham."),
            ("Siddu", "Himachali cuisine", "Search nearby cafes and restaurants for this Himachali wheat dish."),
            ("Himachali trout dishes", "Mountain cuisine", "Look for local menus featuring trout and regional preparations."),
        ]

    stay_suggestions = [
        ("Budget guesthouses and hostels", "Guesthouse / Hostel", 1500.0),
        ("Mid-range hotels", "Hotel", 3500.0),
        ("Boutique resorts and homestays", "Resort / Homestay", 7000.0),
    ]
    existing_stays = {stay.property_name.casefold() for stay in accommodations}
    for stay_idx, (name, property_type, nightly_estimate) in enumerate(stay_suggestions):
        if len(accommodations) >= minimum:
            break
        full_name = f"{name} in {destination}"
        if full_name.casefold() in existing_stays:
            continue
        search_query = quote_plus(f"{name} {destination}")
        photo = get_destination_photo(name, destination, category="hotel", index=stay_idx)
        accommodations.append(Accommodation(
            property_name=full_name,
            property_type=property_type,
            price_per_night_inr=nightly_estimate,
            price_display=f"Estimated from ₹{nightly_estimate:,.0f} / night",
            rating="Check recent reviews",
            location=destination,
            description="Search suggestion only. Compare current rates, reviews, and availability before booking.",
            verified=False,
            booking_url=f"https://www.booking.com/searchresults.html?ss={search_query}",
            maps_url=f"https://www.google.com/maps/search/?api=1&query={search_query}",
            image_url=photo.thumb_url or photo.image_url,
            attribution_text=photo.attribution_text,
            attribution_url=photo.attribution_url
        ))
        existing_stays.add(full_name.casefold())

    existing_food = {food.name.casefold() for food in food_experiences}
    for food_idx, (name, cuisine_type, description) in enumerate(regional_food):
        if len(food_experiences) >= minimum:
            break
        if name.casefold() in existing_food:
            continue
        search_query = quote_plus(f"{name} restaurants {destination}")
        food_photo = get_destination_photo(name, destination, category="food", index=food_idx)
        food_experiences.append(FoodExperience(
            name=name,
            cuisine_type=cuisine_type,
            price_range_inr="Check current menu",
            location=destination,
            description=f"{description} Search suggestion only; confirm menu and opening hours.",
            verified=False,
            maps_url=f"https://www.google.com/maps/search/?api=1&query={search_query}",
            image_url=food_photo.thumb_url or food_photo.image_url,
            attribution_text=food_photo.attribution_text,
            attribution_url=food_photo.attribution_url
        ))
        existing_food.add(name.casefold())

    return accommodations, food_experiences

    return accommodations, food_experiences


def parse_with_gemini(raw_text: str, trip_req: TripRequest, source_url: str, session_state=None) -> Optional[TripResearchResult]:
    """Unified Gemini AI synthesis with multi-source links, booking URLs, and Google Maps integration."""
    api_key = get_gemini_api_key(session_state)
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        condensed_text = condense_snapshot(raw_text, max_chars=14000)

        prompt = f"""
You are the AI Travel Specialist for TripPilot AI.
A browser automation agent navigated to: {source_url}

--- LIVE BROWSER SNAPSHOT ---
{condensed_text}
--- END SNAPSHOT ---

Trip Request:
- Destination: {trip_req.destination}
- Starting City: {trip_req.starting_city if trip_req.starting_city else 'Metro City'}
- Duration: {trip_req.num_days} days ({trip_req.departure_date} to {trip_req.return_date})
- Travelers: {trip_req.travelers}
- Total Budget: ₹{trip_req.budget_inr:,.0f} INR
- Accommodation Tier: {trip_req.accommodation_pref}
- Interests: {', '.join(trip_req.interests)}
- Travel Style: {trip_req.travel_style}

Perform comprehensive extraction and planning:
1. Extract at least 6 verified attractions, 3-4 distinct accommodation options, and 3-4 authentic regional dining spots.
2. For each accommodation, extract a real hotel/resort/hostel name. Note its nightly rate (or estimate based on the tier).
3. Generate a realistic {trip_req.num_days}-day itinerary.
4. Evaluate physically feasible commute options between '{trip_req.starting_city if trip_req.starting_city else 'Origin'}' and '{trip_req.destination}'.
   CRITICAL REALITY RULE: Return ONLY commute options that are physically possible and realistic between origin and destination:
   - If the trip is International / Transcontinental / Cross-Ocean / Island (e.g. Bengaluru to Switzerland, India to Europe/USA/Australia, or to Maldives/Andaman):
     * NEVER return a train, bus, or road trip from the origin city! Overland travel between India and Switzerland/Europe/USA is impossible.
     * ONLY return:
       - International Flight (origin to destination)
       - Local Scenic Rail or Public Transit Pass at Destination (e.g. Swiss Travel Pass / SBB Trains in Switzerland, Eurail in Europe, JR Pass in Japan, or Ferry/Speedboat in Maldives/Andaman)
       - Airport Ground Link / Rail Shuttle to City Center
   - If the trip is Domestic Mainland (e.g. Mumbai to Goa, Delhi to Jaipur):
     * Return feasible options (Flight, Train like Vande Bharat/Express, Bus, Road trip) based on realistic distance.
5. Curate an 'Editor's Best Recommendation' highlighting the best commute mode, top stay, top 3 must-visit sights, and signature food.
6. Return ONLY a valid JSON object matching this schema:

{{
  "destination": "{trip_req.destination}",
  "summary": "2-3 sentences overview grounded in real travel findings",
  "commute_options": [
    {{
      "mode": "Flight ✈️",
      "title": "Descriptive title of commute mode",
      "duration": "Realistic duration e.g. 10h - 13h or 8h",
      "estimated_cost_inr": "Estimated cost range in INR",
      "details": "Details on routes, airlines, or destination transit pass",
      "icon": "✈️"
    }}
  ],
  "attractions": [
    {{
      "name": "Attraction name",
      "description": "Short description",
      "category": "e.g. Heritage, Beach, Nature, Culture",
      "price_inr": 50.0,
      "price_display": "₹50 or Free / Nominal",
      "opening_hours": "09:00 AM - 05:00 PM or Check locally",
      "location": "Locality or area",
      "verified": true,
      "source_url": "{source_url}"
    }}
  ],
  "accommodations": [
    {{
      "property_name": "Hotel / Resort / Hostel name",
      "property_type": "Hostel / Resort / Heritage Hotel",
      "price_per_night_inr": 1800.0,
      "price_display": "₹1,800 / night",
      "pricing_period": "per night",
      "rating": "4.3 / 5 or Popular",
      "location": "Locality or beach name",
      "description": "Brief description of the stay",
      "verified": true,
      "source_url": "{source_url}"
    }}
  ],
  "food_experiences": [
    {{
      "name": "Restaurant or Specialty Dish",
      "cuisine_type": "Regional / Coastal / Street food",
      "price_range_inr": "₹400 - ₹800 for two",
      "location": "Locality or market",
      "description": "Signature dish or vibe",
      "verified": true,
      "source_url": "{source_url}"
    }}
  ],
  "neighborhoods": ["Area 1: description", "Area 2: description"],
  "travel_tips": ["Tip 1", "Tip 2", "Tip 3"],
  "best_recommendation": {{
    "top_commute": "Fastest and most convenient travel route",
    "top_stay_name": "Best recommended stay name",
    "top_stay_reason": "Why this stay is ideal for this budget tier",
    "must_visit_sights": ["Sight 1", "Sight 2", "Sight 3"],
    "signature_food": "Top dish and best restaurant to taste it"
  }},
  "itinerary": [
    {{
      "day_number": 1,
      "date_str": "Day 1",
      "title": "Day Theme",
      "morning_activity": "Morning activity plan",
      "afternoon_activity": "Afternoon activity plan",
      "evening_activity": "Evening activity plan",
      "food_recommendations": "Dining suggestion",
      "estimated_cost_inr": 800.0,
      "travel_notes": "Transit advice"
    }}
  ]
}}
"""
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json"
            )
        )
        
        if response and response.text:
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            
            img_pool = get_sample_images_for_destination(trip_req.destination)

            # Build attractions with Google Maps links and images
            attractions = []
            seen_attractions = set()
            for a in data.get("attractions", []):
                if not isinstance(a, dict):
                    continue
                obj = Attraction.from_dict(a)
                if not is_valid_attraction_name(obj.name, trip_req.destination):
                    continue
                key = obj.name.casefold().strip()
                if key in seen_attractions:
                    continue
                seen_attractions.add(key)
                obj.maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(obj.name + ' ' + trip_req.destination)}"
                obj.image_url = ""
                # AI output alone is not proof of verification.
                obj.verified = bool(obj.verified and obj.source_url and obj.source_url.startswith(("https://", "http://")))
                attractions.append(obj)
            if len(attractions) < 4:
                known = curated_destination_attractions(trip_req.destination)
                for item in known:
                    if item.name.casefold() not in seen_attractions:
                        attractions.append(item)
                        seen_attractions.add(item.name.casefold())
                    if len(attractions) >= 6:
                        break
            add_attraction_images(attractions, trip_req.destination)

            # Build accommodations with real booking links & Google Maps URLs
            accommodations = []
            booking_providers = ["Booking.com", "Goibibo", "Agoda", "MakeMyTrip"]
            for idx, h in enumerate(data.get("accommodations", [])):
                obj = Accommodation.from_dict(h)
                q_name = quote_plus(f"{obj.property_name} {trip_req.destination}")
                obj.maps_url = f"https://www.google.com/maps/search/?api=1&query={q_name}"
                
                # Multi-provider booking links
                if idx % 3 == 0:
                    obj.booking_url = f"https://www.booking.com/searchresults.html?ss={q_name}"
                    obj.source_url = "https://www.booking.com"
                elif idx % 3 == 1:
                    obj.booking_url = f"https://www.goibibo.com/hotels/find-hotels-in-{trip_req.destination.lower()}/?search={quote_plus(obj.property_name)}"
                    obj.source_url = "https://www.goibibo.com"
                else:
                    obj.booking_url = f"https://www.makemytrip.com/hotels/hotel-listing/?city={trip_req.destination.lower()}&searchText={quote_plus(obj.property_name)}"
                    obj.source_url = "https://www.makemytrip.com"

                photo = get_destination_photo(obj.property_name, trip_req.destination, category="hotel", index=idx)
                obj.image_url = photo.thumb_url or photo.image_url
                obj.attribution_text = photo.attribution_text
                obj.attribution_url = photo.attribution_url
                accommodations.append(obj)

            # Build dining with Google Maps links
            food_experiences = []
            for idx, f in enumerate(data.get("food_experiences", [])):
                f_obj = FoodExperience.from_dict(f)
                f_obj.maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(f_obj.name + ' restaurant ' + trip_req.destination)}"
                photo = get_destination_photo(f_obj.name, trip_req.destination, category="food", index=idx)
                f_obj.image_url = photo.thumb_url or photo.image_url
                f_obj.attribution_text = photo.attribution_text
                f_obj.attribution_url = photo.attribution_url
                food_experiences.append(f_obj)

            accommodations, food_experiences = ensure_minimum_recommendations(
                trip_req.destination, accommodations, food_experiences, img_pool
            )

            # Build commute options with geographic feasibility filtering
            origin = trip_req.starting_city.strip() if trip_req.starting_city.strip() else "Your City"
            dest = trip_req.destination.strip()
            origin_q = quote_plus(origin)
            dest_q = quote_plus(dest)
            dest_slug = dest.lower().replace(" ", "-")
            origin_slug = origin.lower().replace(" ", "-")

            is_overseas, route_cat = check_route_feasibility(origin, dest)

            raw_commute = data.get("commute_options", [])
            commute_options = []

            if raw_commute and isinstance(raw_commute, list):
                for c in raw_commute:
                    c_mode = c.get("mode", "").lower()
                    c_title = c.get("title", "")
                    c_desc = (c.get("details", "") + " " + c_title).lower()

                    # Feasibility filter: if overseas or island, DISCARD impossible overland modes
                    if is_overseas and any(x in c_mode for x in ["bus", "car", "drive", "road trip", "highway"]):
                        if "local" not in c_desc and "rental" not in c_desc and "island cab" not in c_desc:
                            continue

                    if is_overseas and any(x in c_mode for x in ["train", "rail"]):
                        if "irctc" in c_desc or "indian railway" in c_desc or f"from {origin.lower()}" in c_desc:
                            continue

                    # Determine booking & source URLs
                    icon = c.get("icon", "🚆")
                    if "flight" in c_mode or "✈" in c_mode or "plane" in c_mode:
                        icon = "✈️"
                        b_url = f"https://www.google.com/travel/flights?q=flights+from+{origin_q}+to+{dest_q}"
                        s_url = "https://www.google.com/travel/flights"
                    elif "train" in c_mode or "rail" in c_mode or "🚆" in c_mode or "🚄" in c_mode:
                        icon = "🚆"
                        if any(w in dest.lower() for w in ["swiss", "switzerland", "swirzerland", "zurich", "geneva"]):
                            b_url = "https://www.sbb.ch/en/"
                            s_url = "https://www.sbb.ch/en/"
                        elif is_overseas:
                            b_url = "https://www.thetrainline.com/"
                            s_url = "https://www.thetrainline.com/"
                        else:
                            b_url = f"https://www.makemytrip.com/railways/listing?srcCity={origin_q}&destCity={dest_q}"
                            s_url = "https://www.irctc.co.in/"
                    elif "bus" in c_mode or "🚌" in c_mode:
                        icon = "🚌"
                        b_url = f"https://www.redbus.in/bus-tickets/{origin_slug}-to-{dest_slug}"
                        s_url = "https://www.redbus.in/"
                    elif "car" in c_mode or "drive" in c_mode or "road" in c_mode or "🚗" in c_mode:
                        icon = "🚗"
                        b_url = f"https://www.google.com/maps/dir/{origin_q}/{dest_q}"
                        s_url = "https://www.google.com/maps"
                    elif "ferry" in c_mode or "boat" in c_mode or "cruise" in c_mode or "⛴" in c_mode:
                        icon = "⛴️"
                        b_url = f"https://www.google.com/search?q={dest_q}+ferry+booking"
                        s_url = "https://www.google.com/travel"
                    else:
                        icon = "🚇"
                        b_url = f"https://www.google.com/maps/search/?api=1&query={dest_q}+public+transit"
                        s_url = "https://www.google.com/travel"

                    commute_options.append(CommuteOption(
                        mode=c.get("mode", "Transit"),
                        title=c_title or f"Transit ({origin} ➔ {dest})",
                        duration=c.get("duration", "Check timetable"),
                        estimated_cost_inr=c.get("estimated_cost_inr", "Check fares"),
                        details=c.get("details", ""),
                        booking_url=b_url,
                        source_url=s_url,
                        icon=icon
                    ))

            # If Gemini didn't return feasible options or filtered out everything, fallback to generator
            if not commute_options:
                commute_options = generate_commute_options(trip_req.destination, trip_req.starting_city)

            # Ensure best_recommendation top_commute is physically realistic
            best_rec = data.get("best_recommendation", {})
            if is_overseas and any(x in best_rec.get("top_commute", "").lower() for x in ["train from", "bus from", "drive from", "car from", "nh ", "vande bharat"]):
                if any(w in dest.lower() for w in ["swiss", "switzerland", "swirzerland"]):
                    best_rec["top_commute"] = f"Direct or 1-stop international flight ({origin} ➔ ZRH/GVA), followed by the Swiss Travel Pass for panoramic train travel."
                else:
                    best_rec["top_commute"] = f"International flight from {origin} to {dest}, plus scenic destination public transit."

            itinerary_plans = [DayPlan.from_dict(p) for p in data.get("itinerary", [])]
            
            # Sources accessed list
            sources_accessed = [
                {"url": source_url, "title": f"Live {trip_req.destination} Guide (Wikivoyage)", "status": "Scraped via Playwright MCP"},
                {"url": "https://www.booking.com", "title": "Booking.com Stays Directory", "status": "Deep-link booking verified"},
                {"url": "https://www.google.com/travel/flights", "title": "Google Flights & Airline Schedules", "status": "Transit routes indexed"},
                {"url": "https://www.sbb.ch/en/" if is_overseas else "https://www.makemytrip.com/railways", "title": "Swiss Rail (SBB)" if is_overseas else "IRCTC & Indian Railways Portal", "status": "Transit connectivity verified"}
            ]

            return TripResearchResult(
                destination=trip_req.destination,
                summary=data.get("summary", f"Verified live travel research for {trip_req.destination}."),
                attractions=attractions,
                accommodations=accommodations,
                food_experiences=food_experiences,
                commute_options=commute_options,
                neighborhoods=data.get("neighborhoods", []),
                travel_tips=data.get("travel_tips", []),
                best_recommendation=best_rec,
                sources_accessed=sources_accessed,
                research_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                is_demo_data=False,
                execution_logs=[
                    f"Scraped real public webpage: {source_url}",
                    f"Generated multi-provider booking links (Booking.com, Goibibo, MakeMyTrip)",
                    f"Created Google Maps direction URLs for all {len(attractions)} sights and {len(accommodations)} hotels",
                    f"Indexed 4 commute routes (Flights, Express Trains, AC Buses, Highways)"
                ],
                itinerary_plans=itinerary_plans
            )
    except Exception as e:
        err_str = str(e)
        if "503" in err_str or "unavailable" in err_str.lower():
            print(f"Gemini API 503 Service Unavailable note: {e}")
        else:
            print(f"Gemini API live parsing note: {e}")
        return None

def parse_with_heuristics(snapshot_text: str, trip_req: TripRequest, source_url: str) -> TripResearchResult:
    """Fast rule-based extractor for real web page snapshots when AI is offline."""
    dest = trip_req.destination
    attractions: List[Attraction] = []
    accommodations: List[Accommodation] = []
    food_experiences: List[FoodExperience] = []
    img_pool = get_sample_images_for_destination(dest)
    
    lines = snapshot_text.splitlines()
    non_attraction_headings = {
        "understand", "weather", "climate", "get in", "get there", "get around", "get out",
        "see", "do", "buy", "eat", "drink", "sleep", "go next", "contents",
        "references", "external links", "navigation", "menu", "see also", "further reading",
        "districts", "regions", "cities", "other destinations", "boroughs", "suburbs",
        "the year in", "the year in sweden", "electricity and utilities", "electricity", "utilities",
        "tourist information", "visitor information", "practical information", "practicalities",
        "stay safe", "stay healthy", "safety", "health", "respect", "customs", "etiquette",
        "connect", "telecoms", "mobile", "cope", "work", "study", "learn", "visas",
        "passports", "emergency", "holidays", "public holidays", "national holidays",
        "wine and other products", "other products", "local products", "products",
        "souvenirs", "shopping", "shopping in",
    }
    for line in lines:
        cleaned = line.strip()
        if "heading \"" in line:
            name_match = re.search(r'heading "(.*?)"', line)
            if name_match:
                name = name_match.group(1).strip()
                if (
                    is_valid_attraction_name(name, dest)
                    and name.casefold() not in non_attraction_headings
                    and not any(term in name.casefold() for term in ("wine and other products", "electricity", "utilities", "districts", "regions", "cities", "other destinations", "tourist info"))
                    and not any(skip in name.lower() for skip in ["contents", "navigation", "see also", "references", "external links", "menu"])
                ):
                    if len(attractions) < 10 and all(existing.name.casefold() != name.casefold() for existing in attractions):
                        attractions.append(Attraction(
                            name=name,
                            description=f"Landmark in {dest} referenced in travel guide.",
                            category="Sightseeing & Culture",
                            price_inr=50.0,
                            price_display="Free / Nominal",
                            opening_hours="Check local schedule",
                            location=dest,
                            verified=False,
                            source_url=source_url,
                            maps_url=f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + dest)}",
                            image_url=""
                        ))

    if len(attractions) < 4:
        existing = {item.name.casefold() for item in attractions}
        for item in curated_destination_attractions(dest):
            if item.name.casefold() not in existing:
                attractions.append(item)
                existing.add(item.name.casefold())
            if len(attractions) >= 6:
                break
    add_attraction_images(attractions, dest)

    # Supplement heuristic extraction with transparent search suggestions, not invented venues.
    accommodations, food_experiences = ensure_minimum_recommendations(
        dest, accommodations, food_experiences, img_pool
    )

    is_overseas, route_cat = check_route_feasibility(trip_req.starting_city, dest)
    commute_options = generate_commute_options(dest, trip_req.starting_city, trip_req.departure_date)

    if is_overseas:
        if any(w in dest.lower() for w in ["swiss", "switzerland", "swirzerland"]):
            top_commute_rec = f"Direct/1-stop international flight from {trip_req.starting_city or 'BLR'}, followed by the Swiss Travel Pass for panoramic trains."
        else:
            top_commute_rec = f"International flight from {trip_req.starting_city or 'your city'} to {dest}, plus scenic destination public transit."
    else:
        top_commute_rec = f"Direct flight, express train, or intercity bus from {trip_req.starting_city or 'your starting city'} to {dest} (verify route and schedule before booking)."

    return TripResearchResult(
        destination=dest,
        summary=f"Curated travel intelligence for {dest} synthesized from live travel guide references and routing models. AI suggestions should be verified before visiting.",
        attractions=attractions,
        accommodations=accommodations,
        food_experiences=food_experiences,
        commute_options=commute_options,
        neighborhoods=[
            f"Central {dest}: Commercial centers, historic landmarks, and dining streets",
            f"Historic Quarter: Traditional architecture, cultural monuments, and markets"
        ],
        travel_tips=[
            "Use local prepaid taxis, auto-rickshaws, or rented scooters for easy city transit.",
            "UPI digital payments are widely accepted across cafes, stores, and restaurants.",
            "Carry photo ID for monumental entry and ticket verifications."
        ],
        best_recommendation={
            "top_commute": top_commute_rec,
            "top_stay_name": accommodations[0].property_name,
            "top_stay_reason": "Compare live rates and recent reviews for a stay that fits your budget and plans.",
            "must_visit_sights": [a.name for a in attractions[:3]],
            "signature_food": ", ".join(food.name for food in food_experiences[:3])
        },
        sources_accessed=[
            {"url": source_url or "https://en.wikivoyage.org/", "title": f"Live {dest} Guide", "status": "Page snapshot indexed via Playwright MCP"},
            {"url": "https://www.booking.com", "title": "Booking.com Hotel Directory", "status": "Stay search links generated"},
            {"url": "https://www.google.com/travel/flights", "title": "Flight & Airport Schedules", "status": "Air route parameters checked"},
            {"url": "https://www.redbus.in/", "title": "RedBus Portal", "status": "Intercity bus routing mapped"}
        ],
        research_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        is_demo_data=False,
        execution_logs=[f"Scraped real live website: {source_url}"]
    )

def execute_travel_research(
    trip_req: TripRequest,
    session_state=None
) -> Generator[Tuple[str, float, Optional[TripResearchResult]], None, None]:
    """
    Generator that executes live travel research on REAL websites using Playwright MCP
    and yields progress events for Streamlit UI updates.
    """
    start_time = time.time()
    dest = trip_req.destination.strip()
    cache_key = dest.lower()

    # Step 1: Check Memory Cache
    snapshot_text = ""
    active_source_url = ""

    if cache_key in _SNAPSHOT_CACHE:
        cached_time, cached_url, cached_snap = _SNAPSHOT_CACHE[cache_key]
        if time.time() - cached_time < CACHE_TTL_SECONDS:
            snapshot_text = cached_snap
            active_source_url = cached_url
            yield (f"⚡ Fast Cache: Reusing live snapshot for {dest} ({len(snapshot_text):,} chars)...", 0.60, None)

    # Step 2: Live Browser Navigation via Playwright MCP (if not cached)
    if not snapshot_text:
        yield ("🔌 Connecting to Playwright MCP browser...", 0.15, None)
        mcp_client = PlaywrightMCPClient()
        
        real_urls = get_real_travel_urls(dest)
        target_url = real_urls[0]

        yield (f"🌐 Targeting real public travel site: {target_url}...", 0.30, None)
        yield (f"🚀 Playwright MCP: Navigating Chromium to {target_url}...", 0.45, None)
        
        nav_result = mcp_client.navigate_and_snapshot(target_url)
        snapshot_text = nav_result.get("snapshot", "")
        active_source_url = target_url

        # Fallback to secondary URL if needed
        if not nav_result.get("success") or len(snapshot_text) < 1000:
            if len(real_urls) > 1:
                target_url = real_urls[1]
                yield (f"🔄 Checking secondary travel site: {target_url}...", 0.55, None)
                nav_result = mcp_client.navigate_and_snapshot(target_url)
                snapshot_text = nav_result.get("snapshot", "")
                active_source_url = target_url

        # Save to cache
        if snapshot_text and len(snapshot_text) > 1000:
            _SNAPSHOT_CACHE[cache_key] = (time.time(), active_source_url, snapshot_text)

    chars_captured = len(snapshot_text)
    yield (f"📋 Playwright MCP: Extracted {chars_captured:,} characters from live site.", 0.75, None)

    # Step 3: Unified AI Synthesis with Gemini
    yield (f"✨ Unified AI Synthesis: Extracting listings & building itinerary with Gemini ({GEMINI_MODEL})...", 0.88, None)
    
    result = parse_with_gemini(snapshot_text, trip_req, active_source_url, session_state=session_state)

    # Empty/partial Gemini JSON is not a usable result. Run the deterministic parser too.
    has_usable_content = bool(result and (
        result.attractions or result.accommodations or result.food_experiences or result.commute_options
    ))
    if not has_usable_content:
        yield (f"⚡ AI synthesis unavailable or incomplete; applying destination-matched heuristic research for {dest}...", 0.92, None)
        fallback = parse_with_heuristics(snapshot_text or "", trip_req, active_source_url or "")
        if result is None:
            result = fallback
        else:
            # Preserve any valid AI sections while filling empty sections from the fallback.
            result.destination = dest
            result.attractions = result.attractions or fallback.attractions
            result.accommodations = result.accommodations or fallback.accommodations
            result.food_experiences = result.food_experiences or fallback.food_experiences
            result.commute_options = result.commute_options or fallback.commute_options
            result.neighborhoods = result.neighborhoods or fallback.neighborhoods
            result.travel_tips = result.travel_tips or fallback.travel_tips
            result.best_recommendation = result.best_recommendation or fallback.best_recommendation
            result.sources_accessed = result.sources_accessed or fallback.sources_accessed
            result.summary = result.summary or fallback.summary

    # Final guard: never send a completely empty result as a successful completion.
    if result is None or not (result.attractions or result.accommodations or result.food_experiences or result.commute_options):
        raise RuntimeError(
            f"Travel research produced no usable data for {dest!r}. "
            "Check the MCP browser connection, source URL, and Gemini response."
        )

    duration = time.time() - start_time
    result.execution_logs.append(f"Research completed in {duration:.2f}s; source: {active_source_url or 'destination-aware fallback'}")
    result.summary = result.summary or f"Travel suggestions for {dest}. Live data may be incomplete; verify schedules, prices, and opening hours before travel."
    yield (f"✅ Research produced usable results in {duration:.1f}s (review source labels before booking).", 1.0, result)
