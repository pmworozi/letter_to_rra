from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # UI routes (homepage, letters, etc.)
    path('', include('core.urls')),

    # API routes
    path('api/', include('core.api_urls')),
]