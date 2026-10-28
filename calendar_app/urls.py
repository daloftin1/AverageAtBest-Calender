from django.urls import path

from .views import (
    add_event_view, calendar_view, edit_event_view, share_calendar_view,
    share_event_view, unshare_calendar_view, unshare_event_view,
)

urlpatterns = [
    path('', calendar_view, name='calendar'),
    path('add/', add_event_view, name='add_event'),
    path('events/<int:event_id>/edit/', edit_event_view, name='edit_event'),
    path('events/<int:event_id>/share/', share_event_view, name='share_event'),
    path('events/<int:event_id>/unshare/<int:user_id>/', unshare_event_view, name='unshare_event'),
    path('calendar/share/', share_calendar_view, name='share_calendar'),
    path('calendar/unshare/<int:share_id>/', unshare_calendar_view, name='unshare_calendar'),
]