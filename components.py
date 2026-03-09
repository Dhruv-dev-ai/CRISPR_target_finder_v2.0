"""
components.py — Reusable UI Components
=======================================
Landing cards, modals, badges, KPI strips, alert banners.
All functions emit HTML/CSS via st.markdown(unsafe_allow_html=True).
"""

import streamlit as st


# ─────────────────────────────────────────────────────────────
# Score badge
# ─────────────────────────────────────────────────────────────

def score_badge(score: float) -> str:
    """Return an HTML badge colored by Doench score tier."""
    if score >= 65:
        return f'<span class="badge-high">▲ {score:.1f}</span>'
    elif score >= 45:
        return f'<span class="badge-mid">◈ {score:.1f}</span>'
    else:
        return f'<span class="badge-low">▽ {score:.1f}</span>'


# ─────────────────────────────────────────────────────────────
# Alert banners
# ─────────────────────────────────────────────────────────────

def info_banner(title: str, body: str, icon: str = "ℹ️"):
    st.markdown(f"""
<div style="background:rgba(14,165,233,0.1);border:1px solid rgba(14,165,233,0.3);
            border-radius:12px;padding:1.2rem 1.5rem;margin:1rem 0;
            border-left:4px solid #0ea5e9;">
    <p style="font-weight:700;color:#0ea5e9;margin:0 0 4px">{icon} {title}</p>
    <p style="color:#8fb3a0;font-size:0.875rem;margin:0">{body}</p>
</div>
""", unsafe_allow_html=True)


def success_banner(title: str, body: str):
    st.markdown(f"""
<div style="background:rgba(0,200,150,0.08);border:1px solid rgba(0,200,150,0.3);
            border-radius:12px;padding:1.2rem 1.5rem;margin:1rem 0;
            border-left:4px solid #00c896;">
    <p style="font-weight:700;color:#00c896;margin:0 0 4px">✅ {title}</p>
    <p style="color:#8fb3a0;font-size:0.875rem;margin:0">{body}</p>
</div>
""", unsafe_allow_html=True)


def warning_banner(title: str, body: str):
    st.markdown(f"""
<div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);
            border-radius:12px;padding:1.2rem 1.5rem;margin:1rem 0;
            border-left:4px solid #f59e0b;">
    <p style="font-weight:700;color:#f59e0b;margin:0 0 4px">⚠️ {title}</p>
    <p style="color:#8fb3a0;font-size:0.875rem;margin:0">{body}</p>
</div>
""", unsafe_allow_html=True)


def error_banner(title: str, body: str):
    st.markdown(f"""
<div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.3);
            border-radius:12px;padding:1.2rem 1.5rem;margin:1rem 0;
            border-left:4px solid #f43f5e;">
    <p style="font-weight:700;color:#f43f5e;margin:0 0 4px">❌ {title}</p>
    <p style="color:#8fb3a0;font-size:0.875rem;margin:0">{body}</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Feature card (landing)
# ─────────────────────────────────────────────────────────────

def feature_card(icon: str, name: str, desc: str, badge: str = ""):
    badge_html = f'<div class="feature-badge">{badge}</div>' if badge else ""
    st.markdown(f"""
<div class="feature-card">
    <div class="feature-icon">{icon}</div>
    <div class="feature-name">{name}</div>
    <div class="feature-desc">{desc}</div>
    {badge_html}
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# KPI card
# ─────────────────────────────────────────────────────────────

def kpi_card(icon: str, value: str, label: str, delta: str = ""):
    delta_html = f'<span class="kpi-delta">{delta}</span>' if delta else ""
    st.markdown(f"""
<div class="kpi-card">
    {delta_html}
    <span class="kpi-icon">{icon}</span>
    <div class="kpi-val">{value}</div>
    <div class="kpi-label">{label}</div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Section header
# ─────────────────────────────────────────────────────────────

def section_header(label: str, title: str):
    st.markdown(f"""
<div style="margin:2rem 0 1.5rem">
    <div style="font-size:0.7rem;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;
                color:#00c896;margin-bottom:0.5rem">{label}</div>
    <h2 style="font-family:'Syne',sans-serif;font-size:clamp(1.6rem,3vw,2.4rem);font-weight:700;
               color:#e8f4f0;letter-spacing:-0.02em;margin:0">{title}</h2>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Empty state
# ─────────────────────────────────────────────────────────────

def empty_state(icon: str, title: str, subtitle: str):
    st.markdown(f"""
<div style="background:#0f1f35;border:1px solid rgba(0,200,150,0.12);border-radius:16px;
            padding:3rem 2rem;text-align:center;margin:1.5rem 0;">
    <div style="font-size:2.8rem;margin-bottom:1rem">{icon}</div>
    <p style="color:#8fb3a0;font-weight:600;font-size:1rem;margin:0">{title}</p>
    <p style="color:#4d7a65;font-size:0.85rem;margin-top:0.5rem">{subtitle}</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Loading skeleton
# ─────────────────────────────────────────────────────────────

def loading_skeleton(lines: int = 4):
    rows = "".join(
        f'<div class="skel" style="width:{80 - (i*8)%30}%;margin-bottom:10px;height:{14 if i%3 else 20}px"></div>'
        for i in range(lines)
    )
    st.markdown(f'<div style="padding:1rem">{rows}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Guest mode notice
# ─────────────────────────────────────────────────────────────

def guest_notice():
    st.markdown("""
<div style="background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.25);
            border-radius:10px;padding:0.8rem 1.2rem;margin-bottom:1rem;
            display:flex;align-items:center;gap:10px;">
    <span style="font-size:1.1rem">👤</span>
    <span style="color:#f59e0b;font-size:0.82rem;font-weight:500">
        Guest mode — analysis results won't be saved.
        <a href="#" style="color:#00c896;font-weight:700;margin-left:4px">Sign in →</a>
    </span>
</div>
""", unsafe_allow_html=True)
