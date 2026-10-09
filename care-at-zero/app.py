"""
CareAtZero — Streamlit entry point (v3, mobile app layout).

Architecture:
  UI (this file)  <--MCP protocol-->  mcp_server/server.py  -->  connectors/combined.py
                                                                   (HRSA, SAMHSA, NC DHHS)

This app does NOT import connectors/scoring directly. Every search, detail
lookup, and referral summary goes through the real MCP server via
utils/mcp_client.py. This app is an MCP *client*.

v3 changes the LOOK only (search, detail, scoring and data are unchanged):
  - the page is a phone-width column (looks like a phone app on desktop too)
  - slim branded header instead of the big blue banner
  - fixed bottom tab bar (Home / Find / Help / About)
  - 2x2 care-type cards, button rows that stay side by side on phones
  - new Help screen with tap-to-call 911 and 988
  - no Save/Saved: without accounts it only lasted one browser session. Instead,
    each clinic's info can be downloaded or copied to take along (see page_detail)

Run with: streamlit run app.py
"""

import streamlit as st

from utils.mcp_client import call_tool, MCPUnavailableError

st.set_page_config(page_title="CareAtZero", page_icon="static/cz-icon.png", layout="centered")

DEFAULT_LOCATION = "27601"  # Raleigh, NC

# Shown under the CareAtZero name on every screen. One place to change it.
TAGLINE = "Free &amp; low-cost care. Know where to go."

SERVICE_META = {
    "medical":    {"icon": ":material/stethoscope:", "label": "Medical",       "desc": "Check-ups, sick visits",
                   "source": "Real, live data from HRSA (federal)"},
    "dental":     {"icon": ":material/dentistry:",   "label": "Dental",        "desc": "Clinics, safety-net sites",
                   "source": "Real data from NC DHHS Safety Net list"},
    "vision":     {"icon": ":material/visibility:",  "label": "Vision",        "desc": "Eye exams, glasses",
                   "source": "No verified real source yet — see About"},
    "behavioral": {"icon": ":material/psychology:",  "label": "Mental health", "desc": "Counseling, crisis care",
                   "source": "Real, live data from SAMHSA (federal)"},
}
# cost class -> (badge text, pill color)
COST_BADGE = {
    "Free": ("FREE · $0", "green"), "Very Low Cost": ("VERY LOW COST", "amber"),
    "Sliding Scale": ("SLIDING SCALE", "amber"), "Unknown": ("COST UNKNOWN", "outline"),
}
TIMING_LABELS = {"today": "Today", "this_week": "This week", "flexible": "Any time"}
INSURANCE_LABELS = {"uninsured": "Uninsured", "underinsured": "Underinsured",
                    "prefer_not_to_say": "Prefer not to say"}
NAV = [("Home", ":material/home:"), ("Find", ":material/search:"),
       ("Help", ":material/call:"), ("About", ":material/info:")]


def score_band(score: float) -> str:
    """Returns a pill/bar color class based on score value, for quick visual scanning."""
    if score >= 80:
        return "green"
    if score >= 50:
        return "amber"
    return "red"


