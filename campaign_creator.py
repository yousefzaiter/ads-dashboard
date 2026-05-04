import json
import os
import re

import requests
import streamlit as st
from bs4 import BeautifulSoup

# ── Constants ──────────────────────────────────────────────────────────────────

CAMPAIGN_TYPES = ["Performance Max", "Search", "Demand Gen"]

ANGLES = [
    "السعر / العرض (Price & Offer)",
    "الجودة / المصداقية (Quality & Trust)",
    "حل مشكلة (Problem & Solution)",
    "الندرة / الإلحاح (Scarcity & Urgency)",
    "🤖 اقترح أنت (AI chooses best angle)",
]

LANGUAGES = ["العربية", "English", "كلاهما (Both)"]

POWER_WORDS = {
    "free", "now", "today", "best", "top", "new", "save", "get", "exclusive",
    "limited", "proven", "guaranteed", "instant", "offer", "deal",
    "مجاني", "الآن", "اليوم", "أفضل", "جديد", "وفر", "احصل", "حصري",
    "مضمون", "فوري", "عرض", "خصم",
}

SYSTEM_PROMPT = (
    "You are an expert Google Ads copywriter specializing in high-converting ad copy. "
    "You follow Google Ads character limits strictly and count every character carefully "
    "(spaces count). You write persuasive, action-oriented copy tailored to the target "
    "audience and marketing angle. Return ONLY valid JSON — no markdown, no code fences, "
    "no explanation."
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _rate(text: str) -> str:
    lower = text.lower()
    score = (1 if re.search(r"\d", text) else 0) + (
        1 if any(w in lower for w in POWER_WORDS) else 0
    )
    return "🔥" if score >= 2 else ("⚡" if score == 1 else "💡")


def _char_badge(text: str, limit: int) -> str:
    n = len(text)
    ok = n <= limit
    color = "#3fb950" if ok else "#f85149"
    icon = "✅" if ok else "❌"
    return (
        f"<span style='font-size:11px;color:{color};font-family:monospace'>"
        f"{icon} {n}/{limit}</span>"
    )


def _copy_btn(text: str, key: str) -> None:
    safe = (
        text.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "")
    )
    st.markdown(
        f"<button onclick=\"navigator.clipboard.writeText('{safe}')"
        f".then(()=>this.textContent='✅ Copied')"
        f".catch(()=>this.textContent='❌');"
        f"setTimeout(()=>this.textContent='Copy',1800)\" "
        f"style='background:#1e2433;color:rgba(255,255,255,0.55);"
        f"border:1px solid rgba(255,255,255,0.1);border-radius:6px;"
        f"padding:3px 10px;font-size:11px;cursor:pointer;margin-top:2px'>"
        f"Copy</button>",
        unsafe_allow_html=True,
    )


def _section_header(title: str) -> None:
    st.markdown(
        f"<div style='font-size:11px;font-weight:700;letter-spacing:1.2px;"
        f"text-transform:uppercase;color:rgba(255,255,255,0.3);"
        f"margin:28px 0 10px;border-bottom:1px solid rgba(255,255,255,0.06);"
        f"padding-bottom:6px'>{title}</div>",
        unsafe_allow_html=True,
    )


# ── Landing page fetcher ───────────────────────────────────────────────────────

def fetch_landing_page(url: str) -> dict:
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        meta = soup.find("meta", {"name": "description"}) or soup.find(
            "meta", {"property": "og:description"}
        )
        meta_desc = meta.get("content", "").strip() if meta else ""

        h1s = [h.get_text(strip=True) for h in soup.find_all("h1")][:3]
        h2s = [h.get_text(strip=True) for h in soup.find_all("h2")][:5]

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        words = soup.get_text(separator=" ").split()
        body_text = " ".join(words[:500])

        return {
            "success": True,
            "title": title,
            "meta_description": meta_desc,
            "headings": [h for h in h1s + h2s if h],
            "body_text": body_text,
        }
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out (12s). Try a different URL."}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.response.status_code}: {e.response.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Claude API ─────────────────────────────────────────────────────────────────

