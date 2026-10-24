from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("talent", "0019_resume_ai_usage_diagnostics")]

    operations = [
        migrations.AddField(
            model_name="resumeaiusage",
            name="reserved_input_tokens",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="resumeaiusage",
            name="validation_rejections",
            field=models.JSONField(default=list),
        ),
    ]
