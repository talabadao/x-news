#!/usr/bin/env python3
"""
SEO Tweet Digest — Daily automated report from SEO experts on X (Twitter)
Runs via GitHub Actions at 8 AM ICT (01:00 UTC) every day.
"""

import os, sys, json, logging
from datetime import datetime, timezone
from src.fetcher import XAPIFetcher
from src.renderer import HTMLRenderer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

HOURS_BACK = 72  # Look-back window (hours)

SEO_EXPERTS = [
    "randfish", "CyrusShepard", "markwebster1", "glenngabe", "rustybrick",
    "Ldnbox", "GaelBreton", "Charles_SEO", "sundarpichai", "aleyda",
    "googlesearchc", "dejanseo", "GregBernhardt4", "JohnMu", "danielwaisberg",
    "lilyraynyc", "chris_nectiv", "thinking_slow", "timsoulo", "VeryWellVersed",
    "JespernissenSEO", "gregelfrink",
]

SEARCH_QUERIES = [
    {
        "label": "🔍 SEO Updates",
        "emoji": "🔍",
        "color": "#4f9cf9",
        "query": "(SEO OR \"search engine optimization\" OR \"rank tracking\" OR \"link building\") -is:retweet lang:en",
    },
    {
        "label": "🤖 AI SEO & GEO",
        "emoji": "🤖",
        "color": "#a855f7",
        "query": "(\"AI SEO\" OR \"AI search\" OR \"GEO\" OR \"generative engine optimization\" OR \"AI Overviews\" OR \"SearchGPT\" OR \"AIO\") -is:retweet lang:en",
    },
    {
        "label": "🔄 Google Updates",
        "emoji": "🔄",
        "color": "#10b981",
        "query": "(\"Google algorithm\" OR \"Google core update\" OR \"Google Search update\" OR \"helpful content\" OR \"spam update\") -is:retweet lang:en",
    },
    {
        "label": "📊 Technical SEO",
        "emoji": "📊",
        "color": "#f59e0b",
        "query": "(\"Core Web Vitals\" OR \"technical SEO\" OR \"crawlability\" OR \"page speed\" OR \"schema markup\" OR \"structured data\") -is:retweet lang:en",
    },
]

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    bearer_token = os.environ.get("BEARER_TOKEN", "").strip()
    if not bearer_token:
        log.error("❌  BEARER_TOKEN environment variable is not set!")
        sys.exit(1)

    log.info("=" * 60)
    log.info("🚀  SEO Tweet Digest — starting run")
    log.info(f"⏱   Looking back {HOURS_BACK} hours")
    log.info(f"👥  Tracking {len(SEO_EXPERTS)} experts, {len(SEARCH_QUERIES)} topic searches")
    log.info("=" * 60)

    fetcher = XAPIFetcher(bearer_token)

    # ── 1. Fetch expert timelines ──────────────────────────────────────────────
    log.info("📥  Fetching expert timelines…")
    user_data = fetcher.fetch_user_tweets(SEO_EXPERTS, hours_back=HOURS_BACK)

    # ── 2. Fetch topic searches ────────────────────────────────────────────────
    log.info("🔎  Running topic searches…")
    topic_data = fetcher.fetch_topic_tweets(SEARCH_QUERIES, hours_back=HOURS_BACK)

    # ── 3. Render HTML ─────────────────────────────────────────────────────────
    log.info("🎨  Rendering HTML report…")
    renderer = HTMLRenderer()
    html_content = renderer.render(
        user_data=user_data,
        topic_data=topic_data,
        generated_at=datetime.now(timezone.utc),
        hours_back=HOURS_BACK,
        experts_config=SEO_EXPERTS,
        topics_config=SEARCH_QUERIES,
    )

    # ── 4. Write output files ──────────────────────────────────────────────────
    os.makedirs("docs", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    report_path = "docs/index.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    log.info(f"✅  Report saved → {report_path}")

    # Save lightweight metadata for debugging / history
    total_expert_tweets = sum(len(v.get("tweets", [])) for v in user_data.values())
    total_topic_tweets  = sum(len(t.get("tweets", [])) for t in topic_data)
    meta = {
        "generated_at":        datetime.now(timezone.utc).isoformat(),
        "hours_back":          HOURS_BACK,
        "expert_tweets_total": total_expert_tweets,
        "topic_tweets_total":  total_topic_tweets,
        "experts_fetched":     [u for u, d in user_data.items() if d.get("tweets")],
        "topics":              [t["label"] for t in topic_data],
    }
    with open("data/last_run.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    log.info(f"📊  Summary: {total_expert_tweets} expert tweets | {total_topic_tweets} topic tweets")
    log.info("🎉  Done!")


if __name__ == "__main__":
    main()
