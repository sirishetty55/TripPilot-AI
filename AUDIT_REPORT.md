# TripPilot AI — Full System Audit & Remediation Report

**Date:** 2026-10-28  
**Scope:** Architecture, Security, Dependency Compatibility, Data Accuracy, Dynamic Imagery & Isolation Audit  
**Test Suite Status:** 67 / 67 Tests Passing (100% Pass Rate)

---

## Executive Summary

A comprehensive multi-phase security, stability, and correctness overhaul was performed on **TripPilot AI**. All 10 reported audit issues plus Phase 3 (dynamic real destination photographs) have been resolved. The test suite was modernized, hardened against side effects, and expanded from failing/brittle tests to **67 automated tests** running in **0.59s**.

---

## 1. Bugs Fixed & Architectural Remediation

### Issue 1: MCP Dependency & Compatibility (`services/mcp_client.py`, `requirements.txt`)
- **Problem:** `requirements.txt` specified `mcp>=1.3.0` which allowed future major breaking versions. Furthermore, `PlaywrightMCPClient` treated typed MCP SDK objects (such as `mcp_types._types.Implementation`) as raw dictionaries and attempted to access attributes via `.get()`, causing `AttributeError: 'Implementation' object has no attribute 'get'`.
- **Root Cause:** Untyped dictionary access on typed Pydantic/dataclass response objects from the official `mcp` SDK (version 2.3.0).
- **Remediation:**
  - Pinned `mcp>=1.3.0,<3.0.0` in `requirements.txt`.
  - Updated `services/mcp_client.py` to inspect `server_info` using `getattr(info, "name", ...)` and safely handle both object attributes and dictionary fallbacks.
  - Added robust exception handling with safe fallbacks and explicit error reporting instead of silently pretending operations succeeded.
  - Added early synchronous URL validation to `navigate_and_snapshot()` preventing subprocess spawning on prohibited URLs.

### Issue 2: SSRF & URL Validation Vulnerabilities (`services/mcp_client.py`)
- **Problem:** The URL validator permitted arbitrary dotted hostnames, accepted insecure schemes, and had inadequate private-network and loopback destination filtering, leaving the MCP browser automation vulnerable to Server-Side Request Forgery (SSRF) and DNS rebinding attacks.
- **Root Cause:** Naive regex/substring checks on user-provided or external URLs without IP resolution, octal/hex bypass defense, or DNS rebinding safeguards.
- **Remediation:**
  - Enforced scheme restrictions: only `https://` is permitted for public travel research destinations (with explicit, controlled `http://localhost:8765` allowlisting for the internal demo server).
  - Implemented domain boundary checking against an explicit travel allowlist (`ALLOWLISTED_TRAVEL_DOMAINS`). Subdomain lookalike bypasses (e.g. `lonelyplanet.com.attacker.com`) are strictly blocked using dot-boundary matching.
  - Integrated pre-flight DNS hostname resolution via `socket.getaddrinfo()`. All resolved IP addresses are evaluated against `ipaddress.ip_address()`, rejecting:
    - Loopback addresses (`127.0.0.0/8`, `::1`)
    - RFC 1918 private IPv4 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
    - Link-local and multicast addresses (`169.254.0.0/16`, `224.0.0.0/4`, `fe80::/10`)
    - IPv4-mapped IPv6 addresses (`::ffff:127.0.0.1`, `::ffff:10.0.0.1`)
    - Cloud metadata IP endpoints (`169.254.169.254`)
  - Covered by 8 comprehensive automated tests in `tests/test_mcp_client.py`.

### Issue 3: Database Test Isolation (`database.py`, `tests/test_database.py`)
- **Problem:** Running unit tests modified the live SQLite database (`trippilot.db`), accumulating test artifacts and corrupting production data.
- **Root Cause:** Hardcoded `DATABASE_PATH = "trippilot.db"` without path-overriding parameters or fixture cleanup.
- **Remediation:**
  - Updated all functions in `database.py` (`get_connection`, `init_db`, `save_trip`, `get_saved_trips`, `log_research_session`, `get_recent_research_logs`) to accept an optional `db_path` parameter, defaulting to `DATABASE_PATH`.
  - Re-architected `tests/test_database.py` using `tempfile.mkdtemp()`: every test runs in an ephemeral temporary database that is cleanly torn down after execution.
  - Added a dedicated regression test (`test_production_database_remains_unmodified`) confirming that the live `trippilot.db` file is completely untouched by test runs (verified: exactly 4 trips and 8 audit logs preserved).