def _build_prompt(
    campaign_type: str,
    angle: str,
    page: dict,
    product_desc: str,
    language: str,
) -> str:
    needs_long = campaign_type in ("Performance Max", "Demand Gen")
    needs_pmax = campaign_type == "Performance Max"
    needs_dgen = campaign_type == "Demand Gen"

    angle_instruction = (
        "Choose the single most effective marketing angle yourself based on the "
        "landing page content and product type."
        if "AI chooses" in angle
        else f"Use this marketing angle: {angle}"
    )

    headings_str = (
        "\n".join(f"    - {h}" for h in page.get("headings", []))
        or "    (none found)"
    )

    extra_context = (
        f"\nAdditional Product Context:\n  {product_desc.strip()}"
        if product_desc.strip()
        else ""
    )

    expected = {
        "headlines": ["headline text"] * 15,
        "descriptions": ["description text"] * 4,
        "sitelinks": [
            {"title": "title text", "desc1": "desc line 1", "desc2": "desc line 2"}
        ] * 4,
        "long_headlines": (["long headline text"] * 5) if needs_long else [],
        "audience_signals": (["audience description"] * 3) if needs_pmax else [],
        "asset_groups": (["Asset Group Name"] * 3) if needs_pmax else [],
        "youtube_desc": ("youtube description text") if needs_dgen else "",
        "thumbnail_angles": (["visual concept description"] * 3) if needs_dgen else [],
    }

    rules = [
        "Exactly 15 headlines (each ≤30 chars — count carefully, spaces count)",
        "Exactly 4 descriptions (each ≤90 chars)",
        "Exactly 4 sitelinks: title ≤25, desc1 ≤35, desc2 ≤35",
    ]
    if needs_long:
        rules.append("Exactly 5 long_headlines (each ≤90 chars)")
    if needs_pmax:
        rules.append("Exactly 3 audience_signals and 3 asset_groups")
    if needs_dgen:
        rules.append("Exactly 1 youtube_desc (≤200 chars) and 3 thumbnail_angles")
    rules.append(f"Write all copy in: {language}")
    rules.append("No pipes (|) in any text field")
    rules.append("Return ONLY the JSON object — no markdown, no explanation")

    return (
        f"Campaign Type: {campaign_type}\n"
        f"Marketing Angle: {angle_instruction}\n"
        f"Language: {language}\n\n"
        f"Landing Page Data:\n"
        f"  Title: {page.get('title', '')}\n"
        f"  Meta Description: {page.get('meta_description', '')}\n"
        f"  Key Headings:\n{headings_str}\n"
        f"  Page Content (first 500 words):\n  {page.get('body_text', '')}\n"
        f"{extra_context}\n\n"
        f"RULES:\n" + "\n".join(f"- {r}" for r in rules) + "\n\n"
        f"Return this JSON structure (replace placeholder values with real copy):\n"
        f"{json.dumps(expected, ensure_ascii=False, indent=2)}"
    )


def call_claude(
    campaign_type: str,
    angle: str,
    page: dict,
    product_desc: str,
    language: str,
) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set in .env"}

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_prompt(campaign_type, angle, page, product_desc, language)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip markdown code fences if the model wrapped the JSON
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"```$", "", raw, flags=re.MULTILINE).strip()

        return json.loads(raw)

    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw": raw}
    except Exception as e:
        return {"error": str(e)}


# ── Violation checker ──────────────────────────────────────────────────────────

def _violations(result: dict) -> list[str]:
    v = []
    for i, h in enumerate(result.get("headlines", []), 1):
        if len(h) > 30:
            v.append(f"Headline {i}: {len(h)}/30 chars")
    for i, d in enumerate(result.get("descriptions", []), 1):
        if len(d) > 90:
            v.append(f"Description {i}: {len(d)}/90 chars")
    for i, sl in enumerate(result.get("sitelinks", []), 1):
        if len(sl.get("title", "")) > 25:
            v.append(f"Sitelink {i} title: {len(sl.get('title', ''))}/25 chars")
        if len(sl.get("desc1", "")) > 35:
            v.append(f"Sitelink {i} desc 1: {len(sl.get('desc1', ''))}/35 chars")
        if len(sl.get("desc2", "")) > 35:
            v.append(f"Sitelink {i} desc 2: {len(sl.get('desc2', ''))}/35 chars")
    for i, lh in enumerate(result.get("long_headlines", []), 1):
        if len(lh) > 90:
            v.append(f"Long Headline {i}: {len(lh)}/90 chars")
    if len(result.get("youtube_desc", "")) > 200:
        v.append(f"YouTube description: {len(result.get('youtube_desc', ''))}/200 chars")
    return v


