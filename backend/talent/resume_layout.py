"""Local, bounded layout routing. Scores are heuristics, never probabilities.

Geometry and text remain worker-local. Persisted diagnostics contain only fixed
labels, counts and source IDs. Classification never grants archival authority.
"""

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from .document_evidence import MAX_BLOCKS, MAX_VIEW_CHARS

VERSION = 'layout-v1'
FAMILIES = {'single_column', 'columns', 'table', 'mixed', 'unknown'}


@dataclass
class DocumentBlock:
    evidence_id: str
    page: int
    text: str
    bbox: list[float] | None = None  # normalized to page dimensions
    column: str = 'wide'
    cells: list[str] = field(default_factory=list)
    source: str = 'native'
    source_bbox: list[float] | None = None  # validator expects PDF point units


@dataclass
class DocumentPage:
    number: int
    blocks: list[DocumentBlock]
    source: str = 'native'


@dataclass
class DocumentStructure:
    filename: str
    pages: list[DocumentPage]
    baseline: dict
    incomplete: bool = False


@dataclass
class LayoutProfile:
    family: str
    pages: list[dict]
    source: str
    employment_structure: str
    section_structure: str


def extract_document(file_obj, filename, *, baseline=None):
    """Adapt existing independently extracted views without a second PDF parse."""
    from .services import OCR_REQUIRED_MARKER, OCR_USED_MARKER, _parse_resume_legacy, read_docx

    baseline = baseline if baseline is not None else _parse_resume_legacy(file_obj, filename)
    metadata = baseline.get('_document_layout', {})
    views = baseline.get('_evidence_views', [])
    blocks = []
    incomplete = bool(metadata.get('layout_incomplete') or baseline.get('_text_truncated'))
    extension = Path(filename).suffix.lower()
    if extension == '.pdf':
        geometry = next((view for view in views if view['method'] == 'layout_geometry'), None)
        if geometry is None:
            geometry = next((view for view in views if view['method'] == 'pdfplumber'), {})
        incomplete |= bool(geometry.get('incomplete'))
        rows = [block for view in views if 'row' in view['method']
                for block in view.get('blocks', [])]
        for index, block in enumerate(geometry.get('blocks', [])):
            # Replace table geometry with the actual row, not a flattened line.
            if any(row['page'] == block['page'] and row['bbox'][1] - 2 <= block['bbox'][1]
                   and block['bbox'][3] <= row['bbox'][3] + 2 for row in rows):
                continue
            blocks.append(_adapt_block(block, f"p{block['page']}:b{index}"))
        blocks.extend(_adapt_block(row, row['entry_id']) for row in rows)
    elif extension == '.docx':
        document = read_docx(file_obj)
        table_index = 0
        for index, item in enumerate(document.iter_inner_content()):
            if hasattr(item, 'text'):
                if item.text.strip():
                    blocks.append(DocumentBlock(f'docx:b{index}', 1, item.text))
            else:
                for row_index, row in enumerate(item.rows):
                    cells = [' '.join(cell.text.split()) for cell in row.cells]
                    blocks.append(DocumentBlock(
                        f'docx:t{table_index}:r{row_index}', 1,
                        ' | '.join(cell for cell in cells if cell), cells=cells))
                table_index += 1
            if len(blocks) > MAX_BLOCKS:
                incomplete = True
                break
    else:
        blocks = [DocumentBlock(f'text:b{index}', 1, line)
                  for index, line in enumerate(baseline['raw_text'].splitlines()) if line.strip()]
    if len(blocks) > MAX_BLOCKS or sum(len(block.text) for block in blocks) > MAX_VIEW_CHARS:
        incomplete = True
    blocks = blocks[:MAX_BLOCKS]
    page_count = min(100, metadata.get('pages') or 1)
    pages = []
    for number in range(1, page_count + 1):
        members = [block for block in blocks if block.page == number]
        source = 'native'
        if extension == '.pdf' and not any(block.text.strip() for block in members):
            source = 'scanned'
            # OCR text has no trustworthy geometry. Keep the existing OCR view
            # intact rather than assigning its words invented coordinates.
            if OCR_USED_MARKER in baseline['raw_text']:
                source = 'ocr'
        _partition_columns(members)
        pages.append(DocumentPage(number, members, source))
    if OCR_REQUIRED_MARKER in baseline['raw_text']:
        incomplete = True
    return DocumentStructure(filename, pages, baseline, incomplete)


