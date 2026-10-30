from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("talent", "0026_employeetransitionenquiry"),
    ]

    operations = [
        migrations.CreateModel(
            name="HiringEnquiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("hire", "Find Talent"), ("team", "Build My Team"), ("drive", "Plan My Drive"), ("founding", "Founding Team"), ("leadership", "Leadership")], max_length=20)),
                ("status", models.CharField(choices=[("new", "New"), ("contacted", "Contacted"), ("in_progress", "In progress"), ("closed", "Closed")], default="new", max_length=20)),
                ("company", models.CharField(max_length=180)),
                ("full_name", models.CharField(max_length=180)),
                ("work_email", models.EmailField(max_length=254)),
                ("details", models.JSONField(default=dict)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="HiringEnquiryAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(max_length=500, upload_to="")),
                ("original_filename", models.CharField(max_length=255)),
                ("size", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("enquiry", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="talent.hiringenquiry")),
            ],
        ),
    ]
