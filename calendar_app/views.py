import calendar
from datetime import date
from collections import defaultdict
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.db.models import Count, Q
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CalendarShareForm, EventForm, EventShareForm
from .models import CalendarShare, Event

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Automatically log them in after sign-up
            return redirect('calendar')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def selected_profile(request):
    profile = request.GET.get('profile', 'all')
    return profile if profile in ['all', *Event.Profile.values] else 'all'


def calendar_url(profile):
    return reverse('calendar') + '?' + urlencode({'profile': profile})


@login_required(login_url='/accounts/login/')
def calendar_view(request):
    today = date.today()
    profile = selected_profile(request)
    try:
        selected_date = date.fromisoformat(request.GET.get('date', ''))
    except ValueError:
        selected_date = None
    try:
        requested_month = date.fromisoformat(request.GET.get('month', '') + '-01')
    except ValueError:
        requested_month = today
    displayed_month = selected_date or requested_month
    month_index = (displayed_month.year - 1) * 12 + displayed_month.month - 1
    previous_index = month_index - 1
    previous_month = date(previous_index // 12 + 1, previous_index % 12 + 1, 1) if previous_index >= 0 else None
    next_index = month_index + 1
    next_month = date(next_index // 12 + 1, next_index % 12 + 1, 1) if next_index < 9999 * 12 else None
    calendar_shares = CalendarShare.objects.filter(viewer=request.user).select_related('owner')
    visible = Event.objects.filter(
        Q(user=request.user) | Q(shared_with=request.user) |
        Q(user__in=calendar_shares.values('owner'))
    ).select_related('user').distinct()
    all_visible = visible
    upcoming_canon = (visible.filter(date__gte=today).values('date')
                      .annotate(count=Count('id', distinct=True))
                      .filter(count__gte=3).order_by('date').first())
    if upcoming_canon:
        upcoming_canon['profiles'] = sorted(set(
            visible.filter(date=upcoming_canon['date']).values_list('profile', flat=True)
        ))
    if profile != 'all':
        visible = visible.filter(profile=profile)
    events = list(visible.filter(date=selected_date).order_by('id') if selected_date
                  else visible.filter(date__gte=today).order_by('date', 'id'))
    month_events = all_visible.filter(date__year=displayed_month.year, date__month=displayed_month.month)
    editable_owners = {share.owner_id for share in calendar_shares if share.permission == CalendarShare.EDIT}
    editable_owners.add(request.user.id)
    by_date = defaultdict(list)
    for event in month_events:
        by_date[event.date].append(event)
    weeks = []
    for week in calendar.Calendar(firstweekday=6).monthdayscalendar(displayed_month.year, displayed_month.month):
        cells = []
        for day in week:
            cell_date = date(displayed_month.year, displayed_month.month, day) if day else None
            day_events = by_date[cell_date] if day else []
            if len(day_events) < 3 and profile != 'all':
                day_events = [event for event in day_events if event.profile == profile]
            cells.append({
                'date': cell_date, 'is_today': cell_date == today, 'selected': cell_date == selected_date and bool(day),
                'number': day, 'events': day_events, 'count': len(day_events),
                'markers': day_events[:2],
                'profiles': sorted({event.profile for event in day_events}),
                'summary': '; '.join(f'{event.get_profile_display()}: {event.title}' for event in day_events),
            })
        weeks.append(cells)
    return render(request, 'calendar.html', {
        'events': events,
        'editable_event_ids': [event.id for event in events if event.user_id in editable_owners],
        'incoming_calendar_shares': calendar_shares,
        'today': today, 'weeks': weeks, 'active_profile': profile,
        'selected_date': selected_date, 'displayed_month': displayed_month,
        'previous_month': previous_month, 'next_month': next_month,
        'upcoming_canon': upcoming_canon,
        'profile_label': dict(Event.Profile.choices).get(profile, 'All'),
        'profiles': [('work', 'Work'), ('school', 'School'), ('personal', 'Personal'), ('all', 'ALL')],
        'today_events': [event for event in events if event.date == today],
        'upcoming_events': [event for event in events if event.date > today],
    })


@login_required(login_url='/accounts/login/')
def add_event_view(request):
    profile = selected_profile(request)
    fixed_profile = profile if profile != 'all' else None
    form = EventForm(request.POST if request.method == 'POST' else None,
                     initial={'profile': fixed_profile or ''}, fixed_profile=fixed_profile)
    if request.method == 'POST' and form.is_valid():
        event = form.save(commit=False)
        event.user = request.user
        event.save()
        return redirect(calendar_url(profile))
    return render(request, 'add_event.html', {
        'form': form, 'active_profile': profile,
        'profile_label': dict(Event.Profile.choices).get(profile, 'All'),
    })


@login_required(login_url='/accounts/login/')
def edit_event_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    can_edit = event.user == request.user or CalendarShare.objects.filter(
        owner=event.user, viewer=request.user, permission=CalendarShare.EDIT
    ).exists()
    if not can_edit:
        return redirect('calendar')
    profile = selected_profile(request)
    form = EventForm(request.POST if request.method == 'POST' else None, instance=event)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect(calendar_url(profile))
    return render(request, 'add_event.html', {
        'form': form, 'editing': True, 'active_profile': profile,
    })


@login_required(login_url='/accounts/login/')
def share_event_view(request, event_id):
    event = get_object_or_404(Event, id=event_id, user=request.user)
    if request.method == 'POST':
        form = EventShareForm(request.POST)
        if form.is_valid():
            viewer = form.cleaned_data['username']
            if viewer == request.user:
                form.add_error('username', 'You cannot share an event with yourself.')
            else:
                event.shared_with.add(viewer)
                return redirect('share_event', event_id=event.id)
    else:
        form = EventShareForm()
    return render(request, 'share_event.html', {
        'event': event,
        'form': form,
        'shared_users': event.shared_with.all(),
    })


@login_required(login_url='/accounts/login/')
def unshare_event_view(request, event_id, user_id):
    event = get_object_or_404(Event, id=event_id, user=request.user)
    event.shared_with.remove(user_id)
    return redirect('share_event', event_id=event.id)


@login_required(login_url='/accounts/login/')
def share_calendar_view(request):
    if request.method == 'POST':
        form = CalendarShareForm(request.POST)
        if form.is_valid():
            viewer = form.cleaned_data['username']
            if viewer == request.user:
                form.add_error('username', 'You cannot share your calendar with yourself.')
            else:
                existing_share = CalendarShare.objects.filter(
                    owner=request.user, viewer=viewer
                ).first()
                if existing_share:
                    existing_share.permission = form.cleaned_data['permission']
                    existing_share.save()
                else:
                    CalendarShare.objects.create(
                        owner=request.user,
                        viewer=viewer,
                        permission=form.cleaned_data['permission'],
                    )
                return redirect('share_calendar')
    else:
        form = CalendarShareForm()
    return render(request, 'share_calendar.html', {
        'form': form,
        'shares': CalendarShare.objects.filter(owner=request.user),
    })


@login_required(login_url='/accounts/login/')
def unshare_calendar_view(request, share_id):
    share = get_object_or_404(CalendarShare, id=share_id, owner=request.user)
    share.delete()
    return redirect('share_calendar')
