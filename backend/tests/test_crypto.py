"""T-02 수용 기준: 암호화 왕복, 암호문≠평문, 마스터 키 없이 복호화 불가."""
import pytest
from cryptography.fernet import InvalidToken

from backend.infra.crypto import CryptoBox


def test_encrypt_decrypt_roundtrip(tmp_path):
    box = CryptoBox(key_file=tmp_path / "master.key")
    token = box.encrypt("my-secret-api-key-123")
    assert token != "my-secret-api-key-123"
    assert "my-secret-api-key-123" not in token
    assert box.decrypt(token) == "my-secret-api-key-123"


def test_master_key_persists(tmp_path):
    kf = tmp_path / "master.key"
    token = CryptoBox(key_file=kf).encrypt("value-1")
    # 새 인스턴스(재시작 시뮬레이션)에서도 복호화 가능
    assert CryptoBox(key_file=kf).decrypt(token) == "value-1"


def test_wrong_key_fails(tmp_path):
    token = CryptoBox(key_file=tmp_path / "a.key").encrypt("value-2")
    other = CryptoBox(key_file=tmp_path / "b.key")
    with pytest.raises(InvalidToken):
        other.decrypt(token)
