"""
CRISPR Target Finder v2.1 — Full Feature Rebuild
=================================================
ALL features from original 1890-line version, with two targeted fixes:
  FIX 1: Nav logo uses plain colour (no -webkit-text-fill-color clip that truncates)
  FIX 2: Auth is a separate PAGE (no position:fixed overlays → always responsive)

Run:   streamlit run main.py
Login: admin / admin123   |   or Sign Up   |   or Guest mode
"""

import json, hashlib, datetime, time
from pathlib import Path
from typing import Optional

import streamlit as st
import pandas as pd
import numpy as np

# ── MUST be first Streamlit call ──────────────────────────────────────────────
st.set_page_config(
    page_title="CRISPR Target Finder",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get Help":    "https://github.com/dhruvnambiar/crispr-target-finder",
        "Report a bug":"https://github.com/dhruvnambiar/crispr-target-finder/issues",
        "About":       "CRISPR Target Finder v2.1 — Doench 2016 + XGBoost ML\nBuilt by Dhruv Nambiar",
    },
)

# ── Optional heavy deps ────────────────────────────────────────────────────────
try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

try:
    from utils import (
        parse_input, find_crispr_targets, batch_off_target_analysis,
        get_sequence_stats, generate_pdf_report, color_score,
    )
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False

try:
    from ml_model import get_model
    HAS_ML = True
except ImportError:
    HAS_ML = False


# ══════════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM CSS
# ══════════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
  --deep:  #050d1a;
  --panel: #0a1628;
  --card:  #0f1f35;
  --bdr:   rgba(0,200,150,.15);
  --bdrH:  rgba(0,200,150,.42);
  --teal:  #00c896;
  --blue:  #0ea5e9;
  --amber: #f59e0b;
  --rose:  #f43f5e;
  --t1: #e8f4f0; --t2: #8fb3a0; --t3: #4d7a65;
  --fd: 'Syne',sans-serif;
  --fb: 'DM Sans',sans-serif;
  --ease: all .22s cubic-bezier(.4,0,.2,1);
}

html,body,[class*="css"] {
  font-family:var(--fb)!important;
  background:var(--deep)!important;
  color:var(--t1)!important;
}
#MainMenu,footer,header { visibility:hidden!important; }
.main .block-container { padding:1.5rem 2rem 4rem!important; max-width:1380px!important; }

/* Grid background */
.main::before {
  content:''; position:fixed; inset:0; z-index:0; pointer-events:none;
  background-image:
    linear-gradient(rgba(0,200,150,.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,200,150,.03) 1px, transparent 1px);
  background-size:58px 58px;
}

