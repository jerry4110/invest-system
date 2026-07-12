"""민감정보 암호화 (constitution §2.5, NFR-01).

2중 구조:
- 값 암호화: Fernet 대칭키 암호화 → 암호문만 DB(secret_store)에 저장
- 마스터 키 보관: 1순위 OS 키스토어(keyring, Windows 자격 증명 관리자),
  실패 시 로컬 키 파일 폴백(권한 제한). 키 파일 경로는 INVEST_MASTER_KEY_FILE로 재정의 가능(테스트용)
"""
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_SERVICE = "invest-system"
_USER = "master-key"
_DEFAULT_KEY_FILE = "data/.master.key"


def _load_from_keyring() -> str | None:
    try:
        import keyring
        key = keyring.get_password(_SERVICE, _USER)
        if key is None:
            key = Fernet.generate_key().decode()
            keyring.set_password(_SERVICE, _USER, key)
        return key
    except Exception:  # 키스토어 미지원 환경 (헤드리스 등)
        return None


class CryptoBox:
    """Fernet 암복호화. 마스터 키는 keyring → 키 파일 순으로 확보."""

    def __init__(self, key_file: str | Path | None = None):
        key: str | None = None
        if key_file is None:
            key_file = os.environ.get("INVEST_MASTER_KEY_FILE")
            if key_file is None:
                key = _load_from_keyring()
                key_file = _DEFAULT_KEY_FILE
        if key is None:
            key = self._load_from_file(Path(key_file))
        self._fernet = Fernet(key.encode())

    @staticmethod
    def _load_from_file(path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key().decode()
        path.write_text(key, encoding="utf-8")
        try:
            os.chmod(path, 0o600)  # 소유자만 읽기 (Windows에서는 무시됨)
        except OSError:
            pass
        logger.warning("마스터 키를 파일(%s)에 저장 — OS 키스토어 사용을 권장", path)
        return key

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()
