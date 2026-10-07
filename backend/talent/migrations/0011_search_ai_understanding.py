from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("talent", "0010_candidatestatus_talent_cand_recruit_da40b5_idx_and_more")]

    operations = [
        migrations.AddField(
            model_name="search",
            name="clarification_history",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="search",
            name="follow_up_options",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="search",
            name="understanding_model",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="search",
            name="understanding_source",
            field=models.CharField(default="deterministic", max_length=32),
        ),
    ]
