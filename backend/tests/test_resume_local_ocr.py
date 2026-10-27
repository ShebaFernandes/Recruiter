"""Local OCR boundaries use fictional text and never call an external service."""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from django.test import override_settings
from pypdf import PdfWriter
from talent import services


def blank_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_image_only_pdf_never_proves_complete_history_without_ocr():
    with override_settings(RESUME_LOCAL_OCR_ENABLED=False):
        parsed = services.parse_resume(BytesIO(blank_pdf()), 'fictional.pdf')
    assert parsed['work_experiences'] == []
    assert parsed['_employment_parse']['ocr_required']
    assert not parsed['_employment_parse']['complete_for_archival']


def test_local_ocr_is_bounded_private_and_never_authorizes_archival(monkeypatch):
    calls = []
    scratch_paths = []
    monkeypatch.setattr(services.shutil, 'which', lambda command: '/bin/' + command)

    def fake_run(command, **kwargs):
        calls.append((command[0], kwargs['timeout']))
        assert command[0] in {'pdftoppm', 'tesseract'}
        if command[0] == 'pdftoppm':
            source = Path(command[-2])
            assert source.is_file()
            scratch_paths.append(source.parent)
            Path(command[-1] + '.png').write_bytes(b'fictional-image')
            return SimpleNamespace(stdout=b'')
        return SimpleNamespace(stdout=(
            b'WORK EXPERIENCE\nEngineer | Fictional Studio | Jan 2020 - Dec 2022'
        ))

    monkeypatch.setattr(services.subprocess, 'run', fake_run)
    with override_settings(RESUME_LOCAL_OCR_ENABLED=True, RESUME_LOCAL_OCR_MAX_PAGES=2,
                           RESUME_LOCAL_OCR_MAX_FILE_BYTES=5_242_880,
                           RESUME_LOCAL_OCR_TIMEOUT_SECONDS=5):
        parsed = services.parse_resume(BytesIO(blank_pdf()), 'fictional.pdf')
    assert [(row['company'], row['role']) for row in parsed['work_experiences']] == [
        ('Fictional Studio', 'Engineer')
    ]
    assert parsed['_employment_parse']['ocr_used']
    assert not parsed['_employment_parse']['complete_for_archival']
    assert calls == [('pdftoppm', 5), ('tesseract', 5)]
    assert all(not path.exists() for path in scratch_paths)


def test_ocr_over_page_limit_does_not_invoke_local_tools(monkeypatch):
    monkeypatch.setattr(services.subprocess, 'run', lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(AssertionError('OCR invoked')))
    with override_settings(RESUME_LOCAL_OCR_ENABLED=True, RESUME_LOCAL_OCR_MAX_PAGES=1):
        result = services._local_ocr_pdf(BytesIO(b'fictional'), [0, 1])
    assert result == {}
