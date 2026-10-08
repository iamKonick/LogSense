"""Bounded PDF reference extraction; document text is evidence, never instructions."""

from hashlib import sha256
from io import BytesIO
from pathlib import PurePath

from app.preprocessing.parser import redact
from pypdf import PdfReader


def extract_reference(data: bytes, filename: str, title: str, kind: str):
    if len(data) > 10_000_000:
        raise ValueError("PDF must be at most 10 MB")
    if not data.startswith(b"%PDF-"):
        raise ValueError("Upload a valid PDF file")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Remove the PDF password before uploading")
        if len(reader.pages) > 100:
            raise ValueError("PDF must contain at most 100 pages")
        pages = []
        total = 0
        for number, page in enumerate(reader.pages, 1):
            if len(page.get_contents().get_data() if page.get_contents() else b"") > 5_000_000:
                raise ValueError("A PDF page is too complex; export a simpler text PDF")
            text = redact((page.extract_text() or "").strip())
            total += len(text)
            if total > 500_000:
                raise ValueError("PDF extracted text exceeds 500,000 characters")
            if text:
                pages.append((number, text))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unable to read this PDF; export a text-based PDF and retry") from exc
    if not pages:
        raise ValueError("No readable text found. Scanned PDFs need OCR before upload")
    document_id = sha256(data).hexdigest()
    filename = redact(PurePath(filename.replace("\\", "/")).name[:200])
    title = redact(title.strip() or filename)
    chunks = []
    for page, text in pages:
        for part, start in enumerate(range(0, len(text), 1300), 1):
            chunks.append(
                {
                    "id": f"pdf:{document_id}:{page}:{part}",
                    "title": f"{title[:160]} · page {page} · part {part}",
                    "content": text[start : start + 1500],
                    "source": f"{filename} · page {page}",
                    "kind": kind,
                }
            )
    return {
        "document_id": document_id,
        "pages": len(pages),
        "chunks": chunks,
        "empty_pages": len(reader.pages) - len(pages),
    }