def _adapt_block(block, evidence_id):
    size = block.get('page_size')
    box = block.get('bbox')
    normalized = ([round(max(0., min(1., value / size[index % 2])), 5)
                   for index, value in enumerate(box)]
                  if box and size and all(value > 0 for value in size) else None)
    return DocumentBlock(evidence_id, block['page'], block['text'], normalized,
                         block.get('column', 'wide'), block.get('cells', []), source_bbox=box)


def _partition_columns(blocks):
    """Locate a repeated whitespace gutter without assuming a 50/50 split.

    Both sides need multiple blocks and their own section heading. Employment
    rows with dates aligned on the right must not become two reading columns.
    """
    from .services import _heading_and_tail

    positioned = [block for block in blocks if block.bbox and not block.cells]
    for edge in sorted({block.bbox[2] + .015 for block in positioned}):
        if not .15 < edge < .8:
            continue
        left = [block for block in positioned if block.bbox[2] < edge]
        right = [block for block in positioned if block.bbox[0] > edge + .025]
        if min(len(left), len(right)) < 2:
            continue
        if not all(any(_heading_and_tail(block.text)[0] for block in side)
                   for side in (left, right)):
            continue
        # Require actual vertical overlap, not two sequential indented sections.
        if max(min(block.bbox[1] for block in left), min(block.bbox[1] for block in right)) >= min(
                max(block.bbox[3] for block in left), max(block.bbox[3] for block in right)):
            continue
        for block in left:
            block.column = 'left'
        for block in right:
            block.column = 'right'
        return


def _sections(blocks):
    """Split each reading region at real headings, retaining continuation blocks."""
    from .services import _heading_and_tail

    regions = []
    for block in blocks:
        heading = _heading_and_tail(block.text.splitlines()[0])[0]
        if heading or not regions:
            regions.append({'heading': heading or 'unknown', 'blocks': []})
        regions[-1]['blocks'].append(block)
    return regions


def classify_layout(document):
    from .services import DATE_RANGE_PATTERN, _heading_and_tail, _looks_like_role

    page_profiles = []
    for page in document.pages:
        columns = Counter(block.column for block in page.blocks if not block.cells)
        table = any(block.cells for block in page.blocks)
        two_columns = columns['left'] >= 2 and columns['right'] >= 2
        if (document.baseline.get('_document_layout', {}).get('layout_incomplete')
                or not page.blocks or page.source != 'native'):
            family, score, reason = 'unknown', 0., 'incomplete_or_no_native_geometry'
        elif table and two_columns:
            family, score, reason = 'mixed', .8, 'table_and_column_regions'
        elif table:
            family, score, reason = 'table', .85, 'source_table_rows'
        elif two_columns:
            family, score, reason = 'columns', .8, 'repeated_separated_column_blocks'
        else:
            family, score, reason = 'single_column', .7, 'continuous_text_flow'
        regions = []
        for column in ('wide', 'left', 'right'):
            members = [block for block in page.blocks if not block.cells
                       and block.column in {column, 'flow'}]
            for section in _sections(members):
                regions.append({'column': column, 'section': section['heading'],
                                'block_ids': [block.evidence_id for block in section['blocks']]})
        regions.extend({'column': 'table', 'section': 'unknown',
                        'block_ids': [block.evidence_id]} for block in page.blocks if block.cells)
        page_profiles.append({'page': page.number, 'family': family, 'score': score,
                              'reason': reason, 'regions': regions})
    families = {page['family'] for page in page_profiles}
    family = next(iter(families)) if len(families) == 1 else 'mixed'
    sources = {page.source for page in document.pages}
    source = next(iter(sources)) if len(sources) == 1 else 'mixed'
    if source == 'ocr':
        source = 'scanned'
    rows = document.baseline.get('work_experiences', [])
    companies = [row.get('company', '').casefold() for row in rows]
    structure = 'unknown'
    if len(companies) > len(set(companies)):
        structure = 'grouped_promotions'
    else:
        for block in (block for page in document.pages for block in page.blocks):
            if DATE_RANGE_PATTERN.match(block.text):
                structure = 'date_first'
                break
            if DATE_RANGE_PATTERN.search(block.text):
                structure = 'title_first' if _looks_like_role(block.text.split('|')[0]) else (
                    'company_first')
                break
    headings = any(_heading_and_tail(block.text.splitlines()[0])[0]
                   for page in document.pages for block in page.blocks if block.text.strip())
    section = 'explicit' if headings else 'inferred' if rows else 'unknown'
    return LayoutProfile(family, page_profiles, source, structure, section)


