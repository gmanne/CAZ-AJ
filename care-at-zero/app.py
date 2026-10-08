"""
CareAtZero — Streamlit entry point (v2).

Architecture:
  UI (this file)  <--MCP protocol-->  mcp_server/server.py  -->  connectors/combined.py
                                                                   (HRSA, SAMHSA, NC DHHS)

Unlike v1, this app does NOT import connectors/scoring directly. Every
search, detail lookup, and referral summary goes through the real MCP
server via utils/mcp_client.py — the same server Claude Desktop or any
other MCP client could connect to. This app is an MCP *client*.

No sample/placeholder data: every result comes from a real federal or
North Carolina state source. See README's "What's covered" section for
exactly what each source does and doesn't tell us.

Run with: streamlit run app.py
"""

import streamlit as st

from utils.mcp_client import call_tool, MCPUnavailableError

st.set_page_config(page_title="CareAtZero", page_icon="🩺", layout="centered")

DEFAULT_LOCATION = "27601"  # Raleigh, NC

SERVICE_META = {
    "medical":    {"icon": "🩺", "label": "Medical Care",       "desc": "Primary care & exams",
                   "source": "Real, live data from HRSA (federal)"},
    "dental":     {"icon": "🦷", "label": "Dental Care",         "desc": "Clinics & safety-net sites",
                   "source": "Real data from NC DHHS Safety Net list"},
    "vision":     {"icon": "👓", "label": "Vision Care",         "desc": "Free exams & glasses",
                   "source": "No verified real source yet — see About"},
    "behavioral": {"icon": "🧠", "label": "Behavioral Health",   "desc": "Counseling & crisis care",
                   "source": "Real, live data from SAMHSA (federal)"},
}
COST_BADGE = {
    "Free": ("🟢", "FREE"), "Very Low Cost": ("🟡", "VERY LOW COST"),
    "Sliding Scale": ("🟠", "SLIDING SCALE"), "Unknown": ("⚪", "COST UNKNOWN"),
}


def score_band(score: float) -> str:
    """Returns a pill/bar color class based on score value, for quick visual scanning."""
    if score >= 80:
        return "green"
    if score >= 50:
        return "amber"
    return "red"

