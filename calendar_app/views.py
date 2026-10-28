from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
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

@login_required(login_url='/accounts/login/')
def calendar_view(request):
    events = []
    added_event_ids = set()

    owned_events = Event.objects.filter(user=request.user)
    individually_shared_events = Event.objects.filter(shared_with=request.user)
    calendar_shares = CalendarShare.objects.filter(viewer=request.user)

    for event in owned_events:
        events.append(event)
        added_event_ids.add(event.id)

    for event in individually_shared_events:
        if event.id not in added_event_ids:
            events.append(event)
            added_event_ids.add(event.id)

    for share in calendar_shares:
        for event in Event.objects.filter(user=share.owner):
            if event.id not in added_event_ids:
                events.append(event)
                added_event_ids.add(event.id)

    events.sort(key=lambda event: event.date)

    editable_event_ids = []
    if owned_events:
        editable_event_ids.extend([event.id for event in owned_events])
    for share in calendar_shares:
        if share.permission == CalendarShare.EDIT:
            for event in Event.objects.filter(user=share.owner):
                editable_event_ids.append(event.id)

    return render(request, 'calendar.html', {
        'events': events,
        'editable_event_ids': editable_event_ids,
        'incoming_calendar_shares': calendar_shares,
    })

@login_required(login_url='/accounts/login/')
def add_event_view(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user  # Link event to current user
            event.save()
            return redirect('calendar')
    else:
        form = EventForm()
    return render(request, 'add_event.html', {'form': form})


@login_required(login_url='/accounts/login/')
def edit_event_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    can_edit = event.user == request.user or CalendarShare.objects.filter(
        owner=event.user, viewer=request.user, permission=CalendarShare.EDIT
    ).exists()
    if not can_edit:
        return redirect('calendar')

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            return redirect('calendar')
    else:
        form = EventForm(instance=event)
    return render(request, 'add_event.html', {'form': form, 'editing': True})


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