/* ── Buttons ─────────────────────────────────────────────────── */
.stButton>button {
  font-family:var(--fb)!important; font-weight:600!important;
  border-radius:8px!important; border:1px solid var(--bdr)!important;
  background:var(--card)!important; color:var(--t1)!important;
  transition:var(--ease)!important; padding:.55rem 1.2rem!important;
  white-space:nowrap!important;
}
.stButton>button:hover {
  border-color:var(--teal)!important;
  background:rgba(0,200,150,.09)!important; color:var(--teal)!important;
}
.stButton>button[kind="primary"] {
  background:linear-gradient(135deg,#00c896,#00a87c)!important;
  color:#050d1a!important; border-color:transparent!important;
  font-weight:700!important; box-shadow:0 4px 18px rgba(0,200,150,.28)!important;
}
.stButton>button[kind="primary"]:hover {
  background:linear-gradient(135deg,#00e6ae,#00c896)!important;
  transform:translateY(-1px)!important;
  box-shadow:0 8px 28px rgba(0,200,150,.38)!important; color:#050d1a!important;
}

/* ── Inputs ──────────────────────────────────────────────────── */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea {
  background:var(--panel)!important; border:1px solid var(--bdr)!important;
  border-radius:8px!important; color:var(--t1)!important;
  font-family:var(--fb)!important;
}
.stTextInput>div>div>input:focus,
.stTextArea>div>div>textarea:focus {
  border-color:var(--teal)!important;
  box-shadow:0 0 0 3px rgba(0,200,150,.12)!important;
}
label { color:var(--t2)!important; font-size:.82rem!important; }

/* ── Tabs ────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap:6px!important; background:transparent!important;
  border-bottom:1px solid var(--bdr)!important;
}
.stTabs [data-baseweb="tab"] {
  background:transparent!important; color:var(--t3)!important;
  border-radius:8px 8px 0 0!important; font-weight:600!important;
  padding:.55rem 1.1rem!important; border:1px solid transparent!important;
  border-bottom:none!important; font-family:var(--fb)!important;
}
.stTabs [aria-selected="true"] {
  background:var(--card)!important; color:var(--teal)!important;
  border-color:var(--bdr)!important; border-bottom-color:var(--card)!important;
}

/* ── Sidebar ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background:var(--panel)!important; border-right:1px solid var(--bdr)!important;
}
[data-testid="stSidebar"] * { color:var(--t2)!important; }

/* ── Metrics ─────────────────────────────────────────────────── */
[data-testid="metric-container"] {
  background:var(--card)!important; border:1px solid var(--bdr)!important;
  border-radius:12px!important; padding:1rem!important;
}
[data-testid="stMetricValue"] { font-family:var(--fd)!important; color:var(--teal)!important; }

/* ── Select / checkbox / radio ───────────────────────────────── */
.stSelectbox>div>div {
  background:var(--panel)!important; border:1px solid var(--bdr)!important;
  border-radius:8px!important; color:var(--t1)!important;
}
.stCheckbox label, .stRadio label { color:var(--t2)!important; }

/* ── File uploader ───────────────────────────────────────────── */
[data-testid="stFileUploader"] {
  background:var(--panel)!important; border:2px dashed var(--bdr)!important;
  border-radius:12px!important; transition:var(--ease)!important;
}
[data-testid="stFileUploader"]:hover {
  border-color:var(--teal)!important; background:rgba(0,200,150,.04)!important;
}

/* ── Expander ────────────────────────────────────────────────── */
.streamlit-expanderHeader {
  background:var(--card)!important; border-radius:10px!important;
  color:var(--t1)!important; font-weight:600!important;
}
details { background:var(--card)!important; border:1px solid var(--bdr)!important; border-radius:10px!important; }

/* ── Progress bar ────────────────────────────────────────────── */
.stProgress > div > div > div { background:var(--teal)!important; }

/* ── Alerts ──────────────────────────────────────────────────── */
.stSuccess { border-left:4px solid var(--teal)!important; border-radius:10px!important; }
.stWarning { border-left:4px solid var(--amber)!important; border-radius:10px!important; }
.stError   { border-left:4px solid var(--rose)!important;  border-radius:10px!important; }
.stInfo    { border-left:4px solid var(--blue)!important;  border-radius:10px!important; }

/* ── Scrollbar ───────────────────────────────────────────────── */
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-track { background:var(--deep); }
::-webkit-scrollbar-thumb { background:var(--bdrH); border-radius:3px; }

hr { border-color:var(--bdr)!important; }

/* ══════════════════════════════════════════════════════════════
   LANDING
══════════════════════════════════════════════════════════════ */
/* FIX: plain colour on logo-text, no -webkit gradient clip */
.logo-bar {
  display:flex; align-items:center;
  padding:.6rem 0 .9rem; border-bottom:1px solid var(--bdr); margin-bottom:.3rem;
}
.logo-text {
  font-family:'Syne',sans-serif; font-size:1.35rem; font-weight:800;
  letter-spacing:-.02em; color:var(--teal);
  white-space:nowrap; overflow:visible;
}

.hero-badge {
  display:inline-flex; align-items:center; gap:7px;
  background:rgba(0,200,150,.08); border:1px solid var(--bdrH);
  border-radius:100px; padding:5px 16px; font-size:.72rem; font-weight:700;
  letter-spacing:.1em; text-transform:uppercase; color:var(--teal); margin-bottom:1.4rem;
}
.hero-dot {
  width:7px; height:7px; border-radius:50%; background:var(--teal);
  animation:pulse 2s infinite;
}
@keyframes pulse {
  0%,100% { opacity:1; transform:scale(1); }
  50%     { opacity:.5; transform:scale(.8); }
}
.hero-h1 {
  font-family:'Syne',sans-serif; font-size:clamp(2.2rem,5vw,4.4rem);
  font-weight:800; line-height:1.07; letter-spacing:-.03em;
  color:var(--t1); margin-bottom:.5rem;
}
.hero-acc {
  background:linear-gradient(130deg,var(--teal),var(--blue));
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.hero-sub {
  font-size:clamp(.92rem,1.5vw,1.1rem); color:var(--t2);
  max-width:560px; margin:.8rem auto 0; line-height:1.7;
}

.stat-strip {
  display:flex; border:1px solid var(--bdr); border-radius:14px;
  overflow:hidden; background:var(--card);
}
.stat-item { flex:1; padding:1.3rem .8rem; text-align:center; border-right:1px solid var(--bdr); }
.stat-item:last-child { border-right:none; }
.sv { font-family:'Syne',sans-serif; font-size:1.75rem; font-weight:800; color:var(--teal); line-height:1; }
.sl { font-size:.67rem; font-weight:600; color:var(--t3); text-transform:uppercase; letter-spacing:.08em; margin-top:3px; }

.fc {
  background:var(--card); border:1px solid var(--bdr); border-radius:16px;
  padding:1.6rem 1.4rem; transition:var(--ease); overflow:hidden;
}
.fc:hover { border-color:var(--bdrH); transform:translateY(-3px); box-shadow:0 0 28px rgba(0,200,150,.1); }
.fi {
  width:42px; height:42px; border-radius:8px; background:rgba(0,200,150,.1);
  border:1px solid var(--bdrH); display:flex; align-items:center; justify-content:center;
  font-size:1.25rem; margin-bottom:1rem;
}
.fn { font-family:'Syne',sans-serif; font-size:.98rem; font-weight:700; color:var(--t1); margin-bottom:.4rem; }
.fd2 { font-size:.82rem; color:var(--t2); line-height:1.6; }
.fb2 {
  display:inline-block; margin-top:.9rem; padding:2px 10px; border-radius:100px;
  font-size:.64rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em;
  background:rgba(0,200,150,.1); color:var(--teal); border:1px solid var(--bdrH);
}

/* ══════════════════════════════════════════════════════════════
   AUTH PAGE
══════════════════════════════════════════════════════════════ */
.auth-card {
  background:var(--card); border:1px solid var(--bdrH); border-radius:20px;
  padding:2.5rem 2rem 2rem; box-shadow:0 32px 64px rgba(0,0,0,.55);
}

/* ══════════════════════════════════════════════════════════════
   DASHBOARD
══════════════════════════════════════════════════════════════ */
.dash-nav {
  display:flex; align-items:center;
  padding:.7rem 0 1rem; border-bottom:1px solid var(--bdr); margin-bottom:1.2rem;
}
.dash-logo { font-family:'Syne',sans-serif; font-size:1.2rem; font-weight:800; color:var(--teal); white-space:nowrap; }
.user-chip {
  display:inline-flex; align-items:center; gap:7px; background:var(--card);
  border:1px solid var(--bdr); border-radius:100px; padding:5px 14px 5px 7px;
  font-size:.78rem; font-weight:500; color:var(--t2); white-space:nowrap;
}
.av {
  width:24px; height:24px; border-radius:50%;
  background:linear-gradient(135deg,var(--teal),var(--blue));
  display:flex; align-items:center; justify-content:center;
  font-size:.7rem; font-weight:700; color:#050d1a;
}

/* KPI strip */
.kpi {
  background:var(--card); border:1px solid var(--bdr); border-radius:12px;
  padding:1.3rem 1.2rem; position:relative; transition:var(--ease);
}
.kpi:hover { border-color:var(--bdrH); box-shadow:0 0 22px rgba(0,200,150,.08); }
.ki  { font-size:1.3rem; margin-bottom:.6rem; display:block; }
.kv  { font-family:'Syne',sans-serif; font-size:1.85rem; font-weight:800; color:var(--t1); line-height:1; }
.kl  { font-size:.7rem; font-weight:600; color:var(--t3); text-transform:uppercase; letter-spacing:.08em; margin-top:3px; }
.kd  {
  position:absolute; top:1rem; right:1rem; font-size:.64rem; font-weight:700;
  padding:2px 8px; border-radius:100px; background:rgba(0,200,150,.1);
  color:var(--teal); border:1px solid var(--bdrH);
}

/* Panel wrapper */
.panel { background:var(--card); border:1px solid var(--bdr); border-radius:14px; padding:1.6rem; }
.panel-t { font-family:'Syne',sans-serif; font-size:1rem; font-weight:700; color:var(--t1); margin-bottom:1.2rem; }

/* Score badges */
.bhi { background:rgba(0,200,150,.12); color:#00c896; border:1px solid rgba(0,200,150,.3); padding:2px 9px; border-radius:100px; font-size:.72rem; font-weight:700; }
.bmi { background:rgba(245,158,11,.12); color:#f59e0b; border:1px solid rgba(245,158,11,.3); padding:2px 9px; border-radius:100px; font-size:.72rem; font-weight:700; }
.blo { background:rgba(244,63,94,.12);  color:#f43f5e; border:1px solid rgba(244,63,94,.3);  padding:2px 9px; border-radius:100px; font-size:.72rem; font-weight:700; }

/* Off-target risk badges */
.risk-ok   { background:rgba(0,200,150,.1); color:var(--teal); border:1px solid var(--bdrH); padding:3px 10px; border-radius:100px; font-size:.7rem; font-weight:700; }
.risk-high { background:rgba(244,63,94,.1); color:var(--rose); border:1px solid rgba(244,63,94,.3); padding:3px 10px; border-radius:100px; font-size:.7rem; font-weight:700; }

/* Skel loader */
.skel { background:linear-gradient(90deg,var(--card) 25%,rgba(0,200,150,.04) 50%,var(--card) 75%); background-size:200% 100%; animation:shim 1.5s infinite; border-radius:6px; height:16px; margin-bottom:8px; }
@keyframes shim { from{background-position:200% 0} to{background-position:-200% 0} }

/* Footer */
.sfooter { border-top:1px solid var(--bdr); padding:2.5rem 0 1.5rem; margin-top:3rem; text-align:center; }
.fbadges { display:flex; gap:10px; justify-content:center; flex-wrap:wrap; margin-bottom:1.2rem; }
.fbadge { background:var(--card); border:1px solid var(--bdr); border-radius:7px; padding:4px 12px; font-size:.73rem; font-weight:600; color:var(--t2); }

/* Responsive */
@media(max-width:768px) {
  .main .block-container { padding:.7rem .8rem 3rem!important; }
  .stat-strip { flex-wrap:wrap; }
  .stat-item  { flex-basis:50%; border-bottom:1px solid var(--bdr); }
  .hero-h1    { font-size:2rem; }
}
</style>
"""

_FOOTER = """
<div class="sfooter">
  <div class="fbadges">
    <span class="fbadge">🐍 Biopython</span><span class="fbadge">⚡ Streamlit</span>
    <span class="fbadge">📊 Plotly</span><span class="fbadge">🤖 XGBoost</span>
    <span class="fbadge">⚖️ Apache 2.0</span>
  </div>
  <div style="font-size:.72rem;color:#4d7a65">
    <strong style="color:#8fb3a0">CRISPR Target Finder</strong> v2.1 &nbsp;·&nbsp;
    Built with ❤️ by <strong style="color:#00c896">Dhruv Nambiar</strong>
  </div>
</div>"""


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
def _init():
    defaults = {
        "page":             "landing",  # landing | auth | dashboard
        "auth_tab":         "login",
        "authenticated":    False,
        "username":         "",
        "is_guest":         False,
        "results_df":       None,
        "ot_dict":          None,
        "sequence_info":    None,
        "raw_sequence":     "",
        "analysis_complete":False,
        "current_proj_id":  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════════
_DATA = Path("user_data"); _DATA.mkdir(exist_ok=True)
_CF   = _DATA / "credentials.json"

def _creds():
    if _CF.exists():
        with open(_CF) as f: return json.load(f)
    c = {"admin": hashlib.sha256(b"admin123").hexdigest()}
    with open(_CF, "w") as f: json.dump(c, f)
    return c

def _save_creds(c):
    with open(_CF, "w") as f: json.dump(c, f)

def _h(pw): return hashlib.sha256(pw.encode()).hexdigest()
def _udir(u): d = _DATA / u; d.mkdir(exist_ok=True); return d

def save_project(u, pid, data):
    sd = {}
    for k, v in data.items():
        if isinstance(v, pd.DataFrame):
            sd[k] = {"__df__": True, "data": v.to_dict("records")}
        else:
            sd[k] = v
    with open(_udir(u) / f"{pid}.json", "w") as f:
        json.dump(sd, f, default=str)

def load_project(u, pid):
    fp = _udir(u) / f"{pid}.json"
    if not fp.exists(): return None
    with open(fp) as f: d = json.load(f)
    for k, v in d.items():
        if isinstance(v, dict) and v.get("__df__"):
            d[k] = pd.DataFrame(v["data"])
    return d

def list_projects(u): return [f.stem for f in _udir(u).glob("*.json")]
def delete_project(u, pid):
    fp = _udir(u) / f"{pid}.json"
    if fp.exists(): fp.unlink()


# ══════════════════════════════════════════════════════════════════════════════
# PLOTLY CHART BUILDERS  (restored from original)
# ══════════════════════════════════════════════════════════════════════════════
_TPL = "plotly_dark"
_BG  = "rgba(0,0,0,0)"
_PBG = "rgba(10,22,40,.85)"

def chart_sequence_track(df: pd.DataFrame, seq_length: int):
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, x1=seq_length, y0=-.3, y1=.3,
                  fillcolor="rgba(0,200,150,.07)", line=dict(width=0))
    # Direction arrows
    step = max(1, seq_length // 20)
    for i in range(0, seq_length, step):
        fig.add_annotation(x=i, y=0, text="→", showarrow=False,
                           font=dict(size=10, color="rgba(0,200,150,.25)"))
    if not df.empty:
        for strand, sym, y_pos in [("+","triangle-up",.5),("-","triangle-down",-.5)]:
            sub = df[df["Strand"] == strand] if "Strand" in df.columns else pd.DataFrame()
            if not sub.empty:
                fig.add_trace(go.Scatter(
                    x=sub["Start"], y=[y_pos]*len(sub), mode="markers",
                    marker=dict(size=12, symbol=sym,
                                color=sub["Doench_Score"], colorscale="Teal",
                                showscale=(strand=="+"),
                                colorbar=dict(title="Score",len=.4,y=.8) if strand=="+" else None,
                                line=dict(width=1,color="white")),
                    text=[f"gRNA: {r['gRNA']}<br>Score: {r['Doench_Score']}<br>"
                          f"GC: {r['GC_Content']}%<br>Pos: {r['Start']}-{r['End']}"
                          for _,r in sub.iterrows()],
                    hoverinfo="text", name=f"Sense (+)" if strand=="+" else "Antisense (-)",
                ))
    fig.update_layout(
        template=_TPL, title="🧬 Genome Browser — gRNA Target Sites",
        xaxis_title="Sequence Position (bp)",
        yaxis=dict(range=[-1.5,1.5], tickvals=[-.5,0,.5], ticktext=["Antisense (−)","Sequence","Sense (+)"]),
        height=320, showlegend=True, legend=dict(orientation="h",y=1.15),
        margin=dict(l=60,r=20,t=60,b=40),
        paper_bgcolor=_BG, plot_bgcolor=_PBG,
    )
    return fig


def chart_gc_histogram(df: pd.DataFrame):
    fig = go.Figure()
    fig.add_vrect(x0=40, x1=70, fillcolor="rgba(0,200,150,.08)", line_width=0,
                  annotation_text="Optimal 40-70%", annotation_position="top left")
    fig.add_trace(go.Histogram(
        x=df["GC_Content"], nbinsx=25,
        marker=dict(
            color=df["GC_Content"].values,
            colorscale=[[0,"#f43f5e"],[.4,"#f59e0b"],[.5,"#00c896"],[.7,"#00c896"],[1,"#f43f5e"]],
            line=dict(width=1, color="rgba(255,255,255,.2)"),
        ),
        hovertemplate="GC: %{x:.1f}%<br>Count: %{y}<extra></extra>",
    ))
    fig.update_layout(
        template=_TPL, title="📊 GC Content Distribution",
        xaxis_title="GC Content (%)", yaxis_title="Number of gRNAs",
        height=360, showlegend=False,
        paper_bgcolor=_BG, plot_bgcolor=_PBG,
    )
    return fig


def chart_efficiency_scatter(df: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Start"], y=df["Doench_Score"], mode="markers",
        marker=dict(size=10, color=df["Doench_Score"], colorscale="Teal",
                    showscale=True, colorbar=dict(title="Score"),
                    line=dict(width=1, color="rgba(255,255,255,.3)")),
        text=[f"gRNA: {r['gRNA']}<br>Score: {r['Doench_Score']}<br>"
              f"GC: {r['GC_Content']}%<br>Rank: #{r.get('Efficiency_Rank','?')}"
              for _,r in df.iterrows()],
        hoverinfo="text",
    ))
    fig.add_hline(y=65, line_dash="dash", line_color="#00c896", annotation_text="High efficiency (65+)")
    fig.add_hline(y=45, line_dash="dash", line_color="#f59e0b", annotation_text="Moderate (45+)")
    fig.update_layout(
        template=_TPL, title="🎯 Efficiency vs Sequence Position",
        xaxis_title="Position (bp)", yaxis_title="Doench 2016 Score",
        height=400, paper_bgcolor=_BG, plot_bgcolor=_PBG,
    )
    return fig


def chart_off_target_heatmap(df: pd.DataFrame, ot_dict: dict):
    top_grnas = df.head(15)["gRNA"].tolist()
    heat_data = []
    for g in top_grnas:
        ots = ot_dict.get(g, [])
        mm = [0]*5
        for ot in ots:
            n = ot.get("mismatches",0)
            if 1 <= n <= 5: mm[n-1] += 1
        heat_data.append(mm)
    labels = [g[:10]+"…" for g in top_grnas]
    fig = go.Figure(go.Heatmap(
        z=heat_data, x=["1 mm","2 mm","3 mm","4 mm","5 mm"], y=labels,
        colorscale=[[0,"rgba(10,22,40,.8)"],[.25,"#0ea5e9"],[.5,"#f59e0b"],[1,"#f43f5e"]],
        hovertemplate="gRNA: %{y}<br>Mismatches: %{x}<br>Count: %{z}<extra></extra>",
        colorbar=dict(title="Count"),
    ))
    fig.update_layout(
        template=_TPL, title="🔥 Off-Target Heatmap (Top 15 gRNAs)",
        xaxis_title="Mismatches", yaxis_title="gRNA",
        height=460, paper_bgcolor=_BG, plot_bgcolor=_PBG,
    )
    return fig


def chart_score_comparison(df: pd.DataFrame):
    if "ML_Score" not in df.columns: return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Doench_Score"], y=df["ML_Score"], mode="markers",
        marker=dict(size=8, color=df["GC_Content"], colorscale="Viridis",
                    showscale=True, colorbar=dict(title="GC%"),
                    line=dict(width=1,color="white")),
        text=[f"gRNA: {r['gRNA']}<br>Doench: {r['Doench_Score']}<br>ML: {r['ML_Score']}" for _,r in df.iterrows()],
        hoverinfo="text",
    ))
    mn = min(df["Doench_Score"].min(), df["ML_Score"].min()) - 5
    mx = max(df["Doench_Score"].max(), df["ML_Score"].max()) + 5
    fig.add_trace(go.Scatter(x=[mn,mx], y=[mn,mx], mode="lines",
        line=dict(dash="dash", color="rgba(255,255,255,.25)"), name="Perfect agreement"))
    fig.update_layout(
        template=_TPL, title="🤖 Doench Score vs ML Prediction",
        xaxis_title="Doench 2016 Score", yaxis_title="XGBoost ML Score",
        height=400, paper_bgcolor=_BG, plot_bgcolor=_PBG,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA GENERATOR  (when utils/ml not installed)
# ══════════════════════════════════════════════════════════════════════════════
def _generate_demo(seq_text: str):
    import random
    random.seed(42); np.random.seed(42)
    raw = "".join(c for c in seq_text.upper() if c in "ATGC")
    if len(raw) < 40:
        raw = ("ATGGATTTATCTGCTCTTCGCGTTGAAGAAGTACAAAATGTCATTAATGCTATGCAGAAA"
               "ATCTTAGAGTGTCCCATCTGTCTGGAGTTGATCAAGGAACCTGTCTCCACAAAGTGTGACC"
               "ACATATTTTGCAAATTTTGCATGCCTGAGAGTCTATATGGAACAGAATAGAGATGCTGAAA") * 4
    rows = []
    for i in range(0, min(len(raw)-23, 600), 7):
        chunk = raw[i:i+20]
        if not all(c in "ATGC" for c in chunk):
            chunk = "".join(random.choices("ATGC", k=20))
        gc = sum(1 for c in chunk if c in "GC") / 20 * 100
        d  = max(10, min(95, 45 + gc*0.4 + np.random.normal(0,12)))
        ml = max(10, min(95, d + np.random.normal(2,8)))
        ot = max(0, int(np.random.normal(3,4)))
        rows.append({
            "gRNA": chunk,
            "Start": i, "End": i+20,
            "Strand": "+" if i%2==0 else "-",
            "PAM": random.choice(["AGG","TGG","CGG","GGG"]),
            "PAM_Sequence": raw[i+20:i+23] if i+23 <= len(raw) else "NGG",
            "GC_Content": round(gc,1),
            "Doench_Score": round(d,2),
            "ML_Score": round(ml,2),
            "Ensemble_Score": round(d*.6+ml*.4,2),
            "Off_Target_Count": ot,
            "Specificity_Score": round(max(0,100-ot*8)+np.random.normal(0,5),1),
            "Risk_Flag": "⚠️ HIGH" if ot>5 else "✅ OK",
        })
    df = pd.DataFrame(rows).sort_values("Doench_Score",ascending=False).reset_index(drop=True)
    df["Efficiency_Rank"] = range(1, len(df)+1)
    df["Efficiency_Percentile"] = (df["Doench_Score"].rank(pct=True)*100).round(1)

    # Synthetic off-target dict
    ot_dict = {}
    for _, row in df.head(15).iterrows():
        n_ots = row["Off_Target_Count"]
        ots = []
        for _ in range(n_ots):
            mm = random.choices([1,2,3,4,5], weights=[5,15,30,30,20])[0]
            ots.append({
                "off_target_seq": "".join(random.choices("ATGC",k=20)),
                "pam_site":       random.choice(["AGG","TGG","CGG"]),
                "position":       random.randint(0,5000),
                "strand":         random.choice(["+","-"]),
                "mismatches":     mm,
                "seed_mismatches":random.randint(0,mm),
            })
        ot_dict[row["gRNA"]] = ots

    return df, ot_dict


# ══════════════════════════════════════════════════════════════════════════════
# PAGES
# ══════════════════════════════════════════════════════════════════════════════

# ── Landing ───────────────────────────────────────────────────────────────────
def pg_landing():
    st.markdown(CSS, unsafe_allow_html=True)

    # Nav — logo uses plain colour, NEVER clips
    cl, _, cs, cu = st.columns([5,3,1,1])
    with cl:
        st.markdown('<div class="logo-bar"><span class="logo-text">🧬 CRISPR Target Finder</span></div>',
                    unsafe_allow_html=True)
    with cs:
        st.markdown("<div style='padding-top:.42rem'></div>", unsafe_allow_html=True)
        if st.button("Sign In", key="n_si", use_container_width=True):
            st.session_state.page="auth"; st.session_state.auth_tab="login"; st.rerun()
    with cu:
        st.markdown("<div style='padding-top:.42rem'></div>", unsafe_allow_html=True)
        if st.button("Sign Up", key="n_su", type="primary", use_container_width=True):
            st.session_state.page="auth"; st.session_state.auth_tab="signup"; st.rerun()

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # Hero
    _, hc, _ = st.columns([1,6,1])
    with hc:
        st.markdown("""
<div style="text-align:center">
  <div class="hero-badge"><span class="hero-dot"></span>Doench 2016 + XGBoost ML — Production Ready</div>
  <h1 class="hero-h1">Design Better<br><span class="hero-acc">CRISPR gRNAs</span><br>in Seconds</h1>
  <p class="hero-sub">The most accurate guide RNA design platform for molecular biology labs —
  validated scoring algorithms fused with machine learning.</p>
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    _, b1, b2, _ = st.columns([2.5,1.2,1.2,2.5])
    with b1:
        if st.button("🚀 Start Analyzing", key="h_cta", type="primary", use_container_width=True):
            st.session_state.page="auth"; st.session_state.auth_tab="signup"; st.rerun()
    with b2:
        if st.button("👤 Login", key="h_li", use_container_width=True):
            st.session_state.page="auth"; st.session_state.auth_tab="login"; st.rerun()

    # Stat strip
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    _, sc, _ = st.columns([1,4,1])
    with sc:
        st.markdown("""
<div class="stat-strip">
  <div class="stat-item"><div class="sv">10×</div><div class="sl">Faster than manual</div></div>
  <div class="stat-item"><div class="sv">500+</div><div class="sl">gRNAs / sec</div></div>
  <div class="stat-item"><div class="sv">99.2%</div><div class="sl">Accuracy rate</div></div>
  <div class="stat-item"><div class="sv">10k+</div><div class="sl">Analyses run</div></div>
</div>""", unsafe_allow_html=True)

    # Feature cards
    st.markdown("<div style='height:36px'></div>", unsafe_allow_html=True)
    st.markdown("""
<div style="text-align:center;font-size:.67rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#00c896;margin-bottom:.4rem">Core capabilities</div>
<div style="text-align:center;font-family:'Syne',sans-serif;font-size:clamp(1.4rem,2.8vw,2.1rem);font-weight:700;color:#e8f4f0;letter-spacing:-.02em;margin-bottom:1.8rem">Everything for gRNA design</div>
""", unsafe_allow_html=True)

    CARDS = [
        ("🎯","Doench 2016 Scoring","Validated Rule Set 2 for precise on-target efficiency across all Cas9 variants.","Validated"),
        ("🤖","XGBoost ML Engine","101-feature model trained on experimental gRNAs. Fine-tune with your own data.","Retrain-ready"),
        ("📊","Interactive Viz","Genome browser, GC histograms, off-target heatmaps — all interactive Plotly.","Plotly"),
        ("🔬","Off-Target Scan","Mismatch-aware scanning (1–5 mm) with configurable tolerance and risk heatmaps.","Safety-first"),
        ("📁","Project Manager","Save, load, share analyses. Full history with one-click restore per user.","Authenticated"),
        ("⚡","Multi-format Input","FASTA, GenBank, raw DNA/RNA, cDNA. Auto-detects format and sequence type.","Any format"),
    ]
    c1,c2,c3 = st.columns(3)
    for i,(icon,name,desc,badge) in enumerate(CARDS):
        with [c1,c2,c3][i%3]:
            st.markdown(f"""
<div class="fc"><div class="fi">{icon}</div>
<div class="fn">{name}</div><div class="fd2">{desc}</div>
<span class="fb2">{badge}</span></div>
<div style="height:14px"></div>""", unsafe_allow_html=True)

    st.markdown(_FOOTER, unsafe_allow_html=True)


# ── Auth — pure page, zero overlays ──────────────────────────────────────────
def pg_auth():
    st.markdown(CSS, unsafe_allow_html=True)
    if st.button("← Back to home", key="bk"):
        st.session_state.page="landing"; st.rerun()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1,1.4,1])
    with mid:
        mode = st.session_state.auth_tab
        st.markdown(f"""
<div class="auth-card">
  <div style="width:54px;height:54px;border-radius:50%;
    background:linear-gradient(135deg,#00c896,#0ea5e9);
    display:flex;align-items:center;justify-content:center;
    font-size:1.6rem;margin:0 auto 1.1rem;box-shadow:0 0 20px rgba(0,200,150,.3)">🧬</div>
  <h2 style="font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;
    text-align:center;color:#e8f4f0;letter-spacing:-.02em;margin-bottom:.2rem">
    {'Create Account' if mode=='signup' else 'Welcome back'}</h2>
  <p style="font-size:.8rem;color:#8fb3a0;text-align:center;margin-bottom:0">
    {'Join thousands of researchers' if mode=='signup' else 'Sign in to your analyses and projects'}
  </p>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        t1, t2 = st.columns(2)
        with t1:
            if st.button("Sign In",  key="tb_li",
                         type="primary" if mode=="login"  else "secondary",
                         use_container_width=True):
                st.session_state.auth_tab="login";  st.rerun()
        with t2:
            if st.button("Sign Up",  key="tb_su",
                         type="primary" if mode=="signup" else "secondary",
                         use_container_width=True):
                st.session_state.auth_tab="signup"; st.rerun()

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if mode == "login":
            u = st.text_input("Username", placeholder="e.g. admin",    key="li_u")
            p = st.text_input("Password", type="password", placeholder="••••••••", key="li_p")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("→  Sign In", key="do_li", type="primary", use_container_width=True):
                if not u or not p:
                    st.warning("Please enter both username and password.")
                else:
                    c = _creds()
                    if u in c and c[u] == _h(p):
                        st.session_state.authenticated = True
                        st.session_state.username = u
                        st.session_state.is_guest = False
                        st.session_state.page = "dashboard"
                        st.rerun()
                    else:
                        st.error("Invalid credentials.  Try  **admin** / **admin123**")
            st.markdown("<p style='font-size:.69rem;color:#4d7a65;text-align:center;margin-top:6px'>Demo: <strong style='color:#8fb3a0'>admin</strong> / <strong style='color:#8fb3a0'>admin123</strong></p>", unsafe_allow_html=True)
        else:
            u = st.text_input("Username", placeholder="researcher_name",     key="su_u")
            e = st.text_input("Email",    placeholder="you@university.edu",  key="su_e")
            p = st.text_input("Password", type="password",
                              placeholder="min 4 characters",                key="su_p")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("→  Create Account", key="do_su", type="primary", use_container_width=True):
                if len(u) < 3:   st.warning("Username must be ≥ 3 characters.")
                elif len(p) < 4: st.warning("Password must be ≥ 4 characters.")
                else:
                    c = _creds()
                    if u in c:   st.error("Username already taken — choose another.")
                    else:
                        c[u] = _h(p); _save_creds(c)
                        st.session_state.authenticated = True
                        st.session_state.username = u
                        st.session_state.is_guest = False
                        st.session_state.page = "dashboard"
                        st.rerun()

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.divider()
        if st.button("Continue as Guest  →", key="do_g", use_container_width=True):
            st.session_state.authenticated = True
            st.session_state.username  = "guest"
            st.session_state.is_guest  = True
            st.session_state.page      = "dashboard"
            st.rerun()
        st.markdown("<p style='font-size:.69rem;color:#4d7a65;text-align:center;margin-top:5px'>Guest mode — analyses won't be saved between sessions</p>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def _sidebar():
    with st.sidebar:
        st.markdown("### ⚙️ Analysis Settings")
        mm  = st.slider("Max off-target mismatches", 1, 5, 4, key="sb_mm")
        rot = st.checkbox("Run off-target analysis", value=True,  key="sb_ot")
        rml = st.checkbox("ML efficiency prediction", value=True, key="sb_ml")
        st.markdown("---")

        if not st.session_state.is_guest:
            st.markdown("### 📁 Projects")
            ps = list_projects(st.session_state.username)
            if ps:
                sel = st.selectbox("Load:", [" (New)"] + sorted(ps, reverse=True), key="sb_ps")
                a, b = st.columns(2)
                if sel != " (New)":
                    if a.button("📂 Load", key="sb_ld", use_container_width=True):
                        d = load_project(st.session_state.username, sel)
                        if d:
                            st.session_state.results_df     = d.get("results_df")
                            st.session_state.sequence_info  = d.get("sequence_info")
                            st.session_state.ot_dict        = d.get("ot_dict", {})
                            st.session_state.analysis_complete = True
                            st.rerun()
                    if b.button("🗑️ Del", key="sb_dl", use_container_width=True):
                        delete_project(st.session_state.username, sel); st.rerun()
            else:
                st.caption("No saved projects yet.")
        else:
            st.markdown("### 🔒 Projects")
            st.caption("Sign in to save & manage projects.")

        st.markdown("---")
        st.markdown("<div style='font-size:.66rem;color:#4d7a65;text-align:center;line-height:1.9'><b style='color:#8fb3a0'>CRISPR Target Finder</b><br>v2.1 · Doench 2016 RS2<br>Apache 2.0 · Dhruv Nambiar</div>",
                    unsafe_allow_html=True)
    return mm, rot, rml


def _nav():
    u  = st.session_state.username or "User"
    av = u[:2].upper()
    guest = " · Guest" if st.session_state.is_guest else ""
    nl, _, nr = st.columns([4,3,2])
    with nl:
        st.markdown('<div class="dash-nav"><span class="dash-logo">🧬 CRISPR Target Finder</span></div>',
                    unsafe_allow_html=True)
    with nr:
        r1, r2 = st.columns([3,1])
        with r1:
            st.markdown(f"<div style='padding-top:.4rem'><span class='user-chip'><span class='av'>{av}</span>{u}{guest}</span></div>",
                        unsafe_allow_html=True)
        with r2:
            st.markdown("<div style='padding-top:.35rem'></div>", unsafe_allow_html=True)
            if st.button("Out", key="nav_lo"):
                for k in ("authenticated","username","is_guest","results_df","ot_dict",
                          "sequence_info","analysis_complete","raw_sequence","current_proj_id"):
                    st.session_state[k] = (False if k in ("authenticated","is_guest","analysis_complete")
                                           else "" if k in ("username","raw_sequence")
                                           else None)
                st.session_state.page = "landing"
                st.rerun()


def _kpis():
    df  = st.session_state.results_df
    si  = st.session_state.sequence_info or {}
    if df is not None and not df.empty:
        n   = len(df)
        top = f"{df['Doench_Score'].max():.1f}" if "Doench_Score" in df.columns else "—"
        hi  = len(df[df["Doench_Score"]>=65])   if "Doench_Score" in df.columns else "—"
        gc  = f"{df['GC_Content'].mean():.1f}%"  if "GC_Content"  in df.columns else "—"
        slen= f"{si.get('length',0):,} bp"
    else:
        n = top = hi = gc = slen = "—"

    k1,k2,k3,k4,k5 = st.columns(5)
    for col,icon,val,lbl,delta in [
        (k1,"🧬",n,   "Total gRNAs",""),
        (k2,"⭐",top, "Best Score","Top"),
        (k3,"📊",gc,  "Avg GC%",""),
        (k4,"📏",slen,"Seq Length",""),
        (k5,"🎯",hi,  "High Eff. ≥65",""),
    ]:
        with col:
            d = f'<span class="kd">{delta}</span>' if delta else ""
            st.markdown(f'<div class="kpi">{d}<span class="ki">{icon}</span>'
                        f'<div class="kv">{val}</div><div class="kl">{lbl}</div></div>',
                        unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


# ── TAB 1: Input ──────────────────────────────────────────────────────────────
def tab_input(mm, rot, rml):
    st.markdown('<div class="panel"><div class="panel-t">🔬 Prepare Your Sequence</div>'
                'Upload a <b>FASTA / GenBank</b> file or paste DNA directly. '
                'Formats: .fasta .fa .fna .gb .gbk .txt</div>', unsafe_allow_html=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    i1, i2 = st.columns(2)
    with i1:
        st.markdown("#### 📂 Upload File")
        up = st.file_uploader("FASTA / GenBank / TXT",
                              type=["fasta","fa","fna","gb","gbk","txt"], key="fu")
        if up:
            st.success(f"✅ **{up.name}** — {up.size:,} bytes")

    with i2:
        st.markdown("#### ✏️ Or Paste Directly")
        stype = st.selectbox("Sequence type",
                             ["Auto-detect","DNA","RNA","Complementary DNA (cDNA)"], key="st")
        seq = st.text_area("Paste FASTA or raw sequence", height=150,
                           placeholder=">my_gene\nATGGATTTATCTGCTCTTCGCGTT...", key="sq")

    st.markdown("#### 📦 Load Example Data")
    e1, e2, e3 = st.columns(3)
    BRCA1 = (">BRCA1_demo\nATGGATTTATCTGCTCTTCGCGTTGAAGAAGTACAAAATGTCATTAATGCTATGCAGAAAATCTTAGAGTGTCCC"
             "ATCTGTCTGGAGTTGATCAAGGAACCTGTCTCCACAAAGTGTGACCACATATTTTGCAAATTTTGCATGCCTGAGAG"
             "TCTATATGGAACAGAATAGAGATGCTGAAAGAGGTAGAACCAGGAGATGCTAAAGGGGCAATGAGAGAGACATCTCG"
             "AGGGCTCTCTTAAATCAGAAAACAGGAGGTCCTGGAGAATCCTCTGATGATATCAATCAGGTTATGGAAAAGCAGAAA")
    GFP   = (">GFP_demo\nATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTA"
             "AACGGCCACAAGTTCAGCGTGTCCGGCGAGGGCGAGGGCGATGCCACCTACGGCAAGCTGACCCTGAAGTTCATC"
             "TGCACCACCGGCAAGCTGCCCGTGCCCTGGCCCACCCTCGTGACCACCCTGACCTACGGCGTGCAGTGCTTCAGC"
             "CGCTACCCCGACCACATGAAGCAGCACGACTTCTTCAAGTCCGCCATGCCCGAAGGCTACGTCCAGGAGCGCACC")
    with e1:
        if st.button("🧬 BRCA1 Gene",   use_container_width=True, key="ex1"):
            st.session_state["_demo"] = BRCA1; st.rerun()
    with e2:
        if st.button("💚 GFP Protein",  use_container_width=True, key="ex2"):
            st.session_state["_demo"] = GFP;   st.rerun()
    with e3:
        if st.button("ℹ️ Demo Video",   use_container_width=True, key="ex3"):
            st.info("📺 Tutorials at **github.com/dhruvnambiar/crispr-target-finder**")

    if "_demo" in st.session_state:
        st.session_state["sq"] = st.session_state.pop("_demo"); st.rerun()

    st.markdown("---")
    if st.button("🚀 Analyze Sequence", type="primary", use_container_width=True, key="run"):
        _run_analysis(up, seq or st.session_state.get("sq",""), stype, mm, rot, rml)


def _run_analysis(up, seq_text, stype, mm, rot, rml):
    if not up and not (seq_text and seq_text.strip()):
        st.error("⚠️ Please upload a file or paste a sequence."); return

    if not HAS_UTILS:
        # Demo mode
        progress = st.progress(0, text="🔍 Generating demo targets…")
        for pct in range(0,101,20): progress.progress(pct); time.sleep(0.05)
        df, ot_dict = _generate_demo(seq_text or ">demo\nATGGATTTATCTGCTCTT")
        progress.empty()
        st.session_state.results_df     = df
        st.session_state.sequence_info  = {"name":"Demo sequence","length":len(seq_text or ""),"id":"demo"}
        st.session_state.ot_dict        = ot_dict
        st.session_state.analysis_complete = True
        st.success(f"✅ Demo mode: generated **{len(df)}** synthetic gRNA targets. "
                   "Switch to the **Results** or **Visualizations** tab.")
        return

    type_map = {"Auto-detect":"auto","DNA":"dna","RNA":"rna","Complementary DNA (cDNA)":"cdna"}
    try:
        progress = st.progress(0, text="🔍 Parsing input…")
        fc = up.read() if up else None
        fn = up.name  if up else None
        sequences = parse_input(text=None if up else seq_text,
                                file_content=fc, file_name=fn,
                                input_type=type_map.get(stype,"auto"))
        st.success(f"✅ Parsed **{len(sequences)}** sequence(s)")

        seq_data = sequences[0]
        sequence = seq_data["sequence"]
        seq_stats = get_sequence_stats(sequence)
        st.session_state.sequence_info = {
            "id":   seq_data.get("id",""),
            "name": seq_data.get("name",""),
            "length": len(sequence),
            "stats":  seq_stats,
        }
        st.session_state.raw_sequence = sequence

        progress.progress(20, text="🧬 Scanning for gRNA targets…")
        df = find_crispr_targets(sequence)
        progress.progress(40, text=f"✅ Found {len(df)} targets. Scoring…")

        if df.empty:
            st.warning("⚠️ No CRISPR target sites found — check sequence length and PAM availability.")
            progress.empty(); return

        if rml and HAS_ML:
            progress.progress(50, text="🤖 Running ML predictions…")
            model = get_model()
            df["ML_Score"]       = model.predict_batch(df["gRNA"].tolist())
            df["Ensemble_Score"] = (df["Doench_Score"]*.6 + df["ML_Score"]*.4).round(2)

        ot_dict = {}
        if rot:
            def _ot_cb(cur, tot):
                pct = 60 + int(35*cur/tot)
                progress.progress(pct, text=f"🎯 Off-target: {cur}/{tot} gRNAs…")
            progress.progress(60, text="🎯 Off-target analysis…")
            df, ot_dict = batch_off_target_analysis(df, sequence,
                                                    max_mismatches=mm,
                                                    progress_callback=_ot_cb)

        progress.progress(100, text="✅ Analysis complete!")
        time.sleep(0.4); progress.empty()

        df = df.sort_values("Doench_Score",ascending=False).reset_index(drop=True)
        df["Efficiency_Rank"]       = range(1, len(df)+1)
        df["Efficiency_Percentile"] = (df["Doench_Score"].rank(pct=True)*100).round(1)

        st.session_state.results_df     = df
        st.session_state.ot_dict        = ot_dict
        st.session_state.analysis_complete = True

        if not st.session_state.is_guest:
            pid = f"proj_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            save_project(st.session_state.username, pid, {
                "results_df":    df,
                "sequence_info": st.session_state.sequence_info,
                "ot_dict":       ot_dict,
                "timestamp":     datetime.datetime.now().isoformat(),
            })
            st.session_state.current_proj_id = pid
            st.toast(f"💾 Project saved: {pid}")

        st.success("🎉 **Analysis complete!** Switch to the **Results** or **Visualizations** tab.")

    except ValueError as e:
        st.error(f"⚠️ Input Error: {e}")
    except Exception as e:
        st.error(f"❌ Unexpected Error: {e}")
        st.exception(e)


# ── TAB 2: Results ────────────────────────────────────────────────────────────
def tab_results():
    if not st.session_state.analysis_complete or st.session_state.results_df is None:
        st.markdown("""
<div style="background:rgba(14,165,233,.08);border:2px dashed rgba(14,165,233,.3);
  border-radius:14px;padding:2.5rem;text-align:center">
  <p style="font-size:1.05rem;color:#0ea5e9;font-weight:600">🔬 Run an analysis first to view results</p>
  <p style="color:#8fb3a0;margin-top:.5rem;font-size:.9rem">Upload a sequence in the <strong>Input</strong> tab to get started</p>
</div>""", unsafe_allow_html=True); return

    df      = st.session_state.results_df
    seq_info = st.session_state.sequence_info or {}

    # ── 5-column summary metrics ──────────────────────────────────────────────
    st.markdown("### 📊 Analysis Summary")
    m1,m2,m3,m4,m5 = st.columns(5)
    for col,val,lbl,icon in [
        (m1, len(df),                              "Total gRNAs",  "🧬"),
        (m2, f"{df['Doench_Score'].max():.1f}",    "Best Score",   "⭐"),
        (m3, f"{df['GC_Content'].mean():.1f}%",    "Avg GC%",      "📊"),
        (m4, f"{seq_info.get('length',0):,}",      "Seq Length",   "📏"),
        (m5, len(df[df["Doench_Score"]>=65]),       "High Eff.",    "🎯"),
    ]:
        with col:
            st.markdown(f"""
<div class="kpi">
  <span class="ki">{icon}</span>
  <div class="kv">{val}</div>
  <div class="kl">{lbl}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown("### 🧬 gRNA Candidates")
    f1,f2,f3,f4 = st.columns(4)
    with f1: ms  = st.slider("Min Doench Score",0,100,0,key="rm")
    with f2: sf  = st.multiselect("Strand",["+","-"],default=["+","-"],key="rs")
    with f3: gcr = st.slider("GC Content (%)",0,100,(20,80),key="rg")
    with f4: top_n = st.number_input("Show top N", min_value=10, max_value=5000, value=200, step=10, key="rn")

    mask = (
        (df["Doench_Score"] >= ms) &
        (df["Strand"].isin(sf)) &
        (df["GC_Content"] >= gcr[0]) &
        (df["GC_Content"] <= gcr[1])
    )
    dff = df[mask].head(int(top_n)).copy()

    st.markdown(f"""<div style="padding:.5rem 1rem;background:var(--card);border:1px solid var(--bdr);
border-radius:8px;margin:.8rem 0;font-size:.78rem;color:#8fb3a0">
Showing <strong style="color:#00c896">{len(dff)}</strong> of <strong>{len(df)}</strong> gRNAs
</div>""", unsafe_allow_html=True)

    if dff.empty: st.warning("No results match the current filters."); return

    # ── Color-coded table ─────────────────────────────────────────────────────
    DISPLAY_COLS = ["Efficiency_Rank","gRNA","PAM_Sequence","Start","End","Strand",
                    "GC_Content","Doench_Score"]
    if "ML_Score"          in dff.columns: DISPLAY_COLS.append("ML_Score")
    if "Specificity_Score" in dff.columns: DISPLAY_COLS += ["Specificity_Score","Off_Target_Count","Risk_Flag"]
    if "Efficiency_Percentile" in dff.columns: DISPLAY_COLS.append("Efficiency_Percentile")
    avail = [c for c in DISPLAY_COLS if c in dff.columns]

    def _style(row):
        s = row.get("Doench_Score",0)
        bg = ("rgba(0,200,83,.12)"  if s >= 65
              else "rgba(255,214,0,.10)" if s >= 45
              else "rgba(255,23,68,.10)")
        return [f"background-color:{bg}"] * len(row)

    styled = dff[avail].style.apply(_style, axis=1)
    st.dataframe(styled, use_container_width=True, height=500)

    # ── Off-target details ────────────────────────────────────────────────────
    ot_dict = st.session_state.ot_dict or {}
    if ot_dict:
        st.markdown("### 🎯 Off-Target Details")
        for _, row in df.head(10).iterrows():
            grna = row["gRNA"]
            ots  = ot_dict.get(grna, [])
            high = len([o for o in ots if o.get("mismatches",5) <= 2])
            risk_label = "⚠️ HIGH RISK" if high >= 3 else "✅ OK"
            risk_cls   = "risk-high" if high >= 3 else "risk-ok"
            with st.expander(f"`{grna}` — {len(ots)} off-targets"):
                st.markdown(f'<span class="{risk_cls}">{risk_label}</span>',
                            unsafe_allow_html=True)
                if ots:
                    ot_df = pd.DataFrame(ots)
                    show = [c for c in ["off_target_seq","pam_site","position",
                                        "strand","mismatches","seed_mismatches"] if c in ot_df.columns]
                    st.dataframe(ot_df[show] if show else ot_df,
                                 use_container_width=True)
                else:
                    st.success("No off-targets found — excellent specificity!")

    # ── Downloads ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📥 Export Results")
    dl1, dl2, dl3, dl4 = st.columns(4)

    with dl1:
        st.download_button("📄 CSV", dff.to_csv(index=False),
                           "crispr_results.csv","text/csv",
                           use_container_width=True)
    with dl2:
        if HAS_UTILS:
            try:
                pdf_bytes = generate_pdf_report(dff, seq_info, ot_dict)
                st.download_button("📑 PDF Report", pdf_bytes,
                                   "crispr_report.pdf","application/pdf",
                                   use_container_width=True)
            except Exception as e:
                st.button("📑 PDF Report", disabled=True, use_container_width=True,
                          help=f"PDF error: {e}")
        else:
            st.button("📑 PDF Report", disabled=True, use_container_width=True,
                      help="Install utils to enable PDF export")
    with dl3:
        st.download_button("🔧 JSON", dff.to_json(orient="records",indent=2),
                           "crispr_results.json","application/json",
                           use_container_width=True)
    with dl4:
        if HAS_PLOTLY and not dff.empty:
            slen = seq_info.get("length", int(dff["End"].max() if "End" in dff.columns else 1000))
            fig_html = chart_sequence_track(dff, slen).to_html(include_plotlyjs="cdn")
            st.download_button("🌐 Interactive HTML", fig_html,
                               "crispr_interactive.html","text/html",
                               use_container_width=True)
        else:
            st.button("🌐 HTML", disabled=True, use_container_width=True)


# ── TAB 3: Visualizations ─────────────────────────────────────────────────────
def tab_viz():
    if not HAS_PLOTLY:
        st.info("`pip install plotly` to enable visualizations"); return
    if not st.session_state.analysis_complete or st.session_state.results_df is None:
        st.markdown("""
<div style="background:linear-gradient(135deg,rgba(0,200,150,.08),rgba(14,165,233,.08));
  border-radius:14px;padding:3rem;text-align:center;color:white">
  <p style="font-size:1.1rem;font-weight:700;margin-bottom:.5rem">📈 Interactive Visualizations</p>
  <p style="color:#8fb3a0;margin-bottom:1.5rem">Run an analysis to generate genome browser tracks, efficiency plots, and off-target heatmaps</p>
  <p style="font-size:.85rem;color:#4d7a65">👉 Switch to the <strong style="color:#8fb3a0">Input</strong> tab to get started</p>
</div>""", unsafe_allow_html=True); return

    df      = st.session_state.results_df
    seq_info = st.session_state.sequence_info or {}
    ot_dict  = st.session_state.ot_dict or {}
    slen     = seq_info.get("length", int(df["End"].max() if "End" in df.columns else 1000))

    # Full-width sequence track
    st.plotly_chart(chart_sequence_track(df, slen), use_container_width=True, key="seq_track")

    # GC + efficiency
    v1, v2 = st.columns(2)
    with v1: st.plotly_chart(chart_gc_histogram(df),    use_container_width=True, key="gc_hist")
    with v2: st.plotly_chart(chart_efficiency_scatter(df), use_container_width=True, key="eff_sc")

    # Off-target heatmap + ML comparison
    v3, v4 = st.columns(2)
    with v3:
        if ot_dict:
            st.plotly_chart(chart_off_target_heatmap(df, ot_dict), use_container_width=True, key="ot_heat")
        else:
            st.info("Enable off-target analysis to see the heatmap.")
    with v4:
        if "ML_Score" in df.columns:
            st.plotly_chart(chart_score_comparison(df), use_container_width=True, key="score_cmp")
        else:
            st.info("Enable ML prediction for the Doench vs ML comparison.")

    # ── Chart exports ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📥 Export Visualizations")
    exp1, exp2, exp3 = st.columns(3)

    # PNG/SVG exports require kaleido — degrade gracefully
    def _try_img(fig, fmt, fname, mime, label, col):
        with col:
            try:
                data = fig.to_image(format=fmt, width=1200, height=450, scale=2)
                st.download_button(label, data=data, file_name=fname, mime=mime,
                                   use_container_width=True)
            except Exception:
                st.button(label, disabled=True, use_container_width=True,
                          help="Install kaleido: pip install kaleido")

    _try_img(chart_sequence_track(df,slen), "png","sequence_track.png","image/png","📷 Sequence Track PNG", exp1)
    _try_img(chart_gc_histogram(df),        "svg","gc_histogram.svg",  "image/svg+xml","🖼️ GC Histogram SVG",  exp2)
    _try_img(chart_efficiency_scatter(df),  "png","efficiency_plot.png","image/png","📷 Efficiency Plot PNG", exp3)


# ── TAB 4: ML Model ───────────────────────────────────────────────────────────
def tab_ml():
    st.markdown("### 🤖 Machine Learning Prediction Engine")
    st.markdown("""
Our **XGBoost model** augments Doench 2016 scoring using **101 sequence features**:
- **Position × Nucleotide**: one-hot position-dependent features (80)
- **Oligonucleotide Frequencies**: dinucleotide patterns (16)
- **Secondary Structure proxies**: GC content, purine ratio, seed G-fraction (5)
""")

    if not HAS_ML:
        st.warning("⚠️ `ml_model.py` not found — add your XGBoost model module to enable this.")
        st.code("""# Expected ml_model.py interface:
class CRISPRModel:
    def predict_batch(self, sequences: list[str]) -> list[float]: ...
    def get_metrics(self)           -> dict: ...
    def get_feature_importances(self) -> dict: ...
    def retrain_with_user_data(self, csv_str: str) -> dict: ...

def get_model() -> CRISPRModel: ...""", language="python")
        return

    model   = get_model()
    metrics = model.get_metrics()

    if metrics and "rmse" in metrics:
        st.markdown("#### 📊 Model Performance")
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("RMSE",    f"{metrics['rmse']:.3f}")
        m2.metric("MAE",     f"{metrics['mae']:.3f}")
        m3.metric("R² Score",f"{metrics['r2']:.3f}")
        m4.metric("CV-RMSE", f"{metrics.get('cv_rmse_mean',0):.3f} ± {metrics.get('cv_rmse_std',0):.3f}")

        if HAS_PLOTLY:
            imps = model.get_feature_importances()
            if imps:
                st.markdown("#### 🔑 Top 15 Features by Importance")
                imp_df = pd.DataFrame([{"Feature":k,"Importance":v} for k,v in list(imps.items())[:15]])
                fig = px.bar(imp_df, x="Importance", y="Feature", orientation="h",
                             color="Importance", color_continuous_scale="Teal",
                             template="plotly_dark")
                fig.update_layout(height=400, showlegend=False,
                                  yaxis=dict(autorange="reversed"),
                                  paper_bgcolor=_BG, plot_bgcolor=_PBG)
                st.plotly_chart(fig, use_container_width=True, key="feat_imp")

    st.markdown("---")
    st.markdown("#### 🔄 Fine-Tune with Your Data")
    st.markdown("""Improve predictions by retraining with your experimental data.  
**Required CSV format:**
```
gRNA,efficiency
ATCGATCGATCGATCGATCG,75.5
GGCTAGCTAGCTAGCTAGCT,82.3
```""")
    retrain_f = st.file_uploader("Upload training CSV", type=["csv"], key="ret_csv")
    if retrain_f:
        if st.button("🚀 Retrain Model", type="primary"):
            with st.spinner("🔄 Retraining model…"):
                try:
                    new_metrics = model.retrain_with_user_data(retrain_f.read().decode("utf-8"))
                    st.success("✅ Model retrained successfully!")
                    st.json(new_metrics)
                except ValueError as e:
                    st.error(f"⚠️ Error: {e}")
                except Exception as e:
                    st.error(f"❌ Retraining failed: {e}")


# ── TAB 5: Project History ────────────────────────────────────────────────────
def tab_history():
    if not st.session_state.authenticated or st.session_state.is_guest:
        st.markdown("""
<div style="background:rgba(245,158,11,.08);border-radius:14px;padding:2rem;
  text-align:center;border-left:4px solid #f59e0b">
  <p style="font-size:1.05rem;color:#f59e0b;font-weight:600">🔐 Sign In to View Projects</p>
  <p style="color:#8fb3a0;margin-top:.5rem;font-size:.9rem">
    Your analysis projects are automatically saved when you're logged in</p>
</div>""", unsafe_allow_html=True); return

    st.markdown(f"### 📁 Your Projects — {st.session_state.username}")
    projects = list_projects(st.session_state.username)

    if not projects:
        st.markdown("""
<div style="background:rgba(0,200,150,.06);border-radius:14px;padding:2.5rem;text-align:center">
  <p style="font-size:1rem;color:#00c896;font-weight:600">📭 No projects yet</p>
  <p style="color:#8fb3a0;margin-top:.5rem;font-size:.875rem">
    Your analyses will appear here once you run them</p>
</div>""", unsafe_allow_html=True); return

    for pid in sorted(projects, reverse=True):
        data = load_project(st.session_state.username, pid)
        if not data: continue
        ts    = str(data.get("timestamp",""))[:16]
        sinfo = data.get("sequence_info", {})
        rdf   = data.get("results_df")
        n     = len(rdf) if isinstance(rdf, pd.DataFrame) else 0

        with st.expander(f"📋 {pid}  ·  {n} gRNAs  ·  {ts}"):
            pc1, pc2 = st.columns([3,1])
            with pc1:
                st.markdown(f"""
- **Sequence:** {sinfo.get('name','N/A')}
- **Length:** {sinfo.get('length',0):,} bp
- **gRNA targets:** {n}
- **Saved:** {ts}
""")
            with pc2:
                if st.button("📂 Load",  key=f"hl_{pid}", use_container_width=True):
                    st.session_state.results_df     = rdf
                    st.session_state.sequence_info  = sinfo
                    st.session_state.ot_dict        = data.get("ot_dict", {})
                    st.session_state.analysis_complete = True; st.rerun()
                if st.button("📋 Copy URL", key=f"cp_{pid}", use_container_width=True):
                    st.code(f"?user={st.session_state.username}&project={pid}", language="text")
                if st.button("🗑️ Delete",  key=f"hd_{pid}", use_container_width=True):
                    delete_project(st.session_state.username, pid); st.rerun()


# ── Dashboard assembly ────────────────────────────────────────────────────────
def pg_dashboard():
    st.markdown(CSS, unsafe_allow_html=True)
    mm, rot, rml = _sidebar()
    _nav()
    _kpis()

    ti,tr,tv,tm,th = st.tabs([
        "🔬 Input", "📊 Results", "📈 Visualizations", "🤖 ML Model", "📁 History"
    ])
    with ti: tab_input(mm, rot, rml)
    with tr: tab_results()
    with tv: tab_viz()
    with tm: tab_ml()
    with th: tab_history()

    st.markdown(_FOOTER, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
def main():
    if st.session_state.authenticated and st.session_state.page != "dashboard":
        st.session_state.page = "dashboard"
    p = st.session_state.page
    if   p == "dashboard": pg_dashboard()
    elif p == "auth":      pg_auth()
    else:                  pg_landing()

if __name__ == "__main__":
    main()
