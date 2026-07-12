"""투자지침 문서 파서 (FR-01-12~13) — MD/TXT/docx/PDF → 텍스트."""
import io
from pathlib import Path


class UnsupportedFormat(Exception):
    pass


def parse_document(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in (".md", ".txt"):
        return content.decode("utf-8-sig", errors="replace")
    if suffix == ".docx":
        import docx
        d = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in d.paragraphs if p.text.strip())
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    raise UnsupportedFormat(f"지원하지 않는 형식: {suffix} (MD/TXT/docx/PDF만 가능)")
