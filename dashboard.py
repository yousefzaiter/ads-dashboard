import io
import os
import smtplib
import urllib.parse
import requests
import pandas as pd
import streamlit as st
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
    status      = row.get("Status", "")
    camp_type   = str(row.get("Type", "")).upper()

    roas = round(conv_value / spend, 2) if spend > 0 else 0.0

    # ── Paused ──
    if status != "ENABLED":
        return dict(tier="paused", emoji="⏸", label="موقوفة", color="#3d4354",
                    decision="الحملة موقوفة حالياً",
                    reason="لا توجد بيانات أداء في الفترة المحددة",
                    action="أعد تفعيلها إذا كانت ذات صلة بالموسم أو المنتج الحالي",
                    roas=0, spend=spend)

    # ── Insufficient data ──
    if impressions < 50 and spend < 3:
        return dict(tier="insufficient", emoji="🔵", label="بيانات غير كافية", color="#58a6ff",
                    decision="بيانات غير كافية للتقييم",
                    reason=f"الظهورات {impressions:,} والإنفاق SAR {spend:.2f} — لا تكفي لحكم دقيق",
                    action="شغّل الحملة 3–5 أيام إضافية قبل اتخاذ أي قرار",
                    roas=roas, spend=spend)

    # ── CTR benchmarks by type ──
    if "SEARCH" in camp_type:
        ctr_good, ctr_low = 3.0, 1.0
    elif "SHOPPING" in camp_type:
        ctr_good, ctr_low = 0.8, 0.25
    else:
        ctr_good, ctr_low = 0.6, 0.15

    issues, strengths = [], []

    # CTR
    if ctr >= ctr_good:
        strengths.append(("ctr_strong", ctr))
    elif ctr >= ctr_low:
        issues.append(("ctr_low", ctr))
    else:
        issues.append(("ctr_very_low", ctr))

    # Conversions & ROAS
    if conversions > 0:
        if roas >= 3:
            strengths.append(("roas_excellent", roas))
        elif roas >= 1.5:
            strengths.append(("roas_good", roas))
        elif roas >= 0.8:
            issues.append(("roas_low", roas))
        else:
            issues.append(("roas_very_low", roas))
        if cpa > 0:
            if cpa <= 120:   strengths.append(("cpa_ok", cpa))
            elif cpa <= 300: issues.append(("cpa_high", cpa))
            else:            issues.append(("cpa_very_high", cpa))
    else:
        if spend >= 40:   issues.append(("no_conv_high", spend))
        elif spend >= 10: issues.append(("no_conv_mid",  spend))
        else:             issues.append(("no_conv_low",  spend))

    # ── Tier ──
    critical = [i for i in issues    if i[0] in ("roas_very_low", "no_conv_high", "ctr_very_low")]
    strong_s = [s for s in strengths if s[0] in ("roas_excellent", "ctr_strong")]

    if strong_s and not issues and conversions > 0:
        tier = "strong"
    elif critical:
        tier = "weak"
    else:
        tier = "moderate"

    # ── Arabic copy ──
    if tier == "strong":
        parts = []
        for k, v in strengths:
            if k == "ctr_strong":     parts.append(f"CTR ممتاز ({v:.2f}%)")
            elif k == "roas_excellent": parts.append(f"ROAS قوي ({v:.1f}×)")
            elif k == "cpa_ok":         parts.append(f"CPA مناسب ({v:.0f} SAR)")
        decision = "ارفع الميزانية +20% إلى +30%"
        reason   = "الحملة تحقق نتائج ممتازة — " + "، ".join(parts)
        action   = "زِد الميزانية اليومية 20–30%، هذا الوقت المناسب للتوسع واستغلال الزخم الحالي"
        color, emoji, label = "#3fb950", "🟢", "قوي — Scale"

    elif tier == "weak":
        r_parts, a_parts = [], []
        for k, v in issues:
            if k == "no_conv_high":
                r_parts.append(f"صُرف SAR {v:.0f} بدون أي تحويل واحد")
                a_parts.append("أوقف الحملة فوراً وراجع الاستهداف والإعلانات من الصفر")
            elif k == "ctr_very_low":
                r_parts.append(f"CTR منخفض جداً ({v:.2f}%) — الإعلانات لا تجذب أحداً")
                a_parts.append("عدّل الصور والعناوين جذرياً أو أوقف الحملة وأعد بناءها")
            elif k == "roas_very_low":
                r_parts.append(f"ROAS ضعيف جداً ({v:.1f}×) — الحملة تخسر")
                a_parts.append("قلّل الإنفاق فوراً وراجع الاستراتيجية بالكامل")
        decision = "أوقف الحملة أو عدّلها"
        reason   = " · ".join(r_parts) if r_parts else "الأداء العام ضعيف جداً"
        action   = a_parts[0] if a_parts else "راجع الحملة بالكامل وعدّل الاستراتيجية"
        color, emoji, label = "#f85149", "🔴", "ضعيف — Pause"

    else:  # moderate
        r_parts, a_parts = [], []
        for k, v in issues:
            if k == "ctr_low":
                r_parts.append(f"CTR ({v:.2f}%) أقل من المستهدف")
                a_parts.append("جرّب عناوين وصور جديدة لرفع نسبة النقر")
            elif k == "roas_low":
                r_parts.append(f"ROAS ({v:.1f}×) دون المستهدف 3×")
                a_parts.append("حسّن صفحة الهبوط أو عدّل الاستهداف لرفع الـ ROAS")
            elif k == "cpa_high":
                r_parts.append(f"CPA مرتفع ({v:.0f} SAR)")
                a_parts.append("ضيّق نطاق الاستهداف لتخفيض تكلفة التحويل")
            elif k == "cpa_very_high":
                r_parts.append(f"CPA مرتفع جداً ({v:.0f} SAR)")
                a_parts.append("راجع الجمهور المستهدف وعدّل العروض لتخفيض CPA")
            elif k in ("no_conv_mid", "no_conv_low"):
                r_parts.append("لم تتحقق تحويلات بعد في هذه الفترة")
                a_parts.append("أعطِ الحملة وقتاً أطول وتأكد من صحة تتبع التحويلات")
        for k, v in strengths:
            if k == "ctr_strong": r_parts.append(f"CTR جيد ({v:.2f}%)")
        decision = "بحاجة تحسين"
        reason   = " · ".join(r_parts) if r_parts else "الأداء متوسط، هناك مجال للتحسين"
        action   = a_parts[0] if a_parts else "راجع الحملة وجرّب تحسينات تدريجية"
        color, emoji, label = "#e3b341", "🟡", "يحتاج تحسين — Optimize"

    return dict(tier=tier, emoji=emoji, label=label, color=color,
                decision=decision, reason=reason, action=action,
                roas=roas, spend=spend)