### Issue 4: Gemini API Compatibility & Error Handling (`services/itinerary_service.py`, `config.py`)
- **Problem:** Gemini 3-series models (e.g. `gemini-3.8-flash`) and reasoning models fail when unsupported sampling parameters like `temperature` are passed in `GenerateContentConfig`.
- **Root Cause:** Passing fixed `temperature=0.3` regardless of target model architecture.
- **Remediation:**
  - Updated `services/itinerary_service.py` to inspect the model name. If the configured model contains `"gemini-3"`, `"gemini-2.5"`, or `"thinking"`, the `temperature` parameter is omitted from `types.GenerateContentConfig()`.
  - Wrapped API calls in structured exception handling, validating output JSON and falling back gracefully to the deterministic destination-aware generator upon timeout or error.

### Issue 5: Domestic vs. International Destination Classification (`services/location_service.py`)
- **Problem:** Pudukkottai was classified as international because its name contains the substring `"uk"`. Luxembourg was misclassified as domestic. Over-simplified substring matching caused widespread route misclassification.
- **Root Cause:** `if any(kw in dest.lower() for kw in INTERNATIONAL_KEYWORDS)` where `"uk"` was a keyword.
- **Remediation:**
  - Built `services/location_service.py` with ISO 3166-1 country code mappings (`IN`, `LU`, `CH`, `FR`, etc.), word-boundary regex patterns (`\b(uk|united kingdom)\b`), and tokenized matching.
  - Added comprehensive catalogs of Indian cities, union territories, hill stations, and world metropolises.
  - Island classification accurately distinguishes domestic islands (Andaman, Lakshadweep: requires domestic flights/ferries, no cars) from international islands (Maldives, Bali) and overland routes.
  - Unresolvable names return `UNKNOWN` country code and `is_ambiguous=True` rather than silently guessing.
  - Covered by 15 tests in `tests/test_location_service.py` and 7 tests in `tests/test_commute_feasibility.py`.

### Issue 6: Budget Calculations & Single Source of Truth (`services/budget_service.py`, `models.py`)
- **Problem:** Flight/intercity commute costs were excluded from totals; hotel estimates mismatched user requested tiers; stale budget overrides persisted across new searches; and per-person vs. group costs were ambiguous.
- **Root Cause:** Lack of intercity transit parsing, missing room-occupancy arithmetic, and unreset session state keys.
- **Remediation:**
  - Intercity transit cost parsing: parses fare estimates from `commute_options` and includes `transit_cost` directly in the budget breakdown.
  - Multi-traveler room arithmetic: hotel calculations now compute `rooms = math.ceil(travelers / 2)` and scale accommodation accordingly.
  - Hotel tier alignment: budget, mid-range, and luxury tiers map directly to price brackets.
  - Unpriced / zero-cost activity buffering: nominal buffer is added for zero-cost activities to ensure realistic budgeting.
  - Added `per_person_total` to `BudgetBreakdown` and added per-person cost breakdown columns in `pages/3_Budget_Planner.py`.
  - Session state scoping: `app.py` and `pages/4_Saved_Trips.py` now explicitly reset `st.session_state["budget_overrides"]` when generating a new search or loading a saved trip.

### Issue 7: Same-Day Trip Accommodation Calculation (`models.py`, `services/budget_service.py`)
- **Problem:** Same-day trips (where departure date == return date) were assigned a hotel stay with 1 night and overnight charges.
- **Root Cause:** `num_nights` property previously returned `max(1, (d2 - d1).days)` or `max(1, num_days - 1)`.
- **Remediation:**
  - Modified `TripRequest.num_nights` in `models.py`: if `d2 <= d1`, returns `0`.
  - Updated `budget_service.py`: when `num_nights == 0`, accommodation cost is forced to `₹0.0` and noted transparently in assumptions.
  - Covered by automated regression tests in `tests/test_budget.py` and `tests/test_itinerary_service.py`.

