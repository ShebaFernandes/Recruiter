"""Local OCR boundaries use fictional text and never call an external service."""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from django.test import override_settings
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
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


def test_readable_local_pdf_view_recovers_supported_roles_without_ocr(monkeypatch):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    })
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})
    })
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 10 Tf 50 740 Td '
                    b'(Fictional profile text with a broken employer career layout) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    payload = output.getvalue()
    alternative = (
        'PROFESSIONAL EXPERIENCE\n'
        'Engineer | Fictional Studio | Jan 2020 - Dec 2022\n'
        'Engineering Intern | Example Works | Jan 2019 - Jun 2019\n'
    )
    monkeypatch.setattr(services.shutil, 'which', lambda command: '/usr/bin/' + command)
    original_run = services.subprocess.run

    def fake_run(command, **kwargs):
        assert command == ['pdftotext', '-layout', '-', '-']
        assert kwargs['input'] == payload
        assert kwargs['timeout'] == 12
        return SimpleNamespace(stdout=alternative.encode())

    monkeypatch.setattr(services.subprocess, 'run', fake_run)
    monkeypatch.setattr(services, '_pdf_readability', lambda text:
                        (100, 2) if text == alternative else (20, 0))
    with override_settings(RESUME_LOCAL_OCR_ENABLED=False):
        parsed = services.parse_resume(BytesIO(payload), 'fictional.pdf')
    assert {(row['company'], row['role']) for row in parsed['work_experiences']} == {
        ('Fictional Studio', 'Engineer'), ('Example Works', 'Engineering Intern'),
    }
    assert not parsed['_employment_parse']['ocr_used']
    assert not parsed['_employment_parse']['ocr_required']
    monkeypatch.setattr(services.subprocess, 'run', original_run)