# ---------------------------------------------------------------- styling
st.markdown("""
<style>
  :root {
    --blue-900:#16265C; --blue-700:#1E3A8A; --blue-600:#2952CC; --blue-500:#3B6BE0; --blue-100:#E6EDFB;
    --red-600:#D8362A; --red-50:#FDEDEB; --green-600:#1B8A4C; --green-50:#E9F7EF;
    --amber-600:#B8790A; --amber-500:#E0A106; --amber-50:#FFF6E5;
    --ink:#14213D; --ink-soft:#4B5670; --ink-faint:#7B84A0; --line:#E2E6F0; --card:#FFFFFF;
    --shadow: 0 1px 2px rgba(20,33,61,0.04), 0 6px 16px rgba(20,33,61,0.06);
  }
  .cz-hero {
    background: linear-gradient(135deg, var(--blue-900), var(--blue-600));
    color: white; padding: 26px 28px; border-radius: 16px; margin-bottom: 16px;
    box-shadow: var(--shadow);
  }
  .cz-hero h1 { margin: 0 0 6px; font-size: 27px; font-weight: 800; letter-spacing: -0.01em; }
  .cz-hero p { margin: 0; opacity: 0.92; font-size: 14.5px; max-width: 46ch; }
  .cz-pill {
    display:inline-block; font-size:11px; font-weight:700; padding:4px 11px;
    border-radius:999px; margin-right:6px; margin-bottom:4px; letter-spacing:0.01em;
  }
  .cz-pill-blue { background:var(--blue-100); color:var(--blue-700); }
  .cz-pill-green { background:var(--green-50); color:var(--green-600); }
  .cz-pill-amber { background:var(--amber-50); color:var(--amber-600); }
  .cz-pill-red { background:var(--red-50); color:var(--red-600); }
  .cz-pill-outline { background:transparent; color:var(--ink-soft); border:1px solid var(--line); }
  .cz-card {
    border:1px solid var(--line); border-radius:14px; padding:18px; margin-bottom:12px;
    background:var(--card); box-shadow: var(--shadow);
  }
  .cz-card-left-free { border-left: 4px solid var(--green-600); }
  .cz-card-left-vlow { border-left: 4px solid var(--amber-500); }
  .cz-card-left-sliding { border-left: 4px solid #C77A1F; }
  .cz-card-left-unknown { border-left: 4px solid var(--ink-faint); }
  .cz-emergency {
    background:var(--red-50); border-left:4px solid var(--red-600); border-radius:12px;
    padding:13px 16px; font-size:13.5px; margin-bottom:18px;
  }
  .cz-emergency b { color: var(--red-600); }
  .cz-source-strip {
    background: var(--blue-100); border-radius: 10px; padding: 9px 14px;
    font-size: 12.5px; color: var(--blue-700); margin-bottom: 16px; font-weight: 600;
  }
  .cz-bar-row { margin: 8px 0 12px; }
  .cz-bar-top { display:flex; justify-content:space-between; font-size:12.5px; margin-bottom:4px; }
  .cz-bar-top b { font-weight: 700; }
  .cz-bar-track { height:8px; background:var(--line); border-radius:999px; overflow:hidden; }
  .cz-bar-fill { height:100%; border-radius:999px; }
  .cz-bar-green { background: linear-gradient(90deg, #22A85E, var(--green-600)); }
  .cz-bar-amber { background: linear-gradient(90deg, #F0B429, var(--amber-600)); }
  .cz-bar-red { background: linear-gradient(90deg, #E8877A, var(--red-600)); }
  .cz-source-note { font-size:12px; color:var(--ink-faint); }
  .cz-score-total { font-size: 30px; font-weight: 800; color: var(--blue-600); line-height:1; }
  .cz-score-sub { font-size: 12.5px; color: var(--ink-faint); }
  .cz-service-card {
    border:1.5px solid var(--line); border-radius:12px; padding:14px 16px; background:var(--card);
    height: 100%;
  }
  .cz-service-card-active { border-color: var(--blue-600); background: var(--blue-100); }
  div[data-testid="stForm"] { border: none; padding: 0; }
</style>
""", unsafe_allow_html=True)


def hero():
    st.markdown("""
    <div class="cz-hero">
      <h1>🩺 CareAtZero</h1>
      <p>Find genuinely free, very-low-cost, and sliding-scale healthcare — powered by real HRSA, SAMHSA, and NC DHHS data.</p>
    </div>
    """, unsafe_allow_html=True)


