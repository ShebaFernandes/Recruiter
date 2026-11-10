from .google_oauth import private


class GoogleOAuthPrivacyMiddleware:
    """Apply privacy headers to successful and rejected OAuth requests alike."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/v1/auth/google/"):
            private(response)
        return response
