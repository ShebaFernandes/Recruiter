from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("talent", "0007_clean_synthetic_candidate_display_names")]

    operations = [
        migrations.AddField(
            model_name="workexperience",
            name="gap_reason",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AlterField(
            model_name="candidatestatus",
            name="status",
            field=models.CharField(
                choices=[
                    ("sourced", "Sourced"),
                    ("shortlisted", "Shortlisted"),
                    ("contacted", "Contacted"),
                    ("screening", "Screening"),
                    ("interviewing", "Interviewing"),
                    ("offered", "Offered"),
                    ("rejected", "Rejected"),
                    ("non_relevant", "Not relevant"),
                    ("hired", "Hired"),
                ],
                max_length=30,
            ),
        ),
    ]
