"""
UI Utilities and Styling for TripPilot AI.
Injects cohesive, modern travel-themed CSS and reusable badges across Streamlit pages.
Fully compatible with both Streamlit Dark Mode and Light Mode.
"""

import html
from urllib.parse import urlparse
import streamlit as st

def safe_html(text) -> str:
    """Escapes user and dynamic text safely for HTML rendering to prevent XSS / script injection."""
    if text is None:
        return ""
    return html.escape(str(text), quote=True)

def safe_url(url) -> str:
    """Validates and returns safe HTTP/HTTPS URL, disarming javascript:, data:, and invalid schemes."""
    if not url:
        return "#"
    url_str = str(url).strip()
    try:
        parsed = urlparse(url_str)
        if parsed.scheme.lower() in ("http", "https"):
            return html.escape(url_str, quote=True)
    except Exception:
        pass
    return "#"

def render_card_image(image_url: str, alt_text: str = "", width_px: int = 170, height_px: int = 120, attribution_text: str = "", attribution_url: str = "") -> str:
    """Renders a safe, responsive image block with alt text and attribution link."""
    clean_url = safe_url(image_url)
    if clean_url == "#" or not image_url:
        return ""
    
    escaped_alt = safe_html(alt_text)
    escaped_attr_text = safe_html(attribution_text)
    clean_attr_url = safe_url(attribution_url)
    
    attr_html = ""
    if escaped_attr_text:
        if clean_attr_url != "#":
            attr_html = f'<div style="font-size: 10px; opacity: 0.7; margin-top: 3px; max-width: {width_px}px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><a href="{clean_attr_url}" target="_blank" style="color: inherit; text-decoration: underline;">{escaped_attr_text}</a></div>'
        else:
            attr_html = f'<div style="font-size: 10px; opacity: 0.7; margin-top: 3px; max-width: {width_px}px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{escaped_attr_text}</div>'

    return f"""
    <div style="flex-shrink: 0; width: {width_px}px;">
        <img src="{clean_url}" alt="{escaped_alt}" loading="lazy" style="width: {width_px}px; height: {height_px}px; object-fit: cover; border-radius: 8px;" />
        {attr_html}
    </div>
    """

def apply_custom_theme():
    """Applies modern travel-inspired CSS styling with full dark/light mode compatibility."""
    st.markdown("""
        <style>
        /* Main background and font styling */
        .main {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        
        /* Metric Cards - Adaptive translucent card for dark & light mode */
        div[data-testid="stMetric"] {
            background-color: rgba(128, 128, 128, 0.12) !important;
            border: 1px solid rgba(128, 128, 128, 0.28) !important;
            padding: 16px 20px !important;
            border-radius: 12px !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05) !important;
        }
        div[data-testid="stMetricLabel"] {
            color: inherit !important;
            font-size: 14px !important;
            font-weight: 600 !important;
            opacity: 0.9 !important;
        }
        div[data-testid="stMetricValue"] {
            color: inherit !important;
            font-size: 26px !important;
            font-weight: 700 !important;
        }
        div[data-testid="stMetricDelta"] {
            font-weight: 600 !important;
        }

        /* Pill Badges */
        .badge-verified {
            background-color: #065f46;
            color: #ecfdf5;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 12px;
            border: 1px solid #10b981;
            display: inline-block;
            margin-right: 6px;
        }

        .badge-unverified {
            background-color: #854d0e;
            color: #fef9c3;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 12px;
            border: 1px solid #facc15;
            display: inline-block;
            margin-right: 6px;
        }

        .badge-price {
            background-color: #1e3a8a;
            color: #dbeafe;
            font-size: 12px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 8px;
            border: 1px solid #3b82f6;
            display: inline-block;
        }

        .badge-demo {
            background-color: #831843;
            color: #fce7f3;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 12px;
            border: 1px solid #ec4899;
            display: inline-block;
        }

        /* Custom Card Container - Dark & Light Mode Adaptive */
        .travel-card {
            background-color: rgba(128, 128, 128, 0.08) !important;
            border: 1px solid rgba(128, 128, 128, 0.25) !important;
            border-radius: 12px;
            padding: 18px 22px;
            margin-bottom: 16px;
            color: inherit !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .travel-card:hover {
            box-shadow: 0 4px 14px rgba(13, 148, 136, 0.2);
            border-color: #0d9488 !important;
        }
        .travel-card h3, .travel-card h4 {
            color: #0d9488 !important;
            margin-top: 0;
        }
        .travel-card p {
            color: inherit !important;
            opacity: 0.92;
        }

        /* Action Buttons & Links */
        .btn-action {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            text-decoration: none !important;
            transition: all 0.2s ease;
            margin-right: 8px;
            margin-top: 8px;
        }
        .btn-book {
            background-color: #0284c7;
            color: #ffffff !important;
            border: 1px solid #0369a1;
        }
        .btn-book:hover {
            background-color: #0369a1;
            transform: translateY(-1px);
        }
        .btn-maps {
            background-color: #059669;
            color: #ffffff !important;
            border: 1px solid #047857;
        }
        .btn-maps:hover {
            background-color: #047857;
            transform: translateY(-1px);
        }
        .btn-source {
            background-color: rgba(128, 128, 128, 0.18);
            color: inherit !important;
            border: 1px solid rgba(128, 128, 128, 0.35);
        }
        .btn-source:hover {
            background-color: rgba(128, 128, 128, 0.3);
        }

        /* Hero Banner */
        .hero-banner {
            background: linear-gradient(135deg, #0d9488 0%, #0284c7 100%);
            color: white !important;
            padding: 24px 28px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(13, 148, 136, 0.25);
        }
        .hero-banner h1 {
            color: white !important;
            margin: 0 0 8px 0;
            font-size: 28px;
        }
        .hero-banner p {
            color: #f0fdfa !important;
            margin: 0;
            font-size: 15px;
            opacity: 0.95;
        }
        </style>
    """, unsafe_allow_html=True)

def render_hero(title: str, subtitle: str):
    """Renders a styled hero banner safely."""
    st.markdown(f"""
        <div class="hero-banner">
            <h1>{safe_html(title)}</h1>
            <p>{safe_html(subtitle)}</p>
        </div>
    """, unsafe_allow_html=True)
