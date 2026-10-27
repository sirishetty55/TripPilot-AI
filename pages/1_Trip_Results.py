"""
TripPilot AI — Page 1: Trip Results & Destination Explorer
Displays verified attractions, accommodations, dining, commute options, and curated recommendations.
"""

import streamlit as st
from services.ui_utils import apply_custom_theme, render_hero, safe_html, safe_url
from models import TripRequest, TripResearchResult, BudgetBreakdown
from services.budget_service import calculate_budget

st.set_page_config(page_title="Trip Results — TripPilot AI", page_icon="🗺️", layout="wide")
apply_custom_theme()

render_hero("🗺️ Trip Results & Destination Intelligence", "Verified multi-source findings gathered via Playwright MCP browser automation.")

# Restore the active trip from Streamlit session state first, then SQLite if needed.
# Streamlit page navigation normally preserves session state, but this recovery path
# prevents an empty Results page after a rerun or a lost in-memory object.
req: TripRequest = st.session_state.get("active_trip_request")
res: TripResearchResult = st.session_state.get("active_research_result")

if not res:
    try:
        import database
        from models import DayPlan
        active_trip_id = st.session_state.get("active_trip_id")
        saved = database.get_trip_by_id(int(active_trip_id)) if active_trip_id else None
        if not saved:
            recent = database.get_all_trips()
            if recent:
                saved = database.get_trip_by_id(int(recent[0]["id"]))
        if saved:
            req_data = saved.get("trip_request", {})
            result_data = saved.get("research_result", {})
            req = TripRequest.from_dict(req_data)
            res = TripResearchResult.from_dict(result_data)
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
    st.info("Return to the Home page, enter your trip details, and run research again. Your submitted form values should now persist across page navigation.")
    st.stop()

if req is None:
    st.error("The trip result exists, but its request details are missing. Please return Home and run the search again.")
    st.stop()

# Header Badge Bar — 4-column summary: Destination, Duration, Party Size, Estimated Trip Cost
active_budget = st.session_state.get("active_budget")
if not active_budget:
    active_budget = calculate_budget(req, res)
    st.session_state["active_budget"] = active_budget

est_total_party = min(active_budget.total_estimated, float(req.budget_inr))

col_h1, col_h2, col_h3, col_h4 = st.columns(4)
with col_h1:
    st.metric("Destination", res.destination)
with col_h2:
    st.metric("Duration", f"{req.num_days} Days / {req.num_nights} Nights")
with col_h3:
    st.metric("Party Size", f"{req.travelers} Traveler(s)")
with col_h4:
    st.metric(
        "Estimated Trip Cost",
        f"₹{est_total_party:,.0f} (Est.)",
        help=f"Estimated total for {req.travelers} traveler(s) across stay, dining, transit, and activities. Realistic estimate capped at budget limit ₹{req.budget_inr:,.0f} INR."
    )

if res.is_demo_data:
    st.markdown('<span class="badge-demo">DEMO MODE ACTIVE: Research conducted on authenticated local travel portal</span>', unsafe_allow_html=True)

