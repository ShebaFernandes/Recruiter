"""Rehearse production-to-public-pages schema upgrade with synthetic records."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


@pytest.mark.django_db(transaction=True)
def test_production_upgrade_preserves_candidate_and_confirmed_resume():
    production = ("talent", "0030_merge_candidate_and_website")
    release = ("talent", "0036_googlesignupevidence_publishedsignupdocument")
    executor = MigrationExecutor(connection)
    try:
        # Only the disposable test DB is rewound to construct production's schema.
        executor.migrate([("talent", "0025_archive_resume_employment")])
        executor = MigrationExecutor(connection)
        executor.migrate([production])
        apps = executor.loader.project_state([production]).apps
        user = apps.get_model("auth", "User").objects.create(username="synthetic-upgrade")
        profile = apps.get_model("talent", "CandidateProfile").objects.create(
            user_id=user.pk, full_name="Synthetic Upgrade", email="upgrade@example.test",
        )
        confirmed = timezone.now()
        resume = apps.get_model("talent", "Resume").objects.create(
            candidate_id=profile.pk, file="quarantine/synthetic-upgrade.pdf",
            original_name="synthetic-upgrade.pdf", version=1,
            file_sha256="a" * 64, ownership_confirmed_file_sha256="a" * 64,
            ownership_confirmed_at=confirmed, scan_status="clean",
            processing_status="completed", extracted_data={"synthetic": True},
        )
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan([release])
        assert not any(backwards for _, backwards in plan)
        assert [m.name for m, _ in plan] == [
            "0030_careerapplication", "0031_opportunityapplication",
            "0032_preserve_transition_contact_phone", "0033_merge_production_public_pages",
            "0034_googleoauthtransaction_externalidentity", "0035_login_identifier_uniqueness",
            "0036_googlesignupevidence_publishedsignupdocument",
        ]
        executor.migrate([release])
        apps = executor.loader.project_state([release]).apps
        saved = apps.get_model("talent", "Resume").objects.get(pk=resume.pk)
        assert saved.candidate_id == profile.pk
        assert saved.file.name == "quarantine/synthetic-upgrade.pdf"
        assert saved.file_sha256 == saved.ownership_confirmed_file_sha256 == "a" * 64
        assert saved.ownership_confirmed_at == confirmed
        assert saved.extracted_data == {"synthetic": True}
        assert saved.scan_status == "clean" and saved.processing_status == "completed"
        candidate = apps.get_model("talent", "CandidateProfile").objects.get(pk=profile.pk)
        assert candidate.email == "upgrade@example.test"
        application = apps.get_model("talent", "OpportunityApplication").objects.create(
            candidate_id=profile.pk, opportunity_id="backend-engineer", note="Synthetic",
        )
        assert application.candidate_id == profile.pk
        assert executor.loader.graph.leaf_nodes("talent") == [release]
    finally:
        MigrationExecutor(connection).migrate([release])
