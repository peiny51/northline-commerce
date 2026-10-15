from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("backend.catalog.urls")),
    path("api/", include("backend.orders.urls")),
    path("api/", include("backend.support.urls")),
]
