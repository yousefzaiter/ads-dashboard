import io
import json
import os
import smtplib
import urllib.parse
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
load_dotenv(override=True)
from auth import check_auth, do_logout, show_login_page
from users import get_user
import plotly.express as px
import plotly.graph_objects as go
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime, timedelta, date
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, Image as RLImage,
                                 HRFlowable)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Ads Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth gate ─────────────────────────────────────────────────────────────────
if not check_auth():
    show_login_page()
    st.stop()

# ── Premium CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

*, *::before, *::after {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  box-sizing: border-box;
}

/* ── Base ── */
.stApp { background: #07090f; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #2a2f42; border-radius: 2px; }

/* ── KPI Cards ── */
.kpi-card {
  position: relative;
  background: linear-gradient(150deg, #111624 0%, #0d1020 100%);
  border-radius: 18px;
  padding: 22px 20px 18px;
  overflow: hidden;
  cursor: default;
  transition: transform 0.28s cubic-bezier(.34,1.4,.64,1),
              box-shadow 0.28s ease,
              border-color 0.28s ease;
  border: 1px solid rgba(255,255,255,0.055);
  min-height: 148px;
}
.kpi-card:hover {
  transform: translateY(-5px) scale(1.015);
  border-color: var(--accent-border, rgba(255,255,255,0.15));
  box-shadow: 0 12px 48px var(--glow, rgba(88,166,255,0.12)),
              0 2px 8px rgba(0,0,0,0.4);
}
/* Accent top bar */
.kpi-card::before {
  content: '';
  position: absolute;
  top: 0; left: 16px; right: 16px;
  height: 2px;
  border-radius: 0 0 4px 4px;
  background: var(--accent, #58a6ff);
  opacity: 0.85;
  transition: opacity 0.28s ease, left 0.28s ease, right 0.28s ease;
}
.kpi-card:hover::before { left: 8px; right: 8px; opacity: 1; }
/* Ambient glow blob */
.kpi-card::after {
  content: '';
  position: absolute;
  top: -50px; right: -50px;
  width: 130px; height: 130px;
  background: var(--accent, #58a6ff);
  border-radius: 50%;
  opacity: 0.03;
  transition: opacity 0.28s ease, transform 0.28s ease;
}
.kpi-card:hover::after { opacity: 0.09; transform: scale(1.2); }

.kpi-icon  { font-size: 16px; opacity: 0.7; margin-bottom: 10px; display: block; }
.kpi-label {
  font-size: 10.5px; font-weight: 600; letter-spacing: 1.5px;
  text-transform: uppercase; color: rgba(255,255,255,0.3); margin-bottom: 9px;
}
.kpi-value {
  font-size: 38px; font-weight: 800; color: #f0f6fc;
  line-height: 1; letter-spacing: -1.5px; margin-bottom: 7px;
}
.kpi-sub { font-size: 11.5px; color: rgba(255,255,255,0.25); font-weight: 400; }

/* ── Section labels ── */
.sec-label {
  font-size: 10.5px; font-weight: 700; letter-spacing: 1.6px;
  text-transform: uppercase; color: rgba(255,255,255,0.25);
  margin: 40px 0 18px; display: flex; align-items: center; gap: 12px;
}
.sec-label::after {
  content: ''; flex: 1; height: 1px;
  background: linear-gradient(90deg, rgba(255,255,255,0.07), transparent);
}

/* ── Status pills ── */
.pill-live {
  display:inline-flex; align-items:center; gap:6px;
  background: rgba(63,185,80,0.1); border: 1px solid rgba(63,185,80,0.22);
  border-radius: 20px; padding: 3px 11px;
  font-size: 11px; font-weight: 600; color: #3fb950; letter-spacing: 0.4px;
}
.dot-pulse {
  width:6px; height:6px; border-radius:50%; background:#3fb950;
  animation: dp 2s ease-in-out infinite;
}
@keyframes dp {
  0%,100% { opacity:1; transform:scale(1);   }
  50%      { opacity:0.4; transform:scale(0.65); }
}

/* ── ROAS banner ── */
.roas-wrap {
  border-radius: 20px;
  padding: 26px 32px;
  display: flex; align-items: center; gap: 36px;
  margin-top: 18px;
}
.roas-divider { width:1px; height:52px; background:rgba(255,255,255,0.07); flex-shrink:0; }
.roas-stat-label { font-size: 11px; color: rgba(255,255,255,0.28); font-weight:500; margin-bottom:4px; letter-spacing:0.5px; }
.roas-stat-value { font-size: 20px; font-weight: 700; color: #f0f6fc; letter-spacing: -0.5px; }

/* ── Campaign tags ── */
.tag { padding: 2px 9px; border-radius: 12px; font-size: 10.5px; font-weight: 700; letter-spacing: 0.3px; white-space:nowrap; }
.tag-best   { background:rgba(63,185,80,0.13);  color:#3fb950; border:1px solid rgba(63,185,80,0.28); }
.tag-second { background:rgba(88,166,255,0.13); color:#58a6ff; border:1px solid rgba(88,166,255,0.28); }
.tag-warn   { background:rgba(248,81,73,0.13);  color:#f85149; border:1px solid rgba(248,81,73,0.28); }
.tag-ok     { background:rgba(255,255,255,0.06); color:rgba(255,255,255,0.35); border:1px solid rgba(255,255,255,0.1); }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
  min-width: 280px !important;
  max-width: 280px !important;
  width: 280px !important;
  background: #080b12 !important;
  border-right: 1px solid rgba(255,255,255,0.04);
}
section[data-testid="stSidebar"] > div {
  min-width: 280px !important;
  padding: 1.5rem 1rem !important;
}
section[data-testid="stSidebar"] * { color: rgba(255,255,255,0.65) !important; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stToggle label {
  color: rgba(255,255,255,0.4) !important;
  font-size: 11px !important;
  letter-spacing: 0.8px;
}
button[kind="secondary"] { white-space: nowrap !important; }

/* ── Buttons ── */
.stButton > button {
  background: linear-gradient(135deg, #151c30, #1a2240) !important;
  border: 1px solid rgba(88,166,255,0.18) !important;
  color: rgba(255,255,255,0.75) !important;
  border-radius: 10px !important;
  font-size: 12px !important; font-weight: 600 !important; letter-spacing: 0.5px !important;
  transition: all 0.22s ease !important;
}
.stButton > button:hover {
  border-color: rgba(88,166,255,0.45) !important;
  box-shadow: 0 0 20px rgba(88,166,255,0.1) !important;
  transform: translateY(-1px) !important;
}

/* ── Dataframe ── */
.stDataFrame { border-radius: 16px !important; overflow: hidden !important; }

/* ── Metrics / selects ── */
div[data-baseweb="select"] > div { background: #0f1520 !important; border-color: rgba(255,255,255,0.08) !important; }

/* ── Client name blur ── */
.client-name-wrap { display:inline-flex; align-items:center; gap:8px; }
.client-blurred    { filter:blur(7px); user-select:none; transition:filter .3s ease; }
.client-visible    { filter:none;      transition:filter .3s ease; }

/* ── Action buttons (PDF / Send) ── */
.btn-pdf {
  display:inline-flex; align-items:center; gap:6px;
  background:linear-gradient(135deg,#1a2035,#1e2a45);
  border:1px solid rgba(88,166,255,0.25); border-radius:10px;
  padding:7px 16px; font-size:12px; font-weight:600;
  color:rgba(255,255,255,0.8); cursor:pointer;
  transition:all 0.22s ease; text-decoration:none;
}
.btn-pdf:hover {
  border-color:rgba(88,166,255,0.55);
  box-shadow:0 0 20px rgba(88,166,255,0.12);
  transform:translateY(-1px);
}
.btn-send {
  display:inline-flex; align-items:center; gap:6px;
  background:linear-gradient(135deg,#1a2e20,#1e3525);
  border:1px solid rgba(63,185,80,0.3); border-radius:10px;
  padding:7px 16px; font-size:12px; font-weight:600;
  color:rgba(63,185,80,0.9); cursor:pointer;
  transition:all 0.22s ease;
}
.btn-send:hover {
  border-color:rgba(63,185,80,0.6);
  box-shadow:0 0 20px rgba(63,185,80,0.1);
  transform:translateY(-1px);
}

/* ── Dialog ── */
[data-testid="stDialog"] {
  background:#0d1018 !important;
  border:1px solid rgba(255,255,255,0.08) !important;
  border-radius:16px !important;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
_CLIENTS_FILE = os.path.join(os.path.dirname(__file__), "clients.json")

def _meta_id_for_google(google_cid: str) -> str:
    """Return meta_account_id from clients.json for the given Google Ads customer ID."""
    try:
        with open(_CLIENTS_FILE, encoding="utf-8") as _f:
            for _c in json.load(_f).get("clients", []):
                if _c.get("client_id", "").replace("-", "") == google_cid.replace("-", ""):
                    return _c.get("meta_account_id", "")
    except Exception:
        pass
    return ""


def hex_to_rgba(h: str, a: float) -> str:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


def fmt_currency(v: float, symbol: str = "SAR") -> str:
    if v >= 1_000_000:
        return f"{symbol} {v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{symbol} {v/1_000:.1f}K"
    return f"{symbol} {v:,.2f}"


def fmt_number(v: float) -> str:
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:,.0f}"


def kpi_card(icon: str, label: str, value: str, sub: str,
             accent: str, glow_alpha: float = 0.14) -> str:
    glow   = hex_to_rgba(accent, glow_alpha)
    border = hex_to_rgba(accent, 0.35)
    return f"""
    <div class="kpi-card" style="--accent:{accent};--glow:{glow};--accent-border:{border};">
      <span class="kpi-icon">{icon}</span>
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>"""


# ── Arabic helpers ────────────────────────────────────────────────────────────
def ar(text: str) -> str:
    """Reshape + apply bidi to Arabic string for correct PDF rendering."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


_ar_font_name = "Helvetica"   # updated by _register_arabic_font()

def _register_arabic_font() -> str:
    global _ar_font_name
    if _ar_font_name != "Helvetica":
        return _ar_font_name
    local = os.path.join(os.path.dirname(__file__), "fonts", "Amiri-Regular.ttf")
    candidates = [
        local,
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont("ArabicFont", p))
                _ar_font_name = "ArabicFont"
                return _ar_font_name
            except Exception:
                continue
    # Download Amiri once
    try:
        os.makedirs(os.path.dirname(local), exist_ok=True)
        r = requests.get(
            "https://github.com/alif-type/amiri/raw/master/Amiri-Regular.ttf",
            timeout=20)
        with open(local, "wb") as fh:
            fh.write(r.content)
        pdfmetrics.registerFont(TTFont("ArabicFont", local))
        _ar_font_name = "ArabicFont"
    except Exception:
        pass
    return _ar_font_name


# ── Chart image for PDF ───────────────────────────────────────────────────────
def _chart_image(df_daily: pd.DataFrame) -> bytes | None:
    if df_daily is None or df_daily.empty or len(df_daily) < 2:
        return None
    try:
        df = df_daily.copy()
        df["ROAS"] = df.apply(
            lambda r: round(r["Conv. Value"] / r["Cost"], 2) if r["Cost"] > 0 else 0.0,
            axis=1)

        dates = list(df["Date"].dt.to_pydatetime())
        if len(dates) < 2:
            return None

        fig, ax1 = plt.subplots(figsize=(10, 3.2))
        ax2 = ax1.twinx()
        fig.patch.set_facecolor("#f8fafc")
        ax1.set_facecolor("#f8fafc")

        ax1.fill_between(dates, df["Cost"], alpha=0.2, color="#3b82f6")
        ax1.plot(dates, df["Cost"],        color="#3b82f6", lw=2, label="Spend")
        ax1.plot(dates, df["Conv. Value"], color="#22c55e", lw=2, label="Revenue")

        cost_max = df["Cost"].max()
        conv_max = df["Conversions"].max()
        if cost_max > 0 and conv_max > 0:
            ax1.bar(dates, df["Conversions"] * (cost_max / conv_max * 0.4),
                    color="#f59e0b", alpha=0.35, width=0.6, label="Purchases (scaled)")

        for i in range(len(df) - 1):
            c = "#22c55e" if df["ROAS"].iloc[i] >= 3 else "#ef4444"
            ax2.plot(dates[i:i+2], df["ROAS"].iloc[i:i+2], color=c, lw=2.5)

        ax2.axhline(y=3, color="#94a3b8", lw=1, linestyle="--", alpha=0.6)
        ax2.text(dates[-1], 3.05, "3x", color="#94a3b8", fontsize=7, ha="right")

        ax1.set_ylabel("SAR", color="#64748b", fontsize=8)
        ax2.set_ylabel("ROAS", color="#64748b", fontsize=8)
        for ax in (ax1, ax2):
            ax.tick_params(labelsize=7, colors="#94a3b8")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("#e2e8f0")
            ax.spines["bottom"].set_color("#e2e8f0")
        ax1.grid(axis="y", alpha=0.3, color="#e2e8f0", linestyle="--")
        ax2.grid(False)

        legend_lines = [Line2D([0],[0],color="#3b82f6",lw=2),
                        Line2D([0],[0],color="#22c55e",lw=2),
                        Line2D([0],[0],color="#f59e0b",lw=6,alpha=0.5),
                        Line2D([0],[0],color="#64748b",lw=2)]
        ax1.legend(legend_lines, ["Spend","Revenue","Purchases","ROAS"],
                   loc="upper left", framealpha=0.9, fontsize=7,
                   facecolor="#f8fafc", edgecolor="#e2e8f0")

        plt.tight_layout(pad=0.4)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor="#f8fafc")
        plt.close()
        return buf.getvalue()
    except Exception as e:
        print(f"Chart generation error: {e}")
        plt.close("all")
        return None


# ── PDF generation ────────────────────────────────────────────────────────────
def generate_pdf(
    client_name: str,
    start_str: str, end_str: str,
    kpis: dict,
    df_camp: pd.DataFrame,
    decisions: dict,
    df_daily: pd.DataFrame,
    show_name: bool = True,
) -> bytes:
    import traceback
    try:
        return _generate_pdf_inner(
            client_name, start_str, end_str, kpis,
            df_camp, decisions, df_daily, show_name)
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"PDF ERROR: {tb}")
        # Return a minimal fallback PDF with the error message
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        doc.build([
            Paragraph("PDF generation error", styles["Heading1"]),
            Paragraph(str(exc), styles["Normal"]),
            Paragraph(tb.replace("\n", "<br/>"), styles["Code"]),
        ])
        buf.seek(0)
        pdf_bytes = buf.getvalue()
        buf.close()
        return pdf_bytes


def _generate_pdf_inner(
    client_name: str,
    start_str: str, end_str: str,
    kpis: dict,
    df_camp: pd.DataFrame,
    decisions: dict,
    df_daily: pd.DataFrame,
    show_name: bool = True,
) -> bytes:
    ar_font = _register_arabic_font()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )
    W = A4[0] - 3.6*cm
    story = []

    # ── Colour palette ──
    C_DARK    = HexColor("#1e293b")
    C_MID     = HexColor("#475569")
    C_LIGHT   = HexColor("#f1f5f9")
    C_BORDER  = HexColor("#e2e8f0")
    C_BLUE    = HexColor("#3b82f6")
    C_GREEN   = HexColor("#22c55e")
    C_RED     = HexColor("#ef4444")
    C_YELLOW  = HexColor("#f59e0b")
    C_WHITE   = white

    # ── Styles ──
    S = getSampleStyleSheet()
    def sty(name="Normal", font="Helvetica", size=9, color=C_DARK,
            align=TA_LEFT, leading=13, space_before=0, space_after=0):
        return ParagraphStyle(
            name, fontName=font, fontSize=size, textColor=color,
            alignment=align, leading=leading,
            spaceBefore=space_before, spaceAfter=space_after)

    heading  = sty("H",  "Helvetica-Bold", 20, C_DARK, leading=24)
    sub      = sty("SB", "Helvetica",       9, C_MID,  leading=13)
    metric_l = sty("ML", "Helvetica",       8, C_MID,  TA_CENTER)
    metric_v = sty("MV", "Helvetica-Bold", 16, C_DARK, TA_CENTER, leading=20)
    tbl_h    = sty("TH", "Helvetica-Bold",  8, C_MID,  TA_LEFT)
    tbl_c    = sty("TC", "Helvetica",        8, C_DARK, TA_LEFT, leading=11)
    ar_dec   = sty("AD", ar_font,           10, C_DARK, TA_RIGHT, leading=16)
    ar_rsn   = sty("AR", ar_font,            8, C_MID,  TA_RIGHT, leading=13)

    display_client = client_name if show_name else "*** Hidden ***"

    def _hx(color) -> str:
        """Convert ReportLab color to 6-digit HTML hex (no 0x prefix)."""
        return f"{int(round(color.red*255)):02x}{int(round(color.green*255)):02x}{int(round(color.blue*255)):02x}"

    # ── Header banner ──
    # IMPORTANT: only use Latin-1-safe chars here — Helvetica can't render
    # emoji, arrows, Arabic glyphs or other non-Latin-1 code points.
    hdr = Table([[
        Paragraph("<b>Ads Intelligence</b>",
                  sty("HH", "Helvetica-Bold", 14, C_DARK)),
        Paragraph(f"{display_client}   |   {start_str} to {end_str}",
                  sty("HS", "Helvetica", 9, C_MID, TA_RIGHT)),
    ]], colWidths=[W*0.55, W*0.45])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), C_LIGHT),
        ("LEFTPADDING",  (0,0),(-1,-1), 14),
        ("RIGHTPADDING", (0,0),(-1,-1), 14),
        ("TOPPADDING",   (0,0),(-1,-1), 12),
        ("BOTTOMPADDING",(0,0),(-1,-1), 12),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
    ]))
    story += [hdr, Spacer(1, 0.5*cm)]

    # ── KPI grid (2 rows × 4 cols) ──
    spend   = kpis.get("spend", 0)
    revenue = kpis.get("revenue", 0)
    roas    = kpis.get("roas", 0)
    conv    = kpis.get("conversions", 0)
    cpa     = kpis.get("cpa", 0)
    impr    = kpis.get("impressions", 0)
    clicks  = kpis.get("clicks", 0)
    ctr     = kpis.get("ctr", 0)
    avg_cpc = kpis.get("avg_cpc", 0)
    roas_c  = C_GREEN if roas >= 3 else C_YELLOW if roas >= 1.5 else C_RED
    cpa_c   = C_GREEN if 0 < cpa <= 120 else C_YELLOW if cpa <= 300 else C_RED if cpa > 300 else C_MID

    def kpi_col(lbl, val, color=C_DARK):
        return [Paragraph(lbl, metric_l),
                Paragraph(f"<font color='#{_hx(color)}'>{val}</font>",
                          sty("KV", "Helvetica-Bold", 14, color, TA_CENTER, 18))]

    kpi_row1 = [[
        kpi_col("Total Spend",  fmt_currency(spend)),
        kpi_col("Impressions",  fmt_number(impr)),
        kpi_col("Clicks",       fmt_number(clicks)),
        kpi_col("CTR",          f"{ctr:.2f}%"),
    ]]
    kpi_row2 = [[
        kpi_col("Avg. CPC",     fmt_currency(avg_cpc)),
        kpi_col("Conversions",  f"{conv:.0f}"),
        kpi_col("CPA",          fmt_currency(cpa) if conv > 0 else "-", cpa_c),
        kpi_col("ROAS",         f"{roas:.2f}x", roas_c),
    ]]
    kpi_style = TableStyle([
        ("BOX",          (0,0),(-1,-1), 1,   C_BORDER),
        ("INNERGRID",    (0,0),(-1,-1), 0.5, C_BORDER),
        ("TOPPADDING",   (0,0),(-1,-1), 9),
        ("BOTTOMPADDING",(0,0),(-1,-1), 9),
        ("BACKGROUND",   (0,0),(-1,-1), C_WHITE),
    ])
    for kd in (kpi_row1, kpi_row2):
        t = Table(kd, colWidths=[W/4]*4)
        t.setStyle(kpi_style)
        story.append(t)
        story.append(Spacer(1, 0.18*cm))
    story.append(Spacer(1, 0.28*cm))

    # ── Daily chart ──
    chart_bytes = _chart_image(df_daily)
    if chart_bytes:
        story.append(Paragraph("<b>Daily Performance</b>",
                               sty("CH","Helvetica-Bold",10,C_DARK,leading=16)))
        story.append(Spacer(1, 0.2*cm))
        img_buf = io.BytesIO(chart_bytes)
        story.append(RLImage(img_buf, width=W, height=W*0.3))
        story.append(Spacer(1, 0.45*cm))

    # ── Campaign Performance table ──
    story.append(Paragraph(
        "<b>Campaign Performance</b>",
        sty("CI", "Helvetica-Bold", 10, C_DARK, leading=16)))
    story.append(Spacer(1, 0.2*cm))

    TIER_COLOR = {"strong": C_GREEN, "moderate": C_YELLOW,
                  "weak": C_RED, "paused": C_MID, "insufficient": C_BLUE}
    # ASCII-safe labels only — Helvetica cannot render emoji or Arabic
    TIER_LABEL = {"strong": "Scale Up", "moderate": "Optimize",
                  "weak": "Pause/Fix", "paused": "Paused",
                  "insufficient": "No Data"}

    camp_rows = [
        [Paragraph(h, sty("TH","Helvetica-Bold",8,C_MID,TA_LEFT))
         for h in ["Campaign", "Status", "Spend", "ROAS", "Conversions", "CTR"]]
    ]
    active = df_camp[df_camp["Status"] == "ENABLED"].sort_values("Cost", ascending=False)
    for idx, row in active.iterrows():
        d      = decisions.get(idx, {})
        roas_v = d.get("roas", 0)
        roas_c2= C_GREEN if roas_v >= 3 else C_RED
        tier   = d.get("tier", "moderate")
        tc     = TIER_COLOR.get(tier, C_MID)
        tl     = TIER_LABEL.get(tier, "")

        camp_rows.append([
            Paragraph(str(row["Campaign"])[:40], tbl_c),
            Paragraph(f"<font color='#{_hx(tc)}'>{tl}</font>",
                      sty("ST", "Helvetica-Bold", 8, tc)),
            Paragraph(f"SAR {row['Cost']:.0f}", tbl_c),
            Paragraph(f"<font color='#{_hx(roas_c2)}'>{roas_v:.1f}x</font>",
                      sty("RV", "Helvetica-Bold", 8, roas_c2)),
            Paragraph(f"{row['Conversions']:.0f}", tbl_c),
            Paragraph(f"{row['CTR']:.2f}%", tbl_c),
        ])

    if len(camp_rows) > 1:
        cw = [W*0.38, W*0.15, W*0.13, W*0.12, W*0.12, W*0.10]
        c_tbl = Table(camp_rows, colWidths=cw, repeatRows=1)
        c_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0),  C_LIGHT),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [C_WHITE, HexColor("#f8fafc")]),
            ("BOX",           (0,0),(-1,-1), 0.5, C_BORDER),
            ("INNERGRID",     (0,0),(-1,-1), 0.5, C_BORDER),
            ("TOPPADDING",    (0,0),(-1,-1), 7),
            ("BOTTOMPADDING", (0,0),(-1,-1), 7),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("RIGHTPADDING",  (0,0),(-1,-1), 8),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ]))
        story.append(c_tbl)

    # ── AI Recommendations section ──
    ai_rows = [d for d in decisions.values()
               if d.get("tier") not in ("paused", "insufficient")]
    if ai_rows:
        story += [Spacer(1, 0.4*cm),
                  Paragraph("<b>AI Recommendations</b>",
                             sty("AIH", "Helvetica-Bold", 10, C_DARK, leading=16)),
                  Spacer(1, 0.18*cm)]
        rec_rows = [[Paragraph(h, sty("RH","Helvetica-Bold",8,C_MID,TA_LEFT))
                     for h in ["Campaign", "Decision", "Action"]]]
        for idx, d in decisions.items():
            if d.get("tier") in ("paused", "insufficient"):
                continue
            cname = df_camp.loc[idx, "Campaign"] if idx in df_camp.index else ""
            tc = TIER_COLOR.get(d.get("tier","moderate"), C_MID)
            rec_rows.append([
                Paragraph(str(cname)[:38], tbl_c),
                Paragraph(ar(d.get("decision", "")),
                          sty("RD", ar_font, 8, tc, TA_RIGHT, leading=13)),
                Paragraph(ar(d.get("action", "")[:70]),
                          sty("RA", ar_font, 7.5, C_MID, TA_RIGHT, leading=12)),
            ])
        if len(rec_rows) > 1:
            r_tbl = Table(rec_rows, colWidths=[W*0.28, W*0.36, W*0.36], repeatRows=1)
            r_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,0),  C_LIGHT),
                ("ROWBACKGROUNDS",(0,1),(-1,-1), [C_WHITE, HexColor("#f8fafc")]),
                ("BOX",           (0,0),(-1,-1), 0.5, C_BORDER),
                ("INNERGRID",     (0,0),(-1,-1), 0.5, C_BORDER),
                ("TOPPADDING",    (0,0),(-1,-1), 6),
                ("BOTTOMPADDING", (0,0),(-1,-1), 6),
                ("LEFTPADDING",   (0,0),(-1,-1), 8),
                ("RIGHTPADDING",  (0,0),(-1,-1), 8),
                ("VALIGN",        (0,0),(-1,-1), "TOP"),
            ]))
            story.append(r_tbl)

    # ── ROAS summary + footer ──
    story += [Spacer(1, 0.45*cm),
              HRFlowable(width=W, thickness=0.5, color=C_BORDER),
              Spacer(1, 0.2*cm)]
    roas_status = "Good Performance" if roas >= 3 else "Below Target"
    roas_sc = C_GREEN if roas >= 3 else C_RED
    story.append(Table([[
        Paragraph(
            f"Period ROAS: <b>{roas:.2f}x</b>  -  "
            f"<font color='#{_hx(roas_sc)}'>{roas_status}</font>",
            sty("RS", "Helvetica", 9, C_DARK)),
        Paragraph(f"Generated: {datetime.now().strftime('%b %d, %Y %H:%M')}",
                  sty("GD", "Helvetica", 8, C_MID, TA_RIGHT)),
    ]], colWidths=[W*0.65, W*0.35]))

    story += [Spacer(1, 0.35*cm),
              HRFlowable(width=W, thickness=0.5, color=C_BORDER),
              Spacer(1, 0.15*cm)]
    story.append(Table([[
        Paragraph("Generated by <b>Ads Intelligence</b>",
                  sty("FL","Helvetica",8,C_MID,TA_LEFT)),
        Paragraph("ads-dashboard.yousefzaiter.com",
                  sty("FR","Helvetica",8,C_BLUE,TA_RIGHT)),
    ]], colWidths=[W*0.5, W*0.5]))

    doc.build(story)
    buf.seek(0)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


# ── Email sending ─────────────────────────────────────────────────────────────
def send_email(to_addr: str, pdf_bytes: bytes, client_name: str,
               start_str: str, end_str: str) -> tuple[bool, str]:
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    sender   = env.get("EMAIL_SENDER", "")
    password = env.get("EMAIL_APP_PASSWORD", "")
    if not sender or not password:
        return False, "EMAIL_SENDER و EMAIL_APP_PASSWORD غير مضبوطين في ملف .env"

    msg = MIMEMultipart()
    msg["From"]    = sender
    msg["To"]      = to_addr
    msg["Subject"] = f"تقرير الأداء الإعلاني — {client_name} ({start_str} → {end_str})"

    body = (
        f"عزيزنا العميل،\n\n"
        f"يسعدنا مشاركتك تقرير الأداء الإعلاني الخاص بك للفترة من {start_str} إلى {end_str}.\n"
        f"تقرير الأداء الإعلاني الخاص بك مرفق.\n\n"
        f"للاستفسار يرجى التواصل معنا.\n\n"
        f"مع التحية،\nفريق Ads Intelligence"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    fname = f"report_{client_name}_{end_str}.pdf".replace(" ", "_")
    part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
    msg.attach(part)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(sender, password)
            srv.sendmail(sender, to_addr, msg.as_string())
        return True, "تم إرسال التقرير بنجاح ✓"
    except Exception as e:
        return False, f"فشل الإرسال: {e}"


# ── Send modal ────────────────────────────────────────────────────────────────
@st.dialog("📤 إرسال التقرير")
def send_modal(pdf_bytes: bytes, client_name: str,
               start_str: str, end_str: str) -> None:
    st.markdown("""
    <div style='font-size:13px;color:rgba(255,255,255,0.5);margin-bottom:16px'>
      أرسل التقرير مباشرةً عبر البريد الإلكتروني أو شارك رابط واتساب
    </div>""", unsafe_allow_html=True)

    tab_email, tab_wa = st.tabs(["📧 البريد الإلكتروني", "💬 واتساب"])

    with tab_email:
        email = st.text_input("البريد الإلكتروني", placeholder="client@example.com",
                              label_visibility="visible")
        if st.button("إرسال", key="send_email_btn", use_container_width=True):
            if not email:
                st.warning("أدخل عنوان البريد الإلكتروني أولاً")
            else:
                with st.spinner("جارٍ الإرسال…"):
                    ok, msg = send_email(email, pdf_bytes, client_name,
                                         start_str, end_str)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
        st.caption("يتطلب ضبط EMAIL_SENDER و EMAIL_APP_PASSWORD في ملف .env")

    with tab_wa:
        phone = st.text_input("رقم الهاتف (مع رمز الدولة)", placeholder="+966501234567",
                              label_visibility="visible")
        if phone:
            msg_text = (
                f"تقرير الأداء الإعلاني الخاص بك جاهز 📊\n\n"
                f"العميل: {client_name}\n"
                f"الفترة: {start_str} → {end_str}\n\n"
                f"يمكنك الاطلاع على التقرير المرفق."
            )
            number  = phone.strip().replace(" ", "").replace("+", "")
            wa_link = f"https://wa.me/{number}?text={urllib.parse.quote(msg_text)}"
            st.markdown(
                f'<a href="{wa_link}" target="_blank" class="btn-send" '
                f'style="display:inline-block;margin-top:8px;text-decoration:none">'
                f'فتح واتساب وإرسال الرسالة ↗</a>',
                unsafe_allow_html=True)
            st.caption("سيُفتح تطبيق واتساب مع الرسالة المملوءة مسبقاً")


# ── Credentials ───────────────────────────────────────────────────────────────
@st.cache_resource(ttl=3500)
def get_access_token():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     env["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": env["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": env["GOOGLE_ADS_REFRESH_TOKEN"],
        "grant_type":    "refresh_token",
    })
    resp.raise_for_status()
    return (resp.json()["access_token"],
            env["GOOGLE_ADS_DEVELOPER_TOKEN"],
            env.get("GOOGLE_ADS_CUSTOMER_ID", "").replace("-", ""),
            env.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", ""))


# ── Client list from API ──────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_clients(token: str, dev_token: str, root_cid: str, mcc_id: str) -> dict[str, str]:
    """Return {descriptive_name: customer_id} for all client accounts under the MCC."""
    clients: dict[str, str] = {}
    mcc_id = mcc_id.replace("-", "").strip()
    try:
        r = requests.post(
            f"https://googleads.googleapis.com/v20/customers/{mcc_id}/googleAds:search",
            headers={
                "Authorization": f"Bearer {token}",
                "developer-token": dev_token,
                "content-type": "application/json",
                "login-customer-id": mcc_id,
            },
            json={
                "query": """
                    SELECT
                      customer_client.client_customer,
                      customer_client.descriptive_name,
                      customer_client.manager,
                      customer_client.status
                    FROM customer_client
                    WHERE customer_client.manager = FALSE
                    AND customer_client.status = 'ENABLED'
                """
            },
            timeout=10,
        )
        if r.status_code == 200:
            for row in r.json().get("results", []):
                client = row["customerClient"]
                cid = client["clientCustomer"].split("/")[-1]
                name = client.get("descriptiveName") or cid
                clients[name] = cid
    except Exception:
        pass
    return clients if clients else {root_cid: root_cid}


# ── Privacy mask ──────────────────────────────────────────────────────────────
def mask_name(name: str, show: bool) -> str:
    """Return real name when show=True, partial mask with lock when False."""
    if show:
        return name
    return "🔒 " + name[:2] + "******"


# ── Google Ads query ──────────────────────────────────────────────────────────
def gaql(query: str, customer_id: str, token: str, dev_token: str, mcc_id: str) -> list:
    mcc_id = mcc_id.replace("-", "").strip()
    customer_id = customer_id.replace("-", "").strip()
    url = f"https://googleads.googleapis.com/v20/customers/{customer_id}/googleAds:search"
    headers = {
        "Authorization":     f"Bearer {token}",
        "developer-token":   dev_token,
        "content-type":      "application/json",
        "login-customer-id": mcc_id,
    }
    resp = requests.post(url, headers=headers, json={"query": query})
    if resp.status_code != 200:
        st.error(f"API error {resp.status_code}: {resp.text[:400]}")
        return []
    return resp.json().get("results", [])


# ── Data fetchers ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_campaign_data(customer_id, token, dev_token, start, end, mcc_id=""):
    q = f"""
    SELECT
      campaign.id, campaign.name, campaign.status,
      campaign.advertising_channel_type,
      metrics.impressions, metrics.clicks, metrics.cost_micros,
      metrics.ctr, metrics.average_cpc, metrics.conversions,
      metrics.conversions_value, metrics.cost_per_conversion,
      metrics.search_impression_share
    FROM campaign
    WHERE segments.date BETWEEN '{start}' AND '{end}'
      AND campaign.status != 'REMOVED'
    ORDER BY metrics.cost_micros DESC
    """
    rows = gaql(q, customer_id, token, dev_token, mcc_id)
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        c, m = r.get("campaign", {}), r.get("metrics", {})
        records.append({
            "Campaign":    c.get("name", ""),
            "Status":      c.get("status", ""),
            "Type":        c.get("advertisingChannelType", ""),
            "Impressions": int(m.get("impressions", 0)),
            "Clicks":      int(m.get("clicks", 0)),
            "Cost":        round(float(m.get("costMicros", 0)) / 1e6, 2),
            "CTR":         round(float(m.get("ctr", 0)) * 100, 2),
            "Avg CPC":     round(float(m.get("averageCpc", 0)) / 1e6, 2),
            "Conversions": round(float(m.get("conversions", 0)), 1),
            "Conv. Value": round(float(m.get("conversionsValue", 0)), 2),
            "CPA":         round(float(m.get("costPerConversion", 0)) / 1e6, 2),
            "Imp. Share":  round(float(m.get("searchImpressionShare", 0)) * 100, 1)
                           if m.get("searchImpressionShare") else None,
        })
    return pd.DataFrame(records)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_daily_data(customer_id, token, dev_token, start, end, mcc_id=""):
    q = f"""
    SELECT
      segments.date,
      metrics.impressions, metrics.clicks, metrics.cost_micros,
      metrics.conversions, metrics.conversions_value
    FROM customer
    WHERE segments.date BETWEEN '{start}' AND '{end}'
    ORDER BY segments.date ASC
    """
    rows = gaql(q, customer_id, token, dev_token, mcc_id)
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        seg, m = r.get("segments", {}), r.get("metrics", {})
        records.append({
            "Date":        seg.get("date", ""),
            "Impressions": int(m.get("impressions", 0)),
            "Clicks":      int(m.get("clicks", 0)),
            "Cost":        round(float(m.get("costMicros", 0)) / 1e6, 2),
            "Conversions": round(float(m.get("conversions", 0)), 1),
            "Conv. Value": round(float(m.get("conversionsValue", 0)), 2),
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


# ── AI Decision Engine ────────────────────────────────────────────────────────
TYPE_LABELS = {
    "SEARCH": "Search", "SHOPPING": "Shopping",
    "PERFORMANCE_MAX": "Perf. Max", "DISPLAY": "Display",
    "VIDEO": "Video", "DEMAND_GEN": "Demand Gen",
}

def ai_decision(row: pd.Series) -> dict:
    spend       = float(row.get("Cost", 0))
    clicks      = int(row.get("Clicks", 0))
    impressions = int(row.get("Impressions", 0))
    conversions = float(row.get("Conversions", 0))
    conv_value  = float(row.get("Conv. Value", 0))
    ctr         = float(row.get("CTR", 0))
    cpa         = float(row.get("CPA", 0))
    avg_cpc     = float(row.get("Avg CPC", 0))
    status      = row.get("Status", "")
    camp_type   = str(row.get("Type", "")).upper()

    roas      = round(conv_value / spend, 2) if spend > 0 else 0.0
    conv_rate = round(conversions / clicks * 100, 2) if clicks > 0 else 0.0

    # ── Paused ──────────────────────────────────────────────────────────────────
    if status != "ENABLED":
        return dict(tier="paused", emoji="⏸", label="موقوفة", color="#3d4354",
                    decision="الحملة موقوفة حالياً",
                    reason="لا توجد بيانات أداء في الفترة المحددة",
                    action="أعد تفعيلها إذا كانت ذات صلة بالموسم أو المنتج الحالي",
                    outcome="",
                    roas=0, conv_rate=0, spend=spend)

    # ── Insufficient data ───────────────────────────────────────────────────────
    if impressions < 50 and spend < 3:
        return dict(tier="insufficient", emoji="🔵", label="بيانات غير كافية", color="#58a6ff",
                    decision="بيانات غير كافية للتقييم",
                    reason=f"ظهور {impressions:,} · إنفاق SAR {spend:.2f} — لا تكفي لحكم دقيق",
                    action="شغّل الحملة 3–5 أيام إضافية قبل اتخاذ أي قرار",
                    outcome="تقييم دقيق بعد تجميع بيانات كافية",
                    roas=roas, conv_rate=conv_rate, spend=spend)

    # ── CTR benchmarks ──────────────────────────────────────────────────────────
    is_search   = "SEARCH"   in camp_type
    is_shopping = "SHOPPING" in camp_type
    is_pmax     = "PERFORMANCE_MAX" in camp_type
    is_dgen     = "DEMAND_GEN" in camp_type

    ctr_target = 3.0 if is_search else 0.8 if is_shopping else 0.5

    # ── PAUSE / FIX (immediate action needed) ──────────────────────────────────
    if conversions == 0 and spend >= 40:
        return dict(
            tier="weak", emoji="🔴", label="أوقف — إنفاق بلا نتائج", color="#f85149",
            decision="أوقف الحملة — إنفاق بدون تحويلات",
            reason=f"صُرف SAR {spend:.0f} بدون أي تحويل — المشكلة في التتبع أو الاستهداف أو الصفحة",
            action="أوقف فوراً وتحقق من tracking · راجع الجمهور والإعلانات من الصفر",
            outcome="وقف نزيف الإنفاق — يمكن إعادة الإطلاق بعد إصلاح التتبع",
            roas=roas, conv_rate=conv_rate, spend=spend,
        )

    if roas > 0 and roas < 1 and spend >= 20:
        return dict(
            tier="weak", emoji="🔴", label="أوقف — الحملة تخسر", color="#f85149",
            decision="أوقف الحملة — ROAS أقل من 1×",
            reason=f"ROAS {roas:.2f}× — كل SAR 1 إنفاق تعود بـ SAR {roas:.2f} فقط · إجمالي خسارة مؤكدة",
            action="أوقف الحملة فوراً أو غيّر الاستراتيجية كلياً قبل الاستمرار",
            outcome="وقف الخسائر الفورية · إعادة البناء بـ bidding strategy مختلف",
            roas=roas, conv_rate=conv_rate, spend=spend,
        )

    if cpa > 300 and conversions > 0 and spend >= 30:
        return dict(
            tier="weak", emoji="🔴", label="Fix — CPA مرتفع جداً", color="#f85149",
            decision="CPA مرتفع جداً — راجع الـ Bidding",
            reason=f"تكلفة التحويل SAR {cpa:.0f} — أعلى من المستوى الصحي بشكل كبير",
            action="غيّر الـ bidding strategy · ضيّق الاستهداف · راجع جودة العروض",
            outcome="خفض CPA إلى أقل من SAR 150 سيجعل الحملة مربحة",
            roas=roas, conv_rate=conv_rate, spend=spend,
        )

    # ── SCALE (increase budget) ─────────────────────────────────────────────────
    if roas >= 3 and conv_rate >= 2 and conversions > 0:
        budget_inc = round(spend * 0.25, 0)
        return dict(
            tier="strong", emoji="🟢", label="Scale — ارفع الميزانية", color="#3fb950",
            decision="ارفع الميزانية 20-30%",
            reason=(
                f"ROAS {roas:.1f}× فوق الهدف 3× · "
                f"معدل التحويل {conv_rate:.1f}% ممتاز · "
                f"CPC {avg_cpc:.2f} SAR كفوء"
            ),
            action=f"ارفع الميزانية اليومية بـ ~SAR {budget_inc:.0f} (20-30%) واستغل الزخم الحالي",
            outcome="متوقع زيادة التحويلات 20-25% مع الحفاظ على نفس الكفاءة",
            roas=roas, conv_rate=conv_rate, spend=spend,
        )

    # ── OPTIMIZE — sub-cases ────────────────────────────────────────────────────
    # Good ROAS but low conv rate → landing page
    if roas >= 1.5 and conv_rate < 1 and clicks >= 50:
        return dict(
            tier="moderate", emoji="🟡", label="Optimize — صفحة هبوط", color="#e3b341",
            decision="Optimize — مشكلة في صفحة الهبوط",
            reason=(
                f"ROAS {roas:.1f}× جيد لكن معدل التحويل {conv_rate:.1f}% ضعيف رغم {clicks:,} نقرة · "
                "المشكلة في الصفحة وليس الإعلان"
            ),
            action="حسّن سرعة الصفحة · اجعل الـ CTA أوضح · اختبر A/B على الهيدر",
            outcome="رفع Conv Rate إلى 2%+ سيزيد ROAS بدون زيادة الميزانية",
            roas=roas, conv_rate=conv_rate, spend=spend,
        )

    # High CPC + low conv rate → audience/copy
    if avg_cpc > 5 and conv_rate < 1 and clicks >= 20:
        return dict(
            tier="moderate", emoji="🟡", label="Optimize — CPC مرتفع", color="#e3b341",
            decision="Optimize — تكلفة النقرة مرتفعة مع تحويل ضعيف",
            reason=(
                f"CPC {avg_cpc:.2f} SAR مرتفع · "
                f"معدل التحويل {conv_rate:.1f}% ضعيف · "
                "مشكلة في الجمهور أو الإعلانات"
            ),
            action="راجع الجمهور المستهدف · جرّب creative جديد · أضف negative keywords",
            outcome="خفض CPC أو رفع Conv Rate سيحسن ROAS بشكل كبير",
            roas=roas, conv_rate=conv_rate, spend=spend,
        )

    # Low CTR → creative/audience
    if ctr < ctr_target and impressions >= 500 and not is_dgen:
        return dict(
            tier="moderate", emoji="🟡", label="Optimize — CTR منخفض", color="#e3b341",
            decision="Optimize — CTR منخفض، الإعلانات لا تجذب الانتباه",
            reason=(
                f"CTR {ctr:.2f}% أقل من الهدف {ctr_target:.1f}% · "
                f"الإعلان يظهر {impressions:,} مرة لكن لا يُضغط عليه"
            ),
            action="جرّب عناوين ومرئيات جديدة · اختبر 3-5 إعلانات مختلفة",
            outcome="رفع CTR إلى الهدف سيزيد النقرات بنفس الإنفاق",
            roas=roas, conv_rate=conv_rate, spend=spend,
        )

    # Good conv rate but low ROAS → pricing/AOV issue
    if conv_rate >= 2 and 0 < roas < 3:
        return dict(
            tier="moderate", emoji="🟡", label="Optimize — قيمة الطلب", color="#e3b341",
            decision="Optimize — معدل التحويل جيد لكن قيمة الطلب منخفضة",
            reason=(
                f"Conv Rate {conv_rate:.1f}% ممتاز · "
                f"لكن ROAS {roas:.1f}× دون الهدف 3× · "
                "قيمة الأوردر منخفضة"
            ),
            action="أضف upsell/cross-sell · ارفع الحد الأدنى للطلب · جرّب bundle offers",
            outcome="رفع متوسط قيمة الأوردر 20% سيرفع ROAS فوق الهدف 3×",
            roas=roas, conv_rate=conv_rate, spend=spend,
        )

    # No conversions with moderate spend
    if conversions == 0 and spend >= 10:
        return dict(
            tier="moderate", emoji="🟡", label="Optimize — لا تحويلات", color="#e3b341",
            decision="Optimize — لا تحويلات بعد",
            reason=f"إنفاق SAR {spend:.0f} بدون تحويلات حتى الآن · قد تحتاج الحملة وقتاً للتعلم",
            action="تأكد من صحة تتبع التحويلات · أعطِ الحملة 3-5 أيام إضافية",
            outcome="إذا لم تتحقق تحويلات بعد 7 أيام، راجع الاستهداف جذرياً",
            roas=roas, conv_rate=conv_rate, spend=spend,
        )

    # ── GOOD — maintain ─────────────────────────────────────────────────────────
    tier  = "strong" if roas >= 3 else "moderate"
    emoji = "🟢" if tier == "strong" else "🟡"
    label = "الحملة في المسار الصح" if tier == "strong" else "أداء مقبول"
    color = "#3fb950" if tier == "strong" else "#e3b341"

    reason_parts = [f"ROAS {roas:.1f}×", f"CTR {ctr:.2f}%"]
    if conv_rate > 0:
        reason_parts.append(f"Conv Rate {conv_rate:.1f}%")
    if cpa > 0:
        reason_parts.append(f"CPA SAR {cpa:.0f}")

    return dict(
        tier=tier, emoji=emoji, label=label, color=color,
        decision="الحملة في المسار الصح — حافظ على الإعدادات",
        reason=" · ".join(reason_parts),
        action="راقب الأداء يومياً وابحث عن فرص التوسع عند استقرار الـ ROAS",
        outcome="استمرار الأداء الجيد مع احتمال تحسن تدريجي",
        roas=roas, conv_rate=conv_rate, spend=spend,
    )


def campaign_card(row: pd.Series, d: dict) -> str:
    """Render a single campaign as an HTML card with AI recommendation."""
    name      = row["Campaign"]
    status    = row["Status"]
    color     = d["color"]
    ctype     = TYPE_LABELS.get(str(row.get("Type","")).upper(), str(row.get("Type","")))
    roas_v    = d["roas"]
    cr_v      = d.get("conv_rate", 0)

    is_active  = status == "ENABLED"
    has_data   = row["Impressions"] > 0 or row["Cost"] > 0
    bg_tint    = hex_to_rgba(color, 0.045)
    border_col = hex_to_rgba(color, 0.18)

    status_dot = (
        '<span style="font-size:10px;color:#3fb950;font-weight:700">● نشطة</span>'
        if is_active else
        '<span style="font-size:10px;color:rgba(255,255,255,0.2);font-weight:500">○ موقوفة</span>'
    )

    if not is_active and not has_data:
        return f"""
        <div style="background:#090c14;border:1px solid rgba(255,255,255,0.04);
                    border-radius:10px;padding:10px 16px;margin-bottom:5px;
                    display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:12.5px;font-weight:500;color:rgba(255,255,255,0.25);
                       max-width:60%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
                title="{name}">{name}</span>
          <span style="font-size:10.5px;color:rgba(255,255,255,0.18)">⏸ موقوفة</span>
        </div>"""

    def chip(label, val, highlight_color=None):
        vc = highlight_color or "rgba(255,255,255,0.75)"
        return (
            f'<div style="text-align:center;padding:0 10px">'
            f'<div style="font-size:9px;color:rgba(255,255,255,0.22);letter-spacing:.5px;'
            f'text-transform:uppercase;margin-bottom:2px">{label}</div>'
            f'<div style="font-size:13px;font-weight:700;color:{vc}">{val}</div>'
            f'</div>'
        )

    roas_color = "#3fb950" if roas_v >= 3 else "#f85149" if 0 < roas_v < 1 else "#e3b341" if roas_v > 0 else "rgba(255,255,255,0.3)"
    cr_color   = "#3fb950" if cr_v >= 2 else "#e3b341" if cr_v >= 0.5 else "#f85149" if cr_v > 0 else "rgba(255,255,255,0.3)"

    metrics_html = (
        chip("Impr.", fmt_number(row["Impressions"])) +
        chip("Clicks", f"{row['Clicks']:,}") +
        chip("CTR", f"{row['CTR']:.2f}%") +
        chip("Spend", f"SAR {row['Cost']:,.0f}") +
        chip("Conv.", f"{row['Conversions']:.0f}") +
        chip("Conv. Rate", f"{cr_v:.1f}%", cr_color) +
        (chip("ROAS", f"{roas_v:.1f}×", roas_color) if roas_v > 0 else "")
    )

    tier_badge = (
        f'<div style="display:flex;align-items:center;gap:6px;padding:5px 12px;'
        f'background:{hex_to_rgba(color,0.1)};border:1px solid {border_col};'
        f'border-radius:20px;flex-shrink:0">'
        f'<span style="font-size:13px">{d["emoji"]}</span>'
        f'<span style="font-size:11px;font-weight:700;color:{color};white-space:nowrap">{d["label"]}</span>'
        f'</div>'
    )

    outcome_html = (
        f'<div style="margin-top:6px;font-size:11.5px;color:rgba(255,255,255,0.2);'
        f'line-height:1.5;display:flex;align-items:flex-start;gap:5px;direction:rtl">'
        f'<span style="color:{color};flex-shrink:0">→</span>'
        f'<span>{d.get("outcome","")}</span></div>'
    ) if d.get("outcome") else ""

    ai_html = (
        f'<div style="padding:14px 20px 16px;border-top:1px solid rgba(255,255,255,0.04);'
        f'background:{bg_tint};direction:rtl;text-align:right">'
        f'<div style="font-size:14.5px;font-weight:800;color:{color};margin-bottom:6px;'
        f'line-height:1.3">{d["emoji"]} {d["decision"]}</div>'
        f'<div style="font-size:12.5px;color:rgba(255,255,255,0.48);margin-bottom:8px;'
        f'line-height:1.65">{d["reason"]}</div>'
        f'<div style="font-size:12px;color:rgba(255,255,255,0.65);line-height:1.5;'
        f'background:rgba(255,255,255,0.03);border-radius:8px;padding:8px 12px;'
        f'border-right:2px solid {color}">💡 {d["action"]}</div>'
        f'{outcome_html}'
        f'</div>'
    )

    return f"""
    <div style="background:#0d1018;border:1px solid rgba(255,255,255,0.055);
                border-left:3px solid {color};border-radius:14px;
                margin-bottom:10px;overflow:hidden">
      <div style="padding:14px 18px;display:flex;justify-content:space-between;
                  align-items:center;gap:16px;flex-wrap:wrap">
        <div style="min-width:180px;flex-shrink:1">
          <div style="font-size:13.5px;font-weight:600;color:#e6edf3;
                      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:280px"
               title="{name}">{name[:42]}{"…" if len(name)>42 else ""}</div>
          <div style="margin-top:4px;display:flex;align-items:center;gap:8px">
            {status_dot}
            <span style="font-size:9.5px;color:rgba(255,255,255,0.18);
                         background:rgba(255,255,255,0.05);padding:1px 7px;
                         border-radius:8px">{ctype}</span>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">{metrics_html}</div>
        {tier_badge}
      </div>
      {ai_html}
    </div>"""


# ── Session state ─────────────────────────────────────────────────────────────
st.session_state.setdefault("client_name_visible", False)
st.session_state.setdefault("_show_send_panel", False)
st.session_state.setdefault("meta_view", "campaigns")       # campaigns | adsets | ads
st.session_state.setdefault("meta_selected_campaign", None) # {id, name}
st.session_state.setdefault("meta_selected_adset", None)    # {id, name}

# ── Auth (needed early for client list) ───────────────────────────────────────
try:
    token, dev_token, root_cid, mcc_id = get_access_token()
except Exception as e:
    st.error(f"Authentication failed: {e}")
    st.stop()

clients = fetch_clients(token, dev_token, root_cid, mcc_id)

# ── Meta pre-fetch (needed before sidebar renders) ────────────────────────────
_active_platform = st.session_state.get("_platform_radio", "🔵  Google Ads")
_meta_token      = os.getenv("META_ACCESS_TOKEN", "")
_meta_accounts: list[dict] = []
_meta_ready      = False   # True when module imported successfully

if _meta_token:
    try:
        from meta_ads_server import (
            get_meta_token, fetch_meta_accounts,
            fetch_meta_campaigns, fetch_meta_daily,
            fetch_meta_adsets, fetch_meta_ads_list,
        )
        _meta_ready = True
    except Exception as _meta_import_err:
        _meta_token = ""   # module missing — clear token

if _meta_ready:
    try:
        _meta_accounts = fetch_meta_accounts(_meta_token)
    except Exception:
        _meta_accounts = []   # API error: keep token for cross-platform fetches

# ── Role helpers ──────────────────────────────────────────────────────────────
_current_username = st.session_state.get("username", "")
_user_info        = get_user(_current_username)
_is_admin         = _user_info.get("role") == "admin"
_display_name     = _user_info.get("display_name", _current_username)

# Clean the URL for client users — token is already in session_state
if not _is_admin and st.query_params.get("token"):
    st.query_params.clear()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    if _is_admin:
        st.markdown("""
        <div style='padding:4px 0 20px'>
          <div style='font-size:17px;font-weight:800;color:#f0f6fc;letter-spacing:-0.5px'>⚡ Ads Intelligence</div>
          <div style='font-size:11px;color:rgba(255,255,255,0.3);margin-top:3px'>Media Buying Dashboard</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='padding:4px 0 20px'>
          <div style='font-size:17px;font-weight:800;color:#f0f6fc;letter-spacing:-0.5px'>{_display_name}</div>
          <div style='font-size:11px;color:rgba(255,255,255,0.3);margin-top:3px;direction:rtl'>تقرير الأداء الإعلاني</div>
        </div>
        """, unsafe_allow_html=True)
    st.divider()

    vis_sidebar = st.session_state.get("client_name_visible", False)

    # ── Logout ────────────────────────────────────────────────────────────────
    current_username = _current_username
    user_info        = _user_info

    col_user, col_logout = st.columns([2, 1])
    col_user.markdown(
        f"<div style='font-size:12px;color:rgba(255,255,255,0.4);padding-top:6px'>"
        f"👤 {current_username}</div>",
        unsafe_allow_html=True,
    )
    if col_logout.button("Logout", use_container_width=True):
        do_logout()

    st.divider()

    # ── Account selector (platform-aware) ────────────────────────────────────
    if user_info.get("role") == "admin":
        if _active_platform == "🔵  Google Ads":
            if not vis_sidebar:
                st.markdown("""
                <style>
                [data-testid="stSidebar"] div[data-baseweb="select"] > div {
                  border: 1px solid #ff4d4f !important;
                  box-shadow: 0 0 8px rgba(255,77,79,0.3) !important;
                }
                </style>
                """, unsafe_allow_html=True)
            client_options = [
                {"id": cid, "name": name, "display": mask_name(name, vis_sidebar)}
                for name, cid in clients.items()
            ]
            sel = st.selectbox(
                "CLIENT",
                options=client_options,
                format_func=lambda x: x["display"],
                label_visibility="visible",
                key="selected_client",
            )
            selected_client      = sel["name"]
            selected_customer_id = sel["id"]
            selected_meta_acct_id   = ""
            selected_meta_acct_name = ""
        else:  # Meta Ads
            selected_client      = ""
            selected_customer_id = ""
            if _meta_accounts:
                _ma_sb_opts = {a["name"]: a["id"] for a in _meta_accounts}
                _ma_sb_sel  = st.selectbox(
                    "META ACCOUNT",
                    list(_ma_sb_opts.keys()),
                    key="meta_account_sel",
                    label_visibility="visible",
                )
                selected_meta_acct_id   = _ma_sb_opts[_ma_sb_sel]
                selected_meta_acct_name = _ma_sb_sel
            else:
                st.warning("No Meta accounts found")
                selected_meta_acct_id   = ""
                selected_meta_acct_name = ""
    else:
        assigned_cid  = user_info.get("client_id", "")
        assigned_name = next((n for n, c in clients.items() if c == assigned_cid), _display_name)
        selected_client         = assigned_name
        selected_customer_id    = assigned_cid
        selected_meta_acct_id   = ""
        selected_meta_acct_name = ""

    if _is_admin:
        st.divider()

    today = date.today()
    preset = st.selectbox("DATE RANGE", [
        "Today", "Yesterday", "Last 7 days", "Last 14 days",
        "Last 30 days", "This month", "Custom"
    ], index=2, label_visibility="visible")

    if preset == "Today":
        start_date, end_date = today, today
    elif preset == "Yesterday":
        start_date = end_date = today - timedelta(days=1)
    elif preset == "Last 7 days":
        start_date, end_date = today - timedelta(days=6), today
    elif preset == "Last 14 days":
        start_date, end_date = today - timedelta(days=13), today
    elif preset == "Last 30 days":
        start_date, end_date = today - timedelta(days=29), today
    elif preset == "This month":
        start_date = today.replace(day=1); end_date = today
    else:
        c1, c2 = st.columns(2)
        start_date = c1.date_input("From", today - timedelta(days=6))
        end_date   = c2.date_input("To",   today)

    st.divider()
    show_paused = st.toggle("Show paused campaigns", value=False)

    st.divider()
    if st.button("↺  Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if _is_admin:
        _src_api  = "Meta Marketing API v20" if _active_platform == "📘  Meta Ads" else "Google Ads API v20"
        _src_note = "Token valid ~60 days"    if _active_platform == "📘  Meta Ads" else "Auto-refresh every 5 min"
        st.markdown(f"""
        <div style='margin-top:24px;padding:14px;background:rgba(255,255,255,0.03);
                    border-radius:12px;border:1px solid rgba(255,255,255,0.05)'>
          <div style='font-size:10px;color:rgba(255,255,255,0.2);letter-spacing:1px;
                      text-transform:uppercase;margin-bottom:8px'>Data source</div>
          <div style='font-size:11.5px;color:rgba(255,255,255,0.45);font-weight:500'>
            {_src_api}</div>
          <div style='font-size:10.5px;color:rgba(255,255,255,0.2);margin-top:2px'>
            {_src_note}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Admin Panel nav (admin-only) ──────────────────────────────────────────
    if _is_admin:
        st.divider()
        _page = st.radio(
            "NAVIGATE",
            ["📊  Dashboard", "✍️  Campaign Creator", "⚙️  Admin Panel"],
            index=0,
            key="_nav_page",
            label_visibility="visible",
        )
    else:
        _page = "📊  Dashboard"

# ── Page routing (admin-only pages) ───────────────────────────────────────────
if _page == "⚙️  Admin Panel":
    from admin_panel import render_admin_panel
    render_admin_panel()
    st.stop()

if _page == "✍️  Campaign Creator":
    from campaign_creator import render_campaign_creator
    render_campaign_creator()
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────
start_str = start_date.strftime("%Y-%m-%d")
end_str   = end_date.strftime("%Y-%m-%d")

vis = st.session_state["client_name_visible"] if _is_admin else True

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    if _is_admin:
        st.markdown(f"""
        <div style='padding:8px 0 4px'>
          <div style='font-size:26px;font-weight:900;color:#f0f6fc;letter-spacing:-1px;line-height:1'>
            Campaign Performance
          </div>
          <div style='font-size:13px;color:rgba(255,255,255,0.28);margin-top:5px;font-weight:400;
                      display:flex;align-items:center;gap:8px;flex-wrap:wrap'>
            <span style='font-weight:600;color:rgba(255,255,255,0.55)'>{mask_name(selected_client, vis)}</span>
            <span style='color:rgba(255,255,255,0.12)'>·</span>
            <span style='font-size:11.5px'>{mask_name(selected_customer_id, vis)}</span>
            <span style='color:rgba(255,255,255,0.12)'>·</span>
            <span>{start_date.strftime("%b %d")} – {end_date.strftime("%b %d, %Y")}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='padding:8px 0 4px'>
          <div style='font-size:26px;font-weight:900;color:#f0f6fc;letter-spacing:-1px;line-height:1;
                      direction:rtl'>تقرير الأداء الإعلاني</div>
          <div style='font-size:13px;color:rgba(255,255,255,0.28);margin-top:5px;font-weight:400;
                      display:flex;align-items:center;gap:8px;flex-wrap:wrap'>
            <span style='font-weight:600;color:rgba(255,255,255,0.55)'>{_display_name}</span>
            <span style='color:rgba(255,255,255,0.12)'>·</span>
            <span>{start_date.strftime("%b %d")} – {end_date.strftime("%b %d, %Y")}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
with col_h2:
    st.markdown("""
    <div style='display:flex;justify-content:flex-end;align-items:flex-start;padding-top:10px;gap:10px'>
      <div class='pill-live'><span class='dot-pulse'></span>Live</div>
    </div>
    """, unsafe_allow_html=True)
    if _is_admin:
        eye_label = "🙈 Hide Client" if vis else "👁 Show Client"
        if st.button(eye_label, use_container_width=True, key="toggle_vis_btn"):
            st.session_state["client_name_visible"] = not vis
            st.rerun()

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── Cross-Platform Overview (admin only, when client has both accounts) ───────
_cross_meta_raw = _meta_id_for_google(selected_customer_id) if selected_customer_id else ""
_cross_meta_id  = (f"act_{_cross_meta_raw}" if _cross_meta_raw and not _cross_meta_raw.startswith("act_")
                   else _cross_meta_raw)

# ── Debug panel (always visible to admin) ─────────────────────────────────────
if _is_admin:
    with st.expander("🔍 Debug — Cross-Platform", expanded=False):
        st.write({
            "selected_client":      selected_client,
            "selected_customer_id": selected_customer_id,
            "cross_meta_raw":       _cross_meta_raw,
            "cross_meta_id":        _cross_meta_id,
            "meta_token_set":       bool(_meta_token),
            "meta_token_prefix":    _meta_token[:20] + "…" if _meta_token else "(empty)",
            "meta_ready":           _meta_ready,
            "meta_accounts_count":  len(_meta_accounts),
            "active_platform":      _active_platform,
            "is_admin":             _is_admin,
        })

if _is_admin and _cross_meta_id and _meta_token and _meta_ready:
    with st.spinner("Loading cross-platform data…"):
        _cp_gdf  = fetch_campaign_data(selected_customer_id, token, dev_token, start_str, end_str, mcc_id)
        _cp_gday = fetch_daily_data(selected_customer_id, token, dev_token, start_str, end_str, mcc_id)
        _cp_mdf  = fetch_meta_campaigns(_meta_token, _cross_meta_id, start_str, end_str)
        _cp_mday = fetch_meta_daily(_meta_token, _cross_meta_id, start_str, end_str)

    # ── Google aggregates ─────────────────────────────────────────────────────
    _g_spend = _cp_gdf["Cost"].sum()        if not _cp_gdf.empty else 0.0
    _g_clicks= int(_cp_gdf["Clicks"].sum()) if not _cp_gdf.empty else 0
    _g_imps  = int(_cp_gdf["Impressions"].sum()) if not _cp_gdf.empty else 0
    _g_conv  = _cp_gdf["Conversions"].sum() if not _cp_gdf.empty else 0.0
    _g_rev   = _cp_gdf["Conv. Value"].sum() if not _cp_gdf.empty else 0.0
    _g_roas  = round(_g_rev  / _g_spend,  2) if _g_spend  else 0.0
    _g_cpa   = round(_g_spend/ _g_conv,   2) if _g_conv   else 0.0
    _g_ctr   = round(_g_clicks/_g_imps*100,2) if _g_imps  else 0.0
    _g_cpc   = round(_g_spend/ _g_clicks, 2) if _g_clicks else 0.0
    _g_cr    = round(_g_conv / _g_clicks*100,2) if _g_clicks else 0.0

    # ── Meta aggregates ───────────────────────────────────────────────────────
    _m_spend = _cp_mdf["Cost"].sum()        if not _cp_mdf.empty else 0.0
    _m_clicks= int(_cp_mdf["Clicks"].sum()) if not _cp_mdf.empty else 0
    _m_imps  = int(_cp_mdf["Impressions"].sum()) if not _cp_mdf.empty else 0
    _m_conv  = _cp_mdf["Conversions"].sum() if not _cp_mdf.empty else 0.0
    _m_rev   = _cp_mdf["Conv. Value"].sum() if not _cp_mdf.empty else 0.0
    _m_roas  = round(_m_rev  / _m_spend,  2) if _m_spend  else 0.0
    _m_cpa   = round(_m_spend/ _m_conv,   2) if _m_conv   else 0.0
    _m_ctr   = round(_m_clicks/_m_imps*100,2) if _m_imps  else 0.0
    _m_cpc   = round(_m_spend/ _m_clicks, 2) if _m_clicks else 0.0
    _m_cr    = round(_m_conv / _m_clicks*100,2) if _m_clicks else 0.0

    # ── Combined totals ───────────────────────────────────────────────────────
    _t_spend = _g_spend + _m_spend
    _t_conv  = _g_conv  + _m_conv
    _t_rev   = _g_rev   + _m_rev
    _t_roas  = round(_t_rev / _t_spend, 2) if _t_spend else 0.0
    _t_cpa   = round(_t_spend / _t_conv, 2) if _t_conv  else 0.0

    # ── Spend split ───────────────────────────────────────────────────────────
    _g_pct = round(_g_spend / _t_spend * 100) if _t_spend else 50
    _m_pct = 100 - _g_pct

    # ── Best platform ─────────────────────────────────────────────────────────
    _best_is_google = _g_roas >= _m_roas
    _best_lbl  = "Google" if _best_is_google else "Meta"
    _best_icon = "🔵" if _best_is_google else "📘"
    _best_roas = _g_roas if _best_is_google else _m_roas
    _other_roas= _m_roas if _best_is_google else _g_roas
    _roas_diff = round((_best_roas - _other_roas) / _other_roas * 100) if _other_roas else 0

    def _roas_color(v: float) -> str:
        return "#3fb950" if v >= 3 else "#58a6ff" if v >= 1.5 else "#f0883e" if v >= 1 else "#f85149"

    def _trow(label: str, gval: str, mval: str, tval: str, highlight: bool = False) -> str:
        bg = "rgba(255,255,255,0.03)" if highlight else "transparent"
        return (
            f"<tr style='background:{bg}'>"
            f"<td style='padding:10px 14px;color:rgba(255,255,255,0.5);font-size:12px;font-weight:600'>{label}</td>"
            f"<td style='padding:10px 14px;color:#58a6ff;font-size:13px;font-weight:700;text-align:right'>{gval}</td>"
            f"<td style='padding:10px 14px;color:#4267B2;font-size:13px;font-weight:700;text-align:right'>{mval}</td>"
            f"<td style='padding:10px 14px;color:#f0f6fc;font-size:13px;font-weight:800;text-align:right'>{tval}</td>"
            f"</tr>"
        )

    _cp_table = f"""
    <table style="width:100%;border-collapse:collapse;margin:16px 0">
      <thead>
        <tr style="border-bottom:1px solid rgba(255,255,255,0.08)">
          <th style="padding:8px 14px;font-size:10px;font-weight:700;letter-spacing:1.2px;
                     text-transform:uppercase;color:rgba(255,255,255,0.25);text-align:left">المؤشر</th>
          <th style="padding:8px 14px;font-size:10px;font-weight:700;letter-spacing:1.2px;
                     text-transform:uppercase;color:#58a6ff;text-align:right">🔵 Google</th>
          <th style="padding:8px 14px;font-size:10px;font-weight:700;letter-spacing:1.2px;
                     text-transform:uppercase;color:#4267B2;text-align:right">📘 Meta</th>
          <th style="padding:8px 14px;font-size:10px;font-weight:700;letter-spacing:1.2px;
                     text-transform:uppercase;color:rgba(255,255,255,0.5);text-align:right">📊 المجموع</th>
        </tr>
      </thead>
      <tbody>
        {_trow("الصرف",       fmt_currency(_g_spend), fmt_currency(_m_spend), fmt_currency(_t_spend), True)}
        {_trow("المبيعات",    fmt_currency(_g_rev),   fmt_currency(_m_rev),   fmt_currency(_t_rev))}
        {_trow("ROAS",         f"{_g_roas:.2f}×",      f"{_m_roas:.2f}×",      f"{_t_roas:.2f}× (مرجّح)", True)}
        {_trow("التحويلات",   f"{_g_conv:,.1f}",       f"{_m_conv:,.1f}",      f"{_t_conv:,.1f}")}
        {_trow("CPA",          fmt_currency(_g_cpa) if _g_conv else "—",
                               fmt_currency(_m_cpa) if _m_conv else "—",
                               fmt_currency(_t_cpa) if _t_conv else "—", True)}
        {_trow("CTR",          f"{_g_ctr:.2f}%", f"{_m_ctr:.2f}%", "—")}
        {_trow("CPC",          fmt_currency(_g_cpc) if _g_clicks else "—",
                               fmt_currency(_m_cpc) if _m_clicks else "—", "—", True)}
        {_trow("Conv Rate",    f"{_g_cr:.2f}%", f"{_m_cr:.2f}%", "—")}
      </tbody>
    </table>
    """

    _g_roas_dot = "🟢" if _g_roas >= 3 else "🟡" if _g_roas >= 1.5 else "🔴"
    _m_roas_dot = "🟢" if _m_roas >= 3 else "🟡" if _m_roas >= 1.5 else "🔴"

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d1117,#0e1521);
                border:1px solid rgba(255,255,255,0.08);border-radius:16px;
                padding:22px 26px 20px;margin-bottom:22px">

      <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:6px">
        <div>
          <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
                      color:rgba(255,255,255,0.28);margin-bottom:4px">Cross-Platform Overview</div>
          <div style="font-size:19px;font-weight:800;color:#f0f6fc">
            📊 {mask_name(selected_client, vis)} — تحليل مقارن
          </div>
        </div>
        <div style="font-size:11px;color:rgba(255,255,255,0.22);padding-top:6px">{start_str} → {end_str}</div>
      </div>

      {_cp_table}

      <div style="margin:18px 0 14px">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;
                    color:rgba(255,255,255,0.25);margin-bottom:10px">توزيع الإنفاق</div>
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
          <div style="width:72px;font-size:11px;color:#58a6ff;font-weight:600">🔵 Google</div>
          <div style="flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:10px;overflow:hidden">
            <div style="width:{_g_pct}%;height:100%;background:linear-gradient(90deg,#58a6ff,#1f6feb);border-radius:4px"></div>
          </div>
          <div style="width:52px;font-size:12px;color:rgba(255,255,255,0.6);font-weight:700;text-align:right">{_g_pct}%</div>
          <div style="width:80px;font-size:11px;color:rgba(255,255,255,0.4);text-align:right">{fmt_currency(_g_spend)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:10px">
          <div style="width:72px;font-size:11px;color:#4267B2;font-weight:600">📘 Meta</div>
          <div style="flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:10px;overflow:hidden">
            <div style="width:{_m_pct}%;height:100%;background:linear-gradient(90deg,#4267B2,#1a3a6b);border-radius:4px"></div>
          </div>
          <div style="width:52px;font-size:12px;color:rgba(255,255,255,0.6);font-weight:700;text-align:right">{_m_pct}%</div>
          <div style="width:80px;font-size:11px;color:rgba(255,255,255,0.4);text-align:right">{fmt_currency(_m_spend)}</div>
        </div>
      </div>

      <div style="display:flex;align-items:center;gap:24px;margin:18px 0 14px;flex-wrap:wrap">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;
                    color:rgba(255,255,255,0.25)">مقارنة ROAS</div>
        <div style="display:flex;align-items:center;gap:8px;background:rgba(255,255,255,0.04);
                    border-radius:8px;padding:8px 14px">
          <span style="font-size:12px;color:#58a6ff;font-weight:600">🔵 Google</span>
          <span style="font-size:16px;font-weight:800;color:{_roas_color(_g_roas)}">{_g_roas:.2f}×</span>
          <span>{_g_roas_dot}</span>
        </div>
        <div style="font-size:12px;color:rgba(255,255,255,0.2)">vs</div>
        <div style="display:flex;align-items:center;gap:8px;background:rgba(255,255,255,0.04);
                    border-radius:8px;padding:8px 14px">
          <span style="font-size:12px;color:#4267B2;font-weight:600">📘 Meta</span>
          <span style="font-size:16px;font-weight:800;color:{_roas_color(_m_roas)}">{_m_roas:.2f}×</span>
          <span>{_m_roas_dot}</span>
        </div>
      </div>

      <div style="background:linear-gradient(90deg,rgba(63,185,80,0.12),rgba(63,185,80,0.04));
                  border:1px solid rgba(63,185,80,0.25);border-radius:10px;
                  padding:12px 16px;font-size:13px;font-weight:700;color:#3fb950">
        🏆 أفضل أداء: {_best_icon} {_best_lbl}
        {"— ROAS أعلى بـ " + str(_roas_diff) + "%" if _roas_diff else "— أداء متساوٍ"}
      </div>

    </div>
    """, unsafe_allow_html=True)

    # ── Daily Breakdown (collapsible) ─────────────────────────────────────────
    _show_daily = st.checkbox("📅 عرض التفاصيل اليومية", key="cp_daily_toggle")
    if _show_daily and (not _cp_gday.empty or not _cp_mday.empty):
        if not _cp_gday.empty:
            _cp_gday = _cp_gday.copy()
            _cp_gday["Date"] = pd.to_datetime(_cp_gday["Date"])
            _cp_gday["G_ROAS"] = _cp_gday.apply(
                lambda r: round(r["Conv. Value"] / r["Cost"], 2) if r["Cost"] > 0 else 0.0, axis=1)
        if not _cp_mday.empty:
            _cp_mday = _cp_mday.copy()
            _cp_mday["Date"] = pd.to_datetime(_cp_mday["Date"])
            _cp_mday["M_ROAS"] = _cp_mday.apply(
                lambda r: round(r["Conv. Value"] / r["Cost"], 2) if r["Cost"] > 0 else 0.0, axis=1)

        _all_dates = sorted(set(
            list(_cp_gday["Date"].dt.date if not _cp_gday.empty else []) +
            list(_cp_mday["Date"].dt.date if not _cp_mday.empty else [])
        ))

        _daily_rows = ""
        for _dt in _all_dates:
            _gday_row = _cp_gday[_cp_gday["Date"].dt.date == _dt] if not _cp_gday.empty else pd.DataFrame()
            _mday_row = _cp_mday[_cp_mday["Date"].dt.date == _dt] if not _cp_mday.empty else pd.DataFrame()
            _gs = _gday_row["Cost"].sum()    if not _gday_row.empty else 0.0
            _gr = _gday_row["G_ROAS"].mean() if not _gday_row.empty else 0.0
            _ms = _mday_row["Cost"].sum()    if not _mday_row.empty else 0.0
            _mr = _mday_row["M_ROAS"].mean() if not _mday_row.empty else 0.0
            _ts = _gs + _ms
            _tr = round(
                (_gday_row["Conv. Value"].sum() + _mday_row["Conv. Value"].sum()) / _ts, 2
            ) if _ts else 0.0
            _row_color = "rgba(63,185,80,0.06)" if _tr >= 3 else \
                         "rgba(248,81,73,0.06)"  if _tr > 0 and _tr < 1 else "transparent"
            _gr_c = _roas_color(_gr)
            _mr_c = _roas_color(_mr)
            _tr_c = _roas_color(_tr)
            _daily_rows += (
                f"<tr style='background:{_row_color};border-bottom:1px solid rgba(255,255,255,0.04)'>"
                f"<td style='padding:7px 12px;font-size:11px;color:rgba(255,255,255,0.4)'>{_dt.strftime('%b %d')}</td>"
                f"<td style='padding:7px 12px;font-size:11px;color:#58a6ff;text-align:right'>{fmt_currency(_gs)}</td>"
                f"<td style='padding:7px 12px;font-size:11px;font-weight:700;color:{_gr_c};text-align:right'>{_gr:.2f}×</td>"
                f"<td style='padding:7px 12px;font-size:11px;color:#4267B2;text-align:right'>{fmt_currency(_ms)}</td>"
                f"<td style='padding:7px 12px;font-size:11px;font-weight:700;color:{_mr_c};text-align:right'>{_mr:.2f}×</td>"
                f"<td style='padding:7px 12px;font-size:11px;color:rgba(255,255,255,0.6);text-align:right'>{fmt_currency(_ts)}</td>"
                f"<td style='padding:7px 12px;font-size:11px;font-weight:800;color:{_tr_c};text-align:right'>{_tr:.2f}×</td>"
                f"</tr>"
            )

        st.markdown(f"""
        <div style="background:#0a0d14;border:1px solid rgba(255,255,255,0.06);
                    border-radius:12px;overflow:hidden;margin-bottom:20px">
          <table style="width:100%;border-collapse:collapse">
            <thead>
              <tr style="background:rgba(255,255,255,0.04)">
                <th style="padding:8px 12px;font-size:10px;font-weight:700;letter-spacing:1px;
                           text-transform:uppercase;color:rgba(255,255,255,0.25);text-align:left">التاريخ</th>
                <th style="padding:8px 12px;font-size:10px;color:#58a6ff;text-align:right">Google Spend</th>
                <th style="padding:8px 12px;font-size:10px;color:#58a6ff;text-align:right">Google ROAS</th>
                <th style="padding:8px 12px;font-size:10px;color:#4267B2;text-align:right">Meta Spend</th>
                <th style="padding:8px 12px;font-size:10px;color:#4267B2;text-align:right">Meta ROAS</th>
                <th style="padding:8px 12px;font-size:10px;color:rgba(255,255,255,0.4);text-align:right">Total Spend</th>
                <th style="padding:8px 12px;font-size:10px;color:rgba(255,255,255,0.4);text-align:right">Total ROAS</th>
              </tr>
            </thead>
            <tbody>{_daily_rows}</tbody>
          </table>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ── Platform selector ────────────────────────────────────────────────────────
_platform = st.radio(
    "platform",
    ["🔵  Google Ads", "📘  Meta Ads"],
    horizontal=True,
    label_visibility="collapsed",
    key="_platform_radio",
)
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# META ADS
# ══════════════════════════════════════════════════════════════════════════════
if _platform == "📘  Meta Ads":
    # Token + account come from pre-fetch block and sidebar respectively
    if not _meta_token:
        st.warning("Meta Ads not configured — add META_ACCESS_TOKEN to .env")
        st.stop()
    if not selected_meta_acct_id:
        st.info("Select a Meta ad account in the sidebar.")
        st.stop()

    # ── Navigation state ──────────────────────────────────────────────────────
    _mv  = st.session_state["meta_view"]
    _msc = st.session_state["meta_selected_campaign"]   # {id, name} | None
    _msa = st.session_state["meta_selected_adset"]      # {id, name} | None

    # ── Breadcrumb ────────────────────────────────────────────────────────────
    def _bc_span(text: str, active: bool) -> str:
        c = "#fff" if active else "rgba(255,255,255,0.35)"
        w = "700"  if active else "400"
        return f'<span style="color:{c};font-weight:{w}">{text}</span>'

    if _mv == "campaigns":
        _bc = _bc_span("Campaigns", True)
    elif _mv == "adsets":
        _bc = _bc_span("Campaigns", False) + ' <span style="color:rgba(255,255,255,0.2)">›</span> ' + \
              _bc_span(_msc["name"] if _msc else "", True)
    else:
        _bc = _bc_span("Campaigns", False) + ' <span style="color:rgba(255,255,255,0.2)">›</span> ' + \
              _bc_span(_msc["name"] if _msc else "", False) + \
              ' <span style="color:rgba(255,255,255,0.2)">›</span> ' + \
              _bc_span(_msa["name"] if _msa else "", True)

    st.markdown(
        f'<div style="font-size:13px;margin-bottom:16px;padding:8px 14px;'
        f'background:#0a0d14;border:1px solid rgba(255,255,255,0.06);border-radius:8px">'
        f'{_bc}</div>',
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # Level 1 — Campaigns
    # ══════════════════════════════════════════════════════════════════════════
    if _mv == "campaigns":
        with st.spinner(""):
            _mdf_camp  = fetch_meta_campaigns(_meta_token, selected_meta_acct_id, start_str, end_str)
            _mdf_daily = fetch_meta_daily(_meta_token, selected_meta_acct_id, start_str, end_str)

        if _mdf_camp.empty:
            st.info("No Meta campaign data for this date range.")
        else:
            # KPI totals
            _ms    = _mdf_camp["Cost"].sum()
            _mc    = int(_mdf_camp["Clicks"].sum())
            _mi    = int(_mdf_camp["Impressions"].sum())
            _mcv   = _mdf_camp["Conversions"].sum()
            _mrv   = _mdf_camp["Conv. Value"].sum()
            _mctr  = (_mc / _mi * 100) if _mi else 0
            _mcpc  = (_ms / _mc) if _mc else 0
            _mcpa  = (_ms / _mcv) if _mcv else 0
            _mroas = (_mrv / _ms) if _ms else 0
            _mcr   = (_mcv / _mc * 100) if _mc else 0

            st.markdown('<div class="sec-label">Meta Key Metrics</div>', unsafe_allow_html=True)
            _mr_sub = "Excellent ✓" if _mroas >= 3 else "Good" if _mroas >= 1.5 else "Below target ⚠"
            _mcols  = st.columns(9)
            _mmetrics = [
                ("💸", "Total Spend",  fmt_currency(_ms),                    f"{len(_mdf_camp)} campaigns", "#4267B2"),
                ("👁",  "Impressions",  fmt_number(_mi),                      "Total ad views",              "#d2a8ff"),
                ("🖱",  "Clicks",       fmt_number(_mc),                      "Total link clicks",           "#3fb950"),
                ("📊", "CTR",          f"{_mctr:.2f}%",                      "Click-through rate",          "#39c5d0"),
                ("⚡", "Avg. CPC",     fmt_currency(_mcpc),                  "Cost per click",              "#ffa657"),
                ("🎯", "Conversions",  f"{_mcv:,.1f}",                       "Purchases tracked",           "#ff6b9d"),
                ("💰", "CPA",          fmt_currency(_mcpa) if _mcv else "—", "Cost per purchase",           "#e3b341"),
                ("🔄", "Conv. Rate",   f"{_mcr:.1f}%" if _mcv else "—",     f"{_mcr:.1f}% click-to-conv",  "#a5d6ff"),
                ("📈", "ROAS",         f"{_mroas:.2f}×",                     _mr_sub,                       "#3fb950" if _mroas >= 3 else "#f85149"),
            ]
            for _col, (_icon, _lbl, _val, _sub, _acc) in zip(_mcols, _mmetrics):
                _col.markdown(kpi_card(_icon, _lbl, _val, _sub, _acc), unsafe_allow_html=True)

            # ROAS hero
            _mrc = "#3fb950" if _mroas >= 3 else "#58a6ff" if _mroas >= 1.5 else "#f0883e" if _mroas >= 1 else "#f85149"
            _mrl = "Excellent" if _mroas >= 3 else "Good" if _mroas >= 1.5 else "Break-even" if _mroas >= 1 else "Below target"
            st.markdown(f"""
            <div class="roas-wrap" style="background:linear-gradient(135deg,#0e1a35,#0a1228);
                 border:1px solid {hex_to_rgba(_mrc, 0.2)};">
              <div>
                <div style="font-size:10.5px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
                            color:rgba(255,255,255,0.28);margin-bottom:6px">Meta ROAS</div>
                <div style="font-size:58px;font-weight:900;color:{_mrc};line-height:1;
                            letter-spacing:-2.5px;text-shadow:0 0 50px {hex_to_rgba(_mrc,0.5)}">
                  {_mroas:.2f}<span style="font-size:28px;opacity:0.7">×</span>
                </div>
              </div>
              <div class="roas-divider"></div>
              <div>
                <div class="roas-stat-label">Conv. Value</div>
                <div class="roas-stat-value">{fmt_currency(_mrv)}</div>
              </div>
              <div class="roas-divider"></div>
              <div>
                <div class="roas-stat-label">Total Spend</div>
                <div class="roas-stat-value">{fmt_currency(_ms)}</div>
              </div>
              <div class="roas-divider"></div>
              <div>
                <div class="roas-stat-label">Status</div>
                <div style="font-size:15px;font-weight:700;color:{_mrc}">{_mrl}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Campaign intelligence + sort/filter
            st.markdown('<div class="sec-label">Meta Campaign Intelligence</div>', unsafe_allow_html=True)
            _m_decisions = {i: ai_decision(row) for i, row in _mdf_camp.iterrows()}
            _mn_s = sum(1 for d in _m_decisions.values() if d["tier"] == "strong")
            _mn_m = sum(1 for d in _m_decisions.values() if d["tier"] == "moderate")
            _mn_w = sum(1 for d in _m_decisions.values() if d["tier"] == "weak")

            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;
                        padding:14px 20px;background:#0a0d14;border:1px solid rgba(255,255,255,0.05);
                        border-radius:12px;margin-bottom:18px;font-size:12px">
              <span style="color:rgba(255,255,255,0.3)">{len(_mdf_camp)} campaigns</span>
              <span style="color:rgba(255,255,255,0.1)">|</span>
              <span style="color:#3fb950;font-weight:600">🟢 {_mn_s} Scale</span>
              <span style="color:#e3b341;font-weight:600">🟡 {_mn_m} Optimize</span>
              <span style="color:#f85149;font-weight:600">🔴 {_mn_w} Pause/Fix</span>
              <span style="margin-left:auto;font-size:11px;color:rgba(255,255,255,0.15)">
                {start_str} → {end_str}
              </span>
            </div>
            """, unsafe_allow_html=True)

            _mc1, _mc2, _mc3 = st.columns([2, 2, 1])
            _m_sort   = _mc1.selectbox("Sort", ["Cost","Clicks","CTR","Impressions","Conversions"],
                                       label_visibility="collapsed", key="meta_sort")
            _m_filter = _mc2.selectbox("Filter", ["All","🟢 Scale","🟡 Optimize","🔴 Pause/Fix"],
                                       label_visibility="collapsed", key="meta_filter")
            _m_asc    = _mc3.selectbox("Dir", ["↓ Desc","↑ Asc"],
                                       label_visibility="collapsed", key="meta_dir") == "↑ Asc"

            _m_tier_map  = {"🟢 Scale": "strong", "🟡 Optimize": "moderate", "🔴 Pause/Fix": "weak"}
            _mdf_sorted  = _mdf_camp.sort_values(_m_sort, ascending=_m_asc)
            _m_any       = False
            for _mi2, _mrow in _mdf_sorted.iterrows():
                _md = _m_decisions[_mi2]
                if _m_filter != "All" and _md["tier"] != _m_tier_map.get(_m_filter, ""):
                    continue
                _m_any = True
                st.markdown(campaign_card(_mrow, _md), unsafe_allow_html=True)
                _cid  = str(_mrow.get("Campaign ID", ""))
                _cname = str(_mrow.get("Campaign", ""))
                if _cid and st.button("📊 View Ad Sets →", key=f"adset_btn_{_mi2}"):
                    st.session_state["meta_view"]              = "adsets"
                    st.session_state["meta_selected_campaign"] = {"id": _cid, "name": _cname}
                    st.session_state["meta_selected_adset"]    = None
                    st.rerun()

            if not _m_any:
                st.info("No campaigns match this filter.")

            # Daily chart
            if not _mdf_daily.empty:
                st.markdown('<div class="sec-label">Meta Daily Performance</div>', unsafe_allow_html=True)
                _mdf_plot = _mdf_daily.copy()
                _mdf_plot["ROAS"] = _mdf_plot.apply(
                    lambda r: round(r["Conv. Value"] / r["Cost"], 2) if r["Cost"] > 0 else 0.0, axis=1)
                _mfig = go.Figure()
                _mfig.add_trace(go.Scatter(
                    x=_mdf_plot["Date"], y=_mdf_plot["Cost"], name="Spend",
                    mode="lines", line=dict(color="#4267B2", width=2.5, shape="spline"),
                    fill="tozeroy",
                    fillgradient=dict(type="vertical",
                        colorscale=[[0,"rgba(66,103,178,0.28)"],[1,"rgba(66,103,178,0)"]]),
                    hovertemplate="<b>Spend</b>: SAR %{y:,.2f}<extra></extra>",
                ))
                _mfig.add_trace(go.Scatter(
                    x=_mdf_plot["Date"], y=_mdf_plot["Conv. Value"], name="Revenue",
                    mode="lines", line=dict(color="#3fb950", width=2.5, shape="spline"),
                    fill="tozeroy",
                    fillgradient=dict(type="vertical",
                        colorscale=[[0,"rgba(63,185,80,0.22)"],[1,"rgba(63,185,80,0)"]]),
                    hovertemplate="<b>Revenue</b>: SAR %{y:,.2f}<extra></extra>",
                ))
                _mfig.add_trace(go.Scatter(
                    x=_mdf_plot["Date"], y=_mdf_plot["ROAS"], name="ROAS",
                    mode="lines", yaxis="y2",
                    line=dict(color="#ffa657", width=2.5, shape="spline"),
                    hovertemplate="<b>ROAS</b>: %{y:.2f}×<extra></extra>",
                ))
                _ml_max = max(_mdf_plot["Cost"].max(), _mdf_plot["Conv. Value"].max(), 1) * 1.35
                _mr_max = max(_mdf_plot["ROAS"].max() * 1.4, 5.0)
                _mfig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0c1018",
                    font=dict(family="Inter", color="rgba(255,255,255,0.3)", size=11),
                    margin=dict(l=0, r=0, t=10, b=0), height=320,
                    xaxis=dict(gridcolor="rgba(255,255,255,0.035)", tickformat="%b %d"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.035)", tickprefix="SAR ",
                               range=[0, _ml_max]),
                    yaxis2=dict(overlaying="y", side="right", showgrid=False,
                                ticksuffix="×", range=[0, _mr_max]),
                    legend=dict(bgcolor="rgba(13,16,24,0.88)",
                                bordercolor="rgba(255,255,255,0.07)", borderwidth=1,
                                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    hovermode="x unified",
                )
                st.plotly_chart(_mfig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # Level 2 — Ad Sets
    # ══════════════════════════════════════════════════════════════════════════
    elif _mv == "adsets":
        if st.button("← Back to Campaigns", key="back_to_camps"):
            st.session_state["meta_view"]              = "campaigns"
            st.session_state["meta_selected_campaign"] = None
            st.rerun()

        _camp_id   = _msc["id"]
        _camp_name = _msc["name"]
        st.markdown(f'<div class="sec-label">Ad Sets — {_camp_name}</div>', unsafe_allow_html=True)

        with st.spinner(""):
            _mdf_adsets = fetch_meta_adsets(_meta_token, _camp_id, start_str, end_str)

        if _mdf_adsets.empty:
            st.info(f"No ad set data for '{_camp_name}' in this date range.")
        else:
            _as_s    = _mdf_adsets["Cost"].sum()
            _as_c    = int(_mdf_adsets["Clicks"].sum())
            _as_i    = int(_mdf_adsets["Impressions"].sum())
            _as_cv   = _mdf_adsets["Conversions"].sum()
            _as_rv   = _mdf_adsets["Conv. Value"].sum()
            _as_roas = round(_as_rv / _as_s, 2) if _as_s else 0.0
            _as_ctr  = round(_as_c / _as_i * 100, 2) if _as_i else 0.0

            _ascols = st.columns(6)
            for _col, (_lbl, _val) in zip(_ascols, [
                ("Spend",       fmt_currency(_as_s)),
                ("Impressions", fmt_number(_as_i)),
                ("Clicks",      fmt_number(_as_c)),
                ("CTR",         f"{_as_ctr:.2f}%"),
                ("Conv.",       f"{_as_cv:,.1f}"),
                ("ROAS",        f"{_as_roas:.2f}×"),
            ]):
                _col.metric(_lbl, _val)

            _as_decisions = {i: ai_decision(row) for i, row in _mdf_adsets.iterrows()}
            for _asi, _asrow in _mdf_adsets.sort_values("Cost", ascending=False).iterrows():
                _asd    = _as_decisions[_asi]
                st.markdown(campaign_card(_asrow, _asd), unsafe_allow_html=True)
                _as_id   = str(_asrow.get("ID", ""))
                _as_name = str(_asrow.get("Campaign", ""))
                if _as_id and st.button("📋 View Ads →", key=f"ads_btn_{_asi}"):
                    st.session_state["meta_view"]           = "ads"
                    st.session_state["meta_selected_adset"] = {"id": _as_id, "name": _as_name}
                    st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # Level 3 — Ads
    # ══════════════════════════════════════════════════════════════════════════
    elif _mv == "ads":
        if st.button("← Back to Ad Sets", key="back_to_adsets"):
            st.session_state["meta_view"]           = "adsets"
            st.session_state["meta_selected_adset"] = None
            st.rerun()

        _adset_id   = _msa["id"]
        _adset_name = _msa["name"]
        st.markdown(f'<div class="sec-label">Ads — {_adset_name}</div>', unsafe_allow_html=True)

        with st.spinner(""):
            _mdf_ads = fetch_meta_ads_list(_meta_token, _adset_id, start_str, end_str)

        if _mdf_ads.empty:
            st.info(f"No ad data for '{_adset_name}' in this date range.")
        else:
            _ad_decisions = {i: ai_decision(row) for i, row in _mdf_ads.iterrows()}
            for _adidx, _adrow in _mdf_ads.sort_values("Cost", ascending=False).iterrows():
                st.markdown(campaign_card(_adrow, _ad_decisions[_adidx]), unsafe_allow_html=True)

    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE ADS — all existing content below
# ══════════════════════════════════════════════════════════════════════════════

# ── Fetch data ────────────────────────────────────────────────────────────────
customer_id = selected_customer_id

with st.spinner(""):
    df_camp  = fetch_campaign_data(customer_id, token, dev_token, start_str, end_str, mcc_id)
    df_daily = fetch_daily_data(customer_id, token, dev_token, start_str, end_str, mcc_id)

if df_camp.empty:
    st.warning("No data found for the selected date range.")
    st.stop()

df_active = df_camp if show_paused else df_camp[df_camp["Status"] == "ENABLED"]

# ── KPI totals ────────────────────────────────────────────────────────────────
total_spend  = df_active["Cost"].sum()
total_clicks = int(df_active["Clicks"].sum())
total_impr   = int(df_active["Impressions"].sum())
total_conv   = df_active["Conversions"].sum()
total_cv     = df_active["Conv. Value"].sum()
avg_ctr      = (total_clicks / total_impr * 100) if total_impr else 0
avg_cpc      = (total_spend / total_clicks) if total_clicks else 0
cpa          = (total_spend / total_conv) if total_conv else 0
roas         = (total_cv / total_spend) if total_spend else 0
conv_rate    = (total_conv / total_clicks * 100) if total_clicks else 0

# ── Action Buttons (PDF / Send) ───────────────────────────────────────────────
_pdf_key = (selected_client, start_str, end_str, vis)
if st.session_state.get("_pdf_cache_key") != _pdf_key:
    st.session_state["_show_send_panel"] = False  # reset on client/date change
    _kpis_dict = dict(
        spend=total_spend, revenue=total_cv, roas=roas,
        conversions=total_conv, cpa=cpa,
        impressions=total_impr, clicks=total_clicks,
        ctr=avg_ctr, avg_cpc=avg_cpc,
    )
    _decisions = {i: ai_decision(row) for i, row in df_active.iterrows()}
    st.session_state["_pdf_bytes"]     = generate_pdf(
        selected_client, start_str, end_str,
        _kpis_dict, df_active, _decisions, df_daily,
        show_name=vis)
    st.session_state["_pdf_cache_key"] = _pdf_key

_pdf_bytes = st.session_state["_pdf_bytes"]
# filename always uses real name — it's a local file, not shown on screen
_fn = f"report_{selected_client}_{end_str}.pdf".replace(" ", "_")

_sep = "━" * 22   # ━━━━━━━━━━━━━━━━━━━━━━
_cpa_str = fmt_currency(cpa) if total_conv > 0 else "-"
_wa_msg = (
    f"{_sep}\n"
    f"📊 تقرير أداء الحملات\n"
    f"{selected_client}\n"
    f"{_sep}\n\n"
    f"🗓 الفترة: {start_str} - {end_str}\n\n"
    f"💰 الإنفاق:      {fmt_currency(total_spend)}\n"
    f"👁 الظهور:       {fmt_number(total_impr)}\n"
    f"🖱 النقرات:      {fmt_number(total_clicks)}\n"
    f"📊 CTR:          {avg_ctr:.2f}%\n"
    f"📈 ROAS:         {roas:.2f}x\n"
    f"✅ التحويلات:     {total_conv:.0f}\n"
    f"💡 CPA:          {_cpa_str}\n\n"
    f"{_sep}\n"
    f"🔗 التقرير الكامل:\n"
    f"https://ads-dashboard.yousefzaiter.com\n"
    f"{_sep}\n"
    f"Ads Intelligence ⚡"
)
# safe='' encodes every non-ASCII char (emoji, Arabic, separators) as %XX
_wa_url = f"https://wa.me/?text={urllib.parse.quote(_wa_msg, safe='')}"

_ab1, _ab2, _ab_rest = st.columns([1, 1, 4])
with _ab1:
    st.download_button("📥 Download PDF", data=_pdf_bytes,
                       file_name=_fn, mime="application/pdf",
                       use_container_width=True)
with _ab2:
    if st.button("📤 Send to Client", use_container_width=True, key="send_btn"):
        st.session_state["_show_send_panel"] = True

# ── Two-step send panel ───────────────────────────────────────────────────────
if st.session_state.get("_show_send_panel"):
    st.markdown("""
    <div style='background:#0d1018;border:1px solid rgba(63,185,80,0.18);
                border-radius:14px;padding:20px 24px;margin:10px 0 4px'>
      <div style='font-size:13px;font-weight:700;color:#3fb950;margin-bottom:14px'>
        📤 إرسال التقرير للعميل — خطوتان
      </div>
      <div style='display:flex;gap:10px;align-items:flex-start;margin-bottom:10px'>
        <div style='width:22px;height:22px;background:#3fb950;border-radius:50%;
                    display:flex;align-items:center;justify-content:center;
                    font-size:11px;font-weight:800;color:#07090f;flex-shrink:0'>1</div>
        <div style='font-size:12.5px;color:rgba(255,255,255,0.6);line-height:1.5'>
          حمّل ملف PDF أدناه أولاً ثم أرفقه يدوياً في محادثة واتساب
        </div>
      </div>
      <div style='display:flex;gap:10px;align-items:flex-start'>
        <div style='width:22px;height:22px;background:#58a6ff;border-radius:50%;
                    display:flex;align-items:center;justify-content:center;
                    font-size:11px;font-weight:800;color:#07090f;flex-shrink:0'>2</div>
        <div style='font-size:12.5px;color:rgba(255,255,255,0.6);line-height:1.5'>
          افتح واتساب — الرسالة جاهزة ومملوءة بالأرقام، أرفق PDF من جهازك
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _sp1, _sp2, _sp3 = st.columns([1, 1, 4])
    with _sp1:
        st.download_button(
            "⬇️ تحميل PDF",
            data=_pdf_bytes, file_name=_fn, mime="application/pdf",
            use_container_width=True, key="send_panel_pdf_dl",
        )
    with _sp2:
        st.markdown(
            f'<a href="{_wa_url}" target="_blank" '
            f'style="display:inline-flex;align-items:center;justify-content:center;gap:6px;'
            f'width:100%;height:38px;background:linear-gradient(135deg,#1a2e20,#1e3525);'
            f'border:1px solid rgba(63,185,80,0.35);border-radius:10px;'
            f'font-size:12px;font-weight:700;color:#3fb950;'
            f'text-decoration:none;">'
            f'💬 فتح واتساب</a>',
            unsafe_allow_html=True,
        )

# ── KPI Cards ─────────────────────────────────────────────────────────────────
st.markdown('<div class="sec-label">Key Metrics</div>', unsafe_allow_html=True)

_cr_sub  = f"avg {conv_rate:.1f}% conv rate" if conv_rate > 0 else "no conversions"
_roas_sub = "Excellent ✓" if roas >= 3 else "Good" if roas >= 1.5 else "Below target ⚠"

cols = st.columns(9)
metrics = [
    ("💸", "Total Spend",    fmt_currency(total_spend),                f"{len(df_active[df_active['Cost']>0])} active campaigns", "#58a6ff"),
    ("👁",  "Impressions",    fmt_number(total_impr),                   "Total ad views",                                          "#d2a8ff"),
    ("🖱",  "Clicks",         fmt_number(total_clicks),                 "Total link clicks",                                       "#3fb950"),
    ("📊", "CTR",            f"{avg_ctr:.2f}%",                        "Click-through rate",                                      "#39c5d0"),
    ("⚡", "Avg. CPC",       fmt_currency(avg_cpc),                    "Cost per click",                                          "#ffa657"),
    ("🎯", "Conversions",    f"{total_conv:,.1f}",                     "Total conversions",                                       "#ff6b9d"),
    ("💰", "CPA",            fmt_currency(cpa) if total_conv else "—", "Cost per conversion",                                    "#e3b341"),
    ("🔄", "Conv. Rate",     f"{conv_rate:.1f}%" if total_conv else "—", _cr_sub,                                               "#a5d6ff"),
    ("📈", "ROAS",           f"{roas:.2f}×",                           _roas_sub,                                                 "#3fb950" if roas >= 3 else "#f85149"),
]
for col, (icon, label, value, sub, accent) in zip(cols, metrics):
    col.markdown(kpi_card(icon, label, value, sub, accent), unsafe_allow_html=True)

# ── ROAS Banner ───────────────────────────────────────────────────────────────
roas_color = "#3fb950" if roas >= 3 else "#58a6ff" if roas >= 1.5 else "#f0883e" if roas >= 1 else "#f85149"
roas_label = "Excellent" if roas >= 3 else "Good" if roas >= 1.5 else "Break-even" if roas >= 1 else "Below target"

st.markdown(f"""
<div class="roas-wrap" style="background:linear-gradient(135deg,#111624,#0d1020);
     border:1px solid {hex_to_rgba(roas_color, 0.2)};">
  <div>
    <div style="font-size:10.5px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
                color:rgba(255,255,255,0.28);margin-bottom:6px">Return on Ad Spend</div>
    <div style="font-size:58px;font-weight:900;color:{roas_color};line-height:1;
                letter-spacing:-2.5px;text-shadow:0 0 50px {hex_to_rgba(roas_color,0.5)}">
      {roas:.2f}<span style="font-size:28px;opacity:0.7">×</span>
    </div>
  </div>
  <div class="roas-divider"></div>
  <div>
    <div class="roas-stat-label">Conv. Value</div>
    <div class="roas-stat-value">{fmt_currency(total_cv)}</div>
  </div>
  <div class="roas-divider"></div>
  <div>
    <div class="roas-stat-label">Total Spend</div>
    <div class="roas-stat-value">{fmt_currency(total_spend)}</div>
  </div>
  <div class="roas-divider"></div>
  <div>
    <div class="roas-stat-label">Status</div>
    <div style="font-size:15px;font-weight:700;color:{roas_color}">{roas_label}</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Campaign Intelligence ──────────────────────────────────────────────────────
st.markdown('<div class="sec-label">توصيات الذكاء الاصطناعي — Campaign Intelligence</div>',
            unsafe_allow_html=True)

if not df_active.empty:
    all_decisions = {i: ai_decision(row) for i, row in df_active.iterrows()}

    n_strong      = sum(1 for d in all_decisions.values() if d["tier"] == "strong")
    n_moderate    = sum(1 for d in all_decisions.values() if d["tier"] == "moderate")
    n_weak        = sum(1 for d in all_decisions.values() if d["tier"] == "weak")
    n_paused      = sum(1 for d in all_decisions.values() if d["tier"] == "paused")

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;
                padding:14px 20px;background:#0a0d14;border:1px solid rgba(255,255,255,0.05);
                border-radius:12px;margin-bottom:18px;font-size:12px">
      <span style="color:rgba(255,255,255,0.3)">{len(df_active)} حملة</span>
      <span style="color:rgba(255,255,255,0.1)">|</span>
      <span style="color:#3fb950;font-weight:600">🟢 {n_strong} Scale</span>
      <span style="color:#e3b341;font-weight:600">🟡 {n_moderate} Optimize</span>
      <span style="color:#f85149;font-weight:600">🔴 {n_weak} Pause/Fix</span>
      <span style="color:rgba(255,255,255,0.2)">⏸ {n_paused} موقوفة</span>
      <span style="margin-left:auto;font-size:11px;color:rgba(255,255,255,0.15)">
        {start_str} → {end_str}
      </span>
    </div>
    """, unsafe_allow_html=True)

    fc1, fc2, fc3 = st.columns([2, 2, 1])
    sort_by = fc1.selectbox(
        "Sort", ["Cost", "Clicks", "CTR", "Impressions", "Conversions"],
        label_visibility="collapsed")
    tier_filter = fc2.selectbox(
        "Filter", ["الكل", "🟢 Scale", "🟡 Optimize", "🔴 Pause/Fix"],
        label_visibility="collapsed")
    sort_asc = fc3.selectbox(
        "Dir", ["↓ Desc", "↑ Asc"],
        label_visibility="collapsed") == "↑ Asc"

    tier_map   = {"🟢 Scale": "strong", "🟡 Optimize": "moderate", "🔴 Pause/Fix": "weak"}
    df_sorted  = df_active.sort_values(sort_by, ascending=sort_asc)
    active_rows = df_sorted[df_sorted["Status"] == "ENABLED"]
    paused_rows = df_sorted[df_sorted["Status"] != "ENABLED"]

    cards_html = ""
    shown = 0
    for i, row in active_rows.iterrows():
        d = all_decisions[i]
        if tier_filter != "الكل" and d["tier"] != tier_map.get(tier_filter, ""):
            continue
        cards_html += campaign_card(row, d)
        shown += 1

    if show_paused:
        for i, row in paused_rows.iterrows():
            cards_html += campaign_card(row, all_decisions[i])

    if not cards_html:
        st.info("لا توجد حملات تطابق هذا الفلتر.")
    else:
        st.markdown(cards_html, unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:11px;color:rgba(255,255,255,0.15);margin-top:4px">'
            f'يعرض {shown} حملة نشطة'
            f'{"  ·  " + str(len(paused_rows)) + " موقوفة" if show_paused else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── Daily Trend Chart ─────────────────────────────────────────────────────────
st.markdown('<div class="sec-label">Daily Performance</div>', unsafe_allow_html=True)

if not df_daily.empty:
    # Per-day ROAS
    df_plot = df_daily.copy()
    df_plot["ROAS"] = df_plot.apply(
        lambda r: round(r["Conv. Value"] / r["Cost"], 2) if r["Cost"] > 0 else 0.0,
        axis=1,
    )

    # ── Summary bar ──────────────────────────────────────────────────────────
    today_str   = date.today().strftime("%Y-%m-%d")
    today_rows  = df_plot[df_plot["Date"].dt.strftime("%Y-%m-%d") == today_str]
    latest_roas = float(today_rows["ROAS"].iloc[-1]) if not today_rows.empty \
                  else float(df_plot["ROAS"].iloc[-1])
    latest_lbl  = "Today" if not today_rows.empty \
                  else df_plot["Date"].iloc[-1].strftime("%b %d")

    period_spend     = df_plot["Cost"].sum()
    period_roas      = round(df_plot["Conv. Value"].sum() / period_spend, 2) \
                       if period_spend > 0 else 0.0
    days_below       = int((df_plot["ROAS"] < 3).sum())
    total_chart_days = len(df_plot)

    is_good       = latest_roas >= 3
    status_color  = "#3fb950" if is_good else "#f85149"
    status_text   = "Good Performance" if is_good else "Below Target"
    status_icon   = "✓" if is_good else "⚠"
    roas_glow     = hex_to_rgba(status_color, 0.38)
    pr_color      = "#3fb950" if period_roas >= 3 else "#f0883e" if period_roas >= 1.5 else "#f85149"

    st.markdown(f"""
    <div style='background:#0d1018;border:1px solid rgba(255,255,255,0.06);border-radius:16px;
                padding:20px 28px;display:flex;align-items:center;gap:28px;
                flex-wrap:wrap;margin-bottom:14px'>
      <div>
        <div style='font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
                    color:rgba(255,255,255,0.22);margin-bottom:5px'>{latest_lbl} ROAS</div>
        <div style='font-size:46px;font-weight:900;color:{status_color};line-height:1;
                    letter-spacing:-2px;text-shadow:0 0 40px {roas_glow}'>
          {latest_roas:.2f}<span style='font-size:22px;font-weight:600;opacity:0.55'>×</span>
        </div>
      </div>
      <div style='padding:9px 18px;background:{hex_to_rgba(status_color,0.09)};
                  border:1px solid {hex_to_rgba(status_color,0.25)};border-radius:12px;
                  display:flex;align-items:center;gap:8px;align-self:center'>
        <span style='font-size:14px;color:{status_color};font-weight:800'>{status_icon}</span>
        <span style='font-size:13px;font-weight:700;color:{status_color}'>{status_text}</span>
      </div>
      <div style='width:1px;height:44px;background:rgba(255,255,255,0.06);align-self:center'></div>
      <div>
        <div style='font-size:10px;color:rgba(255,255,255,0.22);letter-spacing:1px;
                    text-transform:uppercase;margin-bottom:4px'>Period Avg ROAS</div>
        <div style='font-size:22px;font-weight:800;color:{pr_color};letter-spacing:-0.5px'>
          {period_roas:.2f}×</div>
      </div>
      <div style='width:1px;height:44px;background:rgba(255,255,255,0.06);align-self:center'></div>
      <div>
        <div style='font-size:10px;color:rgba(255,255,255,0.22);letter-spacing:1px;
                    text-transform:uppercase;margin-bottom:4px'>Days Below 3×</div>
        <div style='font-size:22px;font-weight:800;letter-spacing:-0.5px;
                    color:{"#f85149" if days_below > 0 else "#3fb950"}'>
          {days_below}<span style='font-size:13px;font-weight:500;opacity:0.4'> / {total_chart_days}</span>
        </div>
      </div>
      <div style='margin-left:auto;font-size:10.5px;color:rgba(255,255,255,0.18);
                  line-height:1.9;text-align:right;align-self:center'>
        <div>Click legend to toggle metrics</div>
        <div style='color:rgba(248,81,73,0.5)'>■ Red shading = ROAS below 3×</div>
        <div style='color:rgba(255,255,255,0.12)'>- - - Target line = 3×</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Build chart ───────────────────────────────────────────────────────────
    fig = go.Figure()

    # Background shading on below-target ROAS days
    below_mask = (df_plot["ROAS"] < 3).values
    in_range, range_start = False, None
    for ri in range(len(df_plot)):
        row_date = df_plot["Date"].iloc[ri]
        if below_mask[ri] and not in_range:
            range_start, in_range = row_date, True
        elif not below_mask[ri] and in_range:
            fig.add_vrect(
                x0=range_start - timedelta(hours=12),
                x1=df_plot["Date"].iloc[ri - 1] + timedelta(hours=12),
                fillcolor="rgba(248,81,73,0.055)", layer="below", line_width=0,
            )
            in_range = False
    if in_range:
        fig.add_vrect(
            x0=range_start - timedelta(hours=12),
            x1=df_plot["Date"].iloc[-1] + timedelta(hours=12),
            fillcolor="rgba(248,81,73,0.055)", layer="below", line_width=0,
        )

    # Purchases — bars, back layer
    fig.add_trace(go.Bar(
        x=df_plot["Date"], y=df_plot["Conversions"],
        yaxis="y1", name="Purchases",
        marker=dict(
            color="rgba(255,166,87,0.3)",
            line=dict(color="rgba(255,166,87,0.65)", width=1),
        ),
        hovertemplate="<b>Purchases</b>: %{y:,.0f} orders<extra></extra>",
    ))

    # Spend — gradient area
    fig.add_trace(go.Scatter(
        x=df_plot["Date"], y=df_plot["Cost"],
        yaxis="y1", name="Spend",
        mode="lines",
        line=dict(color="#58a6ff", width=2.5, shape="spline", smoothing=0.7),
        fill="tozeroy",
        fillgradient=dict(
            type="vertical",
            colorscale=[[0, "rgba(88,166,255,0.28)"], [1, "rgba(88,166,255,0)"]],
        ),
        hovertemplate="<b>Spend</b>: SAR %{y:,.2f}<extra></extra>",
    ))

    # Revenue — gradient area
    fig.add_trace(go.Scatter(
        x=df_plot["Date"], y=df_plot["Conv. Value"],
        yaxis="y1", name="Revenue",
        mode="lines",
        line=dict(color="#3fb950", width=2.5, shape="spline", smoothing=0.7),
        fill="tozeroy",
        fillgradient=dict(
            type="vertical",
            colorscale=[[0, "rgba(63,185,80,0.22)"], [1, "rgba(63,185,80,0)"]],
        ),
        hovertemplate="<b>Revenue</b>: SAR %{y:,.2f}<extra></extra>",
    ))

    # ROAS — segmented line colored green (≥3) or red (<3)
    def build_roas_segments(df):
        segs, seg_x, seg_y, cur = [], [], [], None
        for _, row in df.iterrows():
            c = "#3fb950" if row["ROAS"] >= 3 else "#f85149"
            if c != cur:
                if seg_x:
                    seg_x.append(row["Date"])
                    seg_y.append(row["ROAS"])
                    segs.append(dict(x=seg_x[:], y=seg_y[:], color=cur))
                seg_x, seg_y, cur = [row["Date"]], [row["ROAS"]], c
            else:
                seg_x.append(row["Date"])
                seg_y.append(row["ROAS"])
        if seg_x:
            segs.append(dict(x=seg_x, y=seg_y, color=cur))
        return segs

    for i, seg in enumerate(build_roas_segments(df_plot)):
        first = i == 0
        fig.add_trace(go.Scatter(
            x=seg["x"], y=seg["y"],
            yaxis="y2",
            name="ROAS" if first else f"_roas_{i}",
            legendgroup="roas",
            showlegend=first,
            mode="lines",
            line=dict(color=seg["color"], width=2.8, shape="spline", smoothing=0.7),
            hovertemplate="<b>ROAS</b>: %{y:.2f}×<extra></extra>",
        ))

    # Warning markers on below-target days
    below_pts = df_plot[df_plot["ROAS"] < 3]
    if not below_pts.empty:
        fig.add_trace(go.Scatter(
            x=below_pts["Date"], y=below_pts["ROAS"],
            yaxis="y2", name="⚠ Below 3×",
            legendgroup="roas",
            showlegend=True,
            mode="markers",
            marker=dict(
                symbol="triangle-down", size=9, color="#f85149",
                line=dict(color="rgba(255,255,255,0.5)", width=1.2),
            ),
            hovertemplate="<b>⚠ Below Target</b>: ROAS %{y:.2f}×<extra></extra>",
        ))

    # ROAS = 3 target reference line
    fig.add_shape(
        type="line", xref="paper", yref="y2",
        x0=0, y0=3, x1=1, y1=3,
        line=dict(color="rgba(255,255,255,0.12)", width=1.2, dash="dot"),
        layer="above",
    )
    fig.add_annotation(
        x=0.01, y=3, xref="paper", yref="y2",
        text="3× target",
        showarrow=False, xanchor="left",
        font=dict(size=9.5, color="rgba(255,255,255,0.2)", family="Inter"),
        yshift=8,
    )

    # Axis ranges
    left_max = max(df_plot["Cost"].max(), df_plot["Conv. Value"].max(), 1) * 1.35
    roas_max = max(df_plot["ROAS"].max() * 1.4, 5.0)

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0c1018",
        font=dict(family="Inter", color="rgba(255,255,255,0.3)", size=11),
        margin=dict(l=0, r=0, t=10, b=0),
        height=360,
        barmode="overlay",
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.035)", showline=False,
            tickformat="%b %d", tickfont=dict(size=11),
        ),
        yaxis=dict(
            title=dict(text="SAR", font=dict(color="rgba(255,255,255,0.22)", size=10)),
            gridcolor="rgba(255,255,255,0.035)", showline=False,
            tickprefix="SAR ", tickfont=dict(size=11),
            range=[0, left_max],
        ),
        yaxis2=dict(
            title=dict(text="ROAS", font=dict(color="rgba(255,255,255,0.22)", size=10)),
            overlaying="y", side="right",
            showgrid=False, showline=False,
            ticksuffix="×", tickfont=dict(size=11),
            range=[0, roas_max],
        ),
        legend=dict(
            bgcolor="rgba(13,16,24,0.88)",
            bordercolor="rgba(255,255,255,0.07)", borderwidth=1,
            font=dict(size=11, family="Inter", color="rgba(255,255,255,0.6)"),
            orientation="h",
            yanchor="bottom", y=1.05,
            xanchor="left", x=0,
            itemclick="toggle",
            itemdoubleclick="toggleothers",
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#131929", bordercolor="rgba(255,255,255,0.08)",
            font=dict(family="Inter", size=12, color="#f0f6fc"),
            namelength=-1,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No daily data available for this range.")


# ── Spend Breakdown ───────────────────────────────────────────────────────────
if not df_active.empty and df_active["Cost"].sum() > 0:
    st.markdown('<div class="sec-label">Spend Breakdown</div>', unsafe_allow_html=True)
    ca, cb = st.columns(2)

    PALETTE = ["#58a6ff", "#3fb950", "#d2a8ff", "#ffa657", "#f85149", "#39c5d0", "#e3b341"]

    with ca:
        by_type = df_active.groupby("Type")["Cost"].sum().reset_index()
        by_type = by_type[by_type["Cost"] > 0].sort_values("Cost", ascending=False)
        if not by_type.empty:
            fig2 = go.Figure(go.Pie(
                labels=by_type["Type"], values=by_type["Cost"],
                hole=0.65,
                marker=dict(colors=PALETTE[:len(by_type)],
                            line=dict(color="#07090f", width=2)),
                textinfo="label+percent",
                textfont=dict(family="Inter", size=11),
                hovertemplate="<b>%{label}</b><br>SAR %{value:,.2f}<br>%{percent}<extra></extra>",
            ))
            fig2.add_annotation(
                text=f"<b>{fmt_currency(by_type['Cost'].sum())}</b>",
                x=0.5, y=0.5, showarrow=False,
                font=dict(family="Inter", size=13, color="#f0f6fc"),
            )
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="rgba(255,255,255,0.4)"),
                margin=dict(l=0, r=0, t=0, b=0), height=240,
                showlegend=False,
                hoverlabel=dict(bgcolor="#1a2035", font=dict(family="Inter", size=12)),
            )
            st.caption("By campaign type")
            st.plotly_chart(fig2, use_container_width=True)

    with cb:
        top5 = df_active[df_active["Cost"] > 0].nlargest(5, "Cost").copy()
        top5["short"] = top5["Campaign"].str[:30]
        if not top5.empty:
            bar_colors = [PALETTE[i % len(PALETTE)] for i in range(len(top5))]
            fig3 = go.Figure(go.Bar(
                x=top5["Cost"], y=top5["short"],
                orientation="h",
                marker=dict(
                    color=top5["Cost"],
                    colorscale=[[0, "#1a2a45"], [0.5, "#2a5080"], [1, "#58a6ff"]],
                    line=dict(color="rgba(255,255,255,0)", width=0),
                ),
                text=top5["Cost"].apply(lambda v: f"SAR {v:,.0f}"),
                textposition="inside",
                textfont=dict(family="Inter", size=11, color="rgba(255,255,255,0.85)"),
                hovertemplate="<b>%{y}</b><br>SAR %{x:,.2f}<extra></extra>",
            ))
            fig3.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0c1018",
                font=dict(family="Inter", color="rgba(255,255,255,0.35)", size=11),
                margin=dict(l=0, r=0, t=0, b=0), height=240,
                xaxis=dict(showgrid=False, showticklabels=False, showline=False),
                yaxis=dict(gridcolor="rgba(255,255,255,0.03)", autorange="reversed"),
                hoverlabel=dict(bgcolor="#1a2035", font=dict(family="Inter", size=12)),
            )
            st.caption("Top 5 by spend")
            st.plotly_chart(fig3, use_container_width=True)


