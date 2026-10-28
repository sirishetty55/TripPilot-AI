"""
TripPilot AI — Page 1: Trip Results & Destination Explorer
Displays verified attractions, accommodations, dining, commute options, and curated recommendations.
"""

import re
from datetime import datetime, date, timedelta
from urllib.parse import quote_plus
import streamlit as st
from services.ui_utils import apply_custom_theme, render_hero, safe_html, safe_url, render_html, render_card_image
from models import TripRequest, TripResearchResult, BudgetBreakdown
from services.budget_service import calculate_budget
from services.travel_research import get_categorized_tourist_places, check_route_feasibility

st.set_page_config(page_title="Trip Results — TripPilot AI", page_icon="🗺️", layout="wide")
apply_custom_theme()

render_hero("🗺️ Trip Results & Destination Intelligence", "Verified multi-source findings gathered via Playwright MCP browser automation.")

# Restore the active trip from Streamlit session state first, then SQLite if explicitly active.
# Never blindly fall back to recent[0] to prevent showing a previous destination (e.g. Mumbai when searching Goa).
req: TripRequest = st.session_state.get("active_trip_request")
res: TripResearchResult = st.session_state.get("active_research_result")

if not res:
    try:
        import database
        from models import DayPlan
        active_trip_id = st.session_state.get("active_trip_id")
        saved = database.get_trip_by_id(int(active_trip_id)) if active_trip_id else None
        if saved:
            req_data = saved.get("trip_request", {})
            result_data = saved.get("research_result", {})
            saved_req = TripRequest.from_dict(req_data)
            saved_res = TripResearchResult.from_dict(result_data)
            # Ensure saved trip destination matches request
            if saved_req.destination.casefold().strip() == saved_res.destination.casefold().strip():
                req = saved_req
                res = saved_res
                st.session_state["active_trip_id"] = saved.get("id")
                st.session_state["active_trip_request"] = req
                st.session_state["active_research_result"] = res
                st.session_state["active_itinerary"] = [DayPlan.from_dict(p) for p in saved.get("itinerary", [])]
                budget_data = saved.get("budget", {})
                if budget_data:
                    st.session_state["active_budget"] = BudgetBreakdown.from_dict(budget_data)
    except Exception as exc:
        st.error(f"Could not restore the saved trip: {type(exc).__name__}: {exc}")

if not res:
    st.warning("No active or saved trip research was found.")
    st.info("Return to the Home page, enter your trip details, and run research again. Your submitted form values will persist across page navigation.")
    st.stop()

if req is None:
    st.error("The trip result exists, but its request details are missing. Please return Home and run the search again.")
    st.stop()

# Header Badge Bar — 4-column summary: Destination, Duration, Party Size, Estimated Trip Cost
active_budget = st.session_state.get("active_budget")
if not active_budget:
    active_budget = calculate_budget(req, res)
    st.session_state["active_budget"] = active_budget

est_total_party = active_budget.total_estimated
is_over = active_budget.is_over_budget
diff = abs(active_budget.remaining_budget)

col_h1, col_h2, col_h3, col_h4 = st.columns(4)
with col_h1:
    st.metric("Destination", res.destination)
with col_h2:
    st.metric("Duration", f"{req.num_days} Days / {req.num_nights} Nights")
with col_h3:
    st.metric("Party Size", f"{req.travelers} Traveler(s)")
with col_h4:
    delta_str = f"+₹{diff:,.0f} Over Budget" if is_over else f"₹{diff:,.0f} Buffer Left"
    st.metric(
        "Estimated Trip Cost",
        f"₹{est_total_party:,.0f} (Est.)",
        delta=delta_str,
        delta_color="inverse" if is_over else "normal",
        help=f"Realistic estimate for {req.travelers} traveler(s) across stay, dining, transit, and activities based on selected dates and tier. Stated budget: ₹{req.budget_inr:,.0f} INR."
    )

