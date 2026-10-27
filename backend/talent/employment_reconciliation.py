"""Merge validated resume employment without replacing candidate-owned rows."""

import re
import unicodedata

from .models import WorkExperience
from .services import parse_date


def normalized_text(value):
    value = unicodedata.normalize('NFKC', str(value or '')).casefold().replace('&', ' and ')
    return ' '.join(re.findall(r'\w+', value))


def same_employer(left, right):
    first, second = normalized_text(left), normalized_text(right)
    if first == second:
        return True
    shorter, longer = sorted((first, second), key=len)
    return bool(shorter and longer.startswith(shorter + ' ') and (
        len(shorter.split()) >= 2 or len(shorter) >= 5
    ))


def date_value(value):
    return parse_date(str(value)) if value else None


def same_month(left, right):
    return bool(left and right and left.year == right.year and left.month == right.month)


def precise_date(label, value):
    if not value:
        return False
    iso = value.isoformat()
    return iso in str(label or '') or bool(re.search(
        rf'\b{value.day:02d}[/.-]{value.month:02d}[/.-]{value.year}\b', str(label or '')
    ))


def dates_compatible(saved_date, saved_label, incoming_date, incoming_label):
    if not saved_date or not incoming_date:
        return True
    if not same_month(saved_date, incoming_date):
        return False
    if precise_date(saved_label, saved_date) and precise_date(incoming_label, incoming_date):
        return saved_date == incoming_date
    return True


def row_matches(saved, incoming):
    if not same_employer(saved.company, incoming.get('company')):
        return False
    if normalized_text(saved.role) != normalized_text(incoming.get('role')):
        return False
    start = date_value(incoming.get('start_date'))
    if (normalized_text(saved.company) != normalized_text(incoming.get('company'))
            and not same_month(saved.start_date, start)):
        return False
    return dates_compatible(saved.start_date, saved.date_label, start,
                            incoming.get('date_label'))


def row_equivalent(saved, incoming):
    if not row_matches(saved, incoming):
        return False
    start = date_value(incoming.get('start_date'))
    end = date_value(incoming.get('end_date'))
    if not dates_compatible(saved.start_date, saved.date_label, start,
                            incoming.get('date_label')):
        return False
    if not dates_compatible(saved.end_date, saved.date_label, end,
                            incoming.get('date_label')):
        return False
    if saved.end_date and not end and incoming.get('is_current'):
        return False
    if end and not saved.end_date and saved.is_current:
        return False
    return True


def trusted_rows(extracted):
    rows = extracted.get('work_experiences')
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)
            and row.get('company') and row.get('role') and row.get('source_evidence')
            and row.get('confidence_status') in {'supported', 'partial'}]


def reconcile_employment(profile, rows):
    """Return conflicts; omissions are retained and never become deletions."""
    saved = list(profile.work_experiences.all())
    matched = set()
    conflicts = []
    for item in rows:
        candidates = [(index, row) for index, row in enumerate(saved)
                      if index not in matched and row_matches(row, item)]
        if not candidates:
            # A candidate-corrected title for this same employer and stint is
            # protected, rather than duplicated as a second role.
            corrected = any(
                same_employer(row.company, item.get('company'))
                and same_month(row.start_date, date_value(item.get('start_date')))
                and (row.confidence_status == 'candidate_confirmed'
                     or normalized_text(row.role) == normalized_text(item.get('role')))
                for row in saved
            )
            if corrected:
                conflicts.append(item)
                continue
            # Same employer/title with a different start can be a distinct stint.
            row = WorkExperience(candidate=profile, company=item['company'], role=item['role'])
            for field in ('start_date', 'end_date'):
                setattr(row, field, date_value(item.get(field)))
            for field in ('is_current', 'date_label', 'employment_type', 'location',
                          'description', 'source_evidence', 'confidence_status', 'gap_reason'):
                setattr(row, field, item.get(field) or (False if field == 'is_current' else ''))
            row.save()
            saved.append(row)
            matched.add(len(saved) - 1)
            continue
        index, row = candidates[0]
        matched.add(index)
        if not row_equivalent(row, item):
            conflicts.append(item)
            continue
        # A candidate-confirmed row may contain a deliberate correction or an
        # intentionally blank field. Equivalent resume evidence verifies its
        # identity but must not silently rewrite the candidate's version.
        if row.confidence_status == 'candidate_confirmed':
            continue
        updates = []
        gained_precision = False
        # Fill missing facts, but keep candidate-entered text and precise dates.
        for field in ('start_date', 'end_date'):
            value = date_value(item.get(field))
            current = getattr(row, field)
            if value and (current is None or (
                same_month(current, value)
                and not precise_date(row.date_label, current)
                and precise_date(item.get('date_label'), value)
            )):
                gained_precision = gained_precision or bool(current)
                setattr(row, field, value)
                updates.append(field)
        if gained_precision and item.get('date_label'):
            row.date_label = item['date_label']
            updates.append('date_label')
        if not row.is_current and row.end_date is None and item.get('is_current'):
            row.is_current = True
            updates.append('is_current')
            if not row.date_label or 'end not specified' in row.date_label.casefold():
                row.date_label = item.get('date_label') or row.date_label
                updates.append('date_label')
        for field in (
            'date_label', 'employment_type', 'location', 'description', 'source_evidence'
        ):
            if not getattr(row, field) and item.get(field):
                setattr(row, field, item[field])
                updates.append(field)
        if updates:
            row.save(update_fields=list(set(updates)))
    return conflicts


def apply_reviewed_employment(profile, rows):
    """Apply only the candidate-selected conflicts, preserving all other rows."""
    for item in rows:
        row = next((saved for saved in profile.work_experiences.all()
                    if same_employer(saved.company, item.get('company'))
                    and same_month(saved.start_date, date_value(item.get('start_date')))), None)
        if row is None:
            reconcile_employment(profile, [item])
            continue
        fields = ['company', 'role', 'start_date', 'end_date', 'is_current', 'date_label',
                  'employment_type', 'location', 'description', 'source_evidence',
                  'confidence_status']
        for field in fields:
            value = date_value(item.get(field)) if field in {'start_date', 'end_date'} else (
                item.get(field) or (False if field == 'is_current' else '')
            )
            setattr(row, field, value)
        row.save(update_fields=fields)
