"""
src/fetcher.py — X API v2 client (fixed)
"""

import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.x.com/2"

TWEET_FIELDS  = "created_at,public_metrics,author_id,text,entities"
USER_FIELDS   = "name,username,profile_image_url,public_metrics,verified"
EXPANSIONS    = "author_id"

TIMELINE_MAX_RESULTS = 20
SEARCH_MAX_RESULTS   = 50


class XAPIFetcher:

    def __init__(self, bearer_token: str):
        self._headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type":  "application/json",
        }
        self._user_cache: Dict[str, dict] = {}

    def _get(self, endpoint: str, params: dict, max_retries: int = 3) -> Optional[dict]:
        url = f"{BASE_URL}/{endpoint}"

        for attempt in range(max_retries):
            try:
                resp = requests.get(url, headers=self._headers, params=params, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    # Log nếu API trả errors[] trong body (vẫn 200 nhưng rỗng)
                    if "errors" in data and not data.get("data"):
                        log.warning("⚠️  API returned errors on %s: %s", endpoint, data["errors"])
                    return data

                if resp.status_code == 429:
                    reset_at  = int(resp.headers.get("x-rate-limit-reset", 0))
                    wait_secs = min(max(reset_at - int(time.time()), 15), 900)
                    log.warning("⏳  Rate limited — waiting %ds …", wait_secs)
                    time.sleep(wait_secs)
                    continue

                if resp.status_code in (401, 403):
                    # FIX: log full body để biết lỗi gì (thường là "insufficient credits")
                    log.error(
                        "🔐  Auth/Permission error %d on %s.\n"
                        "    → Check credit balance at https://console.x.com\n"
                        "    → Response: %s",
                        resp.status_code, endpoint, resp.text[:500],
                    )
                    return None

                log.warning("⚠️  HTTP %d on %s (attempt %d/%d): %s",
                            resp.status_code, endpoint, attempt + 1, max_retries, resp.text[:300])

            except requests.exceptions.RequestException as exc:
                log.warning("⚠️  Network error (attempt %d/%d): %s", attempt + 1, max_retries, exc)

            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        log.error("❌  All %d attempts failed for %s", max_retries, endpoint)
        return None

    @staticmethod
    def _start_time_iso(hours_back: int) -> str:
        dt = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _resolve_user_ids(self, usernames: List[str]) -> None:
        missing = [u for u in usernames if u.lower() not in self._user_cache]
        if not missing:
            return

        for i in range(0, len(missing), 100):
            batch = missing[i:i + 100]
            data  = self._get("users/by", {
                "usernames":   ",".join(batch),
                "user.fields": USER_FIELDS,
            })
            if data and "data" in data:
                for user in data["data"]:
                    self._user_cache[user["username"].lower()] = user
                    log.info("  👤  @%s → ID %s", user["username"], user["id"])
            else:
                log.warning("  ⚠️  Could not resolve batch: %s", batch)

    def fetch_user_tweets(self, usernames: List[str], hours_back: int = 24) -> Dict[str, dict]:
        """
        FIX: hours_back default giảm xuống 24 (từ 72) để tiết kiệm credit.
        FIX: bỏ media.fields + expansions phức tạp, chỉ giữ những gì cần thiết.
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

            data = self._get(f"users/{user['id']}/tweets", {
                "start_time":   start_time,
                "max_results":  TIMELINE_MAX_RESULTS,
                "tweet.fields": TWEET_FIELDS,
                "expansions":   EXPANSIONS,
                "user.fields":  USER_FIELDS,
                "exclude":      "retweets",
            })

            tweets = []
            if data and "data" in data:
                for t in data["data"]:
                    t["author"] = user
                tweets = data["data"]
                log.info("       → %d tweet(s)", len(tweets))
            elif data is not None:
                log.warning("       → 0 tweets (empty response). meta: %s", data.get("meta"))

            result[key] = {"user": user, "tweets": tweets}
            time.sleep(0.5)

        return result

    def fetch_topic_tweets(self, queries: List[dict], hours_back: int = 24) -> List[dict]:
        """
        FIX: hours_back default giảm xuống 24.
        FIX: bỏ sort_order='relevancy' — param này không hợp lệ với recent search free tier.
        """
        start_time = self._start_time_iso(hours_back)
        results    = []

        for q in queries:
            log.info("  🔎  %s …", q["label"])

            data = self._get("tweets/search/recent", {
                "query":        q["query"],
                "start_time":   start_time,
                "max_results":  SEARCH_MAX_RESULTS,
                "tweet.fields": TWEET_FIELDS,
                "expansions":   EXPANSIONS,
                "user.fields":  USER_FIELDS,
            })

            tweets = []
            if data and "data" in data:
                users_map = {
                    u["id"]: u
                    for u in data.get("includes", {}).get("users", [])
                }
                for t in data["data"]:
                    if t.get("author_id") in users_map:
                        t["author"] = users_map[t["author_id"]]
                tweets = data["data"]
                log.info("       → %d tweet(s)", len(tweets))
            elif data is not None:
                log.warning("       → 0 tweets. errors: %s", data.get("errors"))

            results.append({**q, "tweets": tweets})
            time.sleep(2)

        return results
