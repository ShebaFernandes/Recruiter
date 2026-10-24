from django.db import migrations, models
from django.db.models import F


def preserve_confirmed_costs(apps, schema_editor):
    usage = apps.get_model("talent", "ResumeAIUsage")
    usage.objects.filter(outcome="succeeded").update(
        actual_cost_usd=F("estimated_cost_usd")
    )


class Migration(migrations.Migration):
    dependencies = [("talent", "0018_resume_ai_usage_and_work_evidence")]

    operations = [
        migrations.AddField(
            model_name="resumeaiusage",
            name="actual_cost_usd",
            field=models.DecimalField(
                blank=True, decimal_places=6, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="resumeaiusage",
            name="failure_stage",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="resumeaiusage",
            name="stop_reason",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.RunPython(preserve_confirmed_costs, migrations.RunPython.noop),
    ]
