"""Candidate-owned, role-scoped corrections with explicit month/year precision."""

import re
from datetime import date

from rest_framework import serializers

from .models import WorkExperience


class YearMonthSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=1900, max_value=2100, allow_null=True)
    month = serializers.IntegerField(min_value=1, max_value=12, allow_null=True)

    def validate(self, attrs):
        if attrs["month"] is not None and attrs["year"] is None:
            raise serializers.ValidationError("Choose a year before choosing a month.")
        return attrs


class EmploymentEditSerializer(serializers.Serializer):
    company = serializers.CharField(max_length=180, required=False, allow_blank=False)
    role = serializers.CharField(max_length=180, required=False, allow_blank=False)
    start = YearMonthSerializer(required=False)
    end = YearMonthSerializer(required=False)
    is_current = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Choose a detail to update.")
        if attrs.get("is_current") and attrs.get("end", {}).get("year") is not None:
            raise serializers.ValidationError("A current role cannot have an end date.")
        return attrs


def _saved_label(row, side):
    labels = re.split(r"\s+[–—-]\s+", row.date_label or "", maxsplit=1)
    if len(labels) == 2:
        value = labels[0 if side == "start" else 1].strip()
        if value:
            return value
    value = getattr(row, f"{side}_date")
    if value:
        return value.strftime("%b %Y")
    return "Start not specified" if side == "start" else "End not specified"


def _date_and_label(value, side):
    year, month = value["year"], value["month"]
    if year is None:
        return None, "Start not specified" if side == "start" else "End not specified"
    if month is None:
        return None, str(year)
    return date(year, month, 1), date(year, month, 1).strftime("%b %Y")


def _year(value, label):
    if value:
        return value.year
    match = re.search(r"\b(?:19|20)\d{2}\b", label)
    return int(match.group()) if match else None


def apply_employment_edit(row: WorkExperience, data: dict) -> bool:
    """Update one active row; unchanged dates and their source precision stay untouched."""
    start_label = _saved_label(row, "start")
    end_label = _saved_label(row, "end")
    start_date, end_date = row.start_date, row.end_date
    current = data.get("is_current", row.is_current)
    if "start" in data:
        start_date, start_label = _date_and_label(data["start"], "start")
    if "end" in data:
        end_date, end_label = _date_and_label(data["end"], "end")
    if current:
        end_date, end_label = None, "Present"
    elif end_label.casefold() in {"present", "current", "now"}:
        end_label = "End not specified"

    start_year, end_year = _year(start_date, start_label), _year(end_date, end_label)
    if not current and start_year and end_year and (
        end_year < start_year or (
            end_year == start_year and start_date and end_date and end_date < start_date
        )
    ):
        raise serializers.ValidationError({"end": "End date must not be before start date."})

    updates = []
    for field, value in (
        ("company", data.get("company", row.company)),
        ("role", data.get("role", row.role)),
        ("start_date", start_date),
        ("end_date", end_date),
        ("is_current", current),
    ):
        if getattr(row, field) != value:
            setattr(row, field, value)
            updates.append(field)
    if "start" in data or "end" in data or "is_current" in data:
        label = f"{start_label} — {end_label}"
        if row.date_label != label:
            row.date_label = label
            updates.append("date_label")
    if not updates:
        return False
    row.origin = "candidate"
    row.confidence_status = WorkExperience.ConfidenceStatus.CANDIDATE_CONFIRMED
    row.save(update_fields=[*updates, "origin", "confidence_status"])
    return True
