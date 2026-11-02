from datetime import date, timedelta

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
            'profile': 'work',
        })
        self.assertRedirects(response, reverse('calendar') + '?profile=all')
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


class CalendarProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('profile-owner')
        self.other = User.objects.create_user('profile-other')
        self.client.force_login(self.user)
        self.today = date.today()

    def event(self, profile='work', **kwargs):
        data = dict(user=self.user, profile=profile, title=profile + ' meeting', date=self.today)
        data.update(kwargs)
        return Event.objects.create(**data)

    def test_filter_includes_current_and_future_but_not_past_or_private(self):
        current = self.event()
        future = self.event(date=self.today + timedelta(days=40))
        self.event(date=self.today - timedelta(days=1))
        self.event('school')
        self.event(user=self.other)
        response = self.client.get(reverse('calendar'), {'profile': 'work'})
        self.assertEqual(response.context['today_events'], [current])
        self.assertEqual(response.context['upcoming_events'], [future])
        self.assertContains(response, 'aria-current="page"')

    def test_all_combines_profiles_and_shared_events_without_duplicates(self):
        own = self.event()
        shared = self.event('school', user=self.other)
        shared.shared_with.add(self.user)
        CalendarShare.objects.create(owner=self.other, viewer=self.user)
        personal = self.event('personal')
        response = self.client.get(reverse('calendar'), {'profile': 'all'})
        self.assertEqual({e.pk for e in response.context['events']}, {own.pk, shared.pk, personal.pk})
        self.assertEqual(len(response.context['events']), 3)
        school = self.client.get(reverse('calendar'), {'profile': 'school'})
        self.assertEqual(school.context['events'], [shared])
        self.assertNotIn(shared.pk, school.context['editable_event_ids'])

    def test_each_tab_assigns_profile_and_rejects_post_override(self):
        for profile in Event.Profile.values:
            response = self.client.post(reverse('add_event') + '?profile=' + profile, {
                'title': profile, 'date': self.today.isoformat(), 'profile': 'invalid',
            })
            self.assertRedirects(response, reverse('calendar') + '?profile=' + profile)
            self.assertEqual(Event.objects.get(title=profile).profile, profile)

    def test_all_requires_explicit_valid_profile(self):
        for profile in ['', 'all', 'invalid']:
            response = self.client.post(reverse('add_event') + '?profile=all', {
                'title': 'Choose me', 'date': self.today.isoformat(), 'profile': profile,
            })
            self.assertEqual(response.status_code, 200)
            self.assertIn('profile', response.context['form'].errors)
        self.assertFalse(Event.objects.exists())
        response = self.client.post(reverse('add_event') + '?profile=all', {
            'title': 'Chosen', 'date': self.today.isoformat(), 'profile': 'school',
        })
        self.assertRedirects(response, reverse('calendar') + '?profile=all')
        self.assertEqual(Event.objects.get().profile, 'school')

    def test_invalid_profile_falls_back_to_all(self):
        response = self.client.get(reverse('calendar'), {'profile': '<script>'})
        self.assertEqual(response.context['active_profile'], 'all')

    def test_marker_threshold_and_profile_filter(self):
        for count, profile in enumerate(['work', 'school', 'personal', 'work'], 1):
            self.event(profile)
            response = self.client.get(reverse('calendar'))
            cell = next(day for week in response.context['weeks'] for day in week if day['number'] == self.today.day)
            self.assertEqual(cell['count'], count)
            self.assertEqual(len(cell['markers']), min(count, 2))
            calendar_grid = response.content.decode().split('class="calendar-legend"')[0]
            self.assertEqual(calendar_grid.count('class="canon-event"'), 1 if count >= 3 else 0)
        response = self.client.get(reverse('calendar'), {'profile': 'work'})
        self.assertContains(response, 'class="canon-event"')
        self.assertEqual(len(response.context['events']), 2)

    def test_edit_preserves_category_and_allows_reassignment(self):
        event = self.event('work')
        response = self.client.get(reverse('edit_event', args=[event.pk]))
        self.assertEqual(response.context['form'].initial['profile'], 'work')
        response = self.client.post(reverse('edit_event', args=[event.pk]) + '?profile=all', {
            'title': 'Moved', 'date': self.today.isoformat(), 'profile': 'school',
        })
        self.assertRedirects(response, reverse('calendar') + '?profile=all')
        event.refresh_from_db()
        self.assertEqual(event.profile, 'school')


    def test_selected_day_shows_only_permitted_events_in_profile(self):
        chosen = self.event('work')
        self.event('school')
        self.event('work', date=self.today + timedelta(days=1))
        self.event('work', user=self.other)
        response = self.client.get(reverse('calendar'), {'profile': 'work', 'date': self.today.isoformat()})
        self.assertEqual(response.context['events'], [chosen])
        self.assertContains(response, 'Show today &amp; upcoming')
        self.assertContains(response, 'selected-day')

    def test_selected_past_day_and_empty_day(self):
        past = self.today - timedelta(days=5)
        event = self.event(date=past)
        response = self.client.get(reverse('calendar'), {'date': past.isoformat()})
        self.assertEqual(response.context['events'], [event])
        self.assertEqual(response.context['displayed_month'], past)
        empty = self.client.get(reverse('calendar'), {'date': (past - timedelta(days=1)).isoformat()})
        self.assertContains(empty, 'No events on this day in this profile.')

    def test_invalid_day_falls_back_to_agenda_and_links_keep_profile(self):
        response = self.client.get(reverse('calendar'), {'date': 'not-a-date', 'profile': 'school'})
        self.assertIsNone(response.context['selected_date'])
        self.assertContains(response, '?profile=school&amp;date=')


    def test_month_navigation_crosses_years_and_keeps_profile(self):
        response = self.client.get(reverse('calendar'), {'month': '2027-01', 'profile': 'work'})
        self.assertEqual(response.context['displayed_month'], date(2027, 1, 1))
        self.assertEqual(response.context['previous_month'], date(2026, 12, 1))
        self.assertEqual(response.context['next_month'], date(2027, 2, 1))
        self.assertContains(response, '?profile=work&amp;month=2026-12')
        self.assertContains(response, '?profile=school&amp;month=2027-01')

    def test_leap_month_markers_and_invalid_month(self):
        event = self.event(date=date(2028, 2, 29))
        response = self.client.get(reverse('calendar'), {'month': '2028-02'})
        cell = next(day for week in response.context['weeks'] for day in week if day['number'] == 29)
        self.assertEqual(cell['events'], [event])
        invalid = self.client.get(reverse('calendar'), {'month': '2026-13'})
        self.assertEqual(invalid.context['displayed_month'], self.today)
        for month in ['0001-01', '9999-12']:
            self.assertEqual(self.client.get(reverse('calendar'), {'month': month}).status_code, 200)


    def test_upcoming_canon_finds_nearest_visible_day_across_months(self):
        past = self.today - timedelta(days=1)
        future = self.today + timedelta(days=40)
        later = future + timedelta(days=1)
        for day in [past, future, later]:
            for profile in ['work', 'school', 'personal']:
                self.event(profile, date=day)
        for unused in range(3):
            self.event(date=self.today, user=self.other)
        response = self.client.get(reverse('calendar'), {'month': '2027-01'})
        self.assertEqual(response.context['upcoming_canon']['date'], future)
        self.assertEqual(response.context['upcoming_canon']['count'], 3)
        self.assertContains(response, 'Upcoming canon event')
        filtered = self.client.get(reverse('calendar'), {'profile': 'work'})
        self.assertEqual(filtered.context['upcoming_canon']['date'], future)
        self.assertEqual(filtered.context['upcoming_canon']['count'], 3)

    def test_upcoming_canon_counts_shared_event_once_and_includes_today(self):
        for unused in range(2):
            self.event()
        event = self.event(user=self.other)
        event.shared_with.add(self.user)
        CalendarShare.objects.create(owner=self.other, viewer=self.user)
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.context['upcoming_canon']['date'], self.today)
        self.assertEqual(response.context['upcoming_canon']['count'], 3)


    def test_canon_markers_visible_in_every_profile_without_mixing_agendas(self):
        for profile in ['work', 'school', 'personal']:
            self.event(profile)
        for profile in ['all', 'work', 'school', 'personal']:
            response = self.client.get(reverse('calendar'), {'profile': profile})
            cell = next(day for week in response.context['weeks'] for day in week if day['number'] == self.today.day)
            self.assertEqual(cell['count'], 3)
            self.assertEqual(set(cell['profiles']), {'work', 'school', 'personal'})
            self.assertEqual(response.context['upcoming_canon']['count'], 3)
            self.assertEqual(len(response.context['events']), 3 if profile == 'all' else 1)
            self.assertContains(response, '?profile=all&amp;date=' + self.today.isoformat())

    def test_normal_dots_stay_filtered_and_private_events_do_not_trigger_canon(self):
        self.event('work')
        self.event('school')
        self.event('personal', user=self.other)
        response = self.client.get(reverse('calendar'), {'profile': 'work'})
        cell = next(day for week in response.context['weeks'] for day in week if day['number'] == self.today.day)
        self.assertEqual(cell['count'], 1)
        self.assertIsNone(response.context['upcoming_canon'])