### Issue 8: Destination-Aware Itinerary Fallbacks (`services/itinerary_service.py`)
- **Problem:** When AI generation was unavailable, the fallback generator recommended beach and coastal activities for landlocked and mountain destinations like Paris and Manali.
- **Root Cause:** Monolithic generic fallback template biased toward coastal/beach activities.
- **Remediation:**
  - Added `_get_destination_theme(destination: str)` utilizing `resolve_location()`.
  - Classifies destinations into distinct geographic archetypes:
    - `mountain`: Scenic trails, alpine vistas, local bazaars, woolen crafts, regional warm cuisine (Manali, Shimla, Alps).
    - `coastal`: Coastal promenades, maritime heritage, fresh seafood, viewpoints (Goa, Kerala, Bali).
    - `metropolis`: Iconic museums, historic quarters, metro transit, regional bistros (Paris, London, Zurich, Tokyo).
    - `heritage`: Historic forts, royal palaces, craft emporiums, traditional thalis (Jaipur, Agra, Varanasi).
  - Same-day itineraries omit accommodation check-in activities.
  - Covered by 9 tests in `tests/test_itinerary_service.py`.

### Issue 9: Real Travel Data & Honest Verification Badges (`services/travel_research.py`, `pages/1_Trip_Results.py`)
- **Problem:** Hardcoded attractions were stamped with misleading "Verified" badges and fake source URLs.
- **Remediation:**
  - Clarified source status: only recommendations actually fetched from live web research or verified guides receive the green `✓ Live Verified Source` badge.
  - Algorithmic and fallback recommendations are stamped with `ℹ️ Curated Guide Suggestion` or `💡 Destination Estimate`.
  - All external links include valid, safe query URLs to Google Maps and official sources.

### Issue 10: HTML Injection & External Content Sanitization (`services/ui_utils.py`, `pages/1_Trip_Results.py`, `pages/3_Budget_Planner.py`, `pages/4_Saved_Trips.py`)
- **Problem:** User input, destination names, and scraped text were rendered directly inside raw HTML string interpolation (`unsafe_allow_html=True`), enabling Cross-Site Scripting (XSS).
- **Remediation:**
  - Built `safe_html(text)` in `services/ui_utils.py` using `html.escape(..., quote=True)`.
  - Built `safe_url(url)` disarming dangerous schemes (`javascript:`, `data:`, `vbscript:`).
  - Created `render_card_image(image_url, alt_text, attribution_text, attribution_url)` which strictly validates image URLs, alt text, and attributions.
  - Replaced raw string interpolation across all Streamlit page views.
  - Covered by 9 automated tests in `tests/test_security_html.py`.

---

## 2. Phase 3: Real Dynamic Destination Photographs

### Architecture (`services/image_service.py`)
To eliminate static, repetitive, or fabricated stock photos, a dynamic photo retrieval service was implemented:

1. **Wikimedia Commons Primary Provider (No API key required, zero rate limit issues):**
   - Queries the official MediaWiki Action API (`api.php?action=query&prop=pageimages|imageinfo&...`).
   - Retrieves high-resolution real photographs of landmarks, monuments, and cities.
   - Extracts author, license, and source attribution metadata.
2. **Unsplash API Optional Secondary Provider:**
   - Enabled when `UNSPLASH_ACCESS_KEY` is present in `.env`.
   - Fetches editorial travel photographs with photographer name and Unsplash referral links compliant with Unsplash API guidelines.
3. **Two-Tier Resilient Caching:**
   - **Tier 1 (In-Memory):** Instant retrieval within active session.
   - **Tier 2 (SQLite `image_cache`):** Persistent caching across application runs, reducing redundant network requests.
4. **Honest Fallback Policy:**
   - If a specific attraction photo is unavailable, falls back to the verified city-level photo.
   - If offline or unreachable, returns empty string `""` — **never fabricates or guesses fake image URLs**.
   - UI gracefully collapses or renders a clean placeholder card without broken image icons.

---

## 3. Test Suite Summary

Total Test Count: **67 Tests**  
Pass Rate: **100% (67 Passed, 0 Failed, 0 Skipped)**  
Execution Duration: **0.59 seconds**

