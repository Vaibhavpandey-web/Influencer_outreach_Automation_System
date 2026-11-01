"""Two-stage Instagram discovery with Apify.

Stage 1: hashtag pages  -> posts            -> unique creator usernames (hashtag posts have NO follower data)
Stage 2: profile pages  -> profile details  -> followers, bio, email, recent posts (engagement)
Raw API responses are saved to data_raw/*.json so you can always see what Apify really returned.
"""
import json
import os
import re
from collections import Counter

import pandas as pd
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
ACTOR = "apify/instagram-scraper"
RAW_DIR = "data_raw"

HASHTAG_CATEGORY = {
    "skincare": "Beauty", "makeup": "Beauty", "makeuptutorial": "Beauty", "skincareroutine": "Beauty",
    "haircare": "Beauty", "fashionstyle": "Fashion", "ootd": "Fashion", "thriftfashion": "Fashion",
    "indianfashion": "Fashion", "streetstyle": "Fashion",
    "affordableskincare": "Beauty", "skincarereview": "Beauty", "drugstoremakeup": "Beauty",
    "makeupreview": "Beauty", "kbeautyskincare": "Beauty", "curlyhaircare": "Beauty",
    "outfitinspo": "Fashion", "thriftedoutfit": "Fashion", "capsulewardrobe": "Fashion",
}
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def extract_email(text):
    m = EMAIL_RE.findall(text) if isinstance(text, str) else []
    return m[0].lower() if m else None


def run_actor(client, run_input, tag):
    run = client.actor(ACTOR).call(run_input=run_input)
    print(f"[Apify] {tag}: status={run.get('status')}  console=https://console.apify.com/actors/runs/{run.get('id')}")
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(f"{RAW_DIR}/{tag}.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2, default=str)
    errors = [i for i in items if i.get("error")]
    if errors:
        print(f"[Apify] {tag}: {len(errors)} error items, first: {errors[0]}")
    return [i for i in items if not i.get("error")]


def calculate_engagement(posts, followers):
    """Average (likes+comments)/followers over up to 10 recent posts. Returns ratio or None if unknown."""
    if not followers:
        return None
    rates = []
    for p in (posts or [])[:10]:
        likes, comments = p.get("likesCount"), p.get("commentsCount") or 0
        if likes is None or likes < 0:     
            continue
        rates.append((likes + comments) / followers)
    return round(sum(rates) / len(rates), 4) if len(rates) >= 3 else None


def build_row(p, source_tag, hashtags):
    username = p.get("username")
    followers = p.get("followersCount") or 0
    bio = p.get("biography") or ""
    posts = p.get("latestPosts") or []
    captions = [(x.get("caption") or "").replace("\n", " ")[:140] for x in posts[:3] if x.get("caption")]
    post_tags = Counter(t.lower() for x in posts for t in (x.get("hashtags") or []))
    tag = source_tag.get(username, hashtags[0])
    eng = calculate_engagement(posts, followers)
    return {
        "Influencer Name": p.get("fullName") or username,
        "Platform": "Instagram",
        "Profile URL": f"https://www.instagram.com/{username}/",
        "Follower Count": followers,
        "Engagement Rate": eng,
        "Engagement Rate (%)": round(eng * 100, 2) if eng is not None else None,
        "Category / Niche": HASHTAG_CATEGORY.get(tag, tag.capitalize()),
        "Source Hashtag": tag,
        "Content Themes": ", ".join(t for t, _ in post_tags.most_common(5)) or bio[:100],
        "Recent Content": " | ".join(captions),
        "Bio": bio.replace("\n", " "),
        "Contact Email": p.get("businessEmail") or extract_email(bio) or "Not Found",
        "Social Handle": f"@{username}",
        "Website": p.get("externalUrl") or "Not Found",
        "Audience Age": "Not Available",
        "Audience Gender": "Not Available",
        "Audience Geography": "Not Available",   
    }


def fetch_real_influencers(hashtags=("affordableskincare", "skincarereview", "drugstoremakeup", "outfitinspo"),
                           results_per_hashtag=100, target_in_range=60, batch_size=40, max_profiles=400,
                           min_followers=5000, max_followers=100000, like_window=(30, 10000),
                           output_csv="raw_influencers.csv", fresh=False):
    """Keeps scraping profile batches until `target_in_range` creators with 5k-100k followers are found."""
    if not APIFY_API_TOKEN:
        raise ValueError("APIFY_API_TOKEN missing. Put it in a .env file next to this script.")
    client = ApifyClient(APIFY_API_TOKEN)

    has_old = not fresh and os.path.exists(output_csv) and os.path.getsize(output_csv) > 5
    existing = pd.read_csv(output_csv) if has_old else pd.DataFrame()
    seen = set(existing["Social Handle"].astype(str).str.lstrip("@")) if len(existing) else set()
    in_range = int(existing["Follower Count"].between(min_followers, max_followers).sum()) if len(existing) else 0
    print(f"[Resume] {len(seen)} creators already saved, {in_range} in range (target {target_in_range})")
    if in_range >= target_in_range:
        print("[Resume] Target already reached. Delete the CSV or raise target_in_range to collect more.")
        return existing

    source_tag, post_likes = {}, {}
    for tag in hashtags:
        items = run_actor(client, {
            "directUrls": [f"https://www.instagram.com/explore/tags/{tag}/"],
            "resultsType": "posts", "resultsLimit": results_per_hashtag, "addParentData": False,
        }, f"hashtag_{tag}")
        for it in items:
            u = it.get("ownerUsername")
            if u and u not in source_tag:
                source_tag[u] = tag
                post_likes[u] = it.get("likesCount")
        print(f"[Stage 1] #{tag}: {len(items)} posts, {len(source_tag)} unique creators so far")

    lo, hi = like_window
    cands = [u for u in source_tag if u not in seen and (post_likes[u] is None or post_likes[u] < 0 or lo <= post_likes[u] <= hi)]
    cands = cands[:max_profiles]
    print(f"[Stage 1] {len(source_tag)} creators -> {len(cands)} candidates after like-count pre-screen")
    if not cands:
        raise RuntimeError("No candidates. Inspect data_raw/hashtag_*.json.")

    rows = []
    for i in range(0, len(cands), batch_size):
        if in_range >= target_in_range:
            break
        batch = cands[i:i + batch_size]
        profiles = run_actor(client, {
            "directUrls": [f"https://www.instagram.com/{u}/" for u in batch],
            "resultsType": "details", "resultsLimit": 1,
        }, f"profiles_{i // batch_size}")
        for p in profiles:
            if not p.get("username") or p.get("private"):
                continue
            row = build_row(p, source_tag, hashtags)
            rows.append(row)
            in_range += min_followers <= row["Follower Count"] <= max_followers
        print(f"[Stage 2] scraped {len(rows)} profiles, {in_range} in {min_followers:,}-{max_followers:,} range")

    df = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True).drop_duplicates("Profile URL", keep="last")
    df.to_csv(output_csv, index=False)
    print(f"[Apify] Saved {len(df)} profiles ({in_range} micro-influencers) -> {output_csv}")
    return df


if __name__ == "__main__":
    fetch_real_influencers()