from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("", admin.site.urls),  # FastAPI mounts this at /admin, so Django receives root path
]

# Note: Static files are served directly by FastAPI at /admin/static/
# No need to serve them through Django URLs
