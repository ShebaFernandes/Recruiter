"""Merge validated resume employment without replacing candidate-owned rows."""

import re
import unicodedata

from django.utils import timezone

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


def complete_employment_history(extracted):
    """Allow omission archiving only after two agreeing, complete observations."""
    parse = extracted.get('_employment_parse') or {}
    interpretation = extracted.get('_interpretation') or {}
    rows = trusted_rows(extracted)
    keys = parse.get('rule_role_keys') or []
    if (not parse.get('complete_for_archival') or extracted.get('_text_truncated')
            or len(rows) != len(keys) or not rows
            or interpretation.get('source') not in {'rules', 'ai', 'ai_cached'}):
        return False
    if (interpretation.get('source') == 'rules'
            and interpretation.get('reason') not in {
                'disabled', 'deterministic_reliable', 'candidate_permission_or_rollout_gate'
            }):
        return False
    # An oversized optional summary/detail is discarded by schema validation,
    # but says nothing about whether the employment list is complete. Any lost
    # required role or evidence fails the role-count and evidence checks below.
    if any(item.get('category', '').startswith('work_experience.')
           for item in extracted.get('_validation_rejections', [])
           if isinstance(item, dict)):
        return False
    unmatched = list(rows)
    for key in keys:
        if not isinstance(key, dict):
            return False
        rule = WorkExperience(
            company=key.get('company') or '', role=key.get('role') or '',
            start_date=date_value(key.get('start_date')),
            end_date=date_value(key.get('end_date')),
            is_current=bool(key.get('is_current')),
            date_label=key.get('date_label') or '',
        )
        index = next((i for i, row in enumerate(unmatched)
                      if row_equivalent(rule, row) and row_equivalent(
                          WorkExperience(
                              company=row['company'], role=row['role'],
                              start_date=date_value(row.get('start_date')),
                              end_date=date_value(row.get('end_date')),
                              is_current=bool(row.get('is_current')),
                              date_label=row.get('date_label') or '',
                          ), key
                      )), None)
        if index is None:
            return False
        unmatched.pop(index)
    return not unmatched


def archive_omitted_employment(profile, extracted, resume):
    """Archive omissions only after independently corroborated complete extraction."""
    if not complete_employment_history(extracted):
        return []
    rows = trusted_rows(extracted)
    archived = []
    for saved in profile.work_experiences.all():
        if any(row_equivalent(saved, item) for item in rows):
            continue
        # Origin, confidence and candidate corrections remain intact in private
        # history. Only active visibility changes when a later resume omits it.
        saved.archived_at = timezone.now()
        saved.archived_by_resume_id = resume.pk
        saved.save(update_fields=['archived_at', 'archived_by_resume_id'])
        archived.append(saved.pk)
    return archived


def reconcile_employment(profile, rows, *, complete=False):
    """Merge supported roles; complete replacements can supersede corrected rows."""
    saved = list(profile.work_experiences.all())
    matched = set()
    conflicts = []
    for item in rows:
        candidates = [(index, row) for index, row in enumerate(saved)
                      if index not in matched and row_matches(row, item)]
        if not candidates:
            archived = next((row for row in WorkExperience.all_objects.filter(
                candidate=profile, archived_at__isnull=False
            ) if row_equivalent(row, item)), None)
            if archived is not None:
                archived.archived_at = None
                archived.archived_by_resume_id = None
                archived.save(update_fields=['archived_at', 'archived_by_resume_id'])
                saved.append(archived)
                candidates = [(len(saved) - 1, archived)]
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
            if corrected and not complete:
                conflicts.append(item)
                continue
            # Same employer/title with a different start can be a distinct stint.
            row = WorkExperience(candidate=profile, company=item['company'], role=item['role'],
                                 origin='resume_derived')
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
            if complete:
                # Materially different dates/current status are a new supported
                # version. The former candidate correction is archived below.
                replacement = WorkExperience(
                    candidate=profile, company=item['company'], role=item['role'],
                    origin='resume_derived',
                )
                for field in ('start_date', 'end_date'):
                    setattr(replacement, field, date_value(item.get(field)))
                for field in ('is_current', 'date_label', 'employment_type', 'location',
                              'description', 'source_evidence', 'confidence_status', 'gap_reason'):
                    setattr(replacement, field, item.get(field) or (
                        False if field == 'is_current' else ''
                    ))
                replacement.save()
                saved.append(replacement)
                matched.add(len(saved) - 1)
            else:
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
