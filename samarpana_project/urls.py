# samarpana_project/urls.py

from django.contrib import admin
from django.urls import path, include
from ticketing.views import CustomLoginView, CustomLogoutView
from django.conf import settings
from django.conf.urls.static import static
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

urlpatterns = [
    path('admin/', admin.site.urls),

    # Custom login/logout views to override defaults
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', CustomLogoutView.as_view(), name='logout'),

    # Include default auth URLs (password reset, password change, etc.)
    path('accounts/', include('django.contrib.auth.urls')),

    # Include your app URLs
    path('', include('ticketing.urls')),
]

print("Static files directory:", BASE_DIR / 'ticketing' / 'static')
print("Static url:", settings.STATIC_URL)


# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=BASE_DIR / 'ticketing' / 'static')

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)