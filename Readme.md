# Influencer Outreach Automation System

> An automated pipeline that discovers Instagram influencers, scores them by engagement, organises them into a clean dataset, and tracks outreach, all from a Streamlit dashboard.

**Author:** Vaibhav Pandey
**Tech:** Python · Apify · Pandas · Streamlit

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Project Structure](#project-structure)
4. [How It Works](#how-it-works)
5. [Tech Stack](#tech-stack)
6. [Installation](#installation)
7. [Configuration](#configuration)
8. [Usage](#usage)
9. [Dataset Schema](#dataset-schema)
10. [Sample Output](#sample-output)
11. [Limitations](#limitations)
12. [Future Improvements](#future-improvements)
13. [Author](#author)

---

## Overview

Finding the right influencers for a brand campaign is slow and manual. This project automates the process:

- Scrapes real Instagram profile and post data using the **Apify** API
- Calculates an **engagement rate** for each influencer from their recent posts
- Classifies each influencer into a **niche/category** based on hashtags and content
- Produces a structured dataset ready for outreach
- Tracks outreach status in a tracker file
- Presents everything in an interactive **Streamlit** dashboard

## Features

- **Automated scraping** of influencer profiles by hashtag via Apify
- **Engagement rate calculation** (average of likes + comments divided by followers, over the 10 most recent posts)
- **Data cleaning** that skips invalid posts and requires at least 3 valid posts for a reliable score
- **Niche detection** that maps hashtags to categories and extracts top content themes
- **Outreach tracker** (CSV) to monitor contacted influencers
- **Interactive dashboard** for exploring and filtering results

## Project Structure

```
Automated_system/
├── apify_scraper.py        # Scrapes influencer data via Apify, builds rows
├── pipeline.py             # Orchestrates scrape → clean → dataset → tracker
├── app.py                  # Streamlit dashboard
├── data_raw/               # Raw scraped data
├── raw_influencers.csv     # Unprocessed scraper output
├── influencer_dataset.csv  # Final cleaned dataset
├── outreach_tracker.csv    # Outreach status tracking
├── requirement.txt         # Python dependencies
├── .env.example            # Template for required environment variables
└── README.md
```

## How It Works

```
Hashtags ──► Apify Scraper ──► Raw Data ──► Cleaning & Engagement Scoring
                                                        │
                                                        ▼
        Streamlit Dashboard ◄── Final Dataset ◄── Niche Classification
                 │
                 ▼
        Outreach Tracker
```

1. **Scrape:** `apify_scraper.py` fetches profiles and their latest posts for a set of target hashtags.
2. **Score:** `calculate_engagement()` computes the engagement rate from up to 10 recent posts.
3. **Structure:** `build_row()` turns each profile into a standardised record.
4. **Export:** the pipeline writes `raw_influencers.csv` and `influencer_dataset.csv`.
5. **Track:** `outreach_tracker.csv` records the outreach status of each influencer.
6. **Explore:** `app.py` presents everything in an interactive dashboard.

### Engagement Rate Formula

```
engagement_rate = mean( (likes + comments) / followers )   over the latest ≤10 posts
```

Posts with missing or negative like counts are skipped. If fewer than 3 valid posts remain, the rate is left empty rather than reporting a misleading number.

## Tech Stack

| Area | Tools |
|------|-------|
| Language | Python 3.10+ |
| Data collection | Apify (Instagram scraper) |
| Data processing | Pandas, `collections.Counter` |
| UI | Streamlit |
| Config | `python-dotenv` |

## Installation

**1. Download or clone the project and open the folder**

```bash
cd Automated_system
```

**2. Create and activate a virtual environment**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and add your own key:

```env
APIFY_API_TOKEN=your_apify_token_here
```

> The `.env` file is intentionally not included in this submission. You need your own Apify API token to run the scraper.

## Usage

Run all commands from inside the `Automated_system` folder.

**Run the full pipeline**

```bash
python pipeline.py
```

**Launch the dashboard**

```bash
streamlit run app.py
```

Then open the local URL shown in the terminal (usually `http://localhost:8501`).

**Generate only the dataset**

```bash
python generate_dataset.py
```

> If you only want to review the results without running the scraper, open `influencer_dataset.csv` and `outreach_tracker.csv` directly. They contain the output of a previous run.

## Dataset Schema

| Column | Description |
|--------|-------------|
| Influencer Name | Full name, or username if unavailable |
| Platform | Instagram |
| Profile URL | Link to the influencer's profile |
| Follower Count | Number of followers |
| Engagement Rate | Engagement as a decimal |
| Engagement Rate (%) | Engagement as a percentage |
| Category / Niche | Mapped from the source hashtag |
| Source Hashtag | Hashtag the influencer was discovered through |
| Content Themes | Top 5 most common hashtags in recent posts |
| Recent Content | Short captions from the latest posts |
| Bio | Profile biography |

## Sample Output

| Influencer Name | Followers | Engagement Rate (%) | Category / Niche |
|-----------------|-----------|---------------------|------------------|
| _example_user_ | 52,300 | 3.41 | Fitness |
| _example_user_ | 18,900 | 5.12 | Travel |


## Limitations

- Depends on Apify availability, quota, and Instagram's data accessibility
- Engagement rate is based on a small sample of recent posts
- Niche classification relies on hashtag mapping and may miss nuance
- Currently supports Instagram only

## Future Improvements

- Support additional platforms (YouTube, TikTok, X)
- Automated email / DM sending with an approval workflow
- Fake-follower and audience-quality detection
- Improved niche classification using NLP / embeddings
- Deployment to Streamlit Cloud or a Docker container

## Author

**Vaibhav Pandey**
B.Tech Computer Science
GitHub: `Vaibhavpandey-web` · LinkedIn: `vaibhav1812`