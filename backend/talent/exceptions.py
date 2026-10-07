from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None and isinstance(exc, Throttled):
        wait = max(1, int(exc.wait or 1))
        response.data = {
            "detail": f"Too many requests. Please try again in {wait} seconds.",
            "code": "rate_limited",
            "retry_after": wait,
        }
    return response
