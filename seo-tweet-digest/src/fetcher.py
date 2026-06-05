"""
src/fetcher.py — X API v2 client
Handles user lookups, timeline fetches, and recent-search calls
with automatic rate-limit handling and exponential back-off.
"""

import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.x.com/2"

# Fields requested on every tweet
TWEET_FIELDS = (
    "created_at,public_metrics,author_id,text,"
    "referenced_tweets,entities,attachments"
)
USER_FIELDS = (
    "name,username,profile_image_url,public_metrics,"
    "description,verified,url"
)
MEDIA_FIELDS = "url,preview_image_url,type,width,height"
EXPANSIONS  = "author_id,attachments.media_keys,referenced_tweets.id"

# How many tweets to pull per user timeline call (max 100)
TIMELINE_MAX_RESULTS = 20
# How many tweets per search query (max 100)
SEARCH_MAX_RESULTS   = 50


class XAPIFetcher:
    """Thin wrapper around the X API v2 endpoints used by this project."""

    def __init__(self, bearer_token: str):
        self._headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type":  "application/json",
        }
        self._user_cache: Dict[str, dict] = {}   # username.lower() → user obj

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _get(
        self,
        endpoint: str,
        params: dict,
        max_retries: int = 3,
    ) -> Optional[dict]:
        """Perform a GET request with retry + rate-limit handling."""
        url = f"{BASE_URL}/{endpoint}"

        for attempt in range(max_retries):
            try:
                resp = requests.get(
                    url, headers=self._headers, params=params, timeout=30
                )

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 429:
                    # Respect x-rate-limit-reset header when present
                    reset_at   = int(resp.headers.get("x-rate-limit-reset", 0))
                    wait_secs  = max(reset_at - int(time.time()), 15)
                    wait_secs  = min(wait_secs, 900)          # cap at 15 min
                    log.warning(
                        "⏳  Rate limited on %s — waiting %ds …", endpoint, wait_secs
                    )
                    time.sleep(wait_secs)
                    continue  # retry immediately after sleep

                if resp.status_code in (401, 403):
                    log.error(
                        "🔐  Auth error %d on %s: %s",
                        resp.status_code, endpoint, resp.text[:300],
                    )
                    return None  # no point retrying auth failures

                log.warning(
                    "⚠️   HTTP %d on %s (attempt %d/%d): %s",
                    resp.status_code, endpoint, attempt + 1, max_retries, resp.text[:200],
                )

            except requests.exceptions.RequestException as exc:
                log.warning("⚠️   Network error on %s (attempt %d/%d): %s",
                            endpoint, attempt + 1, max_retries, exc)

            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)   # 1s, 2s back-off

        log.error("❌  All %d attempts failed for %s", max_retries, endpoint)
        return None

    @staticmethod
    def _start_time_iso(hours_back: int) -> str:
        """Return an ISO-8601 UTC timestamp `hours_back` hours ago."""
        dt = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ──────────────────────────────────────────────────────────────────────────
    # User lookup
    # ──────────────────────────────────────────────────────────────────────────

    def _resolve_user_ids(self, usernames: List[str]) -> None:
        """
        Batch-resolve usernames → user objects and cache them.
        X API allows up to 100 usernames per request.
        """
        missing = [u for u in usernames if u.lower() not in self._user_cache]
        if not missing:
            return

        for i in range(0, len(missing), 100):
            batch = missing[i : i + 100]
            data  = self._get(
                "users/by",
                {
                    "usernames":    ",".join(batch),
                    "user.fields":  USER_FIELDS,
                },
            )
            if data and "data" in data:
                for user in data["data"]:
                    key = user["username"].lower()
                    self._user_cache[key] = user
                    log.info("  👤  @%s → ID %s", user["username"], user["id"])
            else:
                log.warning("  ⚠️  Could not resolve batch: %s", batch)

            if len(missing) > 100:
                time.sleep(1)

    # ──────────────────────────────────────────────────────────────────────────
    # Timeline fetch
    # ──────────────────────────────────────────────────────────────────────────

    def fetch_user_tweets(
        self,
        usernames: List[str],
        hours_back: int = 72,
    ) -> Dict[str, dict]:
        """
        Fetch original tweets (no retweets) from each user in `usernames`
        posted within the last `hours_back` hours.

        Returns a dict keyed by lowercase username:
            {
                "randfish": {
                    "user":   { id, name, username, ... },
                    "tweets": [ { id, text, created_at, public_metrics, ... }, ... ]
                },
                ...
            }
        """
        self._resolve_user_ids(usernames)
        start_time = self._start_time_iso(hours_back)
        result: Dict[str, dict] = {}

        for username in usernames:
            key  = username.lower()
            user = self._user_cache.get(key)

            if not user:
                log.warning("  ⚠️  Skipping @%s (not found)", username)
                result[key] = {"user": None, "tweets": []}
                continue

            log.info("  📄  @%s …", user["username"])

            data = self._get(
                f"users/{user['id']}/tweets",
                {
                    "start_time":       start_time,
                    "max_results":      TIMELINE_MAX_RESULTS,
                    "tweet.fields":     TWEET_FIELDS,
                    "user.fields":      USER_FIELDS,
                    "media.fields":     MEDIA_FIELDS,
                    "expansions":       EXPANSIONS,
                    "exclude":          "retweets",  # original posts only
                },
            )

            tweets: List[dict] = []
            if data:
                raw    = data.get("data", [])
                # Attach the author object to each tweet for convenience
                for t in raw:
                    t["author"] = user
                tweets = raw
                log.info("       → %d tweet(s)", len(tweets))

            result[key] = {"user": user, "tweets": tweets}
            time.sleep(0.5)   # polite pacing between user calls

        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Recent search
    # ──────────────────────────────────────────────────────────────────────────

    def fetch_topic_tweets(
        self,
        queries: List[dict],
        hours_back: int = 72,
    ) -> List[dict]:
        """
        Run each search query and return enriched results.

        `queries` is a list of dicts with keys: label, emoji, color, query.
        Returns the same list with an added "tweets" key on each entry.
        """
        start_time = self._start_time_iso(hours_back)
        results    = []

        for q in queries:
            log.info("  🔎  %s …", q["label"])

            data = self._get(
                "tweets/search/recent",
                {
                    "query":        q["query"],
                    "start_time":   start_time,
                    "max_results":  SEARCH_MAX_RESULTS,
                    "tweet.fields": TWEET_FIELDS,
                    "user.fields":  USER_FIELDS,
                    "media.fields": MEDIA_FIELDS,
                    "expansions":   EXPANSIONS,
                    "sort_order":   "relevancy",
                },
            )

            tweets: List[dict] = []
            if data:
                raw          = data.get("data", [])
                users_map    = {
                    u["id"]: u
                    for u in data.get("includes", {}).get("users", [])
                }
                for t in raw:
                    if t.get("author_id") in users_map:
                        t["author"] = users_map[t["author_id"]]
                tweets = raw
                log.info("       → %d tweet(s)", len(tweets))

            results.append({**q, "tweets": tweets})
            time.sleep(3)   # be polite between search calls

        return results
