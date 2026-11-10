"""Bounded, traceable text views of a private resume document.

Each method is kept separate. A role must be supported within one view; text from
different columns or extractors is never spliced into a synthetic quotation.
"""

import re
from collections import Counter
from difflib import SequenceMatcher
from io import BytesIO

import pdfplumber
from pdfminer.pdfexceptions import PDFException

MAX_VIEW_CHARS = 50_000
MAX_BLOCKS = 600
MAX_WORDS = 6_000
MAX_LAYOUT_ROWS = 300


def _box(value):
    return [round(float(part), 1) for part in value[:4]]


def _positioned_lines(page, page_number, *, split_gutters=False):
    """Reconstruct verbatim word lines, splitting only clear column gutters."""
    words = page.extract_words(x_tolerance=2, y_tolerance=3)
    if len(words) > MAX_WORDS:
        return [], len(words)
    lines = []
    for word in sorted(words, key=lambda item: (item['top'], item['x0'])):
        if not lines or abs(word['top'] - lines[-1][-1]['top']) > 3:
            lines.append([])
        lines[-1].append(word)
    blocks = []
    midpoint = page.width / 2
    for line in lines:
        groups = [[]]
        for word in sorted(line, key=lambda item: item['x0']):
            if groups[-1]:
                previous = groups[-1][-1]
                gutter = word['x0'] - previous['x1']
                if gutter > max(45, page.width * .08) and (
                    split_gutters or previous['x1'] < midpoint and word['x0'] > midpoint
                ):
                    groups.append([])
            groups[-1].append(word)
        for group in groups:
            blocks.append({
                'page': page_number,
                'bbox': _box((min(word['x0'] for word in group),
                              min(word['top'] for word in group),
                              max(word['x1'] for word in group),
                              max(word['bottom'] for word in group))),
                'text': ' '.join(word['text'] for word in group),
                'column': 'wide',
            })
    return blocks, len(words)


def _ordered_blocks(page, page_number):
    blocks, words = _positioned_lines(page, page_number)
    if not blocks:
        return [], False, words
    midpoint = page.width / 2
    left = [item for item in blocks if item['bbox'][2] < midpoint + 12]
    right = [item for item in blocks if item['bbox'][0] > midpoint - 12]
    columns = len(left) >= 2 and len(right) >= 2
    if not columns:
        return sorted(blocks, key=lambda item: (item['bbox'][1], item['bbox'][0])), False, words
    for item in left:
        item['column'] = 'left'
    for item in right:
        item['column'] = 'right'
    wide = [item for item in blocks if item not in left and item not in right]
    first_column_y = min(item['bbox'][1] for item in left + right)
    before = [item for item in wide if item['bbox'][3] <= first_column_y]
    after = [item for item in wide if item not in before]
    def key(item):
        return item['bbox'][1], item['bbox'][0]
    return (sorted(before, key=key) + sorted(left, key=key)
            + sorted(right, key=key) + sorted(after, key=key)), True, words


def _row_view(page_number, table_number, row_number, bbox, cells, kind):
    """One source row is one evidence view; other rows can never lend it facts."""
    text = ' | '.join(cell for cell in cells if cell)
    entry_id = f'p{page_number}:t{table_number}:r{row_number}'
    block = {'page': page_number, 'bbox': _box(bbox), 'column': entry_id,
             'table_row': row_number, 'entry_id': entry_id, 'text': text, 'cells': cells}
    return {'method': kind, 'text': text, 'blocks': [block],
            'validation_safe': True, 'parser_input': False,
            'page': page_number, 'entry_id': entry_id}


def _word_rows(page):
    """Group words only on a shared baseline, then split at real horizontal gutters."""
    words = sorted(page.extract_words(x_tolerance=2, y_tolerance=3),
                   key=lambda word: (word['top'], word['x0']))
    if len(words) > MAX_WORDS:
        return []
    lines = []
    for word in words:
        if not lines or abs(word['top'] - lines[-1][-1]['top']) > 3:
            lines.append([])
        lines[-1].append(word)
    rows = []
    for line in lines:
        cells = [[]]
        for word in sorted(line, key=lambda item: item['x0']):
            if cells[-1] and word['x0'] - cells[-1][-1]['x1'] > max(24, page.width * .04):
                cells.append([])
            cells[-1].append(word)
        rows.append({
            'top': min(word['top'] for word in line),
            'bottom': max(word['bottom'] for word in line),
            'cells': [
                {'x0': min(word['x0'] for word in cell),
                 'x1': max(word['x1'] for word in cell),
                 'text': ' '.join(word['text'] for word in cell)}
                for cell in cells
            ],
        })
    return rows


