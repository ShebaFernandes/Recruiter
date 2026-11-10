"""Fictional, local-only comparisons; held-out templates are not employer renames.

Reports deterministic extraction, not AI quality or real candidate accuracy.
No database writes, provider calls, or production storage access.
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'scripts')]
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['RESUME_AI_ENABLED'] = 'false'

import django  # noqa: E402
from django.test import override_settings  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from pypdf import PdfReader, PdfWriter  # noqa: E402
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject  # noqa: E402

django.setup()

from resume_accuracy_benchmark import Case, Role, cases, document, pdf_bytes  # noqa: E402
from talent.resume_layout import classify_layout, extract_document, parse_document  # noqa: E402
from talent.services import _parse_resume_legacy  # noqa: E402


@dataclass
class Fixture:
    name: str
    split: str
    family: str
    payload: bytes
    filename: str
    roles: list[Role]
    page_families: tuple = ()


def positioned_document(items, *, ruled=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
        NameObject('/F1'): writer._add_object(font)})})
    commands = ['BT', '/F1 9 Tf']
    for x, y, value in items:
        escaped = value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        commands.extend((f'1 0 0 1 {x} {y} Tm', f'({escaped}) Tj'))
    commands.append('ET')
    if ruled:
        commands.extend(('0.5 w',
                         *(f'{x} 610 m {x} 700 l S' for x in (50, 240, 420, 570)),
                         *(f'50 {y} m 570 {y} l S' for y in (610, 640, 670, 700))))
    stream = DecodedStreamObject()
    stream.set_data('\n'.join(commands).encode('latin-1'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def fixtures():
    """Existing templates form development; structurally new ones are held out."""
    for case in cases():
        payload, filename = document(case)
        family = ('unknown' if case.image_only else 'columns' if case.columns
                  else 'table' if case.table else 'single_column')
        yield Fixture(case.name, 'development', family, payload, filename, case.roles)
    sidebar = positioned_document([
        (40, 740, 'SKILLS'), (40, 720, 'Python'), (40, 700, 'EDUCATION'),
        (40, 680, 'Example University'), (200, 740, 'WORK EXPERIENCE'),
        (200, 720, 'Horizon Works'), (200, 700, 'Engineer Jan 2020 - Present')])
    yield Fixture('narrow_sidebar', 'held_out', 'columns', sidebar, 'sidebar.pdf',
                  [Role('Horizon Works', 'Engineer', '2020-01-01', current=True)])
    ruled = positioned_document([
        (50, 740, 'WORK EXPERIENCE'), (60, 680, 'Horizon Works'),
        (250, 680, 'Engineer'), (430, 680, 'Jan 2020 - Dec 2021'),
        (60, 650, 'Later Works'), (250, 650, 'Senior Engineer'),
        (430, 650, 'Jan 2022 - Present')], ruled=True)
    yield Fixture('ruled_pdf', 'held_out', 'table', ruled, 'ruled.pdf',
                  [Role('Horizon Works', 'Engineer', '2020-01-01', '2021-12-01'),
                   Role('Later Works', 'Senior Engineer', '2022-01-01', current=True)])
    # No existing template family is duplicated into held-out by renaming employers.
    writer = PdfWriter()
    for lines in (
        ['Name: Fictional Journey', 'WORK EXPERIENCE', 'Example Systems',
         'Engineer Jan 2020 - Dec 2021'],
        ['Senior Engineer Jan 2022 - Present', 'EDUCATION', 'Example University'],
    ):
        writer.append(PdfReader(BytesIO(pdf_bytes(lines))))
    output = BytesIO()
    writer.write(output)
    yield Fixture('page_continuation', 'held_out', 'single_column', output.getvalue(),
                  'continuation.pdf', [Role('Example Systems', 'Engineer', '2020-01-01',
                                           '2021-12-01'),
                                       Role('Example Systems', 'Senior Engineer', '2022-01-01',
                                            current=True)])
    # A native page and a scan must not be collapsed into a single text source.
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    yield Fixture('native_and_scan', 'held_out', 'mixed', output.getvalue(), 'mixed.pdf',
                  [Role('Example Systems', 'Engineer', '2020-01-01', '2021-12-01'),
                   Role('Example Systems', 'Senior Engineer', '2022-01-01', current=True)],
                  ('single_column', 'single_column', 'unknown'))
    scan = Image.new('RGB', (1000, 1400), 'white')
    ImageDraw.Draw(scan).text((80, 100),
                             'WORK EXPERIENCE\nHorizon Works\nEngineer 2020 - 2022',
                             fill='black')
    scan_output = BytesIO()
    scan.save(scan_output, format='PDF')
    yield Fixture('raster_scan', 'held_out', 'unknown', scan_output.getvalue(), 'scan.pdf',
                  [Role('Horizon Works', 'Engineer', '2020-01-01', '2022-01-01')])
    # A complete pipe record without a section heading exercises inferred sections.
    case = Case('unheaded', ['Name: Fictional Applicant',
                            'Engineer | Horizon Works | Jan 2018 - Dec 2020'],
                [Role('Horizon Works', 'Engineer', '2018-01-01', '2020-12-01')], 'docx')
    payload, filename = document(case)
    yield Fixture(case.name, 'held_out', 'single_column', payload, filename, case.roles)


def score(result, fixture):
    def key(company, role):
        return company.casefold().strip(), role.casefold().strip()

    expected = {key(role.company, role.title) for role in fixture.roles}
    rows = result['work_experiences']
    actual = {key(row['company'], row['role']) for row in rows}
    dates = correct_dates = 0
    for role in fixture.roles:
        row = next((row for row in rows if key(row['company'], row['role']) ==
                    key(role.company, role.title)), None)
        for field, value in (('start_date', role.start), ('end_date', role.end)):
            if value:
                dates += 1
                correct_dates += bool(row and (row.get(field) == value or (
                    row.get(field) is None and value.endswith('-01-01')
                    and value[:4] in row.get('date_label', ''))))
        if role.current:
            dates += 1
            correct_dates += bool(row and row.get('is_current'))
    diagnostics = result.get('_layout_routing', {})
    return {'expected': len(expected), 'actual': len(actual), 'matched': len(actual & expected),
            'unsupported': len(actual - expected), 'date_facts': dates,
            'correct_date_facts': correct_dates,
            'review_required': bool(diagnostics.get('review_required') or (
                not rows and not result.get('_employment_parse', {}).get(
                    'explicit_no_employment'))),
            'ai_quality_fallback_signal': not rows or not result.get(
                '_employment_parse', {}).get('reliable', bool(rows)),
            'complete_journey': actual == expected}


def summarize(items):
    total = {key: sum(item[key] for item in items) for key in (
        'expected', 'actual', 'matched', 'unsupported', 'date_facts', 'correct_date_facts')}
    return {**total, 'fixtures': len(items),
            'precision': round(total['matched'] / total['actual'], 4) if total['actual'] else 1.,
            'recall': round(total['matched'] / total['expected'], 4) if total['expected'] else 1.,
            'date_accuracy': (round(total['correct_date_facts'] / total['date_facts'], 4)
                              if total['date_facts'] else 1.),
            'complete_journeys': sum(item['complete_journey'] for item in items),
            'review_rate': round(sum(item['review_required'] for item in items) / len(items), 4),
            'ai_quality_fallback_rate': round(sum(item['ai_quality_fallback_signal']
                                                  for item in items) / len(items), 4),
            'mean_processing_ms': round(sum(item['processing_ms'] for item in items)
                                        / len(items), 2)}


def run():
    results = []
    groups = defaultdict(list)
    with override_settings(RESUME_LAYOUT_MODE='enabled', RESUME_LOCAL_OCR_ENABLED=False):
        for fixture in fixtures():
            started = perf_counter()
            baseline = _parse_resume_legacy(BytesIO(fixture.payload), fixture.filename)
            baseline_ms = (perf_counter() - started) * 1000
            structure = extract_document(BytesIO(fixture.payload), fixture.filename,
                                         baseline=baseline)
            profile = classify_layout(structure)
            structure_ms = (perf_counter() - started) * 1000
            oracle = deepcopy(profile)
            oracle.family = fixture.family
            for index, page in enumerate(oracle.pages):
                page['family'] = (fixture.page_families[index] if fixture.page_families
                                  else fixture.family)
            outputs = {'legacy': baseline}
            timings = {'legacy': baseline_ms}
            for name, layout in (('oracle', oracle), ('automatic', profile)):
                parse_started = perf_counter()
                outputs[name] = parse_document(structure, layout)
                timings[name] = structure_ms + (perf_counter() - parse_started) * 1000
            item = {'name': fixture.name, 'split': fixture.split, 'expected_family': fixture.family,
                    'predicted_family': profile.family,
                    'classification_correct': profile.family == fixture.family,
                    'elapsed_ms': round((perf_counter() - started) * 1000, 2),
                    'strategies': {name: {**score(result, fixture),
                                          'processing_ms': round(timings[name], 2)}
                                   for name, result in outputs.items()}}
            results.append(item)
            for name, metrics in item['strategies'].items():
                groups[(fixture.split, fixture.family, name)].append(metrics)
    return {'mode': 'synthetic_local_only', 'paid_calls': 0, 'external_calls': 0,
            'paid_cost_usd': 0,
            'classification_accuracy': round(sum(row['classification_correct'] for row in results)
                                             / len(results), 4),
            'groups': [{'split': split, 'family': family, 'strategy': strategy,
                        **summarize(items)}
                       for (split, family, strategy), items in sorted(groups.items())],
            'cases': results,
            'limitations': ['Synthetic fixtures do not establish production accuracy.',
                            'Persistence and archival safety are tested separately in pytest.',
                            'Review rates are routing signals; no AI is invoked.',
                            'Literal year evidence counts as year precision, not month precision.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = run()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
