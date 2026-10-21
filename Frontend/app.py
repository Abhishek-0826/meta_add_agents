import time
from datetime import datetime

import streamlit as st

import api_client as api

st.set_page_config(page_title="Meta Ad Agent", page_icon="♾️", layout="centered",
                   initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
#MainMenu, footer, header[data-testid="stHeader"] {visibility:hidden; height:0;}
.stApp {background:#F5F6FA;}
.block-container {max-width:660px; padding-top:.8rem; padding-bottom:3rem;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px; background:#fff; border-color:#E8EAF0;}
.stButton>button[kind="primary"], .stFormSubmitButton>button[kind="primary"] {
    background:#1877F2; border:0; border-radius:12px; height:3rem; font-weight:600; color:#fff;}
.stButton>button[kind="primary"]:hover, .stFormSubmitButton>button[kind="primary"]:hover {background:#1468d8;}
.brand {display:flex; align-items:center; gap:.7rem;}
.brand .logo {width:38px; height:38px; border-radius:10px; background:#1877F2; color:#fff;
    display:flex; align-items:center; justify-content:center; font-size:1.3rem; font-weight:700;}
.brand .t {font-weight:600; font-size:1rem; line-height:1.1; color:#111827;}
.brand .s {font-size:.7rem; color:#6B7280;}
.sec {display:flex; align-items:center; gap:.75rem; margin-bottom:.4rem;}
.sec .ico {width:36px; height:36px; border-radius:10px; background:#E8F1FE;
    display:flex; align-items:center; justify-content:center; font-size:1rem;}
.sec .h {font-weight:600; color:#111827; line-height:1.2;}
.sec .d {font-size:.78rem; color:#6B7280;}
.page-title {font-size:1.7rem; font-weight:700; color:#111827; margin:.6rem 0 0;}
.page-sub {color:#6B7280; font-size:.9rem; margin-bottom:.6rem;}
.chip {display:inline-block; padding:.2rem .7rem; border-radius:999px; background:#E8F1FE;
    color:#1877F2; font-size:.75rem; font-weight:500;}
.kv {background:#F5F6FA; border-radius:10px; padding:.5rem .8rem; margin-bottom:.4rem;}
.kv .k {font-size:.68rem; color:#6B7280;}
.kv .v {font-size:.85rem; font-weight:600; color:#111827;}
.foot {text-align:center; font-size:.7rem; color:#9CA3AF; margin-top:.4rem;}
</style>
""",
    unsafe_allow_html=True,
)

ss = st.session_state
ss.setdefault("token", "demo" if api.DEMO_MODE else None)
ss.setdefault("page", "create")
ss.setdefault("selected", None)
ss.setdefault("preview", None)
ss.setdefault("oauth_url", None)


def go(page, selected=None):
    ss.page, ss.selected = page, selected
    st.rerun()


def fmt_date(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return str(v or "")


def section(icon, title, sub):
    st.markdown(f"<div class='sec'><div class='ico'>{icon}</div><div><div class='h'>{title}</div>"
                f"<div class='d'>{sub}</div></div></div>", unsafe_allow_html=True)


def kv(label, value):
    st.markdown(f"<div class='kv'><div class='k'>{label}</div><div class='v'>{value or '-'}</div></div>",
                unsafe_allow_html=True)


def title_block(title, sub=""):
    st.markdown(f"<div class='page-title'>{title}</div>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='page-sub'>{sub}</div>", unsafe_allow_html=True)


def header():
    left, right = st.columns([8, 1], vertical_alignment="center")
    left.markdown("<div class='brand'><div class='logo'>∞</div><div><div class='t'>Meta Ad Agent</div>"
                  "<div class='s'>Facebook + Instagram</div></div></div>", unsafe_allow_html=True)
    with right.popover("⋮"):
        if st.button("➕  New campaign", key="m_new", width="stretch"):
            go("create")
        if st.button("🕘  Campaign History", key="m_hist", width="stretch"):
            go("history")
        if st.button("🏢  Clients & Meta", key="m_clients", width="stretch"):
            go("clients")
        if st.button("↪  Logout", key="m_out", width="stretch"):
            ss.token = None
            go("create")


# ------------------------------------------------------------------ login ----
def login_page():
    title_block("Meta Ad Agent", "Sign in to create and manage campaigns.")
    t1, t2 = st.tabs(["Sign in", "Create account"])
    with t1, st.form("login"):
        email = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in", type="primary", width="stretch"):
            try:
                ss.token = api.login(email, pw)
                st.rerun()
            except api.ApiError as e:
                st.error(f"Couldn't sign in. {e}")
    with t2, st.form("signup"):
        org = st.text_input("Company name")
        email2 = st.text_input("Email", key="su_email")
        pw2 = st.text_input("Password (8+ characters)", type="password", key="su_pw")
        if st.form_submit_button("Create account", type="primary", width="stretch"):
            try:
                ss.token = api.signup(email2, pw2, org)
                st.rerun()
            except api.ApiError as e:
                st.error(f"Couldn't create the account. {e}")


# ---------------------------------------------------------- clients page ----
def clients_page():
    title_block("Clients & Meta", "Each campaign belongs to a client with a connected Facebook Page and Instagram account.")
    try:
        clients = api.list_clients(ss.token)
    except api.ApiError as e:
        st.error(f"Couldn't load clients. {e}")
        return

    with st.container(border=True):
        section("➕", "Add a client", "The business you are advertising for.")
        with st.form("new_client", border=False):
            name = st.text_input("Business name")
            website = st.text_input("Website", placeholder="https://yourcompany.com")
            industry = st.text_input("Industry", placeholder="Import and export")
            if st.form_submit_button("Add client", type="primary", width="stretch"):
                if not name.strip():
                    st.error("Enter the business name.")
                else:
                    try:
                        api.create_client(ss.token, name.strip(), website.strip(), industry.strip())
                        st.rerun()
                    except api.ApiError as e:
                        st.error(f"Couldn't add the client. {e}")

    for c in clients:
        with st.container(border=True):
            st.markdown(f"**{c['name']}**")
            try:
                conn = api.get_connection(c["id"], ss.token)
            except api.ApiError as e:
                st.error(str(e))
                continue
            if conn and conn.get("status") == "connected":
                st.markdown("<span class='chip'>✓ Meta connected</span>", unsafe_allow_html=True)
                kv("Ad account", conn.get("ad_account_id"))
                kv("Facebook Page ID", conn.get("page_id"))
                kv("Instagram account ID", conn.get("ig_account_id"))
                continue
            st.caption("Meta isn't connected yet. Step 1: authorise. Step 2: choose the ad account, Page and Instagram account.")
            if st.button("1. Get Meta connect link", key=f"oauth_{c['id']}"):
                try:
                    ss.oauth_url = api.meta_oauth_url(c["id"], ss.token)
                except api.ApiError as e:
                    st.error(f"Couldn't start the Meta connection. {e}")
            if ss.oauth_url:
                st.link_button("Open Meta to authorise", ss.oauth_url)
            with st.form(f"assets_{c['id']}", border=False):
                ad = st.text_input("Ad account ID", placeholder="act_1234567890", key=f"ad_{c['id']}")
                pg = st.text_input("Facebook Page ID", key=f"pg_{c['id']}")
                ig = st.text_input("Instagram account ID (optional)", key=f"ig_{c['id']}")
                if st.form_submit_button("2. Save accounts", type="primary", width="stretch"):
                    try:
                        api.save_assets(c["id"], ss.token, ad.strip(), pg.strip(), ig.strip())
                        st.rerun()
                    except api.ApiError as e:
                        st.error(f"Couldn't save the accounts. {e}")


# ----------------------------------------------------------- create page ----
OBJECTIVES = {"Sales": ("sales", "🛒"), "Leads": ("leads", "👥"), "Traffic": ("traffic", "🌐"),
              "Awareness": ("awareness", "👁")}
PLACEMENTS = {"Auto": "auto", "Feed": "feed", "Stories": "stories", "Reels": "reels"}
TONES = ["Professional", "Friendly", "Bold", "Luxury", "Minimal"]
DURATIONS = {"3 Days": 3, "7 Days": 7, "14 Days": 14, "30 Days": 30}
COUNTRIES = {"United Arab Emirates": "AE", "Saudi Arabia": "SA", "Qatar": "QA", "Kuwait": "KW", "Oman": "OM",
             "Bahrain": "BH", "Egypt": "EG", "Jordan": "JO", "Iraq": "IQ", "Turkey": "TR", "Morocco": "MA",
             "Indonesia": "ID", "Malaysia": "MY", "Bangladesh": "BD", "Pakistan": "PK", "India": "IN",
             "United Kingdom": "GB", "United States": "US"}
# Change the values to "en", "ar"... if your backend dev says it wants language codes.
LANGUAGES = {"English": "english", "Arabic": "arabic", "Urdu": "urdu", "Indonesian": "indonesian",
             "Malay": "malay", "Turkish": "turkish", "Bengali": "bengali", "Hindi": "hindi"}


def create_page():
    title_block("Create a Meta campaign", "Build an advertising campaign for Facebook and Instagram using AI.")
    try:
        clients = api.list_clients(ss.token)
    except api.ApiError as e:
        st.error(f"Couldn't load clients. {e}")
        return
    if not clients:
        st.info("Add a client first. Every campaign belongs to a client.")
        if st.button("Add a client", type="primary"):
            go("clients")
        return
    names = {c["name"]: c["id"] for c in clients}
    client_name = st.selectbox("Client", list(names))

    with st.form("campaign_form", border=False):
        with st.container(border=True):
            section("📣", "Campaign information", "Tell us what you want to advertise.")
            product = st.text_input("Product or service", placeholder="e.g. Premium coffee subscription")
            instructions = st.text_area("Additional instructions", height=100,
                                        placeholder="Describe your offer, key benefits, special promotion, or anything else the AI should know...")
            landing = st.text_input("Where should people land when they click?", placeholder="https://yourcompany.com")
        with st.container(border=True):
            section("🎯", "Campaign objective", "Choose the main result you want from your campaign.")
            objective = st.pills("Objective", list(OBJECTIVES), default="Sales", label_visibility="collapsed",
                                 format_func=lambda o: f"{OBJECTIVES[o][1]} {o}")
        with st.container(border=True):
            section("👥", "Target audience", "Describe who you want to reach.")
            audience = st.text_input("Audience", placeholder="e.g. Importers and distributors aged 25–55")
            countries = st.multiselect("Countries", list(COUNTRIES), placeholder="Choose one or more countries")
            languages = st.multiselect("Ad languages", list(LANGUAGES), default=["English"])
            age = st.slider("Age range", 18, 65, (25, 55))
            gender = st.selectbox("Gender", ["all", "male", "female"])
        with st.container(border=True):
            section("📱", "Platform & placement", "Choose where this campaign should appear.")
            platform = st.pills("Platform", ["Facebook", "Instagram"], default="Facebook")
            placement = st.pills("Placement", list(PLACEMENTS), default="Auto")
        with st.container(border=True):
            section("👛", "Budget & duration", "Set your campaign spending preferences.")
            c1, c2 = st.columns(2)
            budget = c1.number_input("Daily budget (₹)", min_value=0, max_value=5000, step=100, value=None,
                                     placeholder="e.g. ₹1,000")
            duration = c2.selectbox("Duration", list(DURATIONS), index=1)
        with st.container(border=True):
            section("✨", "Creative direction", "Tell AI how you want your campaign to sound.")
            tone = st.pills("Tone", TONES, default="Professional")

        b1, b2 = st.columns(2)
        preview_clicked = b1.form_submit_button("🖼  Preview ad image", width="stretch")
        generate_clicked = b2.form_submit_button("✨  Generate campaign", type="primary", width="stretch")
        st.markdown("<div class='foot'>AI-generated campaign • Nothing goes live until you activate it</div>",
                    unsafe_allow_html=True)

    form = {
        "product": product.strip(), "instructions": instructions.strip(), "landing": landing.strip(),
        "objective": OBJECTIVES.get(objective, ("", ""))[0], "audience": audience.strip(),
        "countries": [COUNTRIES[c] for c in countries], "languages": [LANGUAGES[x] for x in languages],
        "age_range": f"{age[0]}-{age[1]}", "gender": gender,
        "platform": (platform or "").lower(), "placement": PLACEMENTS.get(placement, "auto"),
        "daily_budget": budget, "duration_days": DURATIONS[duration], "tone": tone,
    }

    if preview_clicked:
        if not form["product"] or not form["platform"] or not tone:
            st.error("Enter the product, and choose a platform and a tone.")
        else:
            with st.spinner("Generating your ad image. This can take up to a minute..."):
                try:
                    ss.preview = api.preview_image(form, ss.token) or "empty"
                except api.ApiError as e:
                    ss.preview = None
                    st.error(f"Couldn't generate the image. {e}")
    if ss.preview == "empty":
        st.warning("The image agent answered, but I couldn't find an image in its response. "
                   "Send me what it returned and I'll match the field name.")
    elif ss.preview:
        with st.container(border=True):
            section("🖼", "Ad image preview", "This is the image the AI made from your form.")
            st.image(ss.preview, width="stretch")

    if not generate_clicked:
        return
    problems = []
    if not form["product"]:
        problems.append("Enter the product or service.")
    if not form["landing"]:
        problems.append("Enter the page people should land on.")
    if not form["countries"]:
        problems.append("Choose at least one country.")
    if not form["languages"]:
        problems.append("Choose at least one language.")
    if not form["daily_budget"]:
        problems.append("Enter a daily budget.")
    if not form["objective"] or not form["platform"] or not tone:
        problems.append("Choose an objective, a platform and a tone.")
    if problems:
        st.error("\n".join(f"- {p}" for p in problems))
        return

    client_id = names[client_name]
    try:
        job = api.create_brief(form, client_id, ss.token)
    except api.ApiError as e:
        st.error(f"Couldn't start the campaign. {e}")
        return
    api.add_history({
        "job_id": job["id"], "draft_id": None, "name": f"{form['product']} Campaign",
        "created_at": datetime.now().isoformat(), "objective": form["objective"],
        "budget": form["daily_budget"], "audience": form["audience"] or "-", "platform": form["platform"],
    })
    draft = wait_for_draft(job["id"])
    if draft:
        go("detail", draft)


DONE = {"completed", "complete", "done", "succeeded", "success", "finished"}
FAILED = {"failed", "error"}


def wait_for_draft(job_id):
    """Polls the job while the agents work, then fetches the finished draft."""
    with st.status("Your agents are working...", expanded=True) as status:
        deadline = time.time() + 600
        while time.time() < deadline:
            try:
                job = api.get_job(job_id, ss.token)
            except api.ApiError as e:
                status.update(label="Lost contact with the backend", state="error")
                st.error(str(e))
                return None
            state = str(job.get("status", "")).lower()
            if job.get("error") or state in FAILED:
                status.update(label="The agents hit a problem", state="error")
                st.error(job.get("error") or "The job failed. Check the worker terminal for details.")
                return None
            if job.get("finished_at") or state in DONE:
                break
            status.update(label=f"Working: {job.get('current_node') or state or 'queued'}")
            time.sleep(2)
        else:
            status.update(label="Still running", state="error")
            st.error("This is taking longer than 10 minutes. Is the worker running? Open Campaign History later to check.")
            return None
        try:
            draft = api.find_draft_by_job(job_id, ss.token)
        except api.ApiError as e:
            status.update(label="Finished, but I can't find the draft", state="error")
            st.error(str(e))
            return None
        if not draft:
            status.update(label="Finished, but no draft was created", state="error")
            return None
        api.update_history(job_id, draft_id=draft["id"])
        status.update(label="Campaign ready", state="complete")
        return draft


# ---------------------------------------------------------- history page ----
@st.dialog("Clear campaign history?")
def confirm_clear():
    st.caption("All campaigns will be removed from this list. Campaigns already created on the backend are not deleted.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch"):
        st.rerun()
    if c2.button("Clear", type="primary", width="stretch"):
        api.clear_history()
        st.rerun()


def open_entry(entry):
    try:
        if entry.get("draft_id"):
            draft = api.get_draft(entry["draft_id"], ss.token)
        else:
            draft = api.find_draft_by_job(entry["job_id"], ss.token)
            if draft:
                api.update_history(entry["job_id"], draft_id=draft["id"])
    except api.ApiError as e:
        st.error(f"Couldn't open this campaign. {e}")
        return
    if draft:
        go("detail", draft)
    else:
        st.warning("This campaign isn't ready yet. Try again in a minute.")


def history_page():
    back, title, trash = st.columns([1, 8, 1], vertical_alignment="center")
    if back.button("←", key="h_back"):
        go("create")
    title.markdown("**Campaign History**")
    if trash.button("🗑", key="h_clear"):
        confirm_clear()

    items = api.load_history()
    with st.container(border=True):
        a, b = st.columns([6, 1], vertical_alignment="center")
        n = len(items)
        a.markdown(f"**Generated campaigns**  \n<span style='color:#6B7280;font-size:.8rem'>"
                   f"{n} campaign{'s' if n != 1 else ''} created</span>", unsafe_allow_html=True)
        b.markdown("<span class='chip'>META AI</span>", unsafe_allow_html=True)
    if not items:
        st.info("No campaigns yet. Create your first campaign and it will show up here.")
        if st.button("Create a campaign", type="primary"):
            go("create")
        return
    for it in items:
        with st.container(border=True):
            st.markdown(f"**{it.get('name')}**  \n<span style='color:#9CA3AF;font-size:.75rem'>"
                        f"{fmt_date(it.get('created_at'))}</span>", unsafe_allow_html=True)
            k1, k2 = st.columns(2)
            with k1:
                kv("Objective", str(it.get("objective", "")).title())
                kv("Audience", it.get("audience"))
            with k2:
                kv("Daily budget", f"₹{it.get('budget')}")
            p, v = st.columns([5, 1], vertical_alignment="center")
            p.markdown(f"<span class='chip'>🌐 {str(it.get('platform', '')).title()}</span>", unsafe_allow_html=True)
            if v.button("View details", key=f"v_{it['job_id']}", type="tertiary"):
                open_entry(it)


# ----------------------------------------------------------- detail page ----
def detail_page():
    d = ss.selected
    if not d:
        go("history")
    back, title, refresh = st.columns([1, 8, 2], vertical_alignment="center")
    if back.button("←", key="d_back"):
        go("history")
    title.markdown("**Campaign details**")
    if refresh.button("↻ Refresh", key="d_refresh"):
        try:
            go("detail", api.get_draft(d["id"], ss.token))
        except api.ApiError as e:
            st.error(str(e))

    approved = bool(d.get("approved_by"))
    budget_inr = (d.get("budget") or 0) // 100

    urls = api.media_urls(d.get("creative_urls"))
    with st.container(border=True):
        section("🖼", "Ad image", "Generated by the image agent.")
        if urls:
            st.image(urls, width="stretch")
        else:
            st.info("No image was generated for this campaign.")

    with st.container(border=True):
        section("✨", "Ad copy", "Review everything before approving.")
        shown = False
        for lang, block in (d.get("copy_variants_jsonb") or {}).items():
            variants = block.get("variants", []) if isinstance(block, dict) else []
            for i, v in enumerate(variants, 1):
                shown = True
                st.markdown(f"**{str(lang).title()} · version {i}**")
                for key, label in [("headline", "Headline"), ("primary_text", "Primary text"),
                                   ("description", "Description"), ("cta", "Call to action")]:
                    if v.get(key):
                        st.markdown(f"<span style='color:#6B7280;font-size:.75rem'>{label}</span>  \n{v[key]}",
                                    unsafe_allow_html=True)
        if not shown:
            st.info("No ad copy yet.")

    with st.container(border=True):
        k1, k2 = st.columns(2)
        with k1:
            kv("Daily budget", f"₹{budget_inr}")
        with k2:
            kv("Status", "Approved on Meta (paused)" if approved else "Draft, not sent to Meta")
        with st.expander("Targeting"):
            st.json(d.get("targeting_jsonb") or {})
        with st.expander("Research"):
            st.json(d.get("research_jsonb") or {})

    with st.container(border=True):
        section("✅", "Step 1: Approve", "Creates the ad on Meta as PAUSED. It does not spend any money.")
        ok = st.checkbox("I reviewed the image and copy", key=f"ok_{d['id']}", disabled=approved)
        if st.button("Approve and send to Meta (paused)", type="primary", width="stretch",
                     disabled=approved or not ok, key=f"ap_{d['id']}"):
            with st.spinner("Sending to Meta..."):
                try:
                    res = api.approve(d["id"], ss.token)
                    st.success((res or {}).get("message", "Approved."))
                    go("detail", api.get_draft(d["id"], ss.token))
                except api.ApiError as e:
                    st.error(f"Couldn't approve the campaign. {e}")

    with st.container(border=True):
        section("🚀", "Step 2: Activate", "Makes the ad live. This spends real money from your Meta ad account.")
        if not approved:
            st.caption("Approve the campaign first.")
        else:
            st.caption("Give Meta a minute after approving, then check the campaign in Ads Manager before going live.")
        typed = st.number_input("Type the daily budget (₹) to confirm", min_value=0, step=100, value=None,
                                placeholder=f"Type {budget_inr}", disabled=not approved, key=f"tb_{d['id']}")
        if st.button("Activate campaign", type="primary", width="stretch",
                     disabled=not approved or typed is None, key=f"ac_{d['id']}"):
            try:
                res = api.activate(d["id"], typed, ss.token)
                st.success((res or {}).get("message", "Activation requested."))
            except api.ApiError as e:
                st.error(f"Couldn't activate the campaign. {e}")


# ------------------------------------------------------------------ router ---
if not ss.token:
    login_page()
else:
    header()
    {"create": create_page, "history": history_page, "detail": detail_page,
     "clients": clients_page}[ss.page]()