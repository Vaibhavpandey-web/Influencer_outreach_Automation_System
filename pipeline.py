import argparse
import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")                      
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")   
SENDER_EMAIL = os.getenv("SENDER_EMAIL", " ")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", " ")            

BRAND = {"name": "YourBrand", "product": "vegan skincare & makeup line", "sender": "Your Name"}
TARGET_CATEGORIES = {"Beauty", "Fashion"}                     

client = None
if GROQ_API_KEY:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)


# ---- DISCOVERY ----
def load_data(filepath="raw_influencers.csv"):
    if not os.path.exists(filepath) or os.path.getsize(filepath) < 5:
        if not os.getenv("APIFY_API_TOKEN"):
            raise SystemExit("No raw_influencers.csv and no APIFY_API_TOKEN. Real data is required.")
        from apify_scraper import fetch_real_influencers
        return fetch_real_influencers(output_csv=filepath)
    df = pd.read_csv(filepath)
    print(f"[1. Discovery] Loaded {len(df)} profiles from {filepath}")
    return df


# ---- FILTERING ----
def filter_influencers(df, min_f=5000, max_f=100000, min_eng=0.025):
    status, reason = [], []
    for _, r in df.iterrows():
        f = float(r.get("Follower Count", 0) or 0)
        e = r.get("Engagement Rate")
        cat = r.get("Category / Niche")
        fails = []

        if not (min_f <= f <= max_f):
            fails.append(f"followers {int(f):,} outside {min_f:,}-{max_f:,}")
        if pd.isna(e):
            fails.append("engagement unavailable (likes hidden or too few posts)")
        elif float(e) < min_eng:
            fails.append(f"engagement {float(e)*100:.1f}% < {min_eng*100:.1f}%")
        if cat not in TARGET_CATEGORIES:
            fails.append(f"category {cat} not in Fashion & Beauty")

        status.append("Failed" if fails else "Passed")
        reason.append("; ".join(fails) if fails else "Meets follower, engagement and Fashion & Beauty criteria")

    df["Filter Status"], df["Filter Reason"] = status, reason
    print(f"[2. Filtering] {(df['Filter Status'] == 'Passed').sum()}/{len(df)} passed")
    return df


# ---- ENRICHMENT ----
def enrich_profiles(df):
    df["Contact Email"] = df["Contact Email"].fillna("").astype(str).str.strip()
    df["Contact Email"] = df["Contact Email"].apply(lambda x: x if "@" in x and "." in x else "Not Found")
    for c in ("Website", "Audience Age", "Audience Gender", "Audience Geography"):
        if c not in df.columns:
            df[c] = "Not Available"
        else:
            df[c] = df[c].fillna("Not Available")
    return df


# ---- AI PERSONALIZATION----
SYSTEM = (
    "You write short, human outreach messages from a brand to a micro-influencer. Use ONLY the facts given; "
    "never invent details. Reference their niche, themes or recent content. No placeholders, links or hashtags. "
    'Return JSON only: {"subject": str, "email": str, "dm": str}. '
    "email = concise, around 60-90 words including greeting and sign-off. "
    "dm = short, around 15-30 words, casual, max one emoji."
)


def wc(s):
    return len(str(s or "").split())


def generate_ai_messages(row, attempts=3):
    if row.get("Filter Status") != "Passed":
        return pd.Series(["N/A", "N/A", "N/A"])
    if client is None:
        print(f"[4. AI Warning] Groq client not initialized for {row.get('Influencer Name')}")
        return pd.Series(["N/A", "N/A", "N/A"])

    follower_count = int(float(row.get("Follower Count", 0) or 0))
    facts = {
        "name": str(row.get("Influencer Name", "Creator")),
        "platform": str(row.get("Platform", "Instagram")),
        "niche": str(row.get("Category / Niche", "")),
        "themes": str(row.get("Content Themes", "")),
        "recent_content": str(row.get("Recent Content", "")),
        "followers": follower_count,
        "brand": BRAND,
        "angle": "paid UGC + affiliate" if follower_count < 30000 else "paid sponsorship"
    }

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(facts)}
    ]

    last_generated = None

    for attempt in range(attempts):
        try:
            r = client.chat.completions.create(
                model=GROQ_MODEL,
                temperature=0.7,
                response_format={"type": "json_object"},
                messages=messages
            )
            raw_content = r.choices[0].message.content
            m = json.loads(raw_content)

        
            subject = m.get("subject") or m.get("subject_line") or f"Collab with {BRAND['name']}"
            email = m.get("email") or m.get("email_body") or m.get("email_pitch") or ""
            dm = m.get("dm") or m.get("instagram_dm") or m.get("dm_message") or ""

            ew, dw = wc(email), wc(dm)
            last_generated = (subject, email, dm)

            
            if 45 <= ew <= 110 and 10 <= dw <= 45:
                return pd.Series([subject, email, dm])

            
            messages.append({"role": "assistant", "content": raw_content})
            messages.append({
                "role": "user",
                "content": f"Previous attempt email was {ew} words and DM was {dw} words. "
                           f"Adjust response so email is ~60-90 words and DM is ~15-30 words."
            })

        except Exception as e:
            print(f"[4. AI Warning] Attempt {attempt + 1} failed for {facts['name']}: {e}")

    if last_generated and last_generated[1] and last_generated[2]:
        return pd.Series(list(last_generated))

    return pd.Series(["GENERATION_FAILED"] * 3)


