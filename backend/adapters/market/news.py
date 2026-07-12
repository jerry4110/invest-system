"""뉴스 수집 (FR-04-21) — Google News RSS(국내, 무키) + yfinance 뉴스(해외). 출처 링크 필수."""
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime


def parse_google_rss(xml_bytes: bytes) -> list[dict]:
    items = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        pub = it.findtext("pubDate")
        try:
            date = parsedate_to_datetime(pub).date().isoformat() if pub else ""
        except (TypeError, ValueError):
            date = ""
        src = it.find("source")
        items.append({"title": title, "link": link, "date": date,
                      "source": (src.text or "").strip() if src is not None else "Google News"})
    return items


def fetch_google_news(query: str, limit: int = 15) -> list[dict]:
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    with urllib.request.urlopen(url, timeout=20) as res:
        return parse_google_rss(res.read())[:limit]


def fetch_yf_news(ticker: str, limit: int = 15) -> list[dict]:
    import yfinance as yf
    out = []
    for n in (yf.Ticker(ticker).news or [])[:limit]:
        content = n.get("content", n)
        title = content.get("title", "")
        url = (content.get("canonicalUrl") or {}).get("url") or n.get("link", "")
        if not title or not url:
            continue
        out.append({"title": title, "link": url,
                    "date": (content.get("pubDate") or "")[:10],
                    "source": (content.get("provider") or {}).get("displayName", "Yahoo Finance")})
    return out
