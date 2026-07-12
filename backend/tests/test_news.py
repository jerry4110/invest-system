"""T-25 수용 기준: DART 공시·뉴스 수집(출처 필수), LLM 분류(실패·예산 격리), API."""
import json

import pytest

from backend.infra import db as db_mod


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    from backend.services import settings_service
    settings_service.set_secret("dart_api_key", "TESTKEY")


def test_dart_disclosures_with_links(fresh):
    """FR-04-21: 공시 수집 — 모든 항목에 DART 뷰어 링크(출처)."""
    from backend.adapters.market import dart as dart_mod
    dart_mod._corp_cache = {"005930": "00126380"}
    from backend.adapters.market.dart import DartClient

    def fetch(url):
        assert "list.json" in url
        return json.dumps({"status": "000", "list": [
            {"rcept_no": "20260710000123", "report_nm": "주요사항보고서(자기주식취득)",
             "rcept_dt": "20260710", "flr_nm": "삼성전자"},
        ]}).encode()

    items = DartClient(fetch=fetch).get_disclosures("005930", days=30)
    assert items[0]["title"].startswith("주요사항보고서")
    assert "dart.fss.or.kr" in items[0]["link"] and "20260710000123" in items[0]["link"]
    assert items[0]["date"] == "2026-07-10"


def test_google_news_rss_parse():
    from backend.adapters.market.news import parse_google_rss
    xml = """<?xml version="1.0"?><rss><channel>
      <item><title>삼성전자, HBM4 양산 개시</title>
        <link>https://news.example.com/a1</link>
        <pubDate>Fri, 10 Jul 2026 09:00:00 GMT</pubDate>
        <source url="https://ex.com">전자신문</source></item>
    </channel></rss>"""
    items = parse_google_rss(xml.encode())
    assert items[0]["title"] == "삼성전자, HBM4 양산 개시"
    assert items[0]["link"] == "https://news.example.com/a1"
    assert items[0]["source"] == "전자신문"


class FakeLLM:
    model = "fake"
    def __init__(self, text): self._t = text
    def complete(self, prompt, max_tokens=1024):
        from backend.adapters.llm.base import LLMResult
        return LLMResult(text=self._t, model="fake", input_tokens=10,
                         output_tokens=10, cost_usd=0.001)


def test_llm_classification_merged(fresh):
    from backend.services import news_service
    news = [{"title": "HBM4 양산 개시", "link": "http://a", "source": "s", "date": "2026-07-10"},
            {"title": "리콜 발표", "link": "http://b", "source": "s", "date": "2026-07-09"}]
    llm_json = json.dumps([
        {"index": 0, "sentiment": "호재", "importance": "상", "summary": "차세대 메모리 양산"},
        {"index": 1, "sentiment": "악재", "importance": "중", "summary": "품질 이슈"},
    ], ensure_ascii=False)
    out, notes = news_service.classify_news(news, adapter=FakeLLM(llm_json))
    assert out[0]["sentiment"] == "호재" and out[0]["importance"] == "상"
    assert out[1]["sentiment"] == "악재"
    assert notes == []


def test_llm_invalid_json_isolated(fresh):
    """LLM 응답 파싱 실패 → 미분류로 반환 + 사유 (분석 전체를 막지 않음)."""
    from backend.services import news_service
    news = [{"title": "t", "link": "http://a", "source": "s", "date": "2026-07-10"}]
    out, notes = news_service.classify_news(news, adapter=FakeLLM("죄송하지만 JSON이 아닙니다"))
    assert out[0].get("sentiment") is None
    assert any("분류" in n for n in notes)


def test_budget_exceeded_isolated(fresh):
    from backend.services import llm_service, news_service
    llm_service.set_monthly_limit(0.0)                     # 즉시 차단 상태
    news = [{"title": "t", "link": "http://a", "source": "s", "date": "2026-07-10"}]
    out, notes = news_service.classify_news(news, adapter=FakeLLM("[]"))
    assert out[0].get("sentiment") is None
    assert any("상한" in n for n in notes)


def test_news_api_contract(fresh, monkeypatch):
    """모든 뉴스·공시에 출처 링크 필수 (FR-04-21)."""
    from fastapi.testclient import TestClient
    from backend import main as main_mod
    from backend.services import news_service

    monkeypatch.setattr(news_service, "_load_disclosures",
                        lambda t: [{"title": "공시1", "link": "https://dart.fss.or.kr/x", "date": "2026-07-10"}])
    monkeypatch.setattr(news_service, "_load_news",
                        lambda t, name: [{"title": "뉴스1", "link": "https://n/1", "source": "s", "date": "2026-07-11"}])
    monkeypatch.setattr(news_service, "_load_consensus",
                        lambda t: {"target_price": 350000, "analysts": 21, "recommendation": "buy"})
    monkeypatch.setattr(news_service, "classify_news", lambda items, adapter=None: (items, []))

    body = TestClient(main_mod.create_app()).get("/api/analysis/news/005930").json()
    assert all(i["link"] for i in body["news"] + body["disclosures"])
    assert body["consensus"]["target_price"] == 350000
    assert body["as_of"] and "참고자료" in body["disclaimer"]
