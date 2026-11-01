# Creator Desk — Influencer Outreach Automation

A Python and Streamlit prototype for discovering Instagram creators, filtering profiles, drafting outreach with Groq, and tracking optional email delivery.

## What is implemented

- Apify hashtag discovery followed by profile lookup, with resumable CSV collection.
- Fashion/Beauty filtering by followers and engagement (defaults: 5,000–100,000 followers and 2.5% engagement).
- Engagement scoring from up to ten posts; at least three valid posts are required.
- Contact email extraction from profile data and bios. Websites are recorded, not crawled.
- Groq-generated email subjects, email pitches, and Instagram DM drafts.
- Streamlit review/edit/approval controls, simulated sending, and optional Gmail SMTP delivery.
- Duplicate-email protection based on successful deliveries in the local tracker. DMs are copied and sent manually.

## Run locally

Use Python 3.10+ from the repository root:

```bash
git clone https://github.com/Vaibhavpandey-web/Influencer_outreach_Automation_System.git
cd Influencer_outreach_Automation_System
python -m venv .venv
```

Activate with `source .venv/bin/activate` on macOS/Linux or `.venv\Scripts\activate` in Windows Command Prompt, then:

```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill only the credentials needed:

| Variable | Purpose |
| --- | --- |
| `APIFY_API_TOKEN` | Discover new Instagram profiles through Apify |
| `GROQ_API_KEY` | Generate outreach drafts |
| `GROQ_MODEL` | Optional model override; see the default in `pipeline.py` |
| `SENDER_EMAIL`, `SENDER_PASSWORD` | Optional Gmail SMTP account and app password for live sending |

Set your actual brand, product, and sender in `BRAND` in `pipeline.py` before generating messages.

```bash
streamlit run app.py
```

In the dashboard: find creators → filter and enrich → write messages → review and approve → simulate or send. Without API keys the dashboard can open, but new discovery and message generation are unavailable. Generated CSVs are not included in the repository.

## Command-line workflow

```bash
python apify_scraper.py  # collect profiles, requires Apify
python pipeline.py      # process data and simulate delivery
```

The pipeline reuses `raw_influencers.csv` if present, otherwise starts discovery. Without Groq credentials it leaves messages unavailable. There is no `generate_dataset.py`; the pipeline creates the dataset.

`python pipeline.py --live` enables real SMTP sending with configured credentials. Unlike the dashboard, this CLI path does not provide per-message approval: review your data and use simulation first. No credentials are needed for the offline tests below.

## Files and output

| File | Purpose |
| --- | --- |
| `app.py` | Creator Desk dashboard |
| `apify_scraper.py` | Discovery, engagement scoring, profile normalization |
| `pipeline.py` | Filtering, message generation, simulation/SMTP tracker |
| `requirements.txt` | Standard install entry point, includes `requirement.txt` |
| `.env.example` | Empty credential template |
| `data_raw/` | Saved Apify response snapshots; new runs write here |
| `raw_influencers.csv` | Generated discovery data |
| `influencer_dataset.csv` | Generated filtered profiles and messages |
| `outreach_tracker.csv` | Generated delivery status, timestamps and messages |

The raw dataset includes name, platform, profile URL, followers, engagement ratio and percentage, niche, source hashtag, themes, captions, bio, contact email, handle, and website. Audience age/gender/geography are unavailable placeholders, not measured demographics.

## Validation

```bash
python -m unittest discover -s tests -v
```

Tests use synthetic profiles and mocked Apify/SMTP operations. They do not scrape profiles, incur API charges, or send messages.

## Limitations

This is a local prototype, not a multi-user production service. Collection depends on provider availability and quota. Hashtag categories and recent-post engagement are approximations; audience quality and demographics are not verified. Generated messages need human review. CSV persistence has no concurrency protection, and the tracker must be retained for duplicate protection. Review raw snapshots before sharing them.

Future work: durable storage, stronger validation, CI, additional platforms, and improved niche classification.

Built by [Vaibhav Pandey](https://github.com/Vaibhavpandey-web).