def campaign_card(row: pd.Series, d: dict) -> str:
    """Render a single campaign as an HTML card with AI recommendation."""
    name   = row["Campaign"]
    status = row["Status"]
    color  = d["color"]
    ctype  = TYPE_LABELS.get(str(row.get("Type","")).upper(), str(row.get("Type","")))
    roas_v = d["roas"]

    is_active  = status == "ENABLED"
    has_data   = row["Impressions"] > 0 or row["Cost"] > 0
    bg_tint    = hex_to_rgba(color, 0.045)
    border_col = hex_to_rgba(color, 0.18)

    status_dot = (
        '<span style="font-size:10px;color:#3fb950;font-weight:700">● نشطة</span>'
        if is_active else
        '<span style="font-size:10px;color:rgba(255,255,255,0.2);font-weight:500">○ موقوفة</span>'
    )

    # Compact row for paused-with-no-data
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

    # Metric chips
    roas_chip = (
        f'<div style="text-align:center;padding:0 8px;border-left:1px solid rgba(255,255,255,0.06)">'
        f'<div style="font-size:9.5px;color:rgba(255,255,255,0.22);letter-spacing:.5px;margin-bottom:2px">ROAS</div>'
        f'<div style="font-size:13px;font-weight:700;color:{"#3fb950" if roas_v>=3 else "#f85149" if roas_v>0 else "rgba(255,255,255,0.3)"}">'
        f'{roas_v:.1f}×</div></div>'
    ) if roas_v > 0 else ""

    def chip(icon, label, val):
        return (
            f'<div style="text-align:center;padding:0 10px">'
            f'<div style="font-size:9.5px;color:rgba(255,255,255,0.22);letter-spacing:.5px;margin-bottom:2px">{label}</div>'
            f'<div style="font-size:13px;font-weight:600;color:rgba(255,255,255,0.75)">{val}</div>'
            f'</div>'
        )

    metrics_html = (
        chip("👁", "Impr.", fmt_number(row["Impressions"])) +
        chip("🖱", "Clicks", f"{row['Clicks']:,}") +
        chip("📊", "CTR", f"{row['CTR']:.2f}%") +
        chip("💸", "Spend", f"SAR {row['Cost']:,.0f}") +
        chip("🎯", "Conv.", f"{row['Conversions']:.0f}") +
        roas_chip
    )

    # Tier badge
    tier_badge = (
        f'<div style="display:flex;align-items:center;gap:6px;padding:5px 12px;'
        f'background:{hex_to_rgba(color,0.1)};border:1px solid {border_col};'
        f'border-radius:20px;flex-shrink:0">'
        f'<span style="font-size:13px">{d["emoji"]}</span>'
        f'<span style="font-size:11px;font-weight:700;color:{color};white-space:nowrap">{d["label"]}</span>'
        f'</div>'
    )

    # AI section (RTL Arabic)
    ai_html = (
        f'<div style="padding:14px 20px 16px;border-top:1px solid rgba(255,255,255,0.04);'
        f'background:{bg_tint};direction:rtl;text-align:right">'
        f'<div style="font-size:14.5px;font-weight:800;color:{color};margin-bottom:6px;'
        f'line-height:1.3">{d["emoji"]} {d["decision"]}</div>'
        f'<div style="font-size:12.5px;color:rgba(255,255,255,0.48);margin-bottom:6px;'
        f'line-height:1.65">{d["reason"]}</div>'
        f'<div style="font-size:12px;color:rgba(255,255,255,0.28);line-height:1.5">'
        f'💡 {d["action"]}</div>'
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

# ── Auth (needed early for client list) ───────────────────────────────────────
try:
    token, dev_token, root_cid, mcc_id = get_access_token()
except Exception as e:
    st.error(f"Authentication failed: {e}")
    st.stop()

clients = fetch_clients(token, dev_token, root_cid, mcc_id)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:4px 0 20px'>
      <div style='font-size:17px;font-weight:800;color:#f0f6fc;letter-spacing:-0.5px'>⚡ Ads Intelligence</div>
      <div style='font-size:11px;color:rgba(255,255,255,0.3);margin-top:3px'>Media Buying Dashboard</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    vis_sidebar = st.session_state.get("client_name_visible", False)

    # ── Logout ────────────────────────────────────────────────────────────────
    current_username = st.session_state.get("username", "")
    user_info = get_user(current_username)

    col_user, col_logout = st.columns([2, 1])
    col_user.markdown(
        f"<div style='font-size:12px;color:rgba(255,255,255,0.4);padding-top:6px'>"
        f"👤 {current_username}</div>",
        unsafe_allow_html=True,
    )
    if col_logout.button("Logout", use_container_width=True):
        do_logout()

    st.divider()

    # ── Client selector (admin: dropdown / client: locked) ────────────────────
    if user_info.get("role") == "admin":
        # Red glow on the dropdown when privacy mode is on
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
            {"id": cid, "name": name,
             "display": mask_name(name, vis_sidebar)}
            for name, cid in clients.items()
        ]
        sel = st.selectbox(
            "CLIENT",
            options=client_options,
            format_func=lambda x: x["display"],
            label_visibility="visible",
            key="selected_client")
        selected_client      = sel["name"]
        selected_customer_id = sel["id"]
    else:
        # Client user: locked to their assigned account
        assigned_cid = user_info.get("client_id", "")
        assigned_name = next(
            (n for n, c in clients.items() if c == assigned_cid),
            assigned_cid,
        )
        selected_client      = assigned_name
        selected_customer_id = assigned_cid
        st.markdown(
            f"<div style='font-size:11px;color:rgba(255,255,255,0.3);letter-spacing:1px;"
            f"text-transform:uppercase;margin-bottom:4px'>Client</div>"
            f"<div style='font-size:14px;color:#f0f6fc;font-weight:600'>"
            f"{mask_name(assigned_name, vis_sidebar)}</div>",
            unsafe_allow_html=True,
        )
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

    st.markdown("""
    <div style='margin-top:24px;padding:14px;background:rgba(255,255,255,0.03);
                border-radius:12px;border:1px solid rgba(255,255,255,0.05)'>
      <div style='font-size:10px;color:rgba(255,255,255,0.2);letter-spacing:1px;
                  text-transform:uppercase;margin-bottom:8px'>Data source</div>
      <div style='font-size:11.5px;color:rgba(255,255,255,0.45);font-weight:500'>
        Google Ads API v20</div>
      <div style='font-size:10.5px;color:rgba(255,255,255,0.2);margin-top:2px'>
        Auto-refresh every 5 min</div>
    </div>
    """, unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
start_str = start_date.strftime("%Y-%m-%d")
end_str   = end_date.strftime("%Y-%m-%d")

vis = st.session_state["client_name_visible"]

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
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
with col_h2:
    st.markdown("""
    <div style='display:flex;justify-content:flex-end;align-items:flex-start;padding-top:10px;gap:10px'>
      <div class='pill-live'><span class='dot-pulse'></span>Live</div>
    </div>
    """, unsafe_allow_html=True)
    eye_label = "🙈 Hide Client" if vis else "👁 Show Client"
    if st.button(eye_label, use_container_width=True, key="toggle_vis_btn"):
        st.session_state["client_name_visible"] = not vis
        st.rerun()

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

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

# WhatsApp-safe emojis only (📅 👁️ 🖱️ ⚡ render as ? on many devices)
_wa_msg = (
    "مرحباً،\n"
    "هذا ملخص أداء حملاتك الإعلانية:\n\n"
    f"📊 الفترة: {start_str} - {end_str}\n"
    f"💰 الإنفاق: {fmt_currency(total_spend)}\n"
    f"📊 الظهور: {fmt_number(total_impr)}\n"
    f"📊 النقرات: {fmt_number(total_clicks)}\n"
    f"📈 ROAS: {roas:.2f}x\n"
    f"✅ التحويلات: {total_conv:.0f}\n\n"
    "📎 التقرير المفصّل مرفق في الأسفل\n\n"
    "🔗 لمشاهدة التقرير التفاعلي:\n"
    "https://ads-dashboard.yousefzaiter.com\n\n"
    "Ads Intelligence"
)
# safe='' encodes everything including slashes and emoji as %XX sequences
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

cols = st.columns(7)
metrics = [
    ("💸", "Total Spend",   fmt_currency(total_spend),           f"{len(df_active[df_active['Cost']>0])} active campaigns", "#58a6ff"),
    ("👁",  "Impressions",   fmt_number(total_impr),              "Total ad views",                                          "#d2a8ff"),
    ("🖱",  "Clicks",        fmt_number(total_clicks),            "Total link clicks",                                       "#3fb950"),
    ("📊", "CTR",           f"{avg_ctr:.2f}%",                   "Click-through rate",                                      "#39c5d0"),
    ("⚡", "Avg. CPC",      fmt_currency(avg_cpc),               "Cost per click",                                          "#ffa657"),
    ("🎯", "Conversions",   f"{total_conv:,.1f}",                "Total conversions",                                       "#ff6b9d"),
    ("💰", "CPA",           fmt_currency(cpa) if total_conv else "—", "Cost per conversion",                               "#e3b341"),
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


# ── Campaign Intelligence ──────────────────────────────────────────────────────
st.markdown('<div class="sec-label">توصيات الذكاء الاصطناعي — Campaign Intelligence</div>',
            unsafe_allow_html=True)

if not df_active.empty:
    # Generate all decisions first (needed for summary counts)
    all_decisions = {i: ai_decision(row) for i, row in df_active.iterrows()}

    # Summary counts
    n_strong   = sum(1 for d in all_decisions.values() if d["tier"] == "strong")
    n_moderate = sum(1 for d in all_decisions.values() if d["tier"] == "moderate")
    n_weak     = sum(1 for d in all_decisions.values() if d["tier"] == "weak")
    n_active   = sum(1 for d in all_decisions.values() if d["tier"] not in ("paused",))
    n_paused   = sum(1 for d in all_decisions.values() if d["tier"] == "paused")

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;
                padding:14px 20px;background:#0a0d14;border:1px solid rgba(255,255,255,0.05);
                border-radius:12px;margin-bottom:18px;font-size:12px">
      <span style="color:rgba(255,255,255,0.3)">{len(df_active)} حملة</span>
      <span style="color:rgba(255,255,255,0.1)">|</span>
      <span style="color:#3fb950;font-weight:600">🟢 {n_strong} قوي</span>
      <span style="color:#e3b341;font-weight:600">🟡 {n_moderate} يحتاج تحسين</span>
      <span style="color:#f85149;font-weight:600">🔴 {n_weak} ضعيف</span>
      <span style="color:rgba(255,255,255,0.2)">⏸ {n_paused} موقوفة</span>
      <span style="margin-left:auto;font-size:11px;color:rgba(255,255,255,0.15)">
        {start_str} → {end_str}
      </span>
    </div>
    """, unsafe_allow_html=True)

    # Controls
    fc1, fc2, fc3 = st.columns([2, 2, 1])
    sort_by = fc1.selectbox(
        "Sort", ["Cost", "Clicks", "CTR", "Impressions", "Conversions"],
        label_visibility="collapsed")
    tier_filter = fc2.selectbox(
        "Filter", ["الكل", "🟢 قوي", "🟡 يحتاج تحسين", "🔴 ضعيف"],
        label_visibility="collapsed")
    sort_asc = fc3.selectbox(
        "Dir", ["↓ Desc", "↑ Asc"],
        label_visibility="collapsed") == "↑ Asc"

    tier_map = {"🟢 قوي": "strong", "🟡 يحتاج تحسين": "moderate", "🔴 ضعيف": "weak"}
    df_sorted = df_active.sort_values(sort_by, ascending=sort_asc)

    # Render active campaigns (full cards)
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

    # Paused campaigns (compact, only if show_paused toggled on)
    if show_paused:
        for i, row in paused_rows.iterrows():
            d = all_decisions[i]
            cards_html += campaign_card(row, d)

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
