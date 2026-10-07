from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("health/ready/", views.readiness),
    path("auth/csrf/", views.csrf_token),
    path("auth/signup/", views.signup),
    path("auth/login/", views.login),
    path("auth/logout/", views.logout),
    path("auth/me/", views.me),
    path("auth/verify-email/", views.verify_email),
    path("auth/resend-verification/", views.resend_verification),
    path("auth/password-reset/request/", views.request_password_reset),
    path("auth/password-reset/confirm/", views.confirm_password_reset),
    path("candidate/account/", views.delete_candidate_account),
    path("candidate/profile/", views.candidate_profile),
    path("candidate/profile/submit/", views.submit_candidate_profile),
    path("candidate/resumes/", views.resume_upload),
    path(
        "candidate/resumes/<int:resume_id>/retry/",
        views.retry_resume_processing,
    ),
    path("resumes/<int:resume_id>/download/", views.resume_download),
    path("projects/", views.projects),
    path("projects/<int:project_id>/", views.project_detail),
    path("projects/<int:project_id>/candidates/", views.project_candidate),
    path(
        "projects/<int:project_id>/candidates/<int:candidate_id>/",
        views.project_candidate,
    ),
    path("searches/", views.searches),
    path("searches/<int:search_id>/answer/", views.search_answer),
    path("searches/<int:search_id>/results/", views.search_results),
    path("candidates/<int:candidate_id>/", views.candidate_detail),
    path("candidates/<int:candidate_id>/status/", views.candidate_status),
    path("candidates/compare/", views.candidate_compare),
    path("notifications/", views.notifications),
    path("notifications/<int:notification_id>/read/", views.notification_read),
]