# ---------------------------------------------------------------- styling
# Containers created with key="row_..." keep their columns side by side even on
# a narrow phone (Streamlit normally stacks columns under ~640px).
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800&display=swap');
  :root {
    --navy:#0E2A5C; --blue:#0B5FD6; --blue-50:#E6F0FD; --teal:#0A7C74; --teal-50:#E2F4F1;
    --red-600:#B42318; --red-50:#FDECEC; --green-600:#075E57; --green-50:#E2F4F1;
    --amber-600:#8A4B00; --amber-500:#E0A106; --amber-50:#FFF2DE;
    --ink:#0E2A5C; --ink-soft:#3D4B61; --ink-faint:#55637A; --line:#E2E8F0; --card:#FFFFFF; --bg:#F4F7FA;
  }
  html, body, [class*="st-"], button, input, textarea, select { font-family: 'Figtree', system-ui, sans-serif; }
  .material-symbols-rounded, [data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded' !important; }

  /* ---- phone-width app column; Streamlit's own chrome hidden ---- */
  header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
  #MainMenu, footer, .stDeployButton, [class*="viewerBadge"] { display: none !important; }
  [data-testid="stAppViewContainer"] { background: #DDE4EC; }
  .block-container, [data-testid="stMainBlockContainer"] {
    max-width: 440px !important; min-height: 100vh; background: var(--bg);
    flex: 0 0 auto !important;  /* don't shrink to screen height; let the page grow with its content */
    padding: 14px 16px 110px !important; box-shadow: 0 0 40px rgba(14,42,92,0.12);
  }
  @media (max-width: 480px) {
    [data-testid="stAppViewContainer"] { background: var(--bg); }
    .block-container, [data-testid="stMainBlockContainer"] { box-shadow: none; }
  }
  h1, h2, h3, h4 { color: var(--ink); letter-spacing: -0.01em; }
  [data-testid="stHeaderActionElements"] { display: none !important; }
  h3 { font-size: 20px !important; font-weight: 800 !important; padding-top: 6px !important; }
  h4 { font-size: 15px !important; font-weight: 800 !important; }

  /* ---- rows that never stack ---- */
  [class*="st-key-row"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 8px !important; }
  [class*="st-key-row"] [data-testid="stColumn"] { min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }

  /* ---- header ---- */
  /* brand bar (Home only): the logo's own mark + lettering, tagline as live text */
  .cz-brand { display:flex; align-items:center; gap:10px; padding: 2px 0 14px; }
  .cz-brand-mark { height: 46px; width: auto; }
  .cz-brand-text { display:flex; flex-direction:column; gap:5px; min-width:0; }
  .cz-brand-word { height: 23px; width: auto; align-self: flex-start; }
  .cz-tagline { font-size: 12.5px; font-weight: 600; color: var(--ink-soft); white-space: nowrap; }
  .cz-title { font-size: 28px; font-weight: 800; line-height: 1.12; letter-spacing: -0.5px; margin: 6px 0 4px; color: var(--ink); }
  .cz-sub { font-size: 15px; color: var(--ink-faint); margin-bottom: 10px; }

  /* ---- bottom tab bar ---- */
  .st-key-cz_nav {
    position: fixed; bottom: 0; left: 50%; transform: translateX(-50%); z-index: 1000;
    width: 100%; max-width: 440px; background: #FFFFFF; border-top: 1px solid var(--line);
    padding: 6px 6px 14px; box-sizing: border-box;
  }
  .st-key-cz_nav [data-testid="stHorizontalBlock"] { gap: 0 !important; }
  .st-key-cz_nav button {
    border: none !important; background: transparent !important; color: var(--ink-faint) !important;
    min-height: 54px; padding: 4px 0 !important; box-shadow: none !important;
  }
  .st-key-cz_nav button > div, .st-key-cz_nav button > span { flex-direction: column !important; gap: 2px !important; }
  .st-key-cz_nav button p { font-size: 12px !important; font-weight: 600; }
  .st-key-cz_nav [data-testid="stIconMaterial"] { font-size: 24px !important; margin: 0 !important; }

  /* ---- care-type cards (2x2) ---- */
  [class*="st-key-svc_"] button {
    min-height: 78px; justify-content: flex-start !important; text-align: left; border-radius: 14px !important;
    background: #FFFFFF !important; border: 1px solid var(--line) !important; color: var(--ink) !important;
    padding: 8px 12px !important;
  }
  [class*="st-key-svc_"] button[data-testid="stBaseButton-primary"] {
    background: var(--teal-50) !important; border: 2px solid var(--teal) !important;
  }
  [class*="st-key-svc_"] button p { font-size: 15px !important; font-weight: 700 !important; text-align: left; line-height: 1.25; }
  [class*="st-key-svc_"] [data-testid="stIconMaterial"] { color: var(--teal) !important; font-size: 24px !important; }

  /* ---- buttons, inputs, cards ---- */
  .stButton button, .stDownloadButton button, .stLinkButton a, .stFormSubmitButton button { border-radius: 12px !important; min-height: 44px; font-weight: 700; }
  .stFormSubmitButton button { min-height: 54px; font-size: 17px; box-shadow: 0 6px 16px rgba(10,124,116,0.25); }
  .stFormSubmitButton button p { font-size: 17px !important; font-weight: 800 !important; }
  [data-testid="stTextInput"] input { font-size: 17px; font-weight: 600; }
  div[data-testid="stForm"] { border: none; padding: 0; }
  [class*="st-key-card_"] { background: #FFFFFF; border-radius: 18px !important; border-color: var(--line) !important; }

  .cz-pill {
    display:inline-block; font-size:12px; font-weight:800; padding:4px 10px;
    border-radius:8px; margin-right:6px; margin-bottom:4px; letter-spacing:0.02em;
  }
  .cz-pill-blue { background:var(--blue-50); color:#0A4BAA; }
  .cz-pill-green { background:var(--green-50); color:var(--green-600); }
  .cz-pill-amber { background:var(--amber-50); color:var(--amber-600); }
  .cz-pill-red { background:var(--red-50); color:var(--red-600); }
  .cz-pill-outline { background:#F4F7FA; color:var(--ink-soft); }
  .cz-name { font-size: 18px; font-weight: 800; color: var(--ink); line-height: 1.25; margin: 4px 0 2px; }
  .cz-addr { font-size: 14px; color: var(--ink-soft); }
  .cz-card {
    border:1px solid var(--line); border-radius:16px; padding:14px 16px; margin-bottom:10px; background:var(--card);
  }
  .cz-emergency { display:flex; gap:8px; margin: 4px 0 14px; }
  .cz-emergency a {
    flex:1; text-align:center; text-decoration:none !important; border-radius:12px; padding:10px 6px;
    font-size:14px; font-weight:800;
  }
  .cz-em-red { background: var(--red-50); color: var(--red-600) !important; }
  .cz-em-blue { background: var(--blue-50); color: #0A3D91 !important; }
  .cz-trust { display:flex; align-items:center; gap:8px; font-size:13px; color:var(--ink-faint); margin: 8px 0; }
  .cz-why { display:flex; gap:12px; align-items:flex-start; padding: 12px 14px; background:#FFFFFF;
            border:1px solid var(--line); border-radius:14px; margin-bottom:8px; }
  .cz-why b { font-size: 15px; } .cz-why div div { font-size: 13.5px; color: var(--ink-faint); margin-top: 2px; }
  .cz-why-num { width:30px; height:30px; flex:none; border-radius:9px; background:var(--teal-50); color:var(--teal);
                font-weight:800; display:flex; align-items:center; justify-content:center; }
  .cz-help { border-radius: 18px; padding: 16px; margin-bottom: 12px; }
  .cz-help h4 { margin: 0 0 4px !important; padding: 0 !important; }
  .cz-help p { margin: 0 0 12px; font-size: 14px; }
  .cz-help a { display:block; text-align:center; text-decoration:none !important; border-radius:14px;
               padding:15px; font-size:18px; font-weight:800; color:#FFFFFF !important; }
  .cz-bar-row { margin: 8px 0 12px; }
  .cz-bar-top { display:flex; justify-content:space-between; font-size:13px; margin-bottom:4px; }
  .cz-bar-top b { font-weight: 700; }
  .cz-bar-track { height:8px; background:var(--line); border-radius:999px; overflow:hidden; }
  .cz-bar-fill { height:100%; border-radius:999px; }
  .cz-bar-green { background: #1B8A4C; } .cz-bar-amber { background: var(--amber-500); } .cz-bar-red { background: #D8362A; }
  .cz-source-note { font-size:12.5px; color:var(--ink-faint); }
  .cz-score-total { font-size: 34px; font-weight: 800; color: var(--blue); line-height:1; }
  .cz-score-sub { font-size: 13px; color: var(--ink-faint); }
</style>
""", unsafe_allow_html=True)


def brand_bar():
    """Logo lockup shown at the top of Home only. Other screens lead with their own title,
    the way most phone apps do (the brand is already on the home-screen icon)."""
    st.markdown(f"""
    <div class="cz-brand">
      <img class="cz-brand-mark" src="app/static/cz-mark.png" alt="">
      <div class="cz-brand-text">
        <img class="cz-brand-word" src="app/static/cz-wordmark.png" alt="CareAtZero">
        <div class="cz-tagline">{TAGLINE}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def emergency_banner():
    # tel: links dial directly on a phone
    st.markdown("""
    <div class="cz-emergency">
      <a class="cz-em-red" href="tel:911">Emergency · 911</a>
      <a class="cz-em-blue" href="tel:988">Crisis line · 988</a>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------- session state
if "tab" not in st.session_state:
    st.session_state.tab = "Home"
if "results" not in st.session_state:
    st.session_state.results = None
if "detail_id" not in st.session_state:
    st.session_state.detail_id = None
if "detail_from" not in st.session_state:
    st.session_state.detail_from = "Home"
if "last_search" not in st.session_state:
    st.session_state.last_search = {"service": "medical", "timing": "flexible", "insurance_status": "uninsured", "zip_code": DEFAULT_LOCATION}


def goto(tab: str, detail_id: str = None, detail_from: str = None):
    st.session_state.tab = tab
    if detail_id is not None:
        st.session_state.detail_id = detail_id
    if detail_from is not None:
        st.session_state.detail_from = detail_from


# ---------------------------------------------------------------- bottom tab bar
def bottom_nav():
    # The Detail screen belongs to the Find tab, so Find stays highlighted there.
    active = "Find" if st.session_state.tab == "Detail" else st.session_state.tab
    st.markdown(f"<style>.st-key-nav_{active} button {{ color: var(--teal) !important; }}"
                f".st-key-nav_{active} button p {{ font-weight: 800 !important; }}</style>",
                unsafe_allow_html=True)
    with st.container(key="cz_nav"):
        with st.container(key="row_nav"):
            cols = st.columns(len(NAV))
            for col, (name, icon) in zip(cols, NAV):
                with col:
                    if st.button(name, icon=icon, key=f"nav_{name}", type="tertiary", use_container_width=True):
                        goto(name)
                        st.rerun()


# ---------------------------------------------------------------- search execution
def run_search():
    q = st.session_state.last_search
    try:
        with st.spinner(f"Searching {SERVICE_META[q['service']]['label'].lower()} options via CareAtZero's MCP server..."):
            results = call_tool("search_care", q)
        st.session_state.results = results
    except MCPUnavailableError as e:
        st.session_state.results = []
        st.error(f"Couldn't complete the search: {e}")


def service_picker(key_prefix: str):
    """2x2 care-type cards — tapping one selects it immediately."""
    active = st.session_state.last_search["service"]
    items = list(SERVICE_META.items())
    for r in range(2):
        with st.container(key=f"row_{key_prefix}_svc{r}"):
            cols = st.columns(2)
            for c in range(2):
                key, meta = items[r * 2 + c]
                with cols[c]:
                    with st.container(key=f"svc_{key_prefix}_{key}"):
                        if st.button(f"{meta['label']}  \n:gray[{meta['desc']}]", icon=meta["icon"],
                                     key=f"{key_prefix}_pick_{key}", use_container_width=True,
                                     type=("primary" if key == active else "secondary")):
                            st.session_state.last_search["service"] = key
                            st.rerun()
    st.caption(SERVICE_META[active]["source"])


def search_form(key_prefix: str, on_submit_goto_find: bool):
    q = st.session_state.last_search
    with st.form(f"{key_prefix}_search_form"):
        zip_code = st.text_input("Where are you? (ZIP code)", value=q["zip_code"], key=f"{key_prefix}_zip")
        timing = st.segmented_control("When do you need care?", list(TIMING_LABELS),
                                      format_func=TIMING_LABELS.get, default=q["timing"],
                                      key=f"{key_prefix}_timing")
        insurance_status = st.selectbox("Insurance status", list(INSURANCE_LABELS),
                                        format_func=INSURANCE_LABELS.get,
                                        index=list(INSURANCE_LABELS).index(q["insurance_status"]),
                                        key=f"{key_prefix}_insurance")
        submitted = st.form_submit_button("Find free care", icon=":material/search:",
                                          use_container_width=True, type="primary")
    if submitted:
        st.session_state.last_search = {
            "service": st.session_state.last_search["service"], "timing": timing or q["timing"],
            "insurance_status": insurance_status, "zip_code": zip_code,
        }
        run_search()
        if on_submit_goto_find:
            goto("Find")
        st.rerun()


def badges_html(cost_class: str, facility_type: str = None, score: float = None) -> str:
    label, color = COST_BADGE.get(cost_class, (cost_class.upper(), "outline"))
    html = f'<span class="cz-pill cz-pill-{color}">{label}</span>'
    if facility_type:
        html += f'<span class="cz-pill cz-pill-outline">{facility_type}</span>'
    if score is not None:
        html += f'<span class="cz-pill cz-pill-blue">Score {score:.0f}</span>'
    return html


def result_card(r: dict, key_suffix: str):
    with st.container(border=True, key=f"card_{key_suffix}"):
        st.markdown(badges_html(r["cost_class"], r.get("facility_type"), r["score"])
                    + f'<div class="cz-name">{r["name"]}</div><div class="cz-addr">{r["address"]}</div>',
                    unsafe_allow_html=True)
        with st.expander("Why this matches"):
            for reason in r.get("why_this_matches", []):
                st.write(f"- {reason}")
        st.caption(f"Source: {r.get('source_name', 'Unknown')}")
        with st.container(key=f"row_res_{key_suffix}"):
            bcols = st.columns(2)
            with bcols[0]:
                if st.button("Details", key=f"view_{key_suffix}", use_container_width=True, type="primary"):
                    goto("Detail", detail_id=r["id"], detail_from="Find")
                    st.rerun()
            with bcols[1]:
                if r.get("phone"):
                    st.link_button("Call", f"tel:{r['phone']}", icon=":material/call:", use_container_width=True)


# ---------------------------------------------------------------- pages
def page_home():
    brand_bar()
    st.markdown('<div class="cz-title">Find free care near you</div>'
                '<div class="cz-sub">No insurance needed. Pick what you need below.</div>',
                unsafe_allow_html=True)
    emergency_banner()
    st.markdown("**What do you need?**")
    service_picker("home")
    search_form("home", on_submit_goto_find=True)
    st.markdown('<div class="cz-trust">✓ Real data from HRSA, SAMHSA and NC DHHS</div>', unsafe_allow_html=True)

    st.subheader("Why CareAtZero is different")
    st.markdown("""
    <div class="cz-why"><div class="cz-why-num">1</div><div><b>Clear cost labels first</b>
      <div>Free, Very Low Cost or Sliding Scale — never labeled Free unless the source says so.</div></div></div>
    <div class="cz-why"><div class="cz-why-num">2</div><div><b>Transparent Care Access Score</b>
      <div>Cost fit 35%, timing 25%, service match 15%, eligibility 10%, distance 10%, freshness 5%.</div></div></div>
    <div class="cz-why"><div class="cz-why-num">3</div><div><b>Real sources, honest gaps</b>
      <div>Every result traces to a federal or state source. No data yet? We say so instead of guessing.</div></div></div>
    """, unsafe_allow_html=True)


def page_find():
    st.markdown('<div class="cz-title">Find care</div>'
                '<div class="cz-sub">Search real HRSA, SAMHSA and NC DHHS data.</div>', unsafe_allow_html=True)
    rows = st.session_state.results
    # Once there are results, tuck the search away so the list is the first thing you see.
    with st.expander("Change search", expanded=(rows is None)):
        service_picker("find")
        search_form("find", on_submit_goto_find=False)

    if rows is None:
        st.info("Set your search above and tap **Find free care** to see ranked, real results.")
        return
    if len(rows) == 0:
        svc = st.session_state.last_search["service"]
        if svc == "vision":
            st.warning("No verified real data source is connected for vision care yet — see the About page for details.")
        else:
            st.info("No matching real results found for this search. Try a different ZIP or service.")
        return

    q = st.session_state.last_search
    st.markdown(f"**{len(rows)} option(s)** · {SERVICE_META[q['service']]['label']} near {q['zip_code']} · "
                f"best match first")
    for i, r in enumerate(rows):
        result_card(r, key_suffix=f"find_{i}")


def page_detail():
    rid = st.session_state.detail_id
    if not rid:
        st.info("Pick an option from Find to see its details here.")
        return
    if st.button("Back", icon=":material/arrow_back:", type="tertiary"):
        goto(st.session_state.detail_from)
        st.rerun()

    q = st.session_state.last_search
    try:
        with st.spinner("Loading details..."):
            detail = call_tool("get_care_detail", {
                "record_id": rid, "service": q["service"],
                "timing": q["timing"], "insurance_status": q["insurance_status"],
                "zip_code": q["zip_code"],
            })
    except MCPUnavailableError as e:
        st.error(f"Couldn't load details: {e}")
        return

    if "error" in detail:
        st.error(detail["error"])
        return

    # Plain-text summary (name, address, phone, hours, what to bring, source) the user
    # can keep, print or text to someone. This replaces "Save": no account needed.
    try:
        ref_text = call_tool("get_referral_summary", {"record_id": rid})
    except MCPUnavailableError:
        ref_text = None

    st.markdown(badges_html(detail["cost_class"], detail.get("facility_type"))
                + f'<div class="cz-title">{detail["name"]}</div><div class="cz-addr">{detail["address"]}</div>',
                unsafe_allow_html=True)
    st.write("")
    st.link_button("Get directions",
                   f"https://www.google.com/maps/search/?api=1&query={detail['address'].replace(' ', '+')}",
                   icon=":material/directions:", use_container_width=True, type="primary")
    with st.container(key="row_detail_actions"):
        bcols = st.columns(2)
        with bcols[0]:
            if detail.get("phone"):
                st.link_button("Call", f"tel:{detail['phone']}", icon=":material/call:", use_container_width=True)
        with bcols[1]:
            if ref_text:
                st.download_button("Download info", ref_text, file_name=f"{rid}-care-info.txt",
                                   icon=":material/download:", use_container_width=True)
    if ref_text:
        with st.expander("Copy this info to text or share"):
            st.code(ref_text, language=None)

    with st.container(border=True, key="card_detail_info"):
        st.markdown("#### What to bring")
        st.write(detail["documents_needed"])
        st.markdown("#### When to go")
        st.write(f"**Appointment rule:** {detail['appointment_rule'].replace('_', ' ').title()}")
        if detail.get("next_hours"):
            st.write(f"**Hours:** {detail['next_hours']}")
        st.markdown("#### Services")
        st.write(", ".join(s.title() for s in detail["services"]))
        st.markdown("#### Eligibility")
        st.write(detail["eligibility"])

    if "score_breakdown" in detail:
        b = detail["score_breakdown"]
        with st.container(border=True, key="card_detail_score"):
            st.markdown("#### Care Access Score")
            st.markdown(
                f"<div class='cz-score-total'>{b['total']}<span class='cz-score-sub'> /100</span></div>",
                unsafe_allow_html=True,
            )
            for key, cat in b["categories"].items():
                label_txt = key.replace("_", " ").title()
                pct = cat["points"] / max(cat["weight_pct"], 1) * 100
                cat_band = score_band(cat["score"])
                st.markdown(
                    f"<div class='cz-bar-row'>"
                    f"<div class='cz-bar-top'><b>{label_txt}</b> ({cat['weight_pct']}%)<span>{cat['points']} pts</span></div>"
                    f"<div class='cz-bar-track'><div class='cz-bar-fill cz-bar-{cat_band}' style='width:{pct}%;'></div></div>"
                    f"<span class='cz-source-note'>{cat['reason']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    with st.container(border=True, key="card_detail_source"):
        st.markdown("#### Where this comes from")
        st.write(f"**Source:** {detail['source_name']}")
        if detail.get("source_url"):
            st.write(f"**Learn more:** {detail['source_url']}")
        st.write(f"**Last checked:** {detail['last_checked']}")


def page_help():
    st.markdown('<div class="cz-title">Get help now</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="cz-help" style="background:#FDECEC; color:#7A1414;">
      <h4 style="color:#7A1414 !important;">Life-threatening emergency?</h4>
      <p>Chest pain, trouble breathing, severe bleeding or injury.</p>
      <a href="tel:911" style="background:#B42318;">Call 911</a>
    </div>
    <div class="cz-help" style="background:#E6F0FD; color:#0A3D91;">
      <h4 style="color:#0A3D91 !important;">Mental health or suicide crisis</h4>
      <p>Free and available 24/7. Call or text to talk with someone.</p>
      <a href="tel:988" style="background:#0E2A5C;">Call or text 988</a>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Not an emergency? Find a free clinic", icon=":material/search:", use_container_width=True):
        goto("Find")
        st.rerun()


def page_about():
    st.markdown('<div class="cz-title">About CareAtZero</div>', unsafe_allow_html=True)
    tab = st.segmented_control("About sections", ["Mission", "Scoring", "Sources", "Privacy"],
                               default="Mission", label_visibility="collapsed") or "Mission"
    if tab == "Mission":
        st.markdown("""
### Our Mission
CareAtZero is a free web application that helps uninsured and low-income North Carolinians
find genuinely free or very-low-cost medical, dental, and behavioral healthcare they can
realistically access soon.

### The Problem We Solve
Free and safety-net healthcare exists, but the information is scattered across federal
directories, state lists, and local programs. This app normalizes that data into one
transparent, scored search.
        """)
    elif tab == "Scoring":
        st.markdown("""
### Transparent Scoring
Every result gets a Care Access Score out of 100 — a plain weighted formula:
- **Cost Fit — 35%**
- **Time to Care — 25%**
- **Service Match — 15%**
- **Eligibility Confidence — 10%**
- **Distance — 10%**
- **Data Freshness — 5%**
        """)
    elif tab == "Sources":
        st.markdown("""
### Real Data Sources — No Sample Data
| Category | Source | Type |
|---|---|---|
| Medical | HRSA Health Center Service Delivery Sites | Live federal API |
| Behavioral | SAMHSA FindTreatment.gov | Live federal API |
| Dental & other | NC DHHS Safety Net Sites List | NC state data |
| Vision | *(none yet)* | Not covered — see note below |

**Vision care** has no verified, freely-available public data source at this time.
Rather than invent placeholder clinics, CareAtZero shows real, honest results only —
vision searches return empty with a note, until a suitable connector exists.

Distance is calculated from real ZIP-code centroids (U.S. Census Bureau Gazetteer
data), not exact street-address geocoding — accurate enough for a 10%-weighted signal.
        """)
    else:
        st.markdown("""
### Privacy & Emergency Safety
No login or account is required, and nothing you search for is stored.
To keep a clinic's details, use **Download info** or copy the text on its
detail screen — it stays on your phone, not on our server.

CareAtZero does not diagnose symptoms, give medical advice, or store medical records.
If you are experiencing a life-threatening emergency, call 911. For free 24/7 mental
health and suicide crisis support, dial 988.
        """)


# ---------------------------------------------------------------- render
PAGES = {"Home": page_home, "Find": page_find, "Detail": page_detail,
         "Help": page_help, "About": page_about}
PAGES[st.session_state.tab]()

st.caption("CareAtZero does not diagnose symptoms, give medical advice, or store medical records. "
           "If this is a medical emergency, call 911 or go to the nearest emergency room.")
bottom_nav()
