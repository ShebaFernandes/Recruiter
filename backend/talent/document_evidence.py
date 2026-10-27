"""Bounded, traceable text views of a private resume document.

Each method is kept separate. A role must be supported within one view; text from
different columns or extractors is never spliced into a synthetic quotation.
"""

from io import BytesIO

import pdfplumber
from pdfminer.pdfexceptions import PDFException

MAX_VIEW_CHARS = 50_000
MAX_BLOCKS = 600
MAX_WORDS = 6_000


def _box(value):
    return [round(float(part), 1) for part in value[:4]]


def _positioned_lines(page, page_number):
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
                    previous['x1'] < midpoint and word['x0'] > midpoint
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


def pdf_views(file_obj, primary_text, poppler_text=''):
    """Return separate pdfplumber and Poppler views plus safe layout metadata."""
    file_obj.seek(0)
    payload = file_obj.read(8 * 1024 * 1024 + 1)
    if len(payload) > 8 * 1024 * 1024:
        return [], {'methods': ['primary'], 'layout_incomplete': True}
    views = [{'method': 'primary', 'text': primary_text, 'blocks': [],
              'validation_safe': True}]
    metadata = {'methods': ['primary'], 'pages': 0, 'columns': 0,
                'word_count': 0, 'layout_incomplete': False}
    try:
        with pdfplumber.open(BytesIO(payload)) as document:
            if len(document.pages) > 100:
                return [], {**metadata, 'layout_incomplete': True}
            blocks = []
            words = 0
            for number, page in enumerate(document.pages, start=1):
                ordered, columns, page_words = _ordered_blocks(page, number)
                words += page_words
                blocks.extend(ordered)
                metadata['columns'] += bool(columns)
                if len(blocks) > MAX_BLOCKS or words > MAX_WORDS:
                    metadata['layout_incomplete'] = True
                    break
            metadata['pages'] = len(document.pages)
            metadata['word_count'] = words
            if not metadata['layout_incomplete']:
                reconstructed = '\n'.join(item['text'] for item in blocks)
                if len(reconstructed) <= MAX_VIEW_CHARS:
                    views.append({'method': 'pdfplumber', 'text': reconstructed,
                                  'blocks': blocks, 'validation_safe': True})
                    metadata['methods'].append('pdfplumber')
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
                else:
                    metadata['layout_incomplete'] = True
    except (PDFException, ValueError, OSError):
        metadata['layout_incomplete'] = True
    if poppler_text and len(poppler_text) <= MAX_VIEW_CHARS and poppler_text != primary_text:
        views.append({'method': 'poppler', 'text': poppler_text, 'blocks': [],
                      'validation_safe': not bool(metadata['columns'])})
        metadata['methods'].append('poppler')
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
                    'bbox': block['bbox'], 'column': block['column']}
    for index, block in enumerate(blocks):
        neighbors = [item for item in blocks[index:index + 3]
                     if item['page'] == block['page']
                     and item['column'] == block['column']]
        if needle in normalized('\n'.join(item['text'] for item in neighbors)):
            return {'method': view['method'], 'page': block['page'],
                    'bbox': block['bbox'], 'column': block['column']}
    return {'method': view['method'], 'page': None, 'bbox': None, 'column': None}
