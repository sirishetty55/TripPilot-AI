"""
TripPilot AI — Page 1: Trip Results & Destination Explorer
Displays verified attractions, accommodations, dining, commute options, and curated recommendations.
Protected against HTML injection with dynamic real photographs and honest verification labels.
"""

import streamlit as st
from services.ui_utils import apply_custom_theme, render_hero, safe_html, safe_url, render_card_image
from models import TripRequest, TripResearchResult, BudgetBreakdown

st.set_page_config(page_title="Trip Results — TripPilot AI", page_icon="🗺️", layout="wide")
apply_custom_theme()

render_hero("🗺️ Trip Results & Destination Intelligence", "Multi-source findings gathered via Playwright MCP browser automation and AI synthesis.")

# Check for active trip research in session
req: TripRequest = st.session_state.get("active_trip_request")
res: TripResearchResult = st.session_state.get("active_research_result")

if not res:
    st.warning("⚠️ No active trip research found in this session.")
    st.info("Please start a search on the **Home** page or choose a quick preset to begin browser automation.")
    st.stop()

# Header Badge Bar
col_h1, col_h2, col_h3, col_h4 = st.columns(4)
with col_h1:
    st.metric("Destination", res.destination)
with col_h2:
    night_str = f"{req.num_nights} Night(s)" if req.num_nights > 0 else "Same-Day (0 Nights)"
    st.metric("Duration", f"{req.num_days} Day(s) / {night_str}")
with col_h3:
    st.metric("Party Size", f"{req.travelers} Traveler(s)")
with col_h4:
    demo_tag = "🔬 Local Demo Portal" if res.is_demo_data else "🌐 Live Web Research"
    st.metric("Research Source", demo_tag)

if res.is_demo_data:
    st.markdown('<span class="badge-demo">DEMO MODE: Research conducted on authenticated local travel portal</span>', unsafe_allow_html=True)

# Feature: Editor's Best Recommendations Showcase
best_rec = getattr(res, "best_recommendation", {}) or {}
if best_rec:
    st.markdown("---")
    st.markdown("""<div style="background: linear-gradient(135deg, rgba(13, 148, 136, 0.15) 0%, rgba(2, 132, 199, 0.15) 100%); border: 1px solid rgba(13, 148, 136, 0.4); border-radius: 12px; padding: 18px 24px; margin-bottom: 20px;">
<h3 style="margin: 0 0 10px 0; color: #0d9488; display: flex; align-items: center; gap: 8px;">
🌟 Editor's Top Recommendations for Your Trip
</h3>
</div>""", unsafe_allow_html=True)

    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    with col_b1:
        top_commute = safe_html(best_rec.get('top_commute', 'Flight / Express Train'))
        st.markdown(f"""<div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #0284c7; height: 100%;">
<div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🚆 Best Commute</div>
<div style="font-size: 14px; font-weight: 600; margin-top: 4px;">{top_commute}</div>
</div>""", unsafe_allow_html=True)

    with col_b2:
        top_stay = safe_html(best_rec.get('top_stay_name', 'Verified Stay'))
        top_reason = safe_html(best_rec.get('top_stay_reason', 'Great value and location'))
        st.markdown(f"""<div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #0d9488; height: 100%;">
<div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🏨 Recommended Stay</div>
<div style="font-size: 14px; font-weight: 600; margin-top: 4px;">{top_stay}</div>
<div style="font-size: 12px; opacity: 0.85; margin-top: 2px;">{top_reason}</div>
</div>""", unsafe_allow_html=True)

    with col_b3:
        must_visits = best_rec.get('must_visit_sights', [])
        sights_str = safe_html(", ".join(must_visits) if isinstance(must_visits, list) else str(must_visits))
        st.markdown(f"""<div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #f59e0b; height: 100%;">
<div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🏛️ Must-Visit Sights</div>
<div style="font-size: 13px; font-weight: 500; margin-top: 4px;">{sights_str or 'Historic Forts & Scenic Sights'}</div>
</div>""", unsafe_allow_html=True)

    with col_b4:
        food_rec = safe_html(best_rec.get('signature_food', 'Traditional regional specialty'))
        st.markdown(f"""<div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #ec4899; height: 100%;">
<div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🍲 Signature Food</div>
<div style="font-size: 13px; font-weight: 500; margin-top: 4px;">{food_rec}</div>
</div>""", unsafe_allow_html=True)

st.markdown("---")

# Tabbed Interface
tab_commute, tab_attractions, tab_stays, tab_dining, tab_tips, tab_sources = st.tabs([
    f"🚆 Commute & Transit ({len(getattr(res, 'commute_options', []))})",
    f"🏛️ Attractions ({len(res.attractions)})",
    f"🏨 Accommodations ({len(res.accommodations)})",
    f"🍽️ Cuisine & Food ({len(res.food_experiences)})",
    "💡 Neighborhoods & Tips",
    "🔗 Verified Sources"
])

