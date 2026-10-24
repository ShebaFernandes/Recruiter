from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("talent", "0020_resume_ai_validation_diagnostics")]

    operations = [
        migrations.AddField(
            model_name="resume",
            name="ai_processing_consent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="resume",
            name="ai_processing_consent_version",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="resume",
            name="ai_processing_consent_sha256",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
