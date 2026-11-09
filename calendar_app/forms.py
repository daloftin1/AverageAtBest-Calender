from django import forms
from django.contrib.auth.models import User

from .models import CalendarShare, Event


class EventForm(forms.ModelForm):
    profile = forms.ChoiceField(choices=[('', 'Choose a profile')] + Event.Profile.choices)

    def __init__(self, *args, fixed_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        if fixed_profile:
            self.fields['profile'].initial = fixed_profile
            self.fields['profile'].disabled = True
            self.fields['profile'].widget = forms.HiddenInput()

    class Meta:
        model = Event
        fields = ['title', 'profile', 'date', 'time', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(
                format='%H:%M',
                attrs={'type': 'time'}
            ),
        }


class EventShareForm(forms.Form):
    username = forms.CharField(max_length=150)

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError('No user exists with that username.')


class CalendarShareForm(forms.Form):
    username = forms.CharField(max_length=150)
    permission = forms.ChoiceField(choices=CalendarShare.PERMISSION_CHOICES)

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError('No user exists with that username.')