if is_over:
    st.warning(f"⚠️ **Budget Alert:** The estimated trip expenses (₹{est_total_party:,.0f}) exceed your specified budget of ₹{req.budget_inr:,.0f} by ₹{diff:,.0f}. You can fine-tune individual expense categories in the Budget Planner.")
else:
    st.success(f"✅ **Budget Status:** The estimated trip expenses (₹{est_total_party:,.0f}) are comfortably within your budget of ₹{req.budget_inr:,.0f} with a buffer of ₹{diff:,.0f} remaining.")

if res.is_demo_data:
    render_html('<span class="badge-demo">DEMO MODE ACTIVE: Research conducted on authenticated local travel portal</span>')

# Feature: Editor's Best Recommendations Showcase
best_rec = getattr(res, "best_recommendation", {}) or {}
if best_rec:
    st.markdown("---")
    render_html("""
    <div style="background: linear-gradient(135deg, rgba(13, 148, 136, 0.15) 0%, rgba(2, 132, 199, 0.15) 100%);
                border: 1px solid rgba(13, 148, 136, 0.4); border-radius: 12px; padding: 18px 24px; margin-bottom: 20px;">
        <h3 style="margin: 0 0 10px 0; color: #0d9488; display: flex; align-items: center; gap: 8px;">
            🌟 Editor's Top Recommendations for Your Trip
        </h3>
    </div>
    """)

    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    with col_b1:
        top_commute_val = safe_html(best_rec.get('top_commute', 'Flight / Express Train'))
        render_html(f"""
        <div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #0284c7; height: 100%;">
            <div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🚆 Best Commute</div>
            <div style="font-size: 14px; font-weight: 600; margin-top: 4px;">{top_commute_val}</div>
        </div>
        """)

    with col_b2:
        top_stay = safe_html(best_rec.get('top_stay_name', 'Verified Central Stay'))
        top_reason = safe_html(best_rec.get('top_stay_reason', 'Great value and location'))
        render_html(f"""
        <div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #0d9488; height: 100%;">
            <div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🏨 Recommended Stay</div>
            <div style="font-size: 14px; font-weight: 600; margin-top: 4px;">{top_stay}</div>
            <div style="font-size: 12px; opacity: 0.85; margin-top: 2px;">{top_reason}</div>
        </div>
        """)

    with col_b3:
        must_visits = best_rec.get('must_visit_sights', [])
        sights_str = safe_html(", ".join(must_visits) if isinstance(must_visits, list) else str(must_visits))
        render_html(f"""
        <div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #f59e0b; height: 100%;">
            <div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🏛️ Must-Visit Sights</div>
            <div style="font-size: 13px; font-weight: 500; margin-top: 4px;">{sights_str or 'Historic Forts & Coastal Spots'}</div>
        </div>
        """)

    with col_b4:
        food_rec = safe_html(best_rec.get('signature_food', 'Local traditional platter'))
        render_html(f"""
        <div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #ec4899; height: 100%;">
            <div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🍲 Signature Food</div>
            <div style="font-size: 13px; font-weight: 500; margin-top: 4px;">{food_rec}</div>
        </div>
        """)

st.markdown("---")

# Retrieve destination-specific categorized tourist places
categorized_places = get_categorized_tourist_places(res.destination, res.attractions)
total_places_count = sum(len(items) for items in categorized_places.values())

# Tabbed Interface — includes separate "Tourist Places to Visit" section
tab_commute, tab_places, tab_attractions, tab_stays, tab_dining, tab_tips, tab_sources = st.tabs([
    f"🚆 Commute & Transit ({len(getattr(res, 'commute_options', []))})",
    f"📍 Tourist Places to Visit ({total_places_count})",
    f"🏛️ Attractions & Activities ({len(res.attractions)})",
    f"🏨 Accommodations ({len(res.accommodations)})",
    f"🍽️ Cuisine & Food ({len(res.food_experiences)})",
    "💡 Neighborhoods & Tips",
    "🔗 Verified Sources"
])