def emergency_banner():
    st.markdown("""
    <div class="cz-emergency">🚨 <b>Medical emergency?</b> If experiencing a life-threatening emergency,
    call 911. For free 24/7 mental health &amp; suicide crisis support, dial <b>988</b>.</div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------- saved items
# Session-scoped only (st.session_state), NOT a shared file. This matters once
# this app is deployed publicly: Streamlit Community Cloud runs one shared
# container for every visitor, so a file on disk would mix everyone's saved
# items together. session_state is private per browser session — each
# visitor only ever sees their own. The tradeoff: saved items don't survive
# closing the browser tab (no server-side account system here), but nothing
# is ever shared between different people using the public app.
def toggle_save(record_id: str, name: str, address: str):
    saved = st.session_state.saved
    existing = next((s for s in saved if s["id"] == record_id), None)
    if existing:
        saved.remove(existing)
    else:
        saved.append({"id": record_id, "name": name, "address": address})


# ---------------------------------------------------------------- session state
if "tab" not in st.session_state:
    st.session_state.tab = "Home"
if "results" not in st.session_state:
    st.session_state.results = None
if "detail_id" not in st.session_state:
    st.session_state.detail_id = None
if "detail_from" not in st.session_state:
    st.session_state.detail_from = "Home"
if "saved" not in st.session_state:
    st.session_state.saved = []
if "last_search" not in st.session_state:
    st.session_state.last_search = {"service": "dental", "timing": "flexible", "insurance_status": "uninsured", "zip_code": DEFAULT_LOCATION}
if "referral_open" not in st.session_state:
    st.session_state.referral_open = False


def goto(tab: str, detail_id: str = None, detail_from: str = None):
    st.session_state.tab = tab
    if detail_id is not None:
        st.session_state.detail_id = detail_id
    if detail_from is not None:
        st.session_state.detail_from = detail_from
    st.session_state.referral_open = False


# ---------------------------------------------------------------- nav
hero()
nav_cols = st.columns(5)
nav_labels = {
    "Home": "Home", "Find": "Find", "Detail": "Detail",
    "Saved": f"Saved ({len(st.session_state.saved)})" if st.session_state.saved else "Saved",
    "About": "About",
}
for col, key in zip(nav_cols, ["Home", "Find", "Detail", "Saved", "About"]):
    with col:
        if st.button(nav_labels[key], use_container_width=True, type=("primary" if st.session_state.tab == key else "secondary")):
            goto(key)

st.divider()


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
    """Clickable service cards, matching the webpage's picker — click sets the active service immediately."""
    active = st.session_state.last_search["service"]
    cols = st.columns(4)
    for i, (key, meta) in enumerate(SERVICE_META.items()):
        with cols[i]:
            is_active = key == active
            st.markdown(
                f"<div class='cz-service-card{' cz-service-card-active' if is_active else ''}'>"
                f"<div style='font-size:22px;'>{meta['icon']}</div>"
                f"<div style='font-weight:700; font-size:13px; margin-top:4px;'>{meta['label']}</div>"
                f"<div class='cz-source-note'>{meta['desc']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("Select" if not is_active else "✓ Selected", key=f"{key_prefix}_pick_{key}",
                         use_container_width=True, type=("primary" if is_active else "secondary")):
                st.session_state.last_search["service"] = key
                st.rerun()
    st.caption(SERVICE_META[active]["source"])


def search_form(key_prefix: str, on_submit_goto_find: bool):
    q = st.session_state.last_search
    with st.form(f"{key_prefix}_search_form"):
        c1, c2 = st.columns(2)
        with c1:
            timing = st.selectbox("When do you need care?", ["today", "this_week", "flexible"],
                                   index=["today", "this_week", "flexible"].index(q["timing"]),
                                   key=f"{key_prefix}_timing")
        with c2:
            insurance_status = st.selectbox("Insurance status", ["uninsured", "underinsured", "prefer_not_to_say"],
                                             index=["uninsured", "underinsured", "prefer_not_to_say"].index(q["insurance_status"]),
                                             key=f"{key_prefix}_insurance")
        zip_code = st.text_input("ZIP code (North Carolina)", value=q["zip_code"], key=f"{key_prefix}_zip")
        submitted = st.form_submit_button("🔎 Find Care", use_container_width=True, type="primary")
    if submitted:
        st.session_state.last_search = {
            "service": st.session_state.last_search["service"], "timing": timing,
            "insurance_status": insurance_status, "zip_code": zip_code,
        }
        run_search()
        if on_submit_goto_find:
            goto("Find")
        st.rerun()


def result_card(r: dict, key_suffix: str):
    icon, label = COST_BADGE.get(r["cost_class"], ("⚪", r["cost_class"]))
    is_saved = any(s["id"] == r["id"] for s in st.session_state.saved)
    band = score_band(r["score"])
    with st.container(border=True):
        badges = f'<span class="cz-pill cz-pill-green">{icon} {label}</span>'
        if r.get("facility_type"):
            badges += f'<span class="cz-pill cz-pill-outline">{r["facility_type"]}</span>'
        badges += f'<span class="cz-pill cz-pill-{band}" style="float:right;">Score {r["score"]:.0f}/100</span>'
        st.markdown(badges, unsafe_allow_html=True)
        st.markdown(f"**{r['name']}**")
        st.caption(f"📍 {r['address']}")
        with st.expander("Why this matches"):
            for reason in r.get("why_this_matches", []):
                st.write(f"- {reason}")
        st.caption(f"Source: {r.get('source_name', 'Unknown')}")
        bcols = st.columns(3)
        with bcols[0]:
            if st.button("View Details", key=f"view_{key_suffix}", use_container_width=True):
                goto("Detail", detail_id=r["id"], detail_from="Find")
                st.rerun()
        with bcols[1]:
            if r.get("phone"):
                st.link_button("📞 Call", f"tel:{r['phone']}", use_container_width=True)
        with bcols[2]:
            if st.button(("⭐ Saved" if is_saved else "⭐ Save"), key=f"save_{key_suffix}", use_container_width=True):
                toggle_save(r["id"], r["name"], r["address"])
                st.rerun()


# ---------------------------------------------------------------- pages
def page_home():
    emergency_banner()
    st.subheader("🎯 What type of care do you need?")
    service_picker("home")
    st.write("")
    search_form("home", on_submit_goto_find=True)

    st.write("")
    st.subheader("🌐 Real Data Sources")
    st.markdown("""
    <div class="cz-card">
      <b>🏛️ HRSA — Health Center Service Delivery Sites</b><br>
      <span class="cz-source-note">Federal API · live · covers Medical care</span>
    </div>
    <div class="cz-card">
      <b>🏛️ SAMHSA — FindTreatment.gov</b><br>
      <span class="cz-source-note">Federal API · live · covers Behavioral Health</span>
    </div>
    <div class="cz-card">
      <b>🏛️ NC DHHS — Safety Net Sites List</b><br>
      <span class="cz-source-note">NC state data · covers Dental &amp; other facility types</span>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("💡 Why CareAtZero Is Different")
    w1, w2, w3 = st.columns(3)
    with w1:
        st.markdown("**🏷️ 1. Clear Cost Labels First**")
        st.caption("Free, Very Low Cost, or Sliding Scale — never surprising pricing, and never labeled Free unless the source explicitly says so.")
    with w2:
        st.markdown("**📊 2. Transparent Care Access Score**")
        st.caption("Ranked by cost fit (35%), timing (25%), service match (15%), eligibility (10%), distance (10%), and data freshness (5%) — never a black box.")
    with w3:
        st.markdown("**🔒 3. Real Sources, Honest Gaps**")
        st.caption("Every result traces to a real federal or state source. Where no verified source exists yet (like vision), we say so instead of guessing.")


def page_find():
    st.subheader("🔍 Find Free or Low-Cost Care")
    st.caption("Search real HRSA, SAMHSA, and NC DHHS data.")
    service_picker("find")
    search_form("find", on_submit_goto_find=False)

    rows = st.session_state.results
    if rows is None:
        st.info("Set your search above and hit **Find Care** to see ranked, real results.")
        return
    if len(rows) == 0:
        svc = st.session_state.last_search["service"]
        if svc == "vision":
            st.warning("No verified real data source is connected for vision care yet — see the About page for details.")
        else:
            st.info("No matching real results found for this search. Try a different ZIP or service.")
        return

    st.markdown(f"**{len(rows)} option(s) found**, ranked by Care Access Score")
    for i, r in enumerate(rows):
        result_card(r, key_suffix=f"find_{i}")


def page_detail():
    rid = st.session_state.detail_id
    if not rid:
        st.info("Pick an option from Home or Find to see its details here.")
        return
    if st.button("← Back"):
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

    icon, label = COST_BADGE.get(detail["cost_class"], ("⚪", detail["cost_class"]))
    is_saved = any(s["id"] == rid for s in st.session_state.saved)

    badges = f'<span class="cz-pill cz-pill-green">{icon} {label}</span>'
    if detail.get("facility_type"):
        badges += f'<span class="cz-pill cz-pill-outline">{detail["facility_type"]}</span>'
    st.markdown(badges, unsafe_allow_html=True)
    st.title(detail["name"])
    st.caption(f"📍 {detail['address']}")

    bcols = st.columns(3)
    with bcols[0]:
        if detail.get("phone"):
            st.link_button("📞 " + detail["phone"], f"tel:{detail['phone']}", use_container_width=True)
    with bcols[1]:
        st.link_button("🧭 Get Directions",
                        f"https://www.google.com/maps/search/?api=1&query={detail['address'].replace(' ', '+')}",
                        use_container_width=True)
    with bcols[2]:
        if st.button(("⭐ Saved" if is_saved else "⭐ Save this Option"), use_container_width=True):
            toggle_save(rid, detail["name"], detail["address"])
            st.rerun()

    left, right = st.columns(2)
    with left:
        st.markdown("#### 📝 What to Bring")
        st.write(detail["documents_needed"])
        st.markdown("#### 🕐 Schedule & Policy")
        st.write(f"**Appointment rule:** {detail['appointment_rule'].replace('_', ' ').title()}")
        if detail.get("next_hours"):
            st.write(f"**Hours:** {detail['next_hours']}")
        st.markdown("#### 🩺 Services Offered")
        st.write(", ".join(s.title() for s in detail["services"]))
        st.markdown("#### 📋 Eligibility")
        st.write(detail["eligibility"])

    with right:
        if "score_breakdown" in detail:
            b = detail["score_breakdown"]
            st.markdown("#### 🎯 Care Access Score Breakdown")
            total_band = score_band(b["total"])
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

        st.markdown("#### 🌐 Source Provenance")
        st.write(f"**Source:** {detail['source_name']}")
        if detail.get("source_url"):
            st.write(f"**Learn more:** {detail['source_url']}")
        st.write(f"**Last checked:** {detail['last_checked']}")

        st.markdown("#### 🖨️ Referral Summary")
        rcols = st.columns(2)
        with rcols[0]:
            if st.button("Preview", key="ref_preview", use_container_width=True):
                st.session_state.referral_open = not st.session_state.referral_open
        with rcols[1]:
            try:
                ref_text = call_tool("get_referral_summary", {"record_id": rid})
                st.download_button("⬇️ Download .txt", ref_text, file_name=f"{rid}-referral.txt",
                                    use_container_width=True)
            except MCPUnavailableError:
                st.caption("Referral download unavailable")
        if st.session_state.referral_open:
            try:
                st.code(call_tool("get_referral_summary", {"record_id": rid}), language=None)
            except MCPUnavailableError as e:
                st.error(str(e))


def page_saved():
    st.subheader("⭐ My Saved Care Options")
    if not st.session_state.saved:
        st.info("You haven't saved any care options yet. Search on the Find page and click ⭐ Save to bookmark them here.")
        if st.button("🔎 Find Care Now"):
            goto("Find")
            st.rerun()
        return
    for item in list(st.session_state.saved):
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{item['name']}**")
                st.caption(item["address"])
            with c2:
                if st.button("View", key=f"saved_view_{item['id']}"):
                    goto("Detail", detail_id=item["id"], detail_from="Saved")
                    st.rerun()
                if st.button("Remove", key=f"saved_remove_{item['id']}"):
                    toggle_save(item["id"], item["name"], item["address"])
                    st.rerun()


def page_about():
    st.subheader("ℹ️ About CareAtZero & Trust Standards")
    tab = st.radio("About sections", ["Mission", "Scoring", "Sources", "Privacy"], horizontal=True, label_visibility="collapsed")
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
No login or account is required. Saved options exist only for your current
browser session (they're not written to a server or shared with anyone
else using this app) — they'll be gone if you close the tab.

CareAtZero does not diagnose symptoms, give medical advice, or store medical records.
If you are experiencing a life-threatening emergency, call 911. For free 24/7 mental
health and suicide crisis support, dial 988.
        """)


PAGES = {"Home": page_home, "Find": page_find, "Detail": page_detail, "Saved": page_saved, "About": page_about}
PAGES[st.session_state.tab]()

st.divider()
st.caption("CareAtZero does not diagnose symptoms, give medical advice, or store medical records. "
           "If this is a medical emergency, call 911 or go to the nearest emergency room.")
