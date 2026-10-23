"""Print immutable legal release evidence without changing application state."""

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import ValidationError

from talent import legal


class Command(BaseCommand):
    help = "Validate exact public legal text and print versions plus SHA-256 values."

    def handle(self, *args, **options):
        root = Path(settings.LEGAL_DOCUMENT_ROOT)
        try:
            privacy = legal._published_text(root / "PRIVACY_POLICY_PUBLICATION.txt")
            terms = legal._published_text(root / "TERMS_PUBLICATION.txt")
        except (OSError, ValidationError) as error:
            raise CommandError("Legal documents are not publication-ready.") from error

        fixed = {
            "age": "I confirm that I am at least 18 years old.",
            "submission": (
                "I confirm that I have reviewed my profile and ask ENTER to save it as "
                "submitted. Recruiter access is currently disabled. ENTER will ask for my "
                "separate, explicit permission before sharing my profile or resume with "
                "approved recruiters."
            ),
        }
        texts = {"privacy": privacy, "terms": terms, **fixed}
        versions = {
            purpose: getattr(settings, f"LEGAL_{purpose.upper()}_VERSION")
            for purpose in texts
        }
        manifest = {
            purpose: {
                "version": versions[purpose],
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
            for purpose, text in texts.items()
        }
        self.stdout.write(json.dumps(manifest, sort_keys=True, indent=2))