# 1. Commute & Transit Tab
with tab_commute:
    st.subheader(f"Commute & Travel Options to {res.destination}")
    origin_display = req.starting_city if req.starting_city else "Your City"
    st.caption(f"Estimated routes, flight connections, train lines, and bus links from **{origin_display}** to **{res.destination}**.")

    commute_list = getattr(res, "commute_options", [])
    if not commute_list:
        st.info("Transit options are being generated for this route.")
    else:
        is_air_only = not any(
            any(k in opt.mode.lower() or k in opt.title.lower() for k in ["bus", "car", "drive", "road trip", "highway"])
            for opt in commute_list
        )
        if is_air_only:
            st.info(
                f"✈️ **Physical Feasibility Notice:** Travel between **{origin_display}** and **{res.destination}** requires air travel. "
                f"Overland options (cross-border trains, buses, and road trips) are not physically possible and have been automatically excluded. "
                f"Viable flights and official internal transit at {res.destination} are detailed below."
            )

        for opt in commute_list:
            render_html(f"""
            <div class="travel-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
                    <div>
                        <h4 style="margin: 0; color: #0284c7; display: flex; align-items: center; gap: 8px;">
                            <span>{safe_html(opt.icon)}</span> {safe_html(opt.title)}
                        </h4>
                        <span style="font-size: 13px; font-weight: 600; opacity: 0.85;">Mode: {safe_html(opt.mode)} &bull; ⏱️ Est. Duration: {safe_html(opt.duration)}</span>
                    </div>
                    <div style="text-align: right;">
                        <span class="badge-price">{safe_html(opt.estimated_cost_inr)}</span>
                    </div>
                </div>
                <p style="margin: 10px 0 12px 0; color: inherit; opacity: 0.92;">{safe_html(opt.details)}</p>
                <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                    <a href="{safe_url(opt.booking_url)}" target="_blank" rel="noopener noreferrer" class="btn-action btn-book">
                        🎟️ Check Fares & Book Tickets
                    </a>
                    <a href="{safe_url(opt.source_url)}" target="_blank" rel="noopener noreferrer" class="btn-action btn-source">
                        🔗 Official Transit Portal
                    </a>
                </div>
            </div>
            """)

    # Interactive RedBus Search & Verification Section
    st.markdown("---")
    st.subheader("🚌 RedBus Intercity Bus Search & Live Verification")
    st.caption("Search live bus routes, sleeper coaches, and seat availability directly on RedBus. Verify real-time schedules, boarding points, and fares.")

    col_rb1, col_rb2, col_rb3 = st.columns(3)
    with col_rb1:
        rb_origin_val = req.starting_city if req.starting_city else "Bengaluru"
        rb_origin = st.text_input("Origin City", value=rb_origin_val, key="redbus_search_origin")
    with col_rb2:
        rb_dest = st.text_input("Destination City", value=res.destination, key="redbus_search_dest")
    with col_rb3:
        try:
            default_d = datetime.strptime(req.departure_date, "%Y-%m-%d").date()
        except Exception:
            default_d = date.today() + timedelta(days=14)
        rb_date = st.date_input("Journey Date", value=default_d, min_value=date.today(), key="redbus_search_date")

    clean_origin = rb_origin.strip()
    clean_dest = rb_dest.strip()
    clean_origin_slug = re.sub(r'[^a-zA-Z0-9]+', '-', clean_origin.lower()).strip('-')
    clean_dest_slug = re.sub(r'[^a-zA-Z0-9]+', '-', clean_dest.lower()).strip('-')
    date_param = rb_date.strftime("%Y-%m-%d") if hasattr(rb_date, "strftime") else str(rb_date)

    is_overseas, route_cat = check_route_feasibility(clean_origin, clean_dest)

    if route_cat in ("international", "island") or is_overseas:
        st.info(
            f"ℹ️ **Overland Transit Unavailable:** RedBus operates intercity bus networks in India and select Southeast Asian countries. "
            f"Overland bus travel between **{clean_origin}** and **{clean_dest}** is physically infeasible across borders or oceans. "
            f"Please use flight transit above or visit the official RedBus portal for domestic connecting legs."
        )
        render_html("""
        <div style="margin-top: 10px;">
            <a href="https://www.redbus.in/" target="_blank" rel="noopener noreferrer" class="btn-action btn-source" style="padding: 10px 18px; font-size: 14px;">
                🌐 Open Official RedBus Website
            </a>
        </div>
        """)
    else:
        # Build clean, verified RedBus dynamic route URL avoiding any undefined parameters
        if clean_origin_slug and clean_dest_slug and clean_origin_slug not in ("your-city", "origin", "undefined"):
            redbus_route_url = f"https://www.redbus.in/bus-tickets/{clean_origin_slug}-to-{clean_dest_slug}"
        else:
            redbus_route_url = "https://www.redbus.in/"

        google_bus_url = f"https://www.google.com/search?q=redbus+bus+from+{quote_plus(clean_origin)}+to+{quote_plus(clean_dest)}+{quote_plus(date_param)}"

        render_html(f"""
        <div class="travel-card" style="border-left: 4px solid #ef4444; background: rgba(239, 68, 68, 0.05); padding: 18px 22px; border-radius: 10px; margin-top: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div>
                    <h4 style="margin: 0; color: #b91c1c; font-size: 17px; display: flex; align-items: center; gap: 8px;">
                        <span>🚌</span> RedBus Route Search: {safe_html(clean_origin)} ➔ {safe_html(clean_dest)}
                    </h4>
                    <div style="font-size: 13px; font-weight: 600; opacity: 0.9; margin-top: 4px;">
                        📅 Selected Journey Date: {safe_html(date_param)} &bull; Route: {safe_html(clean_origin)} to {safe_html(clean_dest)}
                    </div>
                </div>
                <span class="badge-price" style="background: #b91c1c; border-color: #ef4444; color: white;">Check Live Fares</span>
            </div>
            <p style="margin: 10px 0 12px 0; font-size: 13px; opacity: 0.92; line-height: 1.5;">
                Open RedBus to search scheduled private AC sleepers (Volvo, Scania, BharatBenz) and state transport buses (KSRTC, Kadamba, MSRTC) for this route on your selected date.
            </p>
            <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                <a href="{safe_url(redbus_route_url)}" target="_blank" rel="noopener noreferrer" class="btn-action btn-book" style="background: #b91c1c; border-color: #991b1b; padding: 9px 18px; font-size: 13px;">
                    🎟️ Search Buses on RedBus ({safe_html(clean_origin)} → {safe_html(clean_dest)})
                </a>
                <a href="https://www.redbus.in/" target="_blank" rel="noopener noreferrer" class="btn-action btn-source" style="padding: 9px 18px; font-size: 13px;">
                    🌐 RedBus Official Portal
                </a>
                <a href="{safe_url(google_bus_url)}" target="_blank" rel="noopener noreferrer" class="btn-action btn-maps" style="padding: 9px 18px; font-size: 13px;">
                    🔍 Alternative Bus Search
                </a>
            </div>
            <div style="margin-top: 12px; font-size: 12px; opacity: 0.75; font-style: italic;">
                ℹ️ <strong>Live Availability & Fares:</strong> TripPilot AI connects you directly to live ticketing. Seat layout, live availability, boarding points, and actual fares must be verified on RedBus. We never fabricate bus fares or availability.
            </div>
        </div>
        """)