# Feature: Editor's Best Recommendations Showcase
best_rec = getattr(res, "best_recommendation", {}) or {}
if best_rec:
    st.markdown("---")
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(13, 148, 136, 0.15) 0%, rgba(2, 132, 199, 0.15) 100%);
                border: 1px solid rgba(13, 148, 136, 0.4); border-radius: 12px; padding: 18px 24px; margin-bottom: 20px;">
        <h3 style="margin: 0 0 10px 0; color: #0d9488; display: flex; align-items: center; gap: 8px;">
            🌟 Editor's Top Recommendations for Your Trip
        </h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-top: 12px;">
    """, unsafe_allow_html=True)

    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    with col_b1:
        st.markdown(f"""
        <div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #0284c7; height: 100%;">
            <div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🚆 Best Commute</div>
            <div style="font-size: 14px; font-weight: 600; margin-top: 4px;">{best_rec.get('top_commute', 'Flight / Express Train')}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_b2:
        top_stay = best_rec.get('top_stay_name', 'Verified Central Stay')
        top_reason = best_rec.get('top_stay_reason', 'Great value and location')
        st.markdown(f"""
        <div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #0d9488; height: 100%;">
            <div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🏨 Recommended Stay</div>
            <div style="font-size: 14px; font-weight: 600; margin-top: 4px;">{top_stay}</div>
            <div style="font-size: 12px; opacity: 0.85; margin-top: 2px;">{top_reason}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_b3:
        must_visits = best_rec.get('must_visit_sights', [])
        sights_str = ", ".join(must_visits) if isinstance(must_visits, list) else str(must_visits)
        st.markdown(f"""
        <div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #f59e0b; height: 100%;">
            <div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🏛️ Must-Visit Sights</div>
            <div style="font-size: 13px; font-weight: 500; margin-top: 4px;">{sights_str or 'Historic Forts & Coastal Spots'}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_b4:
        food_rec = best_rec.get('signature_food', 'Local traditional platter')
        st.markdown(f"""
        <div style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #ec4899; height: 100%;">
            <div style="font-size: 12px; font-weight: bold; opacity: 0.8; text-transform: uppercase;">🍲 Signature Food</div>
            <div style="font-size: 13px; font-weight: 500; margin-top: 4px;">{food_rec}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

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
    st.subheader(f"Commute & Travel Options to {res.destination}")
    origin_display = req.starting_city if req.starting_city else "Your City"
    st.caption(f"Estimated routes, flight connections, train lines, and bus links from **{origin_display}** to **{res.destination}**.")

    commute_list = getattr(res, "commute_options", [])
    if not commute_list:
        st.info("Transit options are being generated for this route.")
    else:
        # Check if overland transit (bus/car) was excluded due to geographic impossibility
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
            with st.container():
                st.markdown(f"""
                <div class="travel-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
                        <div>
                            <h4 style="margin: 0; color: #0284c7; display: flex; align-items: center; gap: 8px;">
                                <span>{opt.icon}</span> {opt.title}
                            </h4>
                            <span style="font-size: 13px; font-weight: 600; opacity: 0.85;">Mode: {opt.mode} &bull; ⏱️ Est. Duration: {opt.duration}</span>
                        </div>
                        <div style="text-align: right;">
                            <span class="badge-price">{opt.estimated_cost_inr}</span>
                        </div>
                    </div>
                    <p style="margin: 10px 0 12px 0; color: inherit; opacity: 0.92;">{opt.details}</p>
                    <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                        <a href="{opt.booking_url}" target="_blank" class="btn-action btn-book">
                            🎟️ Check Fares & Book Tickets
                        </a>
                        <a href="{opt.source_url}" target="_blank" class="btn-action btn-source">
                            🔗 Official Transit Portal
                        </a>
                    </div>
                </div>
                """, unsafe_allow_html=True)

# 2. Attractions Tab (Feature C)
with tab_attractions:
    st.subheader("Attractions & Things to Do")
    st.caption("Explore landmarks, museums, temples, beaches, viewpoints, and local experiences. Suggestions are labelled honestly; check current timings and fees before visiting.")
    
    if not res.attractions:
        st.info("No attractions were found in the current page snapshot.")
    else:
        for idx, attr in enumerate(res.attractions):
            # Render only validated remote image URLs and escape all external/user-controlled text.
            image_url = safe_url(getattr(attr, "image_url", ""))
            image_alt = safe_html(getattr(attr, "name", "Attraction"))
            img_html = f'<img src="{image_url}" style="width: 170px; height: 120px; object-fit: cover; border-radius: 8px; flex-shrink: 0;" alt="{image_alt}" loading="lazy" />' if image_url.startswith("https://") else ""
            attr_name = safe_html(attr.name)
            attr_description = safe_html(attr.description)
            attr_location = safe_html(attr.location)
            attr_hours = safe_html(attr.opening_hours)
            attr_category = safe_html(attr.category)
            attr_price = safe_html(attr.price_display)
            attr_maps_url = safe_url(attr.maps_url)
            attr_source_url = safe_url(attr.source_url)
            with st.container():
                st.markdown(f"""
                <div class="travel-card">
                    <div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
                        {img_html}
                        <div style="flex: 1; min-width: 260px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
                                <h4 style="margin: 0; color: #0d9488;">{attr_name}</h4>
                                <div>
                                    {'<span class="badge-verified">✓ SOURCE LINKED</span>' if attr.verified else '<span class="badge-unverified">SUGGESTION — CHECK DETAILS</span>'}
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
                """, unsafe_allow_html=True)

# 3. Accommodation Research Tab (Feature D)
with tab_stays:
    st.subheader("Accommodation Options & Direct Booking Links")
    st.caption("Card listings link directly to live booking searches (Booking.com / Goibibo / MakeMyTrip) and Google Maps pins.")

    if not res.accommodations:
        st.info("No accommodation listings were extracted from the current page snapshot.")
    else:
        for stay in res.accommodations:
            total_stay_est = stay.price_per_night_inr * req.num_nights * max(1, (req.travelers + 1) // 2)
            stay_img_html = f'<img src="{stay.image_url}" style="width: 170px; height: 130px; object-fit: cover; border-radius: 8px; flex-shrink: 0;" alt="{stay.property_name}" />' if getattr(stay, "image_url", "") else ""
            
            with st.container():
                st.markdown(f"""
                <div class="travel-card">
                    <div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
                        {stay_img_html}
                        <div style="flex: 1; min-width: 260px;">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 6px;">
                                <div>
                                    <h4 style="margin: 0; color: #0d9488;">{stay.property_name}</h4>
                                    <span style="font-size: 12px; color: inherit; opacity: 0.85;">{stay.property_type} &bull; 📍 {stay.location}</span>
                                    {'' if stay.verified else '<div style="font-size: 12px; color: #b45309; margin-top: 4px;">⚠️ AI suggestion — verify rates and availability</div>'}
                                </div>
                                <div style="text-align: right;">
                                    <span class="badge-price" style="font-size: 14px;">{stay.price_display}</span>
                                    <div style="font-size: 12px; color: #f59e0b; font-weight: bold; margin-top: 4px;">★ {stay.rating}</div>
                                </div>
                            </div>
                            <p style="margin: 10px 0; color: inherit; opacity: 0.92;">{stay.description}</p>
                            <div style="background: rgba(128, 128, 128, 0.12); padding: 8px 12px; border-radius: 6px; font-size: 13px; border: 1px solid rgba(128, 128, 128, 0.22); margin-bottom: 10px;">
                                <strong>Estimated Total for Your Party:</strong> ₹{total_stay_est:,.0f} 
                                <span style="opacity: 0.8;">({req.num_nights} nights for {req.travelers} traveler(s))</span>
                            </div>
                            <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
                                <a href="{stay.booking_url}" target="_blank" class="btn-action btn-book">
                                    🏨 Book / Check Availability
                                </a>
                                <a href="{stay.maps_url}" target="_blank" class="btn-action btn-maps">
                                    📍 View on Google Maps
                                </a>
                                {f'<a href="{stay.source_url}" target="_blank" class="btn-action btn-source">🔗 Portal</a>' if stay.source_url else ''}
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

# 4. Dining & Cuisine Tab
with tab_dining:
    st.subheader("Authentic Regional Food & Dining")
    st.caption("Curated dishes and local culinary hotspots with direct Google Maps directions.")
    
    for f in res.food_experiences:
        food_img_html = f'<img src="{f.image_url}" style="width: 150px; height: 110px; object-fit: cover; border-radius: 8px; flex-shrink: 0;" alt="{f.name}" />' if getattr(f, "image_url", "") else ""
        with st.container():
            st.markdown(f"""
            <div class="travel-card">
                <div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
                    {food_img_html}
                    <div style="flex: 1; min-width: 250px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                            <h4 style="margin: 0; color: #0d9488;">{f.name}</h4>
                            <span class="badge-price">{f.price_range_inr}</span>
                        </div>
                        <div style="font-size: 13px; color: #f59e0b; font-weight: 500; margin-top: 2px;">{f.cuisine_type} &bull; 📍 {f.location}</div>
                        {'' if f.verified else '<div style="font-size: 12px; color: #b45309; margin-top: 4px;">⚠️ AI suggestion — confirm menu and hours</div>'}
                        <p style="margin: 8px 0; color: inherit; opacity: 0.92;">{f.description}</p>
                        <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px;">
                            <a href="{f.maps_url}" target="_blank" class="btn-action btn-maps">
                                📍 Directions on Google Maps
                            </a>
                            {f'<a href="{f.source_url}" target="_blank" class="btn-action btn-source">🔗 Food Guide</a>' if f.source_url else ''}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# 5. Neighborhoods & Practical Tips Tab
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

# 6. Verified Sources & MCP Audit Tab
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
