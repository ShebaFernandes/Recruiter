from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("talent", "0021_resume_ai_candidate_consent")]

    operations = [
        migrations.AddField(
            model_name="resumeaiusage",
            name="http_status",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="resumeaiusage",
            name="provider_error_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="resumeaiusage",
            name="provider_error_status",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