def _reading_text(document, profile):
    """Order regions per page; never interleave columns on a shared baseline."""
    if document.incomplete or any(page.source != 'native' for page in document.pages):
        return document.baseline['raw_text']
    parts = []
    for page, decision in zip(document.pages, profile.pages, strict=True):
        if not page.blocks:
            return document.baseline['raw_text']
        blocks = page.blocks
        if decision['family'] in {'columns', 'mixed'}:
            # Full-width headings delimit vertical bands of columns.
            wide = sorted([block for block in blocks if block.column == 'wide' and not block.cells],
                          key=lambda block: block.bbox[1] if block.bbox else 0)
            remaining = [block for block in blocks if block not in wide]
            ordered = []
            for boundary in wide:
                before = [block for block in remaining if block.bbox and boundary.bbox
                          and block.bbox[1] < boundary.bbox[1]]
                ordered.extend(sorted(before, key=lambda block: (
                    block.column == 'right', block.bbox[1])))
                remaining = [block for block in remaining if block not in before]
                ordered.append(boundary)
            ordered.extend(sorted(remaining, key=lambda block: (
                block.column == 'right', block.bbox[1] if block.bbox else 0)))
        else:
            ordered = sorted(blocks, key=lambda block: (
                block.bbox[1], block.bbox[0]) if block.bbox else (0, 0))
        parts.extend(block.text for block in ordered)
    return '\n'.join(parts)


def _role_key(row):
    return tuple(str(row.get(key) or '').casefold() for key in (
        'company', 'role', 'start_date', 'end_date', 'is_current'))


def association_fingerprint(row):
    """Transient identity guard; never persist employer/title text in diagnostics."""
    pair = [' '.join(str(row.get(key) or '').casefold().split()) for key in ('company', 'role')]
    return sha256('\0'.join(pair).encode()).hexdigest()


def protect_layout_conflicts(extracted):
    """An AI/cache fallback must not silently save a disputed local association."""
    fingerprints = set(extracted.pop('_layout_conflict_ids', []))
    if not fingerprints:
        return
    rows = [row for row in extracted.get('work_experiences', [])
            if association_fingerprint(row) not in fingerprints]
    extracted['work_experiences'] = rows
    if rows:
        latest = max(rows, key=lambda row: (row.get('is_current'), row.get('start_date') or ''))
        extracted['headline'], extracted['current_company'] = latest['role'], latest['company']
    else:
        extracted['headline'], extracted['current_company'] = '', ''
    from .resume_understanding import total_experience

    extracted['total_experience'] = total_experience(rows)
    extracted['_employment_parse'].update(
        complete_for_archival=False, rule_role_keys=[], reliable=False)
    extracted['_layout_review_required'] = True


