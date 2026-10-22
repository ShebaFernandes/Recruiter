import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def preserve_existing_acceptance_subjects(apps, schema_editor):
    LegalAcceptance = apps.get_model("talent", "LegalAcceptance")
    for acceptance in LegalAcceptance.objects.select_related("user").iterator():
        acceptance.subject_user_id = acceptance.user_id
        acceptance.subject_joined_at = acceptance.user.date_joined
        acceptance.save(update_fields=["subject_user_id", "subject_joined_at"])


class Migration(migrations.Migration):

    dependencies = [("talent", "0016_legal_review_evidence")]

    operations = [
        migrations.AddField(
            model_name="candidateprofile",
            name="registration_country_code",
            field=models.CharField(blank=True, max_length=2),
        ),
        migrations.AddField(
            model_name="candidateprofile",
            name="retention_transition_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inactivityreminder",
            name="deadline_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inactivityreminder",
            name="delivery_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="inactivityreminder",
            name="last_attempt_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inactivityreminder",
            name="last_error_code",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="inactivityreminder",
            name="next_attempt_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inactivityreminder",
            name="notice_kind",
            field=models.CharField(
                choices=[
                    ("inactivity", "Inactivity"),
                    ("transition", "Existing-account transition"),
                ],
                default="inactivity",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="legalacceptance",
            name="subject_user_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="legalacceptance",
            name="subject_joined_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="legalacceptance",
            name="account_closed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="legalacceptance",
            name="earliest_disposition_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            preserve_existing_acceptance_subjects,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="legalacceptance",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="deletionrequest",
            name="earliest_disposition_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
