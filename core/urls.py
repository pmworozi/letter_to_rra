from django.urls import path
from .views import save_profile, generate_letter_api

urlpatterns = [
    path('generate-letter/', generate_letter_api),
    path('save-profile/', save_profile),
]