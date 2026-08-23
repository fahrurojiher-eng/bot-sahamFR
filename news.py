import feedparser

NEWS_FEEDS = [
    "https://www.cnbcindonesia.com/market/rss",
    "https://www.investing.com/rss/news_25.rss",
]


def ambil_berita(jumlah=5):
    hasil = []
    for url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:jumlah]:
                hasil.append(entry.title)
        except Exception:
            continue
    return hasil[: jumlah * 2] if hasil else []