# 1. Commute & Transit Tab
with tab_commute:
    st.subheader(f"Commute & Travel Options to {safe_html(res.destination)}")
    origin_display = req.starting_city if req.starting_city else "Your City"
    st.caption(f"Estimated routes, flight connections, train lines, and transit links from **{safe_html(origin_display)}** to **{safe_html(res.destination)}**.")

    commute_list = getattr(res, "commute_options", [])
    if not commute_list:
        st.info("Transit options are being generated for this route.")
    else:
        for opt in commute_list:
            safe_title = safe_html(opt.title)
            safe_mode = safe_html(opt.mode)
            safe_dur = safe_html(opt.duration)
            safe_cost = safe_html(opt.estimated_cost_inr)
            safe_details = safe_html(opt.details)
            clean_b_url = safe_url(opt.booking_url)
            clean_s_url = safe_url(opt.source_url)
            
            with st.container():
                st.markdown(f"""<div class="travel-card">
<div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
<div>
<h4 style="margin: 0; color: #0284c7; display: flex; align-items: center; gap: 8px;">
<span>{safe_html(opt.icon)}</span> {safe_title}
</h4>
<span style="font-size: 13px; font-weight: 600; opacity: 0.85;">Mode: {safe_mode} &bull; ⏱️ Est. Duration: {safe_dur}</span>
</div>
<div style="text-align: right;">
<span class="badge-price">{safe_cost}</span>
</div>
</div>
<p style="margin: 10px 0 12px 0; color: inherit; opacity: 0.92;">{safe_details}</p>
<div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
<a href="{clean_b_url}" target="_blank" class="btn-action btn-book">🎟️ Check Fares & Book Tickets</a>
<a href="{clean_s_url}" target="_blank" class="btn-action btn-source">🔗 Official Transit Portal</a>
</div>
</div>""", unsafe_allow_html=True)

# 2. Attractions Tab
with tab_attractions:
    st.subheader("Verified Attractions & Things to Do")
    st.caption("Extracted from travel guides. Real landmark photographs retrieved dynamically with Google Maps navigation pins.")
    
    if not res.attractions:
        st.info("No attractions were found in the current travel guide snapshot.")
    else:
        for attr in res.attractions:
            img_block = render_card_image(
                image_url=attr.image_url,
                alt_text=attr.name,
                width_px=170,
                height_px=120,
                attribution_text=getattr(attr, "attribution_text", ""),
                attribution_url=getattr(attr, "attribution_url", "")
            )
            badge_html = '<span class="badge-verified">✓ SOURCED FROM GUIDE</span>' if attr.verified else '<span class="badge-unverified">AI SUGGESTION</span>'
            clean_maps = safe_url(attr.maps_url)
            clean_source = safe_url(attr.source_url)

            with st.container():
                st.markdown(f"""<div class="travel-card">
<div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
{img_block}
<div style="flex: 1; min-width: 260px;">
<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
<h4 style="margin: 0; color: #0d9488;">{safe_html(attr.name)}</h4>
<div>
{badge_html}
<span class="badge-price">{safe_html(attr.price_display)}</span>
</div>
</div>
<p style="margin: 8px 0 6px 0; color: inherit; opacity: 0.92;">{safe_html(attr.description)}</p>
<div style="font-size: 13px; color: inherit; opacity: 0.85;">
<strong>📍 Location:</strong> {safe_html(attr.location)} &nbsp;|&nbsp; 
<strong>⏰ Timings:</strong> {safe_html(attr.opening_hours)} &nbsp;|&nbsp;
<strong>🏷️ Category:</strong> {safe_html(attr.category)}
</div>
<div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
<a href="{clean_maps}" target="_blank" class="btn-action btn-maps">📍 View on Google Maps</a>
{f'<a href="{clean_source}" target="_blank" class="btn-action btn-source">🔗 Source Details</a>' if clean_source != "#" else ''}
</div>
</div>
</div>
</div>""", unsafe_allow_html=True)