def _inside_box(row, bbox):
    return bbox[1] - 2 <= row['top'] and row['bottom'] <= bbox[3] + 2


def _order_disagrees(first, second):
    """Flag high-overlap text layers whose word order conflicts with geometry."""
    def tokens(value):
        return re.findall(r'(?u)\w+', value.casefold())[:MAX_WORDS]

    left, right = tokens(first), tokens(second)
    if min(len(left), len(right)) < 20:
        return False
    overlap = sum((Counter(left) & Counter(right)).values()) / min(len(left), len(right))
    if overlap < .8:
        return False
    counts = Counter(left) + Counter(right)
    rare_left = [word for word in left if counts[word] == 2]
    rare_right = [word for word in right if counts[word] == 2]
    if min(len(rare_left), len(rare_right)) >= 10:
        return SequenceMatcher(None, rare_left, rare_right).ratio() < .5
    return SequenceMatcher(None, left, right).ratio() < .55


def _borderless_rows(page, page_number, table_boxes, next_table_number):
    """Infer a table only from repeated aligned rows within one section.

    Two-cell rows require a visible employment heading. Three-cell rows must
    have a date-bearing final column. Differently headed side-by-side columns
    are deliberately excluded, even when their baselines line up.
    """
    from .services import EXPERIENCE_HEADINGS, _heading_and_tail

    rows = [row for row in _word_rows(page)
            if not any(_inside_box(row, bbox) for bbox in table_boxes)]
    if len(rows) > MAX_LAYOUT_ROWS:
        return [], [], [], True
    dated = re.compile(r'(?i)\b(?:19|20)\d{2}\b|\bpresent\b|\bcurrent\b')
    section = None
    multiple_headings = False
    candidates = []
    for index, row in enumerate(rows):
        headings = [_heading_and_tail(cell['text'])[0] for cell in row['cells']]
        if sum(bool(heading) for heading in headings) > 1:
            multiple_headings = True
        if len(row['cells']) == 1 and headings[0]:
            section = headings[0]
            continue
        if any(headings) or multiple_headings:
            continue
        cells = row['cells']
        if not 2 <= len(cells) <= 4:
            continue
        if section and section not in EXPERIENCE_HEADINGS:
            continue
        if len(cells) == 2 and section not in EXPERIENCE_HEADINGS:
            continue
        if len(cells) >= 3 and not dated.search(cells[-1]['text']):
            continue
        candidates.append((index, section, row))
    views, boxes, ambiguous = [], [], []
    unpaired = False
    used = set()
    for offset, (index, section, row) in enumerate(candidates):
        if index in used:
            continue
        aligned = [(index, row)]
        for next_index, next_section, next_row in candidates[offset + 1:]:
            if next_section != section or next_index - aligned[-1][0] > 2:
                break
            previous = aligned[-1][1]
            gap = next_row['top'] - previous['top']
            if not 12 <= gap <= 65:
                break
            if (len(next_row['cells']) != len(row['cells'])
                    or any(abs(left['x0'] - right['x0']) > 12
                           for left, right in zip(row['cells'], next_row['cells'], strict=True))):
                break
            if len(row['cells']) == 2 and (bool(dated.search(row['cells'][-1]['text']))
                    != bool(dated.search(next_row['cells'][-1]['text']))):
                break
            aligned.append((next_index, next_row))
        if len(aligned) < 2 and (
            section not in EXPERIENCE_HEADINGS or len(row['cells']) < 3
        ):
            continue
        if len(aligned) < 2:
            unpaired = True
        table_number = next_table_number + len(boxes)
        for row_number, (row_index, member) in enumerate(aligned):
            used.add(row_index)
            bbox = (member['cells'][0]['x0'], member['top'],
                    member['cells'][-1]['x1'], member['bottom'])
            views.append(_row_view(page_number, table_number, row_number, bbox,
                                   [cell['text'] for cell in member['cells']],
                                   'pdfplumber_borderless_row'))
            boxes.append(bbox)
    undated_two = sum(len(row['cells']) == 2
                      and not dated.search(row['cells'][-1]['text'])
                      for _, _, row in candidates)
    for index, _section, row in candidates:
        if index in used:
            continue
        # A lone or non-aligned date-bearing row cannot borrow neighboring
        # employer/title text. Keep it out of flattened validation views.
        if len(row['cells']) >= 3 or (
            len(row['cells']) == 2 and undated_two >= 2
            and not dated.search(row['cells'][-1]['text'])
        ):
            ambiguous.append((row['cells'][0]['x0'], row['top'],
                              row['cells'][-1]['x1'], row['bottom']))
    return views, boxes, ambiguous, unpaired


