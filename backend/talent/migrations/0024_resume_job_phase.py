from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("talent", "0023_preserve_resume_ai_budget_ledger")]

    operations = [
        migrations.AddField(
            model_name="resumeprocessingjob",
            name="phase",
            field=models.CharField(max_length=20, blank=True),
        ),
    ]
