from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import CalendarShare, Event


class CalendarAuthenticationTests(TestCase):
    def test_calendar_requires_login(self):
        response = self.client.get(reverse('calendar'))
        self.assertRedirects(response, '/accounts/login/?next=/')

    def test_registration_creates_user_and_event_belongs_to_user(self):
        response = self.client.post(reverse('register'), {
            'username': 'calendar-user',
            'password1': 'strong-calendar-pass-123',
            'password2': 'strong-calendar-pass-123',
        })
        self.assertRedirects(response, reverse('calendar'))

        user = User.objects.get(username='calendar-user')
        response = self.client.post(reverse('add_event'), {
            'title': 'My event',
            'date': '2026-11-01',
            'description': 'Private event',
        })
        self.assertRedirects(response, reverse('calendar'))
        self.assertEqual(Event.objects.get().user, user)

    def test_users_only_see_their_own_events(self):
        first = User.objects.create_user('first', password='strong-pass-123')
        second = User.objects.create_user('second', password='strong-pass-123')
        Event.objects.create(user=first, title='First event', date='2026-11-01')
        Event.objects.create(user=second, title='Second event', date='2026-11-02')

        self.client.force_login(first)
        response = self.client.get(reverse('calendar'))
        self.assertContains(response, 'First event')
        self.assertNotContains(response, 'Second event')

    def test_individual_event_can_be_shared(self):
        owner = User.objects.create_user('owner', password='pass')
        viewer = User.objects.create_user('viewer', password='pass')
        event = Event.objects.create(user=owner, title='Shared event', date='2026-11-01')
        event.shared_with.add(viewer)

        self.client.force_login(viewer)
        response = self.client.get(reverse('calendar'))
        self.assertContains(response, 'Shared event')

    def test_calendar_edit_permission_is_enforced(self):
        owner = User.objects.create_user('owner', password='pass')
        viewer = User.objects.create_user('viewer', password='pass')
        event = Event.objects.create(user=owner, title='Owner event', date='2026-11-01')
        CalendarShare.objects.create(
            owner=owner, viewer=viewer, permission=CalendarShare.READ
        )

        self.client.force_login(viewer)
        response = self.client.get(reverse('edit_event', args=[event.id]))
        self.assertRedirects(response, reverse('calendar'))

        share = CalendarShare.objects.get(owner=owner, viewer=viewer)
        share.permission = CalendarShare.EDIT
        share.save()
        response = self.client.get(reverse('edit_event', args=[event.id]))
        self.assertEqual(response.status_code, 200)
