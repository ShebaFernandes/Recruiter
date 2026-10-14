import django.db.models.deletion
from django.db import migrations, models

import talent.models


class Migration(migrations.Migration):
    dependencies = [("talent", "0013_candidate_career_preferences")]

    operations = [
        migrations.AddField(
            model_name="candidateprofile",
            name="build_lead_preference",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="CandidatePhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to=talent.models.candidate_photo_path)),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=40)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("candidate", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                    related_name="photo",
                                                    to="talent.candidateprofile")),
            ],
        ),
    ]
