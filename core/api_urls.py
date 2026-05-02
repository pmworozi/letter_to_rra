from django.urls import path
from .views import generate_letter_api, save_profile

urlpatterns = [
    path('generate-letter/', generate_letter_api),
    path('save-profile/', save_profile),
]