# 2. Tourist Places to Visit Tab (Dedicated Categorized Section)
with tab_places:
    st.subheader(f"📍 Top Tourist Places to Visit in {res.destination}")
    st.caption(f"Curated, destination-specific tourist sights in {res.destination} organized into clear categories (beaches, heritage, nature, culture, and viewpoints).")

    if not categorized_places:
        st.info(f"No specific tourist places categorized for {res.destination}. Check the Attractions tab for extracted points of interest.")
    else:
        seen_place_images = set()
        for cat_title, places in categorized_places.items():
            st.markdown(f"### {cat_title}")
            for p in places:
                p_name = safe_html(p.get("name", "Tourist Place"))
                p_cat = safe_html(p.get("category", "Landmark"))
                p_desc = safe_html(p.get("description", ""))
                p_loc = safe_html(p.get("location", res.destination))
                p_timings = safe_html(p.get("timings", "Check local schedule"))
                p_highlights = safe_html(p.get("highlights", ""))
                p_maps_url = safe_url(p.get("maps_url", ""))
                
                # Ensure no repeating photographs across cards
                raw_img = p.get("image_url", "")
                if raw_img and raw_img in seen_place_images:
                    raw_img = ""
                if raw_img:
                    seen_place_images.add(raw_img)

                img_block = render_card_image(raw_img, p_name, width_px=170, height_px=130, category=p_cat)

                render_html(f"""
                <div class="travel-card">
                    <div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
                        {img_block}
                        <div style="flex: 1; min-width: 260px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
                                <h4 style="margin: 0; color: #0d9488;">{p_name}</h4>
                                <div>
                                    <span class="badge-verified">DESTINATION SIGHT</span>
                                    <span class="badge-price">{p_cat}</span>
                                </div>
                            </div>
                            <p style="margin: 8px 0 6px 0; color: inherit; opacity: 0.92; line-height: 1.45;">{p_desc}</p>
                            <div style="font-size: 13px; color: inherit; opacity: 0.88; line-height: 1.6;">
                                <strong>📍 Location:</strong> {p_loc} &nbsp;|&nbsp;
                                <strong>⏰ Timings:</strong> {p_timings}
                            </div>
                            {f'<div style="font-size: 12px; opacity: 0.82; margin-top: 4px;"><strong>✨ Highlights:</strong> {p_highlights}</div>' if p_highlights else ''}
                            <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                                <a href="{p_maps_url}" target="_blank" rel="noopener noreferrer" class="btn-action btn-maps">
                                    📍 View on Google Maps
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
                """)

