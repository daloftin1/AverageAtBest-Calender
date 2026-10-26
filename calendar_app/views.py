import calendar
from datetime import date

from django.shortcuts import render

from .models import Event


# Shows upcoming events and a small calendar for the current month.
def calendar_view(request):
    today = date.today()
    events = Event.objects.filter(date__gte=today).order_by('date')
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(today.year, today.month)

    return render(request, 'calendar.html', {
        'today': today,
        'events': events,
        'weeks': weeks,
    })
