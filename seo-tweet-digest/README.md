# 📡 SEO & AI Daily Digest

Tự động thu thập và tổng hợp tweets từ các SEO experts hàng đầu và các chủ đề trending về **SEO / AI SEO / GEO / Google Updates** — cập nhật **mỗi ngày lúc 8:00 sáng (ICT)** qua GitHub Actions.

---

## 🚨 BẢO MẬT — ĐỌC NGAY

> **Bearer Token của bạn đã bị lộ trong cuộc trò chuyện này.**
> Hãy **thu hồi ngay lập tức** tại:
> 👉 https://developer.x.com/en/portal/dashboard → Apps → Keys and tokens → Regenerate Bearer Token
>
> Sau đó lưu token mới vào **GitHub Secret** theo hướng dẫn bên dưới.

---

## ✨ Tính năng

| Tính năng | Chi tiết |
|-----------|----------|
| 📥 **Theo dõi Experts** | 22+ SEO experts: @randfish, @rustybrick, @JohnMu, @lilyraynyc,… |
| 🔍 **Topic Search** | SEO Updates · AI SEO & GEO · Google Updates · Technical SEO |
| ⏱ **Cửa sổ 72h** | Lấy tất cả tweets trong vòng 72 giờ gần nhất |
| ⏰ **Tự động hàng ngày** | GitHub Actions chạy lúc 01:00 UTC = **8:00 sáng ICT** |
| 🌐 **Trang HTML tĩnh** | Publish tự động lên GitHub Pages |
| 🔎 **Tìm kiếm & Lọc** | Live search, sort by Newest / Top, tab Experts / Topics |

---

## 🚀 Thiết lập (5 bước)

### Bước 1 — Fork / Clone repo

```bash
git clone https://github.com/<your-username>/seo-tweet-digest.git
cd seo-tweet-digest
```

### Bước 2 — Lưu Bearer Token vào GitHub Secret

1. Mở repo trên GitHub → **Settings → Secrets and variables → Actions**
2. Nhấn **New repository secret**
3. Name: `BEARER_TOKEN`
4. Value: Dán Bearer Token mới (sau khi đã regenerate ở developer portal)
5. Nhấn **Add secret**

> ⚠️ **Không bao giờ** hardcode token trong code hoặc commit vào git.

### Bước 3 — Bật GitHub Pages

1. **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `gh-pages` → `/ (root)`
4. Nhấn **Save**

Sau lần đầu deploy, trang sẽ có địa chỉ:
```
https://<your-username>.github.io/seo-tweet-digest/
```

### Bước 4 — Kích hoạt lần đầu (thủ công)

1. **Actions → Daily SEO & AI Digest → Run workflow**
2. Chờ ~2–3 phút để workflow hoàn tất
3. Mở link GitHub Pages để xem kết quả

### Bước 5 — Chạy tự động

Từ đây workflow sẽ tự chạy mỗi ngày lúc **8:00 sáng ICT**.
Bạn cũng có thể trigger thủ công bất kỳ lúc nào.

---

## 📁 Cấu trúc dự án

```
seo-tweet-digest/
├── .github/
│   └── workflows/
│       └── daily_digest.yml    ← GitHub Actions (cron 8AM ICT)
├── src/
│   ├── fetcher.py              ← X API v2 client
│   └── renderer.py             ← HTML report generator
├── docs/
│   └── index.html              ← Generated report (GitHub Pages)
├── data/
│   └── last_run.json           ← Metadata từ lần chạy cuối
├── main.py                     ← Entry point
├── requirements.txt
└── README.md
```

---

## ⚙️ Thêm / bớt experts

Mở `main.py` và chỉnh list `SEO_EXPERTS`:

```python
SEO_EXPERTS = [
    "randfish", "CyrusShepard", "JohnMu",
    # thêm username mới ở đây...
]
```

## ⚙️ Thay đổi topic search

Chỉnh list `SEARCH_QUERIES` trong `main.py`:

```python
SEARCH_QUERIES = [
    {
        "label": "🔍 SEO Updates",
        "emoji": "🔍",
        "color": "#4f9cf9",
        "query": "SEO -is:retweet lang:en",
    },
    # thêm query mới...
]
```

Query syntax theo chuẩn [X API v2 search operators](https://developer.x.com/en/docs/x-api/tweets/search/integrate/build-a-query).

## ⚙️ Thay đổi giờ chạy

Mở `.github/workflows/daily_digest.yml` và sửa cron:

```yaml
schedule:
  - cron: "0 1 * * *"   # UTC → đổi giờ theo múi giờ của bạn
```

Múi giờ tham khảo:
| Giờ địa phương | Cron (UTC) |
|---------------|-----------|
| 8:00 AM ICT (UTC+7) | `0 1 * * *` |
| 7:00 AM WIB (UTC+7) | `0 0 * * *` |
| 8:00 AM CET (UTC+1) | `0 7 * * *` |
| 8:00 AM EST (UTC-5) | `0 13 * * *` |

---

## 📊 X API — Giới hạn

| Tier | Reads/tháng | Recent Search |
|------|------------|---------------|
| Free | Rất ít | Hạn chế |
| **Basic** ($100/tháng) | 10,000 req | ✅ |
| Pro ($5,000/tháng) | 1M tweets | ✅ |

Mỗi lần chạy tốn khoảng **~26–30 API requests** (dưới giới hạn Basic).

---

## 🛠 Chạy local (để test)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export BEARER_TOKEN="your_new_bearer_token_here"
python main.py
# Mở docs/index.html trong trình duyệt
```

---

## 📄 License

MIT — tự do sử dụng và tùy chỉnh.
