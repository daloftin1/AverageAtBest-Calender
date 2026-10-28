from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from .models import Event
from .forms import EventForm

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
    # Only fetch events belonging to the currently logged-in user
    events = Event.objects.filter(user=request.user).order_by('date')
    return render(request, 'calendar.html', {'events': events})

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