def run_personalization(df):
    if client is None:
        print("[4. AI] GROQ_API_KEY not set -> no messages generated.")
        df["Email Subject"] = "N/A"
        df["Generated Email Pitch"] = "N/A"
        df["Generated Instagram DM"] = "N/A"
        return df

    print(f"[4. AI] Generating personalized messages for passing profiles...")
    results = df.apply(generate_ai_messages, axis=1, result_type="expand")
    results.columns = ["Email Subject", "Generated Email Pitch", "Generated Instagram DM"]
    df[["Email Subject", "Generated Email Pitch", "Generated Instagram DM"]] = results
    
    passed_count = (df["Filter Status"] == "Passed").sum()
    gen_success = ((df["Filter Status"] == "Passed") & (df["Generated Email Pitch"] != "GENERATION_FAILED")).sum()
    print(f"[4. AI] Successfully generated messages for {gen_success}/{passed_count} passed profiles.")
    
    return df


def execute_sending_layer(df, tracker_file="outreach_tracker.csv", live=False):
    cols = ["Influencer", "Email", "Profile URL", "Message Generated", "Email Pitch", "Instagram DM", "Sent", "Date", "Status"]
    old = pd.read_csv(tracker_file) if os.path.exists(tracker_file) else pd.DataFrame(columns=cols)
    already = set(old.loc[old["Sent"] == "Yes", "Email"].dropna())
    keep = old[old["Sent"] == "Yes"]  

    rows, server = [], None
    try:
        for _, r in df[df["Filter Status"] == "Passed"].iterrows():
            email = r["Contact Email"]
            ok_msg = r["Generated Email Pitch"] not in ("N/A", "GENERATION_FAILED")
            base = {
                "Influencer": r["Influencer Name"],
                "Email": email,
                "Profile URL": r["Profile URL"],
                "Message Generated": "Yes" if ok_msg else "No",
                "Email Pitch": r["Generated Email Pitch"],
                "Instagram DM": r["Generated Instagram DM"],
                "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            if not ok_msg:
                rows.append({**base, "Sent": "No", "Status": "Skipped - no valid message"})
            elif email == "Not Found":
                rows.append({**base, "Sent": "No", "Status": "Skipped - Email Not Found (DM queued manually)"})
            elif email in already:
                rows.append({**base, "Sent": "No", "Status": "Skipped - Duplicate Outreach Prevented"})
            elif not live:
                rows.append({**base, "Sent": "No", "Status": "Simulated (not delivered)"})
            else:
                try:
                    if server is None:
                        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
                        server.starttls()
                        server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    msg = MIMEText(r["Generated Email Pitch"], "plain")
                    msg["From"], msg["To"], msg["Subject"] = SENDER_EMAIL, email, r["Email Subject"]
                    server.send_message(msg)
                    already.add(email)
                    rows.append({**base, "Sent": "Yes", "Status": "Sent (Live SMTP)"})
                except Exception as e:
                    rows.append({**base, "Sent": "No", "Status": f"Failed - {e}"})
    finally:
        if server:
            server.quit()

    new = pd.DataFrame(rows, columns=cols)
    new = new[~new["Profile URL"].isin(keep["Profile URL"])] if len(keep) else new
    out = pd.concat([keep, new], ignore_index=True)
    out.to_csv(tracker_file, index=False)
    print(f"[5. Sending] {len(new)} records processed this run -> {tracker_file}")
    return out


def run_pipeline(live=False):
    df = load_data()
    df = enrich_profiles(filter_influencers(df))
    df = run_personalization(df)
    df.to_csv("influencer_dataset.csv", index=False)
    execute_sending_layer(df, live=live and bool(SENDER_EMAIL and SENDER_PASSWORD))
    print(f"Total {len(df)} | Passed {(df['Filter Status'] == 'Passed').sum()} | Failed {(df['Filter Status'] == 'Failed').sum()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="really send emails (default: simulate)")
    run_pipeline(ap.parse_args().live)