# ── Copy-all formatter ─────────────────────────────────────────────────────────

def _copy_all_text(result: dict, campaign_type: str) -> str:
    lines = ["=" * 52, f"CAMPAIGN TYPE: {campaign_type}", "=" * 52, ""]

    lines += ["--- HEADLINES (max 30 chars each) ---"]
    for i, h in enumerate(result.get("headlines", []), 1):
        lines.append(f"{i:02}. {h}  [{len(h)}/30]")

    lines += ["", "--- DESCRIPTIONS (max 90 chars each) ---"]
    for i, d in enumerate(result.get("descriptions", []), 1):
        lines.append(f"{i}. {d}  [{len(d)}/90]")

    lines += ["", "--- SITELINKS ---"]
    for i, sl in enumerate(result.get("sitelinks", []), 1):
        lines += [
            f"Sitelink {i}:",
            f"  Title:  {sl.get('title','')}  [{len(sl.get('title',''))}/25]",
            f"  Desc 1: {sl.get('desc1','')}  [{len(sl.get('desc1',''))}/35]",
            f"  Desc 2: {sl.get('desc2','')}  [{len(sl.get('desc2',''))}/35]",
        ]

    if result.get("long_headlines"):
        lines += ["", "--- LONG HEADLINES (max 90 chars each) ---"]
        for i, lh in enumerate(result.get("long_headlines", []), 1):
            lines.append(f"{i}. {lh}  [{len(lh)}/90]")

    if result.get("audience_signals"):
        lines += ["", "--- AUDIENCE SIGNALS ---"]
        for s in result.get("audience_signals", []):
            lines.append(f"• {s}")

    if result.get("asset_groups"):
        lines += ["", "--- ASSET GROUP NAMES ---"]
        for g in result.get("asset_groups", []):
            lines.append(f"• {g}")

    if result.get("youtube_desc"):
        lines += ["", "--- YOUTUBE DESCRIPTION ---", result.get("youtube_desc", "")]

    if result.get("thumbnail_angles"):
        lines += ["", "--- THUMBNAIL ANGLES ---"]
        for a in result.get("thumbnail_angles", []):
            lines.append(f"• {a}")

    return "\n".join(lines)


# ── Output section renderers ───────────────────────────────────────────────────

def _render_headlines(headlines: list) -> None:
    _section_header(f"Headlines — {len(headlines)}/15  ·  max 30 chars each")
    for i, hl in enumerate(headlines[:15]):
        c1, c2, c3, c4 = st.columns([4.5, 1.1, 0.55, 0.75])
        c1.text_input(" ", value=hl, key=f"hl_{i}", label_visibility="collapsed")
        c2.markdown(_char_badge(hl, 30), unsafe_allow_html=True)
        c3.markdown(
            f"<div style='padding-top:6px;font-size:16px;text-align:center'>{_rate(hl)}</div>",
            unsafe_allow_html=True,
        )
        with c4:
            _copy_btn(hl, f"cp_hl_{i}")


def _render_descriptions(descs: list) -> None:
    _section_header(f"Descriptions — {len(descs)}/4  ·  max 90 chars each")
    for i, d in enumerate(descs[:4]):
        c1, c2, c3 = st.columns([5, 1.1, 0.75])
        c1.text_input(" ", value=d, key=f"desc_{i}", label_visibility="collapsed")
        c2.markdown(_char_badge(d, 90), unsafe_allow_html=True)
        with c3:
            _copy_btn(d, f"cp_desc_{i}")


