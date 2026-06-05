"""
src/renderer.py — Generates a self-contained HTML digest page
from the fetched tweet data.
"""

import json
import re
import html as html_lib
from datetime import datetime, timezone
from typing import Dict, List


def _fmt_number(n) -> str:
    """Format large integers to human-readable K/M."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _ago(iso_str: str) -> str:
    """Return a relative time string like '2h ago'."""
    if not iso_str:
        return ""
    try:
        dt  = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        s   = int((now - dt).total_seconds())
        if s < 60:
            return f"{s}s ago"
        if s < 3600:
            return f"{s//60}m ago"
        if s < 86400:
            return f"{s//3600}h ago"
        return f"{s//86400}d ago"
    except Exception:
        return ""


def _tweet_text_to_html(text: str, entities: dict | None = None) -> str:
    """
    Convert raw tweet text to safe HTML with linked mentions, hashtags, URLs.
    """
    if not text:
        return ""

    text = html_lib.escape(text)

    # Replace t.co URLs with display URLs if entity data is available
    if entities:
        for url_obj in entities.get("urls", []):
            expanded = html_lib.escape(url_obj.get("expanded_url", ""))
            display  = html_lib.escape(url_obj.get("display_url", expanded))
            tco      = html_lib.escape(url_obj.get("url", ""))
            if tco:
                text = text.replace(
                    tco,
                    f'<a href="{expanded}" target="_blank" rel="noopener" class="tweet-link">{display}</a>',
                )

    # @mentions
    text = re.sub(
        r"@(\w+)",
        r'<a href="https://x.com/\1" target="_blank" rel="noopener" class="tweet-mention">@\1</a>',
        text,
    )

    # #hashtags
    text = re.sub(
        r"#(\w+)",
        r'<a href="https://x.com/hashtag/\1" target="_blank" rel="noopener" class="tweet-hashtag">#\1</a>',
        text,
    )

    return text


def _serialize_tweet(tweet: dict) -> dict:
    """Return a JSON-serialisable dict with all fields the template needs."""
    author   = tweet.get("author") or {}
    metrics  = tweet.get("public_metrics") or {}
    entities = tweet.get("entities")
    created  = tweet.get("created_at", "")

    avatar_url = author.get("profile_image_url", "")
    # Use larger avatar: replace _normal with _bigger
    if avatar_url:
        avatar_url = avatar_url.replace("_normal", "_bigger")

    display_name = author.get("name", "Unknown")
    username     = author.get("username", "")
    initials     = "".join(w[0].upper() for w in display_name.split()[:2]) or "?"

    return {
        "id":         tweet.get("id", ""),
        "text_html":  _tweet_text_to_html(tweet.get("text", ""), entities),
        "text_raw":   tweet.get("text", ""),
        "created_at": created,
        "time_ago":   _ago(created),
        "url":        f"https://x.com/{username}/status/{tweet.get('id', '')}",
        "author": {
            "id":          author.get("id", ""),
            "name":        display_name,
            "username":    username,
            "avatar_url":  avatar_url,
            "initials":    initials,
            "verified":    bool(author.get("verified")),
            "followers":   _fmt_number(author.get("public_metrics", {}).get("followers_count")),
            "url":         f"https://x.com/{username}",
        },
        "metrics": {
            "likes":     _fmt_number(metrics.get("like_count", 0)),
            "retweets":  _fmt_number(metrics.get("retweet_count", 0)),
            "replies":   _fmt_number(metrics.get("reply_count", 0)),
            "views":     _fmt_number(metrics.get("impression_count", 0)),
            # Raw values for sorting
            "likes_raw":    int(metrics.get("like_count", 0)),
            "retweets_raw": int(metrics.get("retweet_count", 0)),
            "engagement":   int(metrics.get("like_count", 0))
                          + int(metrics.get("retweet_count", 0)) * 2
                          + int(metrics.get("reply_count", 0)),
        },
    }


class HTMLRenderer:
    """Renders the full digest as a self-contained HTML page."""

    def render(
        self,
        user_data: Dict[str, dict],
        topic_data: List[dict],
        generated_at: datetime,
        hours_back: int,
        experts_config: List[str],
        topics_config: List[dict],
    ) -> str:

        # ── Build serialisable payload ──────────────────────────────────────
        expert_sections = []
        all_tweets_pool = []

        for username, info in user_data.items():
            tweets_raw = info.get("tweets", [])
            user_obj   = info.get("user")
            if not user_obj:
                continue
            serialised = [_serialize_tweet(t) for t in tweets_raw]
            # Sort by engagement descending
            serialised.sort(key=lambda t: t["metrics"]["engagement"], reverse=True)
            expert_sections.append({
                "username": user_obj.get("username", username),
                "name":     user_obj.get("name", username),
                "avatar_url": (user_obj.get("profile_image_url", "")
                               .replace("_normal", "_bigger")),
                "initials": "".join(w[0].upper() for w in user_obj.get("name", username).split()[:2])[:2],
                "followers": _fmt_number(user_obj.get("public_metrics", {}).get("followers_count")),
                "url": f"https://x.com/{user_obj.get('username', username)}",
                "tweets": serialised,
                "tweet_count": len(serialised),
            })
            for t in serialised:
                t["_source"] = "expert"
                t["_category"] = "Expert Picks"
                all_tweets_pool.append(t)

        expert_sections.sort(key=lambda u: u["tweet_count"], reverse=True)

        topic_sections = []
        for topic in topic_data:
            serialised = [_serialize_tweet(t) for t in topic.get("tweets", [])]
            serialised.sort(key=lambda t: t["metrics"]["engagement"], reverse=True)
            label = topic.get("label", "Topic")
            topic_sections.append({
                "label":  label,
                "emoji":  topic.get("emoji", "🔎"),
                "color":  topic.get("color", "#4f9cf9"),
                "query":  topic.get("query", ""),
                "tweets": serialised,
                "tweet_count": len(serialised),
            })
            for t in serialised:
                t["_source"] = "topic"
                t["_category"] = label
                all_tweets_pool.append(t)

        # All-tweets feed: newest first (deduplicate by tweet ID)
        seen_ids = set()
        all_unique = []
        for t in sorted(all_tweets_pool, key=lambda x: x["created_at"], reverse=True):
            if t["id"] not in seen_ids:
                seen_ids.add(t["id"])
                all_unique.append(t)

        # Stats
        total_tweets     = len(all_unique)
        active_experts   = len([e for e in expert_sections if e["tweet_count"] > 0])
        total_topic_tw   = sum(s["tweet_count"] for s in topic_sections)
        generated_str    = generated_at.strftime("%b %d, %Y — %H:%M UTC")

        payload = {
            "meta": {
                "generated_at": generated_str,
                "hours_back":   hours_back,
                "total_tweets": total_tweets,
                "active_experts": active_experts,
                "topics_count": len(topic_sections),
            },
            "all_tweets":       all_unique[:300],   # cap at 300 for performance
            "expert_sections":  expert_sections,
            "topic_sections":   topic_sections,
        }

        payload_json = json.dumps(payload, ensure_ascii=False)

        # ── Render HTML ─────────────────────────────────────────────────────
        return HTML_TEMPLATE.replace("__PAYLOAD__", payload_json) \
                            .replace("__GENERATED_AT__", generated_str) \
                            .replace("__HOURS_BACK__", str(hours_back)) \
                            .replace("__TOTAL_TWEETS__", str(total_tweets)) \
                            .replace("__ACTIVE_EXPERTS__", str(active_experts)) \
                            .replace("__TOPICS_COUNT__", str(len(topic_sections)))


# ────────────────────────────────────────────────────────────────────────────
# Self-contained HTML template (CSS + JS inline)
# ────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="description" content="Daily SEO & AI digest from top experts on X"/>
<title>SEO & AI Digest · Daily Report</title>
<style>
:root {
  --bg:        #0d1117;
  --surface:   #161b22;
  --surface2:  #1e2530;
  --border:    #30363d;
  --border2:   #21262d;
  --primary:   #4f9cf9;
  --purple:    #a855f7;
  --green:     #10b981;
  --yellow:    #f59e0b;
  --red:       #ef4444;
  --text:      #e6edf3;
  --text2:     #8b949e;
  --text3:     #656d76;
  --radius:    12px;
  --radius-sm: 8px;
  --shadow:    0 4px 24px rgba(0,0,0,.4);
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Oxygen,Ubuntu,sans-serif;
  background:var(--bg);color:var(--text);line-height:1.5;font-size:15px;min-height:100vh}
a{color:var(--primary);text-decoration:none}
a:hover{text-decoration:underline}

/* ── Layout ── */
.app{display:flex;flex-direction:column;min-height:100vh}

/* ── Header ── */
.header{
  position:sticky;top:0;z-index:100;
  background:rgba(13,17,23,.92);backdrop-filter:blur(12px);
  border-bottom:1px solid var(--border2);
  padding:0 20px;
  display:flex;align-items:center;gap:12px;height:56px;
}
.header-logo{font-size:22px;margin-right:4px}
.header-title{font-size:17px;font-weight:700;white-space:nowrap;
  background:linear-gradient(90deg,var(--primary),var(--purple));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header-meta{margin-left:auto;font-size:12px;color:var(--text2);text-align:right}
.header-dot{display:inline-block;width:7px;height:7px;border-radius:50%;
  background:var(--green);animation:pulse 2s infinite;margin-right:4px}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* ── Stats bar ── */
.stats-bar{
  display:flex;gap:12px;padding:16px 20px;
  overflow-x:auto;border-bottom:1px solid var(--border2);
  background:var(--surface);
}
.stat-card{
  flex:0 0 auto;background:var(--surface2);border:1px solid var(--border);
  border-radius:var(--radius-sm);padding:12px 20px;min-width:120px;text-align:center;
  transition:border-color .2s;
}
.stat-card:hover{border-color:var(--primary)}
.stat-num{font-size:26px;font-weight:800;color:var(--text)}
.stat-label{font-size:11px;color:var(--text2);margin-top:2px;text-transform:uppercase;letter-spacing:.06em}

/* ── Toolbar ── */
.toolbar{
  display:flex;align-items:center;gap:10px;
  padding:12px 20px;border-bottom:1px solid var(--border2);
  flex-wrap:wrap;
}
.search-wrap{position:relative;flex:1;min-width:180px;max-width:340px}
.search-wrap svg{position:absolute;left:10px;top:50%;transform:translateY(-50%);
  width:14px;height:14px;fill:var(--text3);pointer-events:none}
#searchInput{
  width:100%;background:var(--surface2);border:1px solid var(--border);
  border-radius:20px;padding:7px 12px 7px 32px;color:var(--text);
  font-size:13px;outline:none;transition:border-color .2s;
}
#searchInput:focus{border-color:var(--primary)}
#searchInput::placeholder{color:var(--text3)}
.sort-btn{
  background:var(--surface2);border:1px solid var(--border);
  border-radius:20px;padding:7px 14px;font-size:12px;color:var(--text2);
  cursor:pointer;transition:all .2s;white-space:nowrap;
}
.sort-btn:hover,.sort-btn.active{background:var(--primary);color:#fff;border-color:var(--primary)}

/* ── Tabs ── */
.tabs{display:flex;gap:4px;padding:0 20px;
  border-bottom:1px solid var(--border2);background:var(--surface)}
.tab{
  padding:12px 16px;font-size:13px;font-weight:500;cursor:pointer;
  border-bottom:2px solid transparent;color:var(--text2);
  transition:all .2s;white-space:nowrap;
}
.tab:hover{color:var(--text)}
.tab.active{color:var(--primary);border-bottom-color:var(--primary)}

/* ── Main content ── */
.main{flex:1;padding:20px;max-width:1200px;margin:0 auto;width:100%}

/* ── Panel ── */
.panel{display:none}
.panel.active{display:block}

/* ── Tweet grid ── */
.tweet-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
  gap:14px;
}

/* ── Tweet card ── */
.tweet-card{
  background:var(--surface);border:1px solid var(--border2);
  border-radius:var(--radius);padding:16px;
  transition:border-color .2s,transform .15s;
  display:flex;flex-direction:column;gap:10px;
  cursor:pointer;
}
.tweet-card:hover{border-color:var(--primary);transform:translateY(-2px);box-shadow:var(--shadow)}
.tweet-header{display:flex;align-items:center;gap:10px}
.avatar{
  width:40px;height:40px;border-radius:50%;object-fit:cover;flex-shrink:0;
  background:var(--surface2);border:2px solid var(--border);
}
.avatar-placeholder{
  width:40px;height:40px;border-radius:50%;flex-shrink:0;
  background:linear-gradient(135deg,var(--primary),var(--purple));
  display:flex;align-items:center;justify-content:center;
  font-size:14px;font-weight:700;color:#fff;letter-spacing:.02em;
}
.tweet-author{flex:1;min-width:0}
.author-name{font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.author-handle{font-size:12px;color:var(--text2)}
.tweet-time{font-size:11px;color:var(--text3);white-space:nowrap}
.tweet-body{font-size:13.5px;line-height:1.6;color:var(--text);
  overflow-wrap:break-word;word-break:break-word}
.tweet-link{color:var(--primary)}
.tweet-mention{color:var(--primary)}
.tweet-hashtag{color:var(--purple)}
.tweet-footer{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.metric{display:flex;align-items:center;gap:4px;font-size:12px;color:var(--text2)}
.metric svg{width:13px;height:13px;opacity:.7}
.category-badge{
  margin-left:auto;font-size:10px;font-weight:600;
  padding:2px 8px;border-radius:10px;background:var(--surface2);
  color:var(--text2);border:1px solid var(--border);
  white-space:nowrap;
}

/* ── Expert list ── */
.expert-section{margin-bottom:28px}
.expert-header{
  display:flex;align-items:center;gap:12px;
  padding:14px 16px;background:var(--surface);
  border:1px solid var(--border2);border-radius:var(--radius);
  margin-bottom:12px;cursor:pointer;transition:border-color .2s;
}
.expert-header:hover{border-color:var(--primary)}
.expert-avatar{width:44px;height:44px;border-radius:50%;object-fit:cover;
  background:var(--surface2);border:2px solid var(--border);flex-shrink:0}
.expert-avatar-ph{width:44px;height:44px;border-radius:50%;flex-shrink:0;
  background:linear-gradient(135deg,var(--primary),var(--purple));
  display:flex;align-items:center;justify-content:center;
  font-size:16px;font-weight:700;color:#fff}
.expert-info{flex:1;min-width:0}
.expert-name{font-weight:700;font-size:15px}
.expert-sub{font-size:12px;color:var(--text2)}
.expert-count{font-size:12px;color:var(--text2);text-align:right;flex-shrink:0}
.expert-tweets{display:none}
.expert-tweets.open{display:block}

/* ── Topic header ── */
.topic-header{
  display:flex;align-items:center;gap:10px;
  padding:14px 16px;background:var(--surface);
  border-radius:var(--radius) var(--radius) 0 0;
  border:1px solid var(--border2);
  margin-bottom:0;
}
.topic-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.topic-label{font-weight:700;font-size:15px}
.topic-count{font-size:12px;color:var(--text2);margin-left:auto}
.topic-section{
  border:1px solid var(--border2);border-radius:var(--radius);
  margin-bottom:24px;overflow:hidden;
}
.topic-body{padding:16px;display:flex;flex-direction:column;gap:12px}

/* ── Empty state ── */
.empty{
  text-align:center;padding:60px 20px;color:var(--text2);
  background:var(--surface);border:1px solid var(--border2);
  border-radius:var(--radius);
}
.empty .e-icon{font-size:40px;margin-bottom:12px}

/* ── Footer ── */
.footer{
  text-align:center;padding:20px;font-size:12px;color:var(--text3);
  border-top:1px solid var(--border2);margin-top:20px;
}

/* ── Responsive ── */
@media(max-width:640px){
  .header-meta{display:none}
  .tweet-grid{grid-template-columns:1fr}
  .stats-bar{gap:8px;padding:12px}
  .stat-num{font-size:20px}
}
</style>
</head>
<body>
<div class="app">

<!-- ── Header ── -->
<header class="header">
  <span class="header-logo">📡</span>
  <span class="header-title">SEO &amp; AI Daily Digest</span>
  <div class="header-meta">
    <span class="header-dot"></span>
    Updated: __GENERATED_AT__
  </div>
</header>

<!-- ── Stats ── -->
<div class="stats-bar">
  <div class="stat-card">
    <div class="stat-num" id="st-tweets">__TOTAL_TWEETS__</div>
    <div class="stat-label">Tweets</div>
  </div>
  <div class="stat-card">
    <div class="stat-num" id="st-experts">__ACTIVE_EXPERTS__</div>
    <div class="stat-label">Experts</div>
  </div>
  <div class="stat-card">
    <div class="stat-num">__HOURS_BACK__h</div>
    <div class="stat-label">Window</div>
  </div>
  <div class="stat-card">
    <div class="stat-num">__TOPICS_COUNT__</div>
    <div class="stat-label">Topics</div>
  </div>
</div>

<!-- ── Toolbar ── -->
<div class="toolbar">
  <div class="search-wrap">
    <svg viewBox="0 0 20 20"><path d="M12.9 14.32a8 8 0 1 1 1.41-1.41l3.9 3.88-1.42 1.42-3.89-3.89zM8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12z"/></svg>
    <input id="searchInput" type="text" placeholder="Search tweets, users, hashtags…"/>
  </div>
  <button class="sort-btn active" data-sort="newest" onclick="setSort(this)">⏰ Newest</button>
  <button class="sort-btn" data-sort="top"    onclick="setSort(this)">🔥 Top</button>
</div>

<!-- ── Tabs ── -->
<nav class="tabs">
  <div class="tab active" onclick="showTab('all')">🏠 All Feed</div>
  <div class="tab"        onclick="showTab('experts')">👥 Experts</div>
  <div class="tab"        onclick="showTab('topics')">🔍 Topics</div>
</nav>

<!-- ── Main ── -->
<main class="main">

  <!-- All feed -->
  <section class="panel active" id="panel-all">
    <div class="tweet-grid" id="all-grid"></div>
    <div id="all-empty" class="empty" style="display:none">
      <div class="e-icon">🔍</div>
      <div>No tweets match your search.</div>
    </div>
  </section>

  <!-- Experts -->
  <section class="panel" id="panel-experts">
    <div id="experts-container"></div>
  </section>

  <!-- Topics -->
  <section class="panel" id="panel-topics">
    <div id="topics-container"></div>
  </section>

</main>

<footer class="footer">
  Generated automatically by GitHub Actions · X API v2 · Last run: __GENERATED_AT__
</footer>
</div>

<!-- ── Embedded data ── -->
<script>
const DATA = __PAYLOAD__;
</script>

<!-- ── App logic ── -->
<script>
/* ─── State ─────────────────────────────────────────────────── */
let currentSort   = 'newest';
let currentSearch = '';

/* ─── Utilities ─────────────────────────────────────────────── */
function avatarEl(author) {
  if (author.avatar_url) {
    return `<img class="avatar" src="${author.avatar_url}" alt="${author.name}"
               onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
            <div class="avatar-placeholder" style="display:none">${author.initials}</div>`;
  }
  return `<div class="avatar-placeholder">${author.initials}</div>`;
}

function tweetCard(t) {
  const category = t._category || '';
  return `
  <article class="tweet-card" onclick="window.open('${t.url}','_blank')">
    <div class="tweet-header">
      <a href="${t.author.url}" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="display:flex;align-items:center">
        ${avatarEl(t.author)}
      </a>
      <div class="tweet-author">
        <div class="author-name">${escHtml(t.author.name)}</div>
        <div class="author-handle">@${t.author.username}</div>
      </div>
      <span class="tweet-time" title="${t.created_at}">${t.time_ago}</span>
    </div>
    <div class="tweet-body">${t.text_html}</div>
    <div class="tweet-footer">
      <span class="metric">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M1.751 10c0-4.42 3.584-8 8.005-8h4.366c4.49 0 7.501 4.435 5.37 8.392L15.648 20H5.748L1.751 10z"/></svg>
        ${t.metrics.replies}
      </span>
      <span class="metric">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M4.75 3.79l4.603 4.3-1.706 1.82L6 8.38v7.37c0 .97.784 1.75 1.75 1.75H13V19.5H7.75C5.683 19.5 4 17.817 4 15.75V8.38L2.353 9.91.647 8.09l4.103-4.3zm11.5 2.71H11V4h5.25c2.067 0 3.75 1.683 3.75 3.75v7.37l1.647-1.53 1.706 1.82-4.603 4.3-4.103-4.3 1.706-1.82L18 14.62V7.25c0-.97-.784-1.75-1.75-1.75z"/></svg>
        ${t.metrics.retweets}
      </span>
      <span class="metric">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M16.697 5.5c-1.222-.06-2.679.51-3.89 2.16l-.805 1.09-.806-1.09C9.984 6.01 8.526 5.44 7.304 5.5c-1.243.07-2.349.78-2.91 1.91-.552 1.12-.633 2.78.479 4.82 1.074 1.97 3.257 4.27 7.129 6.61 3.87-2.34 6.052-4.64 7.126-6.61 1.111-2.04 1.03-3.7.477-4.82-.561-1.13-1.666-1.84-2.908-1.91zm4.187 7.69c-1.351 2.48-4.001 5.12-8.379 7.67l-.503.3-.504-.3c-4.379-2.55-7.029-5.19-8.382-7.67-1.36-2.5-1.41-4.86-.514-6.67.887-1.79 2.647-2.91 4.601-3.01 1.651-.09 3.368.56 4.798 2.01 1.429-1.45 3.146-2.1 4.796-2.01 1.954.1 3.714 1.22 4.601 3.01.896 1.81.846 4.17-.514 6.67z"/></svg>
        ${t.metrics.likes}
      </span>
      ${t.metrics.views && t.metrics.views !== '0' ? `
      <span class="metric">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
        ${t.metrics.views}
      </span>` : ''}
      ${category ? `<span class="category-badge">${category}</span>` : ''}
    </div>
  </article>`;
}

function escHtml(s) {
  return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* ─── Sort & filter ──────────────────────────────────────────── */
function setSort(btn) {
  document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentSort = btn.dataset.sort;
  renderAll();
}

function sortTweets(arr) {
  if (currentSort === 'top') {
    return [...arr].sort((a,b) => b.metrics.engagement - a.metrics.engagement);
  }
  return [...arr].sort((a,b) => (b.created_at > a.created_at ? 1 : -1));
}

function matchesSearch(t) {
  if (!currentSearch) return true;
  const q = currentSearch.toLowerCase();
  return (
    (t.text_raw || '').toLowerCase().includes(q) ||
    (t.author.username || '').toLowerCase().includes(q) ||
    (t.author.name || '').toLowerCase().includes(q) ||
    (t._category || '').toLowerCase().includes(q)
  );
}

/* ─── Render: All ────────────────────────────────────────────── */
function renderAll() {
  const filtered = sortTweets(DATA.all_tweets.filter(matchesSearch));
  const grid     = document.getElementById('all-grid');
  const empty    = document.getElementById('all-empty');
  if (!filtered.length) {
    grid.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';
  grid.innerHTML = filtered.map(tweetCard).join('');
}

/* ─── Render: Experts ────────────────────────────────────────── */
function renderExperts() {
  const container = document.getElementById('experts-container');
  let html = '';
  for (const exp of DATA.expert_sections) {
    if (!exp.tweets.length) continue;
    const filtered = exp.tweets.filter(matchesSearch);
    if (!filtered.length && currentSearch) continue;
    const avEl = exp.avatar_url
      ? `<img class="expert-avatar" src="${exp.avatar_url}" alt="${exp.name}"
             onerror="this.style.display='none';this.nextSibling.style.display='flex'">
         <div class="expert-avatar-ph" style="display:none">${exp.initials}</div>`
      : `<div class="expert-avatar-ph">${exp.initials}</div>`;

    html += `
    <div class="expert-section">
      <div class="expert-header" onclick="toggleExpert(this)">
        <a href="${exp.url}" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="display:flex;align-items:center">
          ${avEl}
        </a>
        <div class="expert-info">
          <div class="expert-name">${escHtml(exp.name)}</div>
          <div class="expert-sub">@${exp.username} · ${exp.followers} followers</div>
        </div>
        <div class="expert-count">${exp.tweet_count} tweet${exp.tweet_count===1?'':'s'} ▾</div>
      </div>
      <div class="expert-tweets tweet-grid">
        ${filtered.map(tweetCard).join('')}
      </div>
    </div>`;
  }
  if (!html) {
    html = `<div class="empty"><div class="e-icon">👥</div><div>No expert tweets found.</div></div>`;
  }
  container.innerHTML = html;
}

function toggleExpert(header) {
  const tweets = header.nextElementSibling;
  tweets.classList.toggle('open');
  const btn = header.querySelector('.expert-count');
  btn.textContent = btn.textContent.replace(/[▾▴]/, tweets.classList.contains('open') ? '▴' : '▾');
}

/* ─── Render: Topics ─────────────────────────────────────────── */
function renderTopics() {
  const container = document.getElementById('topics-container');
  let html = '';
  for (const topic of DATA.topic_sections) {
    const filtered = sortTweets(topic.tweets.filter(matchesSearch));
    if (!filtered.length && currentSearch) continue;
    html += `
    <div class="topic-section">
      <div class="topic-header">
        <span class="topic-dot" style="background:${topic.color}"></span>
        <span class="topic-label">${topic.label}</span>
        <span class="topic-count">${filtered.length} tweet${filtered.length===1?'':'s'}</span>
      </div>
      <div class="topic-body tweet-grid">
        ${filtered.length
          ? filtered.map(tweetCard).join('')
          : '<div class="empty" style="width:100%"><div class="e-icon">🔍</div><div>No tweets found.</div></div>'}
      </div>
    </div>`;
  }
  if (!html) {
    html = `<div class="empty"><div class="e-icon">🔍</div><div>No topic tweets found.</div></div>`;
  }
  container.innerHTML = html;
}

/* ─── Tabs ───────────────────────────────────────────────────── */
const TABS = {
  all:     () => renderAll(),
  experts: () => renderExperts(),
  topics:  () => renderTopics(),
};

function showTab(name) {
  document.querySelectorAll('.tab').forEach((t,i) => {
    t.classList.toggle('active', ['all','experts','topics'][i] === name);
  });
  document.querySelectorAll('.panel').forEach((p,i) => {
    p.classList.toggle('active', ['panel-all','panel-experts','panel-topics'][i] === `panel-${name}`);
  });
  TABS[name]();
}

/* ─── Search ─────────────────────────────────────────────────── */
let searchTimer;
document.getElementById('searchInput').addEventListener('input', function() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    currentSearch = this.value.trim();
    // Re-render whichever panel is active
    const active = document.querySelector('.panel.active');
    if (active.id === 'panel-all')     renderAll();
    if (active.id === 'panel-experts') renderExperts();
    if (active.id === 'panel-topics')  renderTopics();
  }, 200);
});

/* ─── Boot ───────────────────────────────────────────────────── */
renderAll();
</script>
</body>
</html>"""