# 3. Attractions & Activities Tab
with tab_attractions:
    st.subheader(f"Attractions & Activities in {res.destination}")
    st.caption("Explore verified landmarks, museums, beaches, and local sights. Suggestions are labelled honestly; verify current timings and fees before visiting.")
    
    if not res.attractions:
        st.info("No attractions were found in the current page snapshot.")
    else:
        seen_attr_images = set()
        for idx, attr in enumerate(res.attractions):
            attr_name = safe_html(attr.name)
            attr_description = safe_html(attr.description)
            attr_location = safe_html(attr.location)
            attr_hours = safe_html(attr.opening_hours)
            attr_category = safe_html(attr.category)
            attr_price = safe_html(attr.price_display)
            attr_maps_url = safe_url(attr.maps_url)
            attr_source_url = safe_url(attr.source_url)

            # Prevent duplicate photos across cards
            raw_img = getattr(attr, "image_url", "")
            if raw_img and raw_img in seen_attr_images:
                raw_img = ""
            if raw_img:
                seen_attr_images.add(raw_img)

            img_block = render_card_image(
                raw_img,
                attr.name,
                width_px=170,
                height_px=120,
                category=attr.category,
                attribution_text=getattr(attr, "attribution_text", ""),
                attribution_url=getattr(attr, "attribution_url", "")
            )

            status_badge = '<span class="badge-verified">✓ SOURCE LINKED</span>' if attr.verified else '<span class="badge-unverified">SUGGESTION — CHECK DETAILS</span>'

            render_html(f"""
            <div class="travel-card">
                <div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
                    {img_block}
                    <div style="flex: 1; min-width: 260px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
                            <h4 style="margin: 0; color: #0d9488;">{attr_name}</h4>
                            <div>
                                {status_badge}
                                <span class="badge-price">{attr_price}</span>
                            </div>
                        </div>
                        <p style="margin: 8px 0 6px 0; color: inherit; opacity: 0.92;">{attr_description}</p>
                        <div style="font-size: 13px; color: inherit; opacity: 0.85;">
                            <strong>📍 Location:</strong> {attr_location} &nbsp;|&nbsp; 
                            <strong>⏰ Timings:</strong> {attr_hours} &nbsp;|&nbsp;
                            <strong>🏷️ Category:</strong> {attr_category}
                        </div>
                        <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                            <a href="{attr_maps_url}" target="_blank" rel="noopener noreferrer" class="btn-action btn-maps">
                                📍 View on Google Maps
                            </a>
                            {f'<a href="{attr_source_url}" target="_blank" rel="noopener noreferrer" class="btn-action btn-source">🔗 Source Details</a>' if attr_source_url.startswith(("https://", "http://")) else ''}
                        </div>
                    </div>
                </div>
            </div>
            """)