| Test Module | Coverage Area | Count | Result |
|-------------|---------------|-------|--------|
| `tests/test_budget.py` | Same-day trips, hotel tiers, room counts, transit costs, overrides | 8 | ✅ Pass |
| `tests/test_commute_feasibility.py` | Pudukkottai domestic, Luxembourg intl, overland feasibility | 7 | ✅ Pass |
| `tests/test_database.py` | Isolated tempfile database, production DB preservation, audit logs | 3 | ✅ Pass |
| `tests/test_mcp_client.py` | SSRF prevention, allowlist boundaries, DNS rebinding, typed metadata | 8 | ✅ Pass |
| `tests/test_attraction_images.py` | Wikipedia image heuristic extraction, no unrelated stock photos | 2 | ✅ Pass |
| `tests/test_recommendations.py` | Minimum recommendation supplementation, preservation of live data | 2 | ✅ Pass |
| `tests/test_security_html.py` | XSS protection, script tags, event handlers, URL scheme disarming | 9 | ✅ Pass |
| `tests/test_image_service.py` | Wikimedia fetch, caching, destination fallback, offline honesty | 4 | ✅ Pass |
| `tests/test_itinerary_service.py` | Paris/Manali geo-appropriate themes, same-day plans, rich data usage | 9 | ✅ Pass |
| `tests/test_location_service.py` | Island detection, token matching, ambiguous destinations, ISO codes | 15 | ✅ Pass |

---

## 4. Configuration & Environment Variables

Updated `.env.example`:
```ini
# Google Gemini API Key (Optional: get from https://aistudio.google.com/)
GEMINI_API_KEY=

# AI Model Selection (Default: gemini-3.8-flash)
GEMINI_MODEL=gemini-3.8-flash

# Playwright MCP Server Configuration
PLAYWRIGHT_MCP_COMMAND=npx
PLAYWRIGHT_TIMEOUT_SECONDS=35

# SQLite Database Location
DATABASE_PATH=trippilot.db

# Local Demo Server Port
DEMO_SERVER_PORT=8765

# Unsplash API Key (Optional: for higher-quality destination photographs)
# Get a free key at https://unsplash.com/developers
# If omitted, TripPilot AI uses Wikimedia Commons (free, no key required).
UNSPLASH_ACCESS_KEY=

# Image Cache Location (defaults to DATABASE_PATH if unset)
# IMAGE_CACHE_PATH=trippilot.db
```

---

## 5. Verification Checklist for Users

To verify the fixes in the running application:

1. **Launch Application:**
   ```bash
   streamlit run app.py
   ```
2. **Verify Destination Classification (Pudukkottai & Luxembourg):**
   - Search for destination `"Pudukkottai"` with starting city `"Bengaluru"`.
   - Check Route Feasibility: Displays domestic overland options (Train, Bus, Drive). Does **not** classify as international.
   - Search for destination `"Luxembourg"` with starting city `"Mumbai"`.
   - Check Route Feasibility: Displays international flight route. Excludes cars, buses, and domestic trains.
3. **Verify Same-Day Trip Accommodation:**
   - Select departure date and return date as the **same day** (e.g. today).
   - In **Trip Results** and **Budget Planner**, verify Accommodation is **₹0 (0 nights)**.
4. **Verify Destination-Aware Itinerary Fallback:**
   - Search `"Paris"` without a Gemini API key.
   - Inspect **Itinerary**: Activities include museums, historic districts, and cafes. Contains **no** beach, coastal, or surfing activities.
5. **Verify Real Destination Photos:**
   - Inspect destination cards in **Trip Results**: Real photographs with attribution captions are displayed.
6. **Verify Security & HTML Sanitization:**
   - Enter `<script>alert(1)</script>` or `"><img src=x onerror=alert(1)>` as a custom destination or interest.
   - Verify that characters are rendered harmlessly as escaped text and no script executes.
7. **Verify Database Isolation:**
   - Run the test suite:
     ```bash
     python -m unittest discover -s tests -p "test_*.py"
     ```
   - Check `trippilot.db`: production saved trips and audit logs remain exactly intact.

