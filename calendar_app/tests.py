import re
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from .holidays import us_holidays
from .models import CalendarShare, Event


class CalendarAuthenticationTests(TestCase):
    def test_calendar_requires_login(self):
        response = self.client.get(reverse('calendar'))
        self.assertRedirects(response, '/accounts/login/?next=/')

    def test_registration_creates_user_and_event_belongs_to_user(self):
        response = self.client.post(reverse('register'), {
            'username': 'calendar-user',
            'email': 'calendar-user@example.com',
            'password1': 'strong-calendar-pass-123',
            'password2': 'strong-calendar-pass-123',
        })
        self.assertRedirects(response, reverse('calendar'))

        user = User.objects.get(username='calendar-user')
        self.assertEqual(user.email, 'calendar-user@example.com')
        response = self.client.post(reverse('add_event'), {
            'title': 'My event',
            'date': '2026-11-01',
            'description': 'Private event',
            'profile': 'work',
        })
        self.assertRedirects(response, reverse('calendar') + '?profile=all')
        self.assertEqual(Event.objects.get().user, user)

    def test_registration_rejects_an_email_already_used_case_insensitively(self):
        User.objects.create_user(
            'existing-user', password='strong-calendar-pass-123',
            email='already-used@example.com',
        )

        response = self.client.post(reverse('register'), {
            'username': 'new-user',
            'email': 'ALREADY-USED@example.com',
            'password1': 'strong-calendar-pass-123',
            'password2': 'strong-calendar-pass-123',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An account already uses this email address.')
        self.assertFalse(User.objects.filter(username='new-user').exists())

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

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_calendar_can_be_shared_by_email_and_sends_notification(self):
        owner = User.objects.create_user(
            'owner', password='pass', email='owner@example.com'
        )
        viewer = User.objects.create_user(
            'viewer', password='pass', email='Viewer@example.com'
        )
        self.client.force_login(owner)

        response = self.client.post(reverse('share_calendar'), {
            'username': 'viewer@example.com',
            'permission': CalendarShare.READ,
        })

        self.assertRedirects(response, reverse('share_calendar'))
        self.assertTrue(CalendarShare.objects.filter(owner=owner, viewer=viewer).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['Viewer@example.com'])
        self.assertIn(reverse('calendar'), mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_event_can_be_shared_by_email_and_sends_notification(self):
        owner = User.objects.create_user(
            'owner', password='pass', email='owner@example.com'
        )
        viewer = User.objects.create_user(
            'viewer', password='pass', email='viewer@example.com'
        )
        event = Event.objects.create(
            user=owner, title='Shared event', date='2026-11-01'
        )
        self.client.force_login(owner)

        response = self.client.post(reverse('share_event', args=[event.id]), {
            'username': 'viewer@example.com',
        })

        self.assertRedirects(response, reverse('share_event', args=[event.id]))
        self.assertTrue(event.shared_with.filter(id=viewer.id).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Shared event', mail.outbox[0].body)

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


class CalendarReminderTests(TestCase):
    def test_reminder_controls_and_event_metadata_render_for_signed_in_user(self):
        user = User.objects.create_user('reminder-user')
        event = Event.objects.create(
            user=user, title='Timed event', date=date.today(), time='12:34:00',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('calendar'))

        self.assertContains(response, f'id="reminderPreferences" data-user-id="{user.pk}"')
        self.assertContains(response, '<input type="checkbox" id="enableNotifications">', html=True)
        for minutes in (5, 15, 30):
            self.assertContains(
                response, f'<option value="{minutes}">{minutes} minutes before</option>', html=True,
            )
        self.assertContains(response, '<option value="60" selected>60 minutes before</option>', html=True)
        self.assertContains(response, f'data-event-id="{event.pk}"')
        self.assertContains(response, 'data-event-time="12:34:00"')


class HolidayCalendarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('holiday-viewer')
        self.client.force_login(self.user)
        self.url = reverse('calendar')

    def test_federal_holidays_include_fixed_floating_and_observed_dates(self):
        for year, memorial_day, labor_day, thanksgiving in (
            (2026, 25, 7, 26),
            (2027, 31, 6, 25),
        ):
            with self.subTest(year=year):
                entries = us_holidays(date(year, 1, 1), date(year, 12, 31))
                names = {(entry.date, entry.title) for entry in entries}
                self.assertEqual(len(names), len(entries))
                for month, day, name in (
                    (1, 1, "New Year's Day"),
                    (5, memorial_day, 'Memorial Day'),
                    (6, 19, 'Juneteenth National Independence Day'),
                    (7, 4, 'Independence Day'),
                    (9, labor_day, 'Labor Day'),
                    (11, thanksgiving, 'Thanksgiving Day'),
                    (12, 25, 'Christmas Day'),
                ):
                    self.assertIn((date(year, month, day), name), names)
        entries = us_holidays(date(2026, 7, 3), date(2026, 7, 4))
        self.assertEqual([entry.title for entry in entries], [
            'Independence Day (observed)', 'Independence Day',
        ])
        entries = us_holidays(date(2021, 12, 31), date(2021, 12, 31))
        self.assertEqual([entry.title for entry in entries], ["New Year's Day (observed)"])

    def test_holidays_and_all_filters_render_expected_agenda_and_month(self):
        day = date(2026, 7, 4)
        Event.objects.create(user=self.user, title='Team meetup', date=day, profile='work')
        for profile in ('holidays', 'all', 'work', 'school', 'personal'):
            with self.subTest(profile=profile):
                response = self.client.get(self.url, {'profile': profile, 'date': day})
                self.assertContains(response, 'data-profile="holidays"')
                cell = next(
                    cell for week in response.context['weeks'] for cell in week if cell['date'] == day
                )
                if profile in ('holidays', 'all'):
                    self.assertContains(response, '<h3>Independence Day</h3>', html=True)
                    self.assertContains(response, 'July 4 · All day')
                    self.assertEqual(cell['holidays'], ['Independence Day'])
                else:
                    self.assertNotContains(response, 'Independence Day')
                    self.assertEqual(cell['holidays'], [])
                if profile in ('all', 'work'):
                    self.assertContains(response, 'Team meetup')
                else:
                    self.assertNotContains(response, 'Team meetup')
        self.assertEqual(Event.objects.count(), 1)

    def test_hide_preference_survives_reload_and_is_account_scoped(self):
        url = self.url + '?profile=all&date=2026-12-25'
        response = self.client.post(url, {'show_holidays': '0'}, follow=True)
        self.assertRedirects(response, url)
        self.assertNotContains(response, 'Christmas Day')
        self.assertNotContains(self.client.get(url), 'Christmas Day')
        self.assertContains(self.client.get(self.url, {
            'profile': 'holidays', 'date': '2026-12-25',
        }), 'Christmas Day')
        other_user = User.objects.create_user('other-holiday-viewer')
        self.client.force_login(other_user)
        self.assertContains(self.client.get(url), 'Christmas Day')
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(url), 'Christmas Day')
        self.assertContains(self.client.post(url, {'show_holidays': '1'}, follow=True), 'Christmas Day')

    def test_holiday_entries_have_no_actions_or_reminder_metadata(self):
        day = date(2026, 12, 25)
        response = self.client.get(self.url, {'profile': 'holidays', 'date': day})
        self.assertContains(response, 'Christmas Day')
        self.assertNotContains(response, 'aria-label="Edit event:')
        self.assertNotContains(response, 'aria-label="Share event:')
        self.assertNotContains(response, 'data-event-id=')
        self.assertNotContains(response, 'data-event-time=')
        self.assertNotContains(response, '>Add event</a>')
        self.assertFalse(Event.objects.exists())


    def test_all_keeps_reminder_metadata_only_on_timed_personal_event(self):
        day = date(2026, 12, 25)
        event = Event.objects.create(
            user=self.user, title='Family dinner', profile=Event.Profile.PERSONAL,
            date=day, time='18:30:00',
        )

        response = self.client.get(self.url, {'profile': 'all', 'date': day})

        self.assertEqual(response.status_code, 200)
        cards = re.findall(r'<article\b([^>]*)>(.*?)</article>', response.content.decode(), re.S)
        holiday_cards = [attrs for attrs, body in cards if '<h3>Christmas Day</h3>' in body]
        self.assertEqual(len(holiday_cards), 1)
        for attribute in ('data-event-id', 'data-event-date', 'data-event-time'):
            self.assertNotIn(attribute, holiday_cards[0])
        reminder_cards = [(attrs, body) for attrs, body in cards if 'data-event-id=' in attrs]
        self.assertEqual(len(reminder_cards), 1)
        attrs, body = reminder_cards[0]
        self.assertIn('<h3>Family dinner</h3>', body)
        self.assertIn(f'data-event-id="{event.pk}"', attrs)
        self.assertIn('data-event-date="2026-12-25"', attrs)
        self.assertIn('data-event-time="18:30:00"', attrs)
