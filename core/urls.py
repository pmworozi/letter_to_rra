from django.urls import path
from .views import home, my_letters, index

urlpatterns = [
    path('', home, name='home'),
    path('letters/', index, name='letters'),
    path('my-letters/', my_letters, name='my_letters'),
]