def _validated_rows(result, views):
    """Reproduce each deterministic association inside one safe source scope.

    Rule rows already carry literal evidence. Reparse an independent source
    scope rather than converting them to AI proposals: the AI schema has
    different date precision and quotation conventions. Never combine scopes.
    """
    import re

    from .document_evidence import evidence_location
    from .services import _parse_resume_text

    supported = {}
    for view in sorted(views, key=lambda item: not bool(item.get('blocks'))):
        if not view.get('validation_safe', True) or not view.get('text'):
            continue
        text = view['text']
        if 'row' in view['method']:
            text = 'WORK EXPERIENCE\n' + text
        scoped = _parse_resume_text(text, 'scope.txt', [], {}, [])
        for row in scoped['work_experiences']:
            supported.setdefault(_role_key(row), (view, row))
    accepted = []
    seen = set()
    for row in result['work_experiences']:
        key = _role_key(row)
        if key not in supported or key in seen:
            continue
        view, scoped = supported[key]
        seen.add(key)
        item = dict(scoped)
        item['_evidence_location'] = evidence_location(scoped.get('source_evidence'), view)
        # Literal years retain their precision; do not manufacture January dates.
        labels = re.split(r'\s+(?:-|–|—|to)\s+', item.get('date_label', ''), maxsplit=1)
        for index, field_name in enumerate(('start_date', 'end_date')):
            if index < len(labels) and re.fullmatch(r'\d{4}', labels[index]):
                item[field_name] = None
        accepted.append(item)
    return accepted


def _evidence_views(document):
    views = deepcopy(document.baseline.get('_evidence_views', []))
    if Path(document.filename).suffix.lower() != '.docx':
        geometry = any(view['method'] == 'layout_geometry' for view in views)
        if geometry and not document.incomplete and not any(
                block.cells for page in document.pages for block in page.blocks):
            if any(block.column == 'right' for page in document.pages for block in page.blocks):
                # Flattened text may cross the newly discovered gutter. Only
                # narrower scopes may validate associations on these pages.
                for view in views:
                    view['validation_safe'] = False
                for column in ('left', 'right'):
                    members = [block for page in document.pages for block in page.blocks
                               if block.column in {column, 'wide'}]
                    views.append({'method': f'layout_{column}',
                                  'text': '\n'.join(block.text for block in members),
                                  'blocks': [{'text': block.text, 'page': block.page,
                                              'bbox': block.source_bbox or block.bbox,
                                              'column': block.column,
                                              'entry_id': block.evidence_id}
                                             for block in members],
                                  'validation_safe': True, 'parser_input': False})
        if views:
            return views
        return [{'method': 'primary', 'text': document.baseline['raw_text'], 'blocks': [],
                 'validation_safe': Path(document.filename).suffix.lower() != '.pdf'}]
    # Unlike flattened DOCX text, table-row views cannot borrow another row's company.
    if not any(block.cells for page in document.pages for block in page.blocks):
        return views
    views = []
    flow = []
    for page in document.pages:
        for block in page.blocks:
            if block.cells:
                if flow:
                    views.append({'method': 'docx_flow', 'text': '\n'.join(flow), 'blocks': []})
                    flow = []
                views.append({'method': 'docx_row', 'text': block.text, 'blocks': [{
                    'text': block.text, 'page': 1, 'bbox': None, 'column': block.evidence_id,
                    'entry_id': block.evidence_id}]})
            else:
                flow.append(block.text)
    if flow:
        views.append({'method': 'docx_flow', 'text': '\n'.join(flow), 'blocks': []})
    return views


