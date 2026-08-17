import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.knowledge_upload import KNOWLEDGE_DIR, _safe_filename, ingest


class KnowledgeUploadTests(unittest.TestCase):
    def test_accepts_and_sanitizes_docx_filename(self) -> None:
        self.assertEqual(_safe_filename("../NCR - New Guide.docx"), "NCR - New Guide.docx")

    def test_rejects_non_docx_files(self) -> None:
        with self.assertRaisesRegex(ValueError, "Only DOCX"):
            _safe_filename("guide.pdf")

    def test_rejects_empty_filename(self) -> None:
        with self.assertRaises(ValueError):
            _safe_filename(".docx")

    @patch("app.services.knowledge_upload.tempfile.TemporaryDirectory")
    @patch("app.services.knowledge_upload.upsert_document")
    @patch("app.services.knowledge_upload.extract_docx")
    def test_upload_stages_on_the_knowledge_filesystem(self, extract_docx, upsert_document, temporary_directory) -> None:
        temporary_directory.return_value.__enter__.return_value = str(KNOWLEDGE_DIR / ".upload-test")
        temporary_directory.return_value.__exit__.return_value = False
        extract_docx.return_value = ("SECTION: Test STEP 1 Do the thing.", [{"text": "Do the thing.", "images": []}], [])
        upload = MagicMock()
        upload.filename = "Test Guide.docx"
        upload.read = AsyncMock(return_value=b"PK valid test content")
        with patch.object(Path, "write_bytes"), patch("app.services.knowledge_upload.os.replace"):
            import asyncio
            asyncio.run(ingest(upload))
        temporary_directory.assert_called_once_with(dir=KNOWLEDGE_DIR, prefix=".upload-")
        upsert_document.assert_called_once()


if __name__ == "__main__":
    unittest.main()
