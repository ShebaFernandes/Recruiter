import re

from django.db import migrations


def clean_synthetic_candidate_names(apps, schema_editor):
    candidate_profile = apps.get_model("talent", "CandidateProfile")
    profiles = candidate_profile.objects.select_related("user").filter(
        user__email__startswith="seed-",
        user__email__endswith="@example.com",
    )
    for profile in profiles.iterator():
        cleaned = re.sub(r"\s+\d{13}$", "", profile.full_name).strip()
        if cleaned and cleaned != profile.full_name:
            profile.full_name = cleaned
            profile.save(update_fields=["full_name"])


class Migration(migrations.Migration):
    dependencies = [("talent", "0006_candidateupdatenotification_change_type_and_more")]

    operations = [migrations.RunPython(clean_synthetic_candidate_names, migrations.RunPython.noop)]
