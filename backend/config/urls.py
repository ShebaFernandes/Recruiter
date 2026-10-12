from django.contrib import admin
from django.urls import include, path
from talent.admin import protected_admin_login

urlpatterns = [
    path("admin/login/", protected_admin_login),
    path("admin/", admin.site.urls),
    path("api/v1/", include("talent.urls")),
]
