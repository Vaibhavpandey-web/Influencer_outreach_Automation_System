"""Creator Desk: Streamlit front end for the influencer outreach pipeline.

Run:  streamlit run app.py
Uses pipeline.py and apify_scraper.py from the same folder; data stays in the same CSV files.
"""
import contextlib
import html
import io
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

import pipeline as P

RAW, WORK, TRACK = "raw_influencers.csv", "influencer_dataset.csv", "outreach_tracker.csv"
MSG_COLS = ["Email Subject", "Generated Email Pitch", "Generated Instagram DM"]
BAD_MSG = ("N/A", "GENERATION_FAILED", "", "nan")
SHADES = ["#E4DDF0", "#F2CDD3", "#DE97AE", "#A8446F", "#6B2C5E", "#2B1A33"]

st.set_page_config(page_title="Creator Desk", page_icon="◐", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Instrument+Sans:wght@400;500;600&display=swap');
:root { --ink:#231826; --line:#E0D7E6; --berry:#8C2F5B; --muted:#6E6277; }
html, body, .stApp, p, label, input, textarea, button, li, td, th { font-family:'Instrument Sans', system-ui, sans-serif; }
h1, h2, h3, h4 { font-family:'Bricolage Grotesque','Instrument Sans',system-ui,sans-serif !important; letter-spacing:-0.02em; color:var(--ink); }
.block-container { padding-top:2.4rem; max-width:1180px; }
[data-testid="stSidebar"] { border-right:1px solid var(--line); }
.hero h1 { font-size:2.9rem; line-height:1.05; margin:0 0 .35rem 0; font-weight:700; }
.hero p { font-size:1.05rem; color:var(--muted); margin:0 0 1.4rem 0; max-width:62ch; }
.strip { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin:0 0 1.6rem 0; }
.chip { background:#fff; border:1px solid var(--line); border-radius:4px; overflow:hidden; }
.chip .sw { height:54px; }
.chip .meta { padding:.55rem .75rem .7rem .75rem; }
.chip .n { font-family:'Bricolage Grotesque',sans-serif; font-size:1.9rem; font-weight:700; line-height:1.1; color:var(--ink); }
.chip .l { font-size:.85rem; color:var(--muted); }
.card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:1.1rem 1.3rem; }
.card h3 { margin:.1rem 0 .2rem 0; font-size:1.5rem; }
.card .sub { color:var(--muted); margin-bottom:.8rem; }
.tag { display:inline-block; padding:.12rem .6rem; border-radius:999px; border:1px solid var(--line); background:#F7F4F8; font-size:.85rem; margin:0 .35rem .35rem 0; }
.why { border-left:4px solid var(--berry); padding:.1rem .8rem; margin:.7rem 0; }
.why.fail { border-left-color:#9A9AA5; }
.quote { color:var(--muted); font-style:italic; }
.wc { display:inline-block; padding:.05rem .55rem; border-radius:4px; font-size:.82rem; font-weight:600; }
.wc.ok { background:#DDEEDC; color:#1F4D2B; }
.wc.bad { background:#F6D9DE; color:#7A1F36; }
.stButton button[kind="primary"] { font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ---------------- data helpers ----------------
def read_csv(path):
    p = Path(path)
    if p.exists() and p.stat().st_size > 5:
        try:
            return pd.read_csv(p)
        except Exception:
            return None
    return None


def ensure_cols(df):
    for c in MSG_COLS:
        if c not in df.columns:
            df[c] = "N/A"
        df[c] = df[c].fillna("N/A").astype(str)
    for c in ("Approved", "DM Done"):
        if c not in df.columns:
            df[c] = False
        df[c] = df[c].fillna(False).astype(bool)
    return df


def wc(s):
    return len(str(s).split())


def msg_ok(row):
    return str(row["Generated Email Pitch"]) not in BAD_MSG


def valid_lengths(email, dm):
    return 60 <= wc(email) <= 90 and 15 <= wc(dm) <= 30


def load_working():
    df = read_csv(WORK)
    return ensure_cols(df) if df is not None else None


def save():
    st.session_state.df.to_csv(WORK, index=False)


def row_idx(url):
    df = st.session_state.df
    hits = df.index[df["Profile URL"] == url]
    return hits[0] if len(hits) else None


def esc(x):
    return html.escape(str(x)) if x is not None and str(x) != "nan" else ""


if "df" not in st.session_state:
    st.session_state.df = load_working()
df = st.session_state.df
has_status = df is not None and "Filter Status" in df.columns


# ---------------- sidebar ----------------
with st.sidebar:
    st.markdown("### Your criteria")
    min_f = st.number_input("Minimum followers", 1000, 1_000_000, 5000, step=1000)
    max_f = st.number_input("Maximum followers", 5000, 5_000_000, 100_000, step=5000)
    min_eng = st.slider("Minimum engagement (%)", 0.0, 10.0, 2.5, step=0.1)
    st.caption("Creators must also be in Fashion or Beauty to pass.")
    st.markdown("### Connections")
    provider = getattr(P, "LLM_PROVIDER", "groq")
    model = getattr(P, "HF_MODEL", "") if provider == "hf" else getattr(P, "GROQ_MODEL", "")
    st.write("Instagram search:", "ready" if os.getenv("APIFY_API_TOKEN") else "needs APIFY_API_TOKEN")
    st.write("Message writing:", f"{provider} · {model}" if getattr(P, "client", None) else "needs an API key")
    creds = bool(getattr(P, "SENDER_EMAIL", "") and getattr(P, "SENDER_PASSWORD", ""))
    st.write("Email sending:", "ready" if creds else "simulation only")


# ---------------- header + swatch strip ----------------
st.markdown("""<div class="hero"><h1>Creator Desk</h1>
<p>Find fashion and beauty creators, check them against your criteria, review the messages, then send.</p></div>""",
            unsafe_allow_html=True)

raw_df = read_csv(RAW)
track_df = read_csv(TRACK)
if df is not None and has_status:
    passed = df["Filter Status"] == "Passed"
    good = df.apply(msg_ok, axis=1) if len(df) else pd.Series(dtype=bool)
    n_found, n_pass = len(df), int(passed.sum())
    n_email = int((passed & (df["Contact Email"] != "Not Found")).sum())
    n_written = int((passed & good).sum())
    n_appr = int((passed & good & df["Approved"]).sum())
else:
    n_found, n_pass, n_email, n_written, n_appr = (len(raw_df) if raw_df is not None else 0), 0, 0, 0, 0
n_sent = int((track_df["Sent"] == "Yes").sum()) if track_df is not None and "Sent" in track_df.columns else 0
labels = [("Found", n_found), ("Passed filter", n_pass), ("Has email", n_email),
          ("Messages ready", n_written), ("Approved", n_appr), ("Sent", n_sent)]
st.markdown('<div class="strip">' + "".join(
    f'<div class="chip"><div class="sw" style="background:{c}"></div><div class="meta">'
    f'<div class="n">{n}</div><div class="l">{l}</div></div></div>' for (l, n), c in zip(labels, SHADES)) + "</div>",
    unsafe_allow_html=True)

tab_find, tab_creators, tab_msgs, tab_send = st.tabs(["Find and filter", "Creators", "Messages", "Send"])


# ---------------- tab: find and filter ----------------
def run_find(tags, per_tag, target, fresh):
    from apify_scraper import fetch_real_influencers
    buf = io.StringIO()
    with st.status("Searching Instagram through Apify. This can take a few minutes.") as status:
        try:
            tag_list = tuple(t.lower().lstrip("#") for t in re.split(r"[,\s]+", tags) if t.strip())
            with contextlib.redirect_stdout(buf):
                fetch_real_influencers(hashtags=tag_list, results_per_hashtag=int(per_tag),
                                       target_in_range=int(target), fresh=fresh)
            status.update(label="Search finished. Next: filter and enrich.", state="complete")
        except Exception as e:
            status.update(label="Search stopped", state="error")
            st.error(f"The search stopped: {e}")
    st.session_state.log = buf.getvalue()


def run_process(raw, old):
    with st.spinner("Filtering, then looking for public emails on each passed creator's website..."):
        out = P.filter_influencers(raw.copy(), int(min_f), int(max_f), min_eng / 100)
        out = P.enrich_profiles(out)
        if old is not None:
            prev = old.drop_duplicates("Profile URL").set_index("Profile URL")
            for c in MSG_COLS + ["Approved", "DM Done"]:
                if c in prev.columns:
                    out[c] = out["Profile URL"].map(prev[c])
        st.session_state.df = ensure_cols(out.reset_index(drop=True))
        save()


def run_write(n, redo):
    d = st.session_state.df
    todo = [i for i in d.index[d["Filter Status"] == "Passed"] if redo or not msg_ok(d.loc[i])][: int(n)]
    bar = st.progress(0.0, text="Writing messages")
    for k, i in enumerate(todo):
        d.loc[i, MSG_COLS] = list(P.generate_ai_messages(d.loc[i]))
        d.loc[i, "Approved"] = False
        bar.progress((k + 1) / len(todo), text=f"Wrote {k + 1} of {len(todo)}")
    save()
    st.session_state.log = st.session_state.get("log", "") + f"\nWrote messages for {len(todo)} creators."
    bar.empty()


with tab_find:
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.subheader("Find creators")
        tags = st.text_input("Hashtags, without #, separated by spaces",
                             "affordableskincare skincarereview drugstoremakeup outfitinspo")
        a, b = st.columns(2)
        per_tag = a.number_input("Posts per hashtag", 20, 300, 100, step=10)
        target = b.number_input("Stop at this many creators in range", 5, 300, 60, step=5)
        fresh = st.checkbox("Replace saved creators instead of adding to them")
        token_ok = bool(os.getenv("APIFY_API_TOKEN"))
        if not token_ok:
            st.warning("Add APIFY_API_TOKEN to your .env file to search Instagram.")
        if st.button("Find creators", type="primary", disabled=not token_ok):
            run_find(tags, per_tag, target, fresh)
    with right:
        st.subheader("Filter and enrich")
        st.write(f"A creator passes with {int(min_f):,} to {int(max_f):,} followers, at least {min_eng}% engagement, "
                 "and a Fashion or Beauty niche. Passed creators also get a public-email lookup on their own website.")
        if st.button("Filter and enrich", type="primary", disabled=raw_df is None):
            run_process(raw_df, st.session_state.df)
            st.rerun()
        if raw_df is None:
            st.caption("Find creators first. The results are saved to raw_influencers.csv.")
        st.subheader("Write messages")
        c1, c2 = st.columns(2)
        n_write = c1.number_input("Creators to write for", 1, 200, 10)
        redo = c2.checkbox("Rewrite existing messages")
        can_write = has_status and getattr(P, "client", None) is not None
        if st.button("Write messages", type="primary", disabled=not can_write):
            run_write(n_write, redo)
            st.rerun()
        if not has_status:
            st.caption("Filter and enrich first.")
        elif getattr(P, "client", None) is None:
            st.caption("Add your message-writing API key to .env first.")
    if st.session_state.get("log"):
        with st.expander("Run log"):
            st.code(st.session_state.log, language=None)


# ---------------- tab: creators ----------------
with tab_creators:
    if not has_status:
        st.info("No creators to show yet. Open Find and filter, search for creators, then run Filter and enrich.")
    else:
        f1, f2, f3, f4 = st.columns([1.2, 1.2, 1.6, 1])
        status_sel = f1.multiselect("Result", ["Passed", "Failed"], default=["Passed", "Failed"])
        cats = sorted(df["Category / Niche"].dropna().unique())
        cat_sel = f2.multiselect("Category", cats, default=cats)
        q = f3.text_input("Search name or handle")
        email_only = f4.checkbox("Has email")
        view = df[df["Filter Status"].isin(status_sel) & df["Category / Niche"].isin(cat_sel)]
        if q:
            view = view[view["Influencer Name"].astype(str).str.contains(q, case=False, na=False)
                        | view["Social Handle"].astype(str).str.contains(q, case=False, na=False)]
        if email_only:
            view = view[view["Contact Email"] != "Not Found"]
        cols = [c for c in ["Influencer Name", "Social Handle", "Category / Niche", "Follower Count",
                            "Engagement Rate (%)", "Contact Email", "Filter Status", "Filter Reason", "Profile URL"]
                if c in view.columns]
        st.dataframe(view[cols], hide_index=True, column_config={
            "Profile URL": st.column_config.LinkColumn("Profile", display_text="Open"),
            "Follower Count": st.column_config.NumberColumn("Followers", format="%d"),
            "Engagement Rate (%)": st.column_config.NumberColumn("Engagement (%)", format="%.1f"),
            "Filter Status": "Result", "Filter Reason": "Why"})
        st.caption(f"{len(view)} of {len(df)} creators shown.")

        if len(view):
            pick = st.selectbox("Open a creator", view["Influencer Name"].tolist())
            r = view[view["Influencer Name"] == pick].iloc[0]
            ok = r["Filter Status"] == "Passed"
            eng = r.get("Engagement Rate (%)")
            email_line = esc(r["Contact Email"]) + (f' ({esc(r["Email Source"])})' if str(r.get("Email Source", "")) not in ("", "nan") else "")
            st.markdown(f"""<div class="card">
<h3>{esc(r['Influencer Name'])}</h3>
<div class="sub"><a href="{esc(r['Profile URL'])}" target="_blank">{esc(r['Social Handle'])}</a></div>
<span class="tag">{esc(r['Category / Niche'])}</span>
<span class="tag">{int(r['Follower Count']):,} followers</span>
<span class="tag">{'engagement ' + format(eng, '.1f') + '%' if pd.notna(eng) else 'engagement unavailable'}</span>
<span class="tag">{email_line}</span>
<div class="why {'' if ok else 'fail'}"><b>{'Passed' if ok else 'Failed'}.</b> {esc(r['Filter Reason'])}</div>
<div><b>Themes:</b> {esc(r.get('Content Themes'))}</div>
<div class="quote">{esc(r.get('Recent Content'))}</div></div>""", unsafe_allow_html=True)


# ---------------- tab: messages ----------------
def set_field(url, col, key):
    i = row_idx(url)
    d = st.session_state.df
    d.at[i, col] = st.session_state[key]
    if not valid_lengths(d.at[i, "Generated Email Pitch"], d.at[i, "Generated Instagram DM"]):
        d.at[i, "Approved"] = False
        st.session_state[f"appr_{url}"] = False
    save()


def set_approved(url):
    i = row_idx(url)
    st.session_state.df.at[i, "Approved"] = bool(st.session_state[f"appr_{url}"])
    save()


def rewrite(url):
    i = row_idx(url)
    d = st.session_state.df
    d.loc[i, MSG_COLS] = list(P.generate_ai_messages(d.loc[i]))
    d.at[i, "Approved"] = False
    for col, k in zip(MSG_COLS, ("subj", "email", "dm")):
        st.session_state[f"{k}_{url}"] = d.at[i, col]
    st.session_state[f"appr_{url}"] = False
    save()


def approve_all(urls):
    d = st.session_state.df
    for u in urls:
        i = row_idx(u)
        if valid_lengths(d.at[i, "Generated Email Pitch"], d.at[i, "Generated Instagram DM"]):
            d.at[i, "Approved"] = True
            st.session_state[f"appr_{u}"] = True
    save()


def chip(n, lo, hi):
    return f'<span class="wc {"ok" if lo <= n <= hi else "bad"}">{n} words, aim for {lo} to {hi}</span>'


with tab_msgs:
    if not has_status or n_pass == 0:
        st.info("Messages appear here once at least one creator has passed the filter.")
    else:
        d = st.session_state.df
        ready = d[(d["Filter Status"] == "Passed") & d.apply(msg_ok, axis=1)]
        if ready.empty:
            st.info("No messages written yet. Open Find and filter and choose Write messages.")
        else:
            m1, m2 = st.columns([1, 1])
            show = m1.radio("Show", ["Needs approval", "Approved", "All"], horizontal=True)
            m2.button("Approve every message with valid lengths", on_click=approve_all,
                      args=(ready["Profile URL"].tolist(),))
            if show == "Needs approval":
                ready = ready[~ready["Approved"]]
            elif show == "Approved":
                ready = ready[ready["Approved"]]
            for _, r in ready.iterrows():
                url = r["Profile URL"]
                with st.container(border=True):
                    h1, h2 = st.columns([3, 1])
                    h1.markdown(f"**{r['Influencer Name']}** · {r['Category / Niche']} · {int(r['Follower Count']):,} followers · "
                                f"email: {r['Contact Email']}")
                    h2.button("Rewrite", key=f"rw_{url}", on_click=rewrite, args=(url,))
                    st.text_input("Subject", r["Email Subject"], key=f"subj_{url}",
                                  on_change=set_field, args=(url, "Email Subject", f"subj_{url}"))
                    e1, e2 = st.columns([3, 2], gap="large")
                    with e1:
                        st.text_area("Email", r["Generated Email Pitch"], height=190, key=f"email_{url}",
                                     on_change=set_field, args=(url, "Generated Email Pitch", f"email_{url}"))
                        st.markdown(chip(wc(r["Generated Email Pitch"]), 60, 90), unsafe_allow_html=True)
                    with e2:
                        st.text_area("Instagram DM", r["Generated Instagram DM"], height=190, key=f"dm_{url}",
                                     on_change=set_field, args=(url, "Generated Instagram DM", f"dm_{url}"))
                        st.markdown(chip(wc(r["Generated Instagram DM"]), 15, 30), unsafe_allow_html=True)
                    ok = valid_lengths(r["Generated Email Pitch"], r["Generated Instagram DM"])
                    st.checkbox("Approved for sending" if ok else "Fix the word counts to approve",
                                value=bool(r["Approved"]), key=f"appr_{url}", disabled=not ok,
                                on_change=set_approved, args=(url,))


# ---------------- tab: send ----------------
def set_dm_done(url):
    i = row_idx(url)
    st.session_state.df.at[i, "DM Done"] = bool(st.session_state[f"dm_done_{url}"])
    save()


with tab_send:
    if not has_status or n_appr == 0:
        st.info("Approve at least one message in the Messages tab to unlock sending.")
    else:
        d = st.session_state.df
        approved = d[(d["Filter Status"] == "Passed") & d.apply(msg_ok, axis=1) & d["Approved"]]
        with_email = int((approved["Contact Email"] != "Not Found").sum())
        st.subheader("Send approved emails")
        st.write(f"{len(approved)} approved creators: {with_email} have an email address, "
                 f"{len(approved) - with_email} will get a DM only. Creators already emailed are skipped automatically.")
        mode = st.radio("How to send", ["Simulate (nothing is delivered)", "Send real emails"], horizontal=True)
        live = mode.startswith("Send")
        confirm = ""
        if live:
            if not creds:
                st.error("Add SENDER_EMAIL and SENDER_PASSWORD (a Gmail app password) to .env to send real emails.")
            confirm = st.text_input("Type SEND to confirm")
        can = (not live) or (creds and confirm.strip() == "SEND")
        if st.button("Send emails now" if live else "Run simulation", type="primary", disabled=not can):
            with st.spinner("Working through the approved list..."):
                P.execute_sending_layer(approved, TRACK, live=live)
            st.success("Done. The tracker below is updated.")
            track_df = read_csv(TRACK)
        if track_df is not None:
            track_df = read_csv(TRACK)
            show_cols = [c for c in ["Influencer", "Email", "Sent", "Status", "Date"] if c in track_df.columns]
            st.dataframe(track_df[show_cols], hide_index=True)
            st.download_button("Download tracker (CSV)", track_df.to_csv(index=False), "outreach_tracker.csv", "text/csv")

        st.subheader("Instagram DMs to send by hand")
        st.caption("Instagram has no permitted way to send cold DMs automatically. Copy each message and send it from the creator's profile.")
        for _, r in approved.iterrows():
            url = r["Profile URL"]
            with st.expander(f"{r['Influencer Name']}  ({r['Social Handle']})"):
                st.code(r["Generated Instagram DM"], language=None)
                x1, x2 = st.columns([1, 2])
                x1.link_button("Open profile", url)
                x2.checkbox("Sent this DM", value=bool(r["DM Done"]), key=f"dm_done_{url}",
                            on_change=set_dm_done, args=(url,))