def _structured_rows(page, page_number):
    from .services import EXPERIENCE_HEADINGS, _heading_and_tail

    views, boxes = [], []
    page_rows = _word_rows(page)
    for table_number, table in enumerate(page.find_tables()):
        section = None
        for positioned in page_rows:
            if positioned['bottom'] >= table.bbox[1]:
                break
            headings = [_heading_and_tail(cell['text'])[0]
                        for cell in positioned['cells']]
            if sum(bool(heading) for heading in headings) > 1:
                section = 'ambiguous'
            elif len(headings) == 1 and headings[0]:
                section = headings[0]
        for row_number, (row, values) in enumerate(zip(
            table.rows, table.extract(), strict=False,
        )):
            cells = [' '.join((value or '').split()) for value in values]
            if (len([cell for cell in cells if cell]) < 2
                    or section and section not in EXPERIENCE_HEADINGS):
                continue
            views.append(_row_view(page_number, table_number, row_number,
                                   row.bbox, cells, 'pdfplumber_ruled_row'))
        boxes.append(table.bbox)
    borderless, row_boxes, ambiguous, overflow = _borderless_rows(
        page, page_number, boxes, len(boxes))
    return views + borderless, boxes + row_boxes + ambiguous, bool(ambiguous or overflow)


def pdf_views(file_obj, primary_text, poppler_text='', *, include_structure=False):
    """Return separate pdfplumber and Poppler views plus safe layout metadata."""
    file_obj.seek(0)
    payload = file_obj.read(8 * 1024 * 1024 + 1)
    if len(payload) > 8 * 1024 * 1024:
        return [], {'methods': ['primary'], 'layout_incomplete': True}
    views = [{'method': 'primary', 'text': primary_text, 'blocks': [],
              'validation_safe': True}]
    metadata = {'methods': ['primary'], 'pages': 0, 'columns': 0,
                'word_count': 0, 'layout_incomplete': False,
                'layout_uncertain': False, 'text_layer_disordered': False}
    reconstructed = ''
    try:
        with pdfplumber.open(BytesIO(payload)) as document:
            if len(document.pages) > 100:
                return [], {**metadata, 'layout_incomplete': True}
            blocks = []
            geometry = []
            geometry_incomplete = False
            structured = []
            table_boxes = {}
            words = 0
            for number, page in enumerate(document.pages, start=1):
                ordered, columns, page_words = _ordered_blocks(page, number)
                words += page_words
                for block in ordered:
                    block['page_size'] = [float(page.width), float(page.height)]
                blocks.extend(ordered)
                if include_structure:
                    positioned, _ = _positioned_lines(page, number, split_gutters=True)
                    for block in positioned:
                        block['page_size'] = [float(page.width), float(page.height)]
                    geometry.extend(positioned)
                    if len(geometry) > MAX_BLOCKS:
                        geometry_incomplete = True
                        geometry = geometry[:MAX_BLOCKS]
                metadata['columns'] += bool(columns)
                if len(blocks) > MAX_BLOCKS or words > MAX_WORDS:
                    metadata['layout_incomplete'] = True
                    break
                row_views, boxes, uncertain = _structured_rows(page, number)
                for view in row_views:
                    for block in view['blocks']:
                        block['page_size'] = [float(page.width), float(page.height)]
                structured.extend(row_views)
                table_boxes[number] = boxes
                metadata['layout_uncertain'] |= uncertain
                if uncertain and not boxes and not row_views:
                    metadata['layout_incomplete'] = True
                    break
            metadata['pages'] = len(document.pages)
            metadata['word_count'] = words
            if not metadata['layout_incomplete']:
                reconstructed = '\n'.join(item['text'] for item in blocks)
                if len(reconstructed) <= MAX_VIEW_CHARS:
                    metadata['text_layer_disordered'] = _order_disagrees(
                        primary_text, reconstructed)
                    metadata['layout_uncertain'] |= metadata['text_layer_disordered']
                    if include_structure:
                        views.append({'method': 'layout_geometry',
                                      'text': '\n'.join(block['text'] for block in geometry),
                                      'blocks': geometry, 'validation_safe': False,
                                      'incomplete': geometry_incomplete,
                                      'parser_input': False})
                    views.append({'method': 'pdfplumber', 'text': reconstructed,
                                  'blocks': blocks, 'validation_safe': True})
                    metadata['methods'].append('pdfplumber')
                    if metadata['text_layer_disordered']:
                        views[0]['validation_safe'] = False
                    if metadata['columns']:
                        # A flattened full-page view can falsely pair an employer
                        # in the left column with a role in the right column.
                        for column in ('left', 'right'):
                            scoped = [item for item in blocks
                                      if item['column'] in {column, 'wide'}]
                            views.append({
                                'method': f'pdfplumber_{column}',
                                'text': '\n'.join(item['text'] for item in scoped),
                                'blocks': scoped, 'validation_safe': True,
                            })
                        for view in views:
                            if view['method'] in {'primary', 'pdfplumber'}:
                                view['validation_safe'] = False
                    if structured or any(table_boxes.values()):
                        # Full-page strings erase row membership. Exclude them from
                        # validation while retaining them as parser/model input.
                        for view in views:
                            view['validation_safe'] = False
                        views.extend(structured)
                        for number in range(1, len(document.pages) + 1):
                            outside = [block for block in blocks if block['page'] == number
                                       and not any(_inside_box({
                                           'top': block['bbox'][1],
                                           'bottom': block['bbox'][3]}, box)
                                           for box in table_boxes[number])]
                            for column in ('left', 'right') if metadata['columns'] else ('wide',):
                                scoped = [block for block in outside if block['column'] in
                                          {column, 'wide'}]
                                if scoped:
                                    views.append({
                                        'method': f'pdfplumber_flow_p{number}_{column}',
                                        'text': '\n'.join(block['text'] for block in scoped),
                                        'blocks': scoped, 'validation_safe': True,
                                        'parser_input': False, 'page': number,
                                    })
                        metadata['table_rows'] = len(structured)
                        metadata['table_regions'] = sum(map(len, table_boxes.values()))
                else:
                    metadata['layout_incomplete'] = True
    except (PDFException, ValueError, OSError):
        metadata['layout_incomplete'] = True
    if poppler_text and len(poppler_text) <= MAX_VIEW_CHARS and poppler_text != primary_text:
        views.append({'method': 'poppler', 'text': poppler_text, 'blocks': [],
                      'validation_safe': not bool(metadata['columns'])
                      and not bool(metadata.get('table_regions'))
                      and not _order_disagrees(poppler_text,
                                               reconstructed or primary_text)})
        metadata['methods'].append('poppler')
    if metadata['layout_incomplete']:
        for view in views:
            view['validation_safe'] = False
    return views, metadata


