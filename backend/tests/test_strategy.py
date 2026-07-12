"""T-09 수용 기준: 페르소나·지침 버전·파일 파싱·목표배분·LLM 컨텍스트."""
import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return TestClient(main_mod.create_app())


def test_default_strategy_has_persona_templates(client):
    """FR-01-01·03: 기본 페르소나 + 사전 제공 템플릿."""
    body = client.get("/api/strategy").json()
    assert body["persona"] in ("value", "growth", "trader")
    assert len(body["guideline_text"]) > 50        # 기본 행동양식 템플릿
    assert body["version"] == 1


def test_persona_switch_loads_template(client):
    """FR-01-02: 페르소나 전환 시 해당 템플릿 제공, 선택 유지."""
    r = client.put("/api/strategy/persona", json={"persona": "trader"})
    assert r.status_code == 200
    body = client.get("/api/strategy").json()
    assert body["persona"] == "trader"
    assert "트레이더" in body["guideline_text"] or "단기" in body["guideline_text"]
    assert client.put("/api/strategy/persona", json={"persona": "invalid"}).status_code == 422


def test_guideline_update_increments_version(client):
    """FR-01-11·14: 지침 수정 시 버전 증가."""
    client.put("/api/strategy/guideline", json={"text": "나만의 규칙 1"})
    body = client.get("/api/strategy").json()
    assert body["guideline_text"] == "나만의 규칙 1"
    assert body["version"] == 2
    client.put("/api/strategy/guideline", json={"text": "나만의 규칙 2"})
    assert client.get("/api/strategy").json()["version"] == 3


def test_file_upload_md_and_docx(client, tmp_path):
    """FR-01-12~13: MD·docx 업로드 → 텍스트 파싱·보관."""
    r = client.post("/api/strategy/files",
                    files={"file": ("지침.md", "# 원칙\n손절 -7%".encode(), "text/markdown")})
    assert r.status_code == 200 and "손절 -7%" in r.json()["parsed_preview"]

    import docx
    p = tmp_path / "지침.docx"
    d = docx.Document(); d.add_paragraph("분할 매수 3회 원칙"); d.save(p)
    r = client.post("/api/strategy/files",
                    files={"file": ("지침.docx", p.read_bytes(),
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert r.status_code == 200 and "분할 매수" in r.json()["parsed_preview"]

    files = client.get("/api/strategy").json()["files"]
    assert len(files) == 2 and files[0]["filename"]


def test_unsupported_file_rejected(client):
    r = client.post("/api/strategy/files",
                    files={"file": ("virus.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 422


def test_allocation_roundtrip_and_validation(client):
    """FR-01-15: 목표 자산배분."""
    r = client.put("/api/strategy/allocation",
                   json={"stock_pct": 70, "cash_pct": 30, "domestic_pct": 60, "overseas_pct": 40})
    assert r.status_code == 200
    body = client.get("/api/strategy").json()
    assert body["allocation"]["stock_pct"] == 70
    assert client.put("/api/strategy/allocation", json={"stock_pct": 150}).status_code == 422


def test_llm_context_for_phase2(client):
    """FR-01-13: 페르소나+지침+업로드 문서가 LLM 컨텍스트로 합성 (Phase 2 입력 계약)."""
    from backend.services import strategy_service
    client.put("/api/strategy/guideline", json={"text": "PER 15 이하만 매수"})
    client.post("/api/strategy/files",
                files={"file": ("m.md", "장기 보유 원칙".encode(), "text/markdown")})
    ctx = strategy_service.get_llm_context()
    assert "PER 15 이하만 매수" in ctx and "장기 보유 원칙" in ctx
    assert "계좌" not in ctx  # NFR-01: 계좌 식별정보 미포함
