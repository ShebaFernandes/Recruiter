"""Intake gates affect HTTP requests only, never worker execution or stored records."""

from django.conf import settings
from django.http import JsonResponse


class LaunchControlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path.rstrip("/")
        recruiter_paths = (
            "/recruiter",
            "/api/v1/projects",
            "/api/v1/searches",
            "/api/v1/candidates",
            "/api/v1/notifications",
        )
        if settings.CANDIDATE_ONLY and any(
            path == prefix or path.startswith(prefix + "/") for prefix in recruiter_paths
        ):
            return JsonResponse({"detail": "Not found."}, status=404)
        paused = request.method == "POST" and (
            (settings.CANDIDATE_REGISTRATION_PAUSED and path == "/api/v1/auth/signup")
            or (
                settings.RESUME_UPLOADS_PAUSED
                and (
                    path == "/api/v1/candidate/resumes"
                    or (path.startswith("/api/v1/candidate/resumes/") and path.endswith("/retry"))
                )
            )
        )
        if paused:
            response = JsonResponse(
                {
                    "detail": "New submissions are temporarily paused. Please try later.",
                    "code": "intake_paused",
                },
                status=503,
            )
            response["Retry-After"] = "3600"
            response["Cache-Control"] = "no-store"
            return response
        return self.get_response(request)