def _render_sitelinks(sitelinks: list) -> None:
    _section_header(f"Sitelinks — {len(sitelinks)}/4")
    for i, sl in enumerate(sitelinks[:4]):
        t  = sl.get("title", "")
        d1 = sl.get("desc1", "")
        d2 = sl.get("desc2", "")
        with st.expander(f"Sitelink {i + 1}  —  {t}", expanded=True):
            r1, r1b = st.columns([4, 1])
            r1.text_input("Title (25)", value=t, key=f"sl_t_{i}")
            r1b.markdown(_char_badge(t, 25), unsafe_allow_html=True)

            r2, r2b = st.columns([4, 1])
            r2.text_input("Desc 1 (35)", value=d1, key=f"sl_d1_{i}")
            r2b.markdown(_char_badge(d1, 35), unsafe_allow_html=True)

            r3, r3b = st.columns([4, 1])
            r3.text_input("Desc 2 (35)", value=d2, key=f"sl_d2_{i}")
            r3b.markdown(_char_badge(d2, 35), unsafe_allow_html=True)

            _copy_btn(f"{t}\n{d1}\n{d2}", f"cp_sl_{i}")


def _render_long_headlines(lhls: list) -> None:
    _section_header(f"Long Headlines — {len(lhls)}/5  ·  max 90 chars each")
    for i, lhl in enumerate(lhls[:5]):
        c1, c2, c3 = st.columns([5, 1.1, 0.75])
        c1.text_input(" ", value=lhl, key=f"lhl_{i}", label_visibility="collapsed")
        c2.markdown(_char_badge(lhl, 90), unsafe_allow_html=True)
        with c3:
            _copy_btn(lhl, f"cp_lhl_{i}")


def _render_pmax_extras(result: dict) -> None:
    signals = result.get("audience_signals", [])
    if signals:
        _section_header("Audience Signals — 3 suggestions")
        for i, s in enumerate(signals[:3]):
            st.markdown(
                f"<div style='background:rgba(88,166,255,0.06);"
                f"border:1px solid rgba(88,166,255,0.15);border-radius:10px;"
                f"padding:10px 14px;margin-bottom:6px;font-size:13px;"
                f"color:rgba(255,255,255,0.7)'><b style='color:rgba(88,166,255,0.8)'>"
                f"{i+1}.</b> {s}</div>",
                unsafe_allow_html=True,
            )

    groups = result.get("asset_groups", [])
    if groups:
        _section_header("Asset Group Names — 3 suggestions")
        for i, g in enumerate(groups[:3]):
            c1, c2 = st.columns([5.5, 0.75])
            c1.text_input(" ", value=g, key=f"ag_{i}", label_visibility="collapsed")
            with c2:
                _copy_btn(g, f"cp_ag_{i}")


def _render_dgen_extras(result: dict) -> None:
    yt = result.get("youtube_desc", "")
    if yt:
        _section_header("YouTube Description  ·  max 200 chars")
        c1, c2, c3 = st.columns([5, 1.1, 0.75])
        c1.text_area(" ", value=yt, key="yt_desc", height=80, label_visibility="collapsed")
        c2.markdown(_char_badge(yt, 200), unsafe_allow_html=True)
        with c3:
            _copy_btn(yt, "cp_yt")

    angles = result.get("thumbnail_angles", [])
    if angles:
        _section_header("Thumbnail Angle Suggestions — 3")
        for i, a in enumerate(angles[:3]):
            st.markdown(
                f"<div style='background:rgba(188,140,255,0.06);"
                f"border:1px solid rgba(188,140,255,0.15);border-radius:10px;"
                f"padding:10px 14px;margin-bottom:6px;font-size:13px;"
                f"color:rgba(255,255,255,0.7)'><b style='color:rgba(188,140,255,0.8)'>"
                f"{i+1}.</b> {a}</div>",
                unsafe_allow_html=True,
            )


# ── Main entry point ───────────────────────────────────────────────────────────

