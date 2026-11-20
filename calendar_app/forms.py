from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import CalendarShare, Event


class AccountCreationForm(UserCreationForm):
    email = forms.EmailField(required=False, help_text='Optional.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email address.')
        return email


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
    username = forms.CharField(max_length=254, label='Username or email')

    def clean_username(self):
        identifier = self.cleaned_data['username'].strip()
        if '@' in identifier:
            matches = User.objects.filter(email__iexact=identifier)
            if matches.count() == 1:
                return matches.first()
            if matches.count() > 1:
                raise forms.ValidationError('Multiple users have that email address. Use their username.')
            raise forms.ValidationError('No user exists with that email address.')
        try:
            return User.objects.get(username=identifier)
        except User.DoesNotExist:
            raise forms.ValidationError('No user exists with that username.')


class CalendarShareForm(forms.Form):
    username = forms.CharField(max_length=254, label='Username or email')
    permission = forms.ChoiceField(choices=CalendarShare.PERMISSION_CHOICES)

    def clean_username(self):
        identifier = self.cleaned_data['username'].strip()
        if '@' in identifier:
            matches = User.objects.filter(email__iexact=identifier)
            if matches.count() == 1:
                return matches.first()
            if matches.count() > 1:
                raise forms.ValidationError('Multiple users have that email address. Use their username.')
            raise forms.ValidationError('No user exists with that email address.')
        try:
            return User.objects.get(username=identifier)
        except User.DoesNotExist:
            raise forms.ValidationError('No user exists with that username.')