# 4. Accommodation Research Tab
with tab_stays:
    st.subheader(f"Accommodation Options in {res.destination}")
    st.caption("Card listings link directly to live booking searches (Booking.com / Goibibo / MakeMyTrip) and Google Maps pins.")

    if not res.accommodations:
        st.info("No accommodation listings were extracted from the current page snapshot.")
    else:
        seen_stay_images = set()
        for stay in res.accommodations:
            total_stay_est = stay.price_per_night_inr * req.num_nights * max(1, (req.travelers + 1) // 2)
            
            # Prevent photo repetition
            raw_img = getattr(stay, "image_url", "")
            if raw_img and raw_img in seen_stay_images:
                raw_img = ""
            if raw_img:
                seen_stay_images.add(raw_img)

            stay_img_block = render_card_image(
                raw_img,
                stay.property_name,
                width_px=170,
                height_px=130,
                category="hotel",
                attribution_text=getattr(stay, "attribution_text", ""),
                attribution_url=getattr(stay, "attribution_url", "")
            )

            p_name = safe_html(stay.property_name)
            p_type = safe_html(stay.property_type)
            p_loc = safe_html(stay.location)
            p_price = safe_html(stay.price_display)
            p_rating = safe_html(stay.rating)
            p_desc = safe_html(stay.description)
            p_book_url = safe_url(stay.booking_url)
            p_maps_url = safe_url(stay.maps_url)
            p_source_url = safe_url(stay.source_url)
            
            notice_html = '' if stay.verified else '<div style="font-size: 12px; color: #b45309; margin-top: 4px;">⚠️ AI suggestion — verify rates and availability</div>'

            render_html(f"""
            <div class="travel-card">
                <div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
                    {stay_img_block}
                    <div style="flex: 1; min-width: 260px;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 6px;">
                            <div>
                                <h4 style="margin: 0; color: #0d9488;">{p_name}</h4>
                                <span style="font-size: 12px; color: inherit; opacity: 0.85;">{p_type} &bull; 📍 {p_loc}</span>
                                {notice_html}
                            </div>
                            <div style="text-align: right;">
                                <span class="badge-price" style="font-size: 14px;">{p_price}</span>
                                <div style="font-size: 12px; color: #f59e0b; font-weight: bold; margin-top: 4px;">★ {p_rating}</div>
                            </div>
                        </div>
                        <p style="margin: 10px 0; color: inherit; opacity: 0.92;">{p_desc}</p>
                        <div style="background: rgba(128, 128, 128, 0.12); padding: 8px 12px; border-radius: 6px; font-size: 13px; border: 1px solid rgba(128, 128, 128, 0.22); margin-bottom: 10px;">
                            <strong>Estimated Total for Your Party:</strong> ₹{total_stay_est:,.0f} 
                            <span style="opacity: 0.8;">({req.num_nights} nights for {req.travelers} traveler(s))</span>
                        </div>
                        <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
                            <a href="{p_book_url}" target="_blank" rel="noopener noreferrer" class="btn-action btn-book">
                                🏨 Book / Check Availability
                            </a>
                            <a href="{p_maps_url}" target="_blank" rel="noopener noreferrer" class="btn-action btn-maps">
                                📍 View on Google Maps
                            </a>
                            {f'<a href="{p_source_url}" target="_blank" rel="noopener noreferrer" class="btn-action btn-source">🔗 Portal</a>' if p_source_url != "#" else ''}
                        </div>
                    </div>
                </div>
            </div>
            """)

# 5. Dining & Cuisine Tab
with tab_dining:
    st.subheader(f"Authentic Regional Food & Dining in {res.destination}")
    st.caption("Curated dishes and local culinary hotspots with direct Google Maps directions.")
    
    seen_food_images = set()
    for f in res.food_experiences:
        raw_img = getattr(f, "image_url", "")
        if raw_img and raw_img in seen_food_images:
            raw_img = ""
        if raw_img:
            seen_food_images.add(raw_img)

        food_img_block = render_card_image(
            raw_img,
            f.name,
            width_px=150,
            height_px=110,
            category="food",
            attribution_text=getattr(f, "attribution_text", ""),
            attribution_url=getattr(f, "attribution_url", "")
        )

        f_name = safe_html(f.name)
        f_price = safe_html(f.price_range_inr)
        f_cuisine = safe_html(f.cuisine_type)
        f_loc = safe_html(f.location)
        f_desc = safe_html(f.description)
        f_maps_url = safe_url(f.maps_url)
        f_source_url = safe_url(f.source_url)
        f_notice = '' if f.verified else '<div style="font-size: 12px; color: #b45309; margin-top: 4px;">⚠️ AI suggestion — confirm menu and hours</div>'

        render_html(f"""
        <div class="travel-card">
            <div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
                {food_img_block}
                <div style="flex: 1; min-width: 250px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                        <h4 style="margin: 0; color: #0d9488;">{f_name}</h4>
                        <span class="badge-price">{f_price}</span>
                    </div>
                    <div style="font-size: 13px; color: #f59e0b; font-weight: 500; margin-top: 2px;">{f_cuisine} &bull; 📍 {f_loc}</div>
                    {f_notice}
                    <p style="margin: 8px 0; color: inherit; opacity: 0.92;">{f_desc}</p>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px;">
                        <a href="{f_maps_url}" target="_blank" rel="noopener noreferrer" class="btn-action btn-maps">
                            📍 Directions on Google Maps
                        </a>
                        {f'<a href="{f_source_url}" target="_blank" rel="noopener noreferrer" class="btn-action btn-source">🔗 Food Guide</a>' if f_source_url != "#" else ''}
                    </div>
                </div>
            </div>
        </div>
        """)

# 6. Neighborhoods & Practical Tips Tab
with tab_tips:
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("🏘️ Recommended Neighborhoods")
        for n in res.neighborhoods:
            st.markdown(f"- {n}")
    with col_t2:
        st.subheader("🧳 Practical Travel Tips & Transit Advice")
        for tip in res.travel_tips:
            st.markdown(f"- {tip}")

# 7. Verified Sources & MCP Audit Tab
with tab_sources:
    st.subheader("🔍 Playwright MCP Browser Navigation Audit")
    st.write("TripPilot AI visited the following URLs through the official Playwright MCP server to extract this data:")
    for s in res.sources_accessed:
        st.markdown(f"""
        - **URL:** `{s.get('url')}`
        - **Title:** {s.get('title')}
        - **Status:** `{s.get('status')}`
        """)

    with st.expander("Inspect Raw MCP Execution Logs"):
        for log in res.execution_logs:
            st.code(log, language="text")