def render_campaign_creator() -> None:
    st.markdown("""
    <div style='padding:8px 0 20px'>
      <div style='font-size:26px;font-weight:900;color:#f0f6fc;letter-spacing:-1px'>
        ✍️ Campaign Creator
      </div>
      <div style='font-size:13px;color:rgba(255,255,255,0.28);margin-top:5px'>
        AI-powered Google Ads copy — headlines, descriptions, sitelinks &amp; more
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Session state ─────────────────────────────────────────────────────────
    st.session_state.setdefault("cc_result", None)
    st.session_state.setdefault("cc_page_data", None)
    st.session_state.setdefault("cc_url_fetched", "")
    st.session_state.setdefault("cc_campaign_type", "Search")

    # ── Inputs ────────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    campaign_type = c1.selectbox("Campaign Type *", CAMPAIGN_TYPES, key="cc_ctype")
    angle = c2.selectbox("Marketing Angle *", ANGLES, key="cc_angle")

    url_col, btn_col = st.columns([5, 1])
    url = url_col.text_input(
        "Landing Page URL *",
        placeholder="https://example.com/product-page",
        key="cc_url",
    )
    fetch_clicked = btn_col.button(
        "🔍 Fetch", use_container_width=True, key="cc_fetch"
    )

    if fetch_clicked:
        if not url.strip():
            st.error("Please enter a URL first.")
        else:
            with st.spinner("Fetching landing page content…"):
                page_data = fetch_landing_page(url.strip())
            if page_data.get("success"):
                st.session_state["cc_page_data"] = page_data
                st.session_state["cc_url_fetched"] = url.strip()
                st.success(
                    f"✓ Page fetched — \"{page_data.get('title','')[:70]}\""
                )
            else:
                st.error(f"Could not fetch page: {page_data.get('error', 'Unknown error')}")
                st.session_state["cc_page_data"] = None

    page_data = st.session_state.get("cc_page_data")

    # Show what was fetched
    if page_data and page_data.get("success") and st.session_state.get("cc_url_fetched"):
        with st.expander("📄 Fetched page content (used by AI)", expanded=False):
            st.write(f"**Title:** {page_data.get('title','')}")
            st.write(f"**Meta description:** {page_data.get('meta_description','')}")
            headings = page_data.get("headings", [])
            if headings:
                st.write("**Headings:** " + " · ".join(headings))
            st.caption(f"Body text preview: {page_data.get('body_text','')[:300]}…")

    product_desc = st.text_area(
        "Product Description (optional — add context the page doesn't cover)",
        placeholder="e.g. We offer free shipping, 30-day returns, and a 3-year warranty…",
        height=90,
        key="cc_product_desc",
    )

    language = st.radio(
        "Language *",
        LANGUAGES,
        index=0,
        horizontal=True,
        key="cc_language",
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    can_generate = bool(page_data and page_data.get("success"))

    generate_clicked = st.button(
        "🚀 توليد المحتوى",
        type="primary",
        disabled=not can_generate,
        key="cc_generate",
    )

    if not can_generate:
        st.caption("Fetch a landing page successfully to enable generation.")

    if generate_clicked and can_generate:
        with st.spinner("Calling Claude AI — generating ad copy…"):
            result = call_claude(
                campaign_type=campaign_type,
                angle=angle,
                page=page_data,
                product_desc=product_desc,
                language=language,
            )
        st.session_state["cc_result"] = result
        st.session_state["cc_campaign_type"] = campaign_type

    # ── Results ───────────────────────────────────────────────────────────────
    result = st.session_state.get("cc_result")
    if not result:
        return

    if "error" in result:
        st.error(f"Generation failed: {result['error']}")
        if "raw" in result:
            with st.expander("Raw API response"):
                st.code(result["raw"])
        return

    ctype = st.session_state.get("cc_campaign_type", "Search")

    st.markdown(
        "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:24px 0 4px'>",
        unsafe_allow_html=True,
    )

    # Violations banner — warn but still show everything
    v = _violations(result)
    if v:
        st.warning(
            "⚠️ Some items exceed character limits — edit manually or regenerate:\n"
            + "\n".join(f"• {x}" for x in v)
        )
    else:
        st.success("✅ All items within character limits")

    _render_headlines(result.get("headlines", []))
    _render_descriptions(result.get("descriptions", []))
    _render_sitelinks(result.get("sitelinks", []))

    if ctype in ("Performance Max", "Demand Gen"):
        _render_long_headlines(result.get("long_headlines", []))

    if ctype == "Performance Max":
        _render_pmax_extras(result)

    if ctype == "Demand Gen":
        _render_dgen_extras(result)

    # ── Copy All ──────────────────────────────────────────────────────────────
    st.markdown(
        "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:24px 0 8px'>",
        unsafe_allow_html=True,
    )
    _section_header("Copy Everything")

    all_text = _copy_all_text(result, ctype)
    st.text_area(
        "all_copy",
        value=all_text,
        height=300,
        key="cc_copy_all",
        label_visibility="collapsed",
    )
    _copy_btn(all_text, "cp_all_final")
