from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from app.knowledge.pdf import extract_reference
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def reference_pdf(
    text="Quartz database timeout: check pool saturation and release idle connections.",
):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 40 750 Td ({escaped}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_extracts_readable_pdf_with_page_citations_and_stable_ids():
    data = reference_pdf()
    result = extract_reference(data, "resolution.pdf", "Quartz fix", "runbook")
    assert result["pages"] == 1
    assert result["chunks"][0]["source"] == "resolution.pdf · page 1"
    assert "release idle connections" in result["chunks"][0]["content"]
    assert (
        extract_reference(data, "renamed.pdf", "Other title", "runbook")["chunks"][0]["id"]
        == result["chunks"][0]["id"]
    )


def test_rejects_invalid_scanned_encrypted_and_oversize_pdfs():
    with pytest.raises(ValueError, match="valid PDF"):
        extract_reference(b"not a PDF", "bad.pdf", "bad", "runbook")
    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    output = BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match="OCR"):
        extract_reference(output.getvalue(), "scan.pdf", "scan", "runbook")
    writer.encrypt("password")
    output = BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match="password"):
        extract_reference(output.getvalue(), "locked.pdf", "locked", "runbook")
    with pytest.raises(ValueError, match="10 MB"):
        extract_reference(b"%PDF-" + b"x" * 10_000_000, "large.pdf", "large", "runbook")


def test_pdf_upload_validates_before_persistence():
    from app.api.main import app
    from fastapi.testclient import TestClient

    repo = Mock()
    repo.add_pdf_reference.return_value = {"inserted": 1}
    with patch.object(app.state, "repo", repo, create=True):
        client = TestClient(app)
        response = client.post(
            "/api/knowledge/pdf", files={"file": ("bad.pdf", b"invalid", "application/pdf")}
        )
        assert response.status_code == 422
        repo.add_pdf_reference.assert_not_called()
        response = client.post(
            "/api/knowledge/pdf",
            data={"title": "Quartz fix", "kind": "runbook"},
            files={"file": ("fix.pdf", reference_pdf(), "application/pdf")},
        )
        assert response.status_code == 201
        assert repo.add_pdf_reference.call_args.args[0]["chunks"][0]["kind"] == "runbook"