# 3. Accommodation Research Tab
with tab_stays:
    st.subheader("Accommodation Options & Booking Searches")
    st.caption("Direct links to live booking portals (Booking.com / Goibibo / MakeMyTrip) and Google Maps pins.")

    if not res.accommodations:
        st.info("No accommodation listings were found for this destination.")
    else:
        for stay in res.accommodations:
            total_stay_est = stay.price_per_night_inr * req.num_nights * max(1, (req.travelers + 1) // 2)
            stay_img_block = render_card_image(
                image_url=stay.image_url,
                alt_text=stay.property_name,
                width_px=170,
                height_px=130,
                attribution_text=getattr(stay, "attribution_text", ""),
                attribution_url=getattr(stay, "attribution_url", "")
            )
            clean_book = safe_url(stay.booking_url)
            clean_maps = safe_url(stay.maps_url)
            clean_source = safe_url(stay.source_url)
            badge_html = '<span class="badge-verified">✓ LISTING RATE</span>' if stay.verified else '<span class="badge-unverified">ESTIMATED SEARCH</span>'

            with st.container():
                st.markdown(f"""<div class="travel-card">
<div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
{stay_img_block}
<div style="flex: 1; min-width: 260px;">
<div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 6px;">
<div>
<h4 style="margin: 0; color: #0d9488;">{safe_html(stay.property_name)}</h4>
<span style="font-size: 12px; color: inherit; opacity: 0.85;">{safe_html(stay.property_type)} &bull; 📍 {safe_html(stay.location)}</span>
{badge_html}
</div>
<div style="text-align: right;">
<span class="badge-price" style="font-size: 14px;">{safe_html(stay.price_display)}</span>
<div style="font-size: 12px; color: #f59e0b; font-weight: bold; margin-top: 4px;">★ {safe_html(stay.rating)}</div>
</div>
</div>
<p style="margin: 10px 0; color: inherit; opacity: 0.92;">{safe_html(stay.description)}</p>
<div style="background: rgba(128, 128, 128, 0.12); padding: 8px 12px; border-radius: 6px; font-size: 13px; border: 1px solid rgba(128, 128, 128, 0.22); margin-bottom: 10px;">
<strong>Estimated Total for Party:</strong> ₹{total_stay_est:,.0f} 
<span style="opacity: 0.8;">({req.num_nights} night(s) for {req.travelers} traveler(s))</span>
</div>
<div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
<a href="{clean_book}" target="_blank" class="btn-action btn-book">🏨 Book / Check Availability</a>
<a href="{clean_maps}" target="_blank" class="btn-action btn-maps">📍 View on Google Maps</a>
{f'<a href="{clean_source}" target="_blank" class="btn-action btn-source">🔗 Portal</a>' if clean_source != "#" else ''}
</div>
</div>
</div>
</div>""", unsafe_allow_html=True)

# 4. Dining & Cuisine Tab
with tab_dining:
    st.subheader("Authentic Regional Food & Dining")
    st.caption("Curated dishes and local culinary hotspots with direct Google Maps directions.")
    
    for f in res.food_experiences:
        food_img_block = render_card_image(
            image_url=f.image_url,
            alt_text=f.name,
            width_px=150,
            height_px=110,
            attribution_text=getattr(f, "attribution_text", ""),
            attribution_url=getattr(f, "attribution_url", "")
        )
        clean_maps = safe_url(f.maps_url)
        clean_source = safe_url(f.source_url)
        badge_html = '<span class="badge-verified">✓ REGIONAL SPECIALTY</span>' if f.verified else '<span class="badge-unverified">SUGGESTED DISH</span>'

        with st.container():
            st.markdown(f"""<div class="travel-card">
<div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
{food_img_block}
<div style="flex: 1; min-width: 250px;">
<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
<h4 style="margin: 0; color: #0d9488;">{safe_html(f.name)}</h4>
<span class="badge-price">{safe_html(f.price_range_inr)}</span>
</div>
<div style="font-size: 13px; color: #f59e0b; font-weight: 500; margin-top: 2px;">{safe_html(f.cuisine_type)} &bull; 📍 {safe_html(f.location)} &bull; {badge_html}</div>
<p style="margin: 8px 0; color: inherit; opacity: 0.92;">{safe_html(f.description)}</p>
<div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px;">
<a href="{clean_maps}" target="_blank" class="btn-action btn-maps">📍 Directions on Google Maps</a>
{f'<a href="{clean_source}" target="_blank" class="btn-action btn-source">🔗 Food Guide</a>' if clean_source != "#" else ''}
</div>
</div>
</div>
</div>""", unsafe_allow_html=True)

# 5. Neighborhoods & Practical Tips Tab
with tab_tips:
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("🏘️ Recommended Neighborhoods")
        for n in res.neighborhoods:
            st.markdown(f"- {safe_html(n)}")
    with col_t2:
        st.subheader("🧳 Practical Travel Tips & Transit Advice")
        for tip in res.travel_tips:
            st.markdown(f"- {safe_html(tip)}")

# 6. Verified Sources & MCP Audit Tab
with tab_sources:
    st.subheader("🔍 Playwright MCP Browser Navigation Audit")
    st.write("TripPilot AI visited the following URLs through the official Playwright MCP server to extract this data:")
    for s in res.sources_accessed:
        clean_s_url = safe_url(s.get('url'))
        st.markdown(f"""
        - **URL:** `{safe_html(s.get('url'))}`
        - **Title:** {safe_html(s.get('title'))}
        - **Status:** `{safe_html(s.get('status'))}`
        """)

    with st.expander("Inspect Raw MCP Execution Logs"):
        for log in res.execution_logs:
            st.code(log, language="text")
