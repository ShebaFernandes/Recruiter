from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("talent", "0017_retention_delivery_and_registration_country")]

    operations = [
        migrations.AddField(
            model_name="workexperience",
            name="confidence_status",
            field=models.CharField(
                choices=[
                    ("supported", "Supported by resume evidence"),
                    ("partial", "Some fields need candidate review"),
                    ("candidate_confirmed", "Confirmed by candidate"),
                ],
                default="partial",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="workexperience",
            name="employment_type",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="workexperience",
            name="is_current",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="workexperience",
            name="location",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="workexperience",
            name="source_evidence",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="ResumeAIUsage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attempt", models.PositiveSmallIntegerField()),
                ("provider", models.CharField(max_length=40)),
                ("model", models.CharField(max_length=120)),
                ("outcome", models.CharField(choices=[("reserved", "Reserved"), ("succeeded", "Succeeded"), ("failed", "Failed")], max_length=20)),
                ("failure_category", models.CharField(blank=True, max_length=40)),
                ("request_id", models.CharField(blank=True, max_length=180)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("estimated_cost_usd", models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                ("latency_ms", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("resume", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_usage", to="talent.resume")),
            ],
        ),
        migrations.AddConstraint(
            model_name="resumeaiusage",
            constraint=models.UniqueConstraint(fields=("resume", "attempt"), name="unique_resume_ai_attempt"),
        ),
        migrations.AddIndex(
            model_name="resumeaiusage",
            index=models.Index(fields=["created_at", "outcome"], name="resume_ai_created_outcome_idx"),
        ),
    ]