def docx_view(text):
    # The DOCX reader has already preserved table rows with cell separators.
    blocks = [{'page': 1, 'bbox': None, 'column': 'table' if ' | ' in line else 'flow',
               'text': line} for line in text.splitlines() if line.strip()]
    return [{'method': 'docx', 'text': text, 'blocks': blocks}], {
        'methods': ['docx'], 'pages': None,
        'columns': 0, 'word_count': len(text.split()), 'layout_incomplete': False,
        'table_rows': sum(item['column'] == 'table' for item in blocks),
    }


def evidence_location(quote, view):
    """Keep only page/box references for exact quotes, never document excerpts."""
    if not quote:
        return None
    from .resume_understanding import normalized

    needle = normalized(quote)
    blocks = view.get('blocks', [])
    for block in blocks:
        if needle in normalized(block['text']):
            return {'method': view['method'], 'page': block['page'],
                    'bbox': block['bbox'], 'column': block['column'],
                    'entry_id': block.get('entry_id'),
                    'table_row': block.get('table_row')}
    for index, block in enumerate(blocks):
        neighbors = [item for item in blocks[index:index + 3]
                     if item['page'] == block['page']
                     and item['column'] == block['column']]
        if needle in normalized('\n'.join(item['text'] for item in neighbors)):
            return {'method': view['method'], 'page': block['page'],
                    'bbox': block['bbox'], 'column': block['column'],
                    'entry_id': block.get('entry_id'),
                    'table_row': block.get('table_row')}
    return {'method': view['method'], 'page': None, 'bbox': None, 'column': None,
            'entry_id': None, 'table_row': None}
