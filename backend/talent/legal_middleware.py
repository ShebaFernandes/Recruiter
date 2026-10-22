from django.conf import settings
from django.http import JsonResponse


class LocalLegalPreviewMiddleware:
    """Unpublished review is only available through a direct loopback connection."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if str(settings.DATABASES["default"]["NAME"]).startswith("enter_restore_"):
            return JsonResponse(
                {"detail": "Isolated recovery database: HTTP access disabled."}, status=503
            )
        if settings.LEGAL_WORKFLOW_PREVIEW and (
            request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}
            or request.META.get("HTTP_X_FORWARDED_FOR")
            or request.META.get("HTTP_FORWARDED")
        ):
            return JsonResponse({"detail": "Unpublished review is local only."}, status=403)
        return self.get_response(request)
