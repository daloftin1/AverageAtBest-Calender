from django.urls import path
from .views import add_event_view, calendar_view

urlpatterns = [
    path('', calendar_view, name='calendar'),
    path('add/', add_event_view, name='add_event'),
]