def parse_document(document, profile):
    """Compare at most two local readings; retain conflicts for review, not saving."""
    from .resume_understanding import total_experience
    from .services import _parse_resume_text

    started = perf_counter()
    baseline = document.baseline
    views = _evidence_views(document)
    text = _reading_text(document, profile)
    candidate = _parse_resume_text(text, document.filename, views,
                                   deepcopy(baseline.get('_document_layout', {})), [])
    candidates = [baseline, candidate] if text != baseline['raw_text'] else [candidate]
    checked = [_validated_rows(result, views) for result in candidates]
    # Prefer complete evidence-supported associations, not raw extraction volume.
    selected = max(range(len(candidates)), key=lambda index: (
        sum(row['confidence_status'] == 'supported' for row in checked[index]),
        len(checked[index])))
    result = deepcopy(candidates[selected])
    rows = checked[selected]
    conflicts = set()
    if len(checked) == 2:
        left, right = ({_role_key(row) for row in items} for items in checked)
        for first in left - right:
            for second in right - left:
                # Same company/title with differing dates, or one title/tenure
                # assigned to different employers, requires human resolution.
                if (first[:2] == second[:2] or first[1:] == second[1:]
                        or first[:2] == second[1::-1] and first[2:] == second[2:]):
                    conflicts.update((first, second))
    if conflicts:
        result['_layout_conflict_ids'] = sorted({association_fingerprint({
            'company': key[0], 'role': key[1]}) for key in conflicts})
    rows = [row for row in rows if _role_key(row) not in conflicts]
    result['work_experiences'] = rows
    if rows:
        latest = max(rows, key=lambda row: (row['is_current'], row.get('start_date') or ''))
        result['headline'], result['current_company'] = latest['role'], latest['company']
    else:
        result['headline'], result['current_company'] = '', ''
    result['total_experience'] = total_experience(rows)
    result['_evidence_views'] = views
    rejected = len(candidates[selected]['work_experiences']) - len(rows)
    uncertain = bool(conflicts or rejected or document.incomplete or profile.family == 'unknown'
                     or any(page['family'] == 'unknown' for page in profile.pages))
    result['_document_layout']['layout_uncertain'] = bool(
        result['_document_layout'].get('layout_uncertain') or uncertain)
    # Layout selection cannot independently prove completeness. This version
    # deliberately leaves archival disabled even when both readings agree.
    result['_employment_parse'].update(
        complete_for_archival=False, rule_role_keys=[],
        reliable=bool(rows) and not uncertain)
    if conflicts or rejected or (uncertain and rows):
        result['_layout_review_required'] = True
        result['_layout_review_reason'] = (
            'conflicting_layout_associations' if conflicts else
            'unsupported_layout_associations' if rejected else 'document_layout_uncertain')
    references = []
    for index, row in enumerate(rows[:100]):
        location = row.get('_evidence_location') or {}
        references.append({'role_index': index, 'method': location.get('method'),
                           'page': location.get('page'), 'entry_id': location.get('entry_id'),
                           'block_ids': [block.evidence_id for page in document.pages
                                         for block in page.blocks
                                         if block.text.strip() and block.text.strip() in
                                         row.get('source_evidence', '')][:12]})
    # No quotations, names or geometry in diagnostics persisted with the resume.
    result['_layout_routing'] = {
        'version': VERSION, 'family': profile.family, 'source': profile.source,
        'employment_structure': profile.employment_structure,
        'section_structure': profile.section_structure,
        'pages': [{key: page[key] for key in ('page', 'family', 'score', 'reason')}
                  for page in profile.pages[:100]],
        'strategy': 'region_order' if candidates[selected] is candidate else 'legacy',
        'strategies_compared': len(candidates), 'baseline_roles': len(baseline['work_experiences']),
        'accepted_roles': len(rows), 'rejected_roles': rejected,
        'conflicting_associations': len(conflicts), 'review_required': uncertain,
        'missing_sections': ['employment'] if not rows and not result['_employment_parse'].get(
            'explicit_no_employment') else [],
        'field_evidence': references,
        'elapsed_ms': round((perf_counter() - started) * 1000, 2),
    }
    return result
