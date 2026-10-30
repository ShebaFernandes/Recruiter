import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("talent", "0027_hiringenquiry_hiringenquiryattachment")]

    operations = [
        migrations.AddField(
            model_name="employeetransitionenquiry",
            name="contacted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="employeetransitionenquiry",
            name="follow_up_due_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="employeetransitionenquiry",
            name="internal_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="employeetransitionenquiry",
            name="status",
            field=models.CharField(
                choices=[
                    ("new", "New"), ("contacted", "Contacted"),
                    ("in_progress", "In progress"), ("closed", "Closed"),
                ],
                default="new", max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="employeetransitionenquiry",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="hiringenquiry",
            name="contacted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="hiringenquiry",
            name="follow_up_due_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="hiringenquiry",
            name="internal_note",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="EnquiryNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("available_at", models.DateTimeField(
                    db_index=True, default=django.utils.timezone.now,
                )),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=60)),
                ("hiring_enquiry", models.OneToOneField(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="alert", to="talent.hiringenquiry",
                )),
                ("transition_enquiry", models.OneToOneField(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="alert", to="talent.employeetransitionenquiry",
                )),
            ],
            options={"constraints": [models.CheckConstraint(
                condition=(
                    models.Q(hiring_enquiry__isnull=False, transition_enquiry__isnull=True)
                    | models.Q(hiring_enquiry__isnull=True, transition_enquiry__isnull=False)
                ),
                name="one_enquiry_per_notification",
            )]},
        ),
    ]
