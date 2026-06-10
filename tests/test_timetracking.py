from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import date, time, timedelta
from trackable.profiles.models import Profile
from trackable.timetracking.models import TimeEntry
from trackable.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class TimeEntryModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.profile = Profile.objects.create(
            user=self.user,
            title="Software Developer",
            position="Senior Developer",
            weekly_hours=40,
            hourly_rate=75.50,
        )

    def test_create_time_entry(self):
        entry = TimeEntry.objects.create(
            profile=self.profile,
            date=date.today(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            pause_duration=1,
        )

        self.assertEqual(entry.profile, self.profile)
        self.assertEqual(entry.hours_worked, 7)

    def test_hours_calculation_no_pause(self):
        entry = TimeEntry.objects.create(
            profile=self.profile,
            date=date.today(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            pause_duration=0,
        )

        self.assertEqual(entry.hours_worked, 8)

    def test_hours_calculation_with_pause(self):
        entry = TimeEntry.objects.create(
            profile=self.profile,
            date=date.today(),
            start_time=time(9, 0),
            end_time=time(17, 30),
            pause_duration=1.5,
        )

        self.assertEqual(entry.hours_worked, 7)

    def test_cross_day_calculation(self):
        entry = TimeEntry.objects.create(
            profile=self.profile,
            date=date.today(),
            start_time=time(22, 0),
            end_time=time(2, 0),
            pause_duration=0,
        )

        self.assertEqual(entry.hours_worked, 4)


class TimeEntryViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.profile = Profile.objects.create(
            user=self.user,
            title="Software Developer",
            position="Senior Developer",
            weekly_hours=40,
            hourly_rate=75.50,
        )
        self.client.login(username="testuser", password="testpass123")

    def test_add_time_entry(self):
        response = self.client.post(
            reverse("add_entry", kwargs={"profile_id": self.profile.pk}),
            {
                "date": date.today(),
                "start_time": "09:00",
                "end_time": "17:00",
                "pause_duration": 1,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(TimeEntry.objects.filter(profile=self.profile).exists())

    def test_monthly_table(self):
        today = date.today()
        TimeEntry.objects.create(
            profile=self.profile,
            date=today,
            start_time=time(9, 0),
            end_time=time(17, 0),
            pause_duration=1,
        )

        response = self.client.get(
            reverse(
                "monthly_table",
                kwargs={
                    "profile_id": self.profile.pk,
                    "year": today.year,
                    "month": today.month,
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Working hours")

    def test_pdf_export(self):
        today = date.today()
        TimeEntry.objects.create(
            profile=self.profile,
            date=today,
            start_time=time(9, 0),
            end_time=time(17, 0),
            pause_duration=1,
        )

        response = self.client.get(
            reverse(
                "export_pdf",
                kwargs={
                    "profile_id": self.profile.pk,
                    "year": today.year,
                    "month": today.month,
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")


class TimerOnlyBlockingTest(TestCase):
    """Tests for timer-only mode blocking manual entries."""

    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pass123"
        )
        self.org = Organization.objects.create(
            name="Acme Corp", created_by=self.manager
        )
        self.membership = OrganizationMembership.objects.create(
            organization=self.org, user=self.manager, role="manager"
        )
        self.org.timer_only_mode = True
        self.org.save()

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role="employee"
        )
        self.profile = Profile.objects.create(
            user=self.user,
            title="Software Developer",
            position="Senior Developer",
            weekly_hours=40,
            hourly_rate=75.50,
        )
        self.client.login(username="testuser", password="testpass123")

    def test_add_entry_blocked_in_timer_mode(self):
        """Manual add_entry is blocked when timer-only mode is active."""
        response = self.client.post(
            reverse("add_entry", kwargs={"profile_id": self.profile.pk}),
            {
                "date": date.today(),
                "start_time": "09:00",
                "end_time": "17:00",
                "pause_duration": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # No entry was created
        self.assertFalse(TimeEntry.objects.filter(profile=self.profile).exists())

    def test_edit_entry_blocked_in_timer_mode(self):
        """Edit entry is blocked when timer-only mode is active."""
        entry = TimeEntry.objects.create(
            profile=self.profile,
            date=date.today(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            pause_duration=1,
        )
        response = self.client.post(
            reverse("edit_entry", kwargs={"pk": entry.pk}),
            {
                "date": date.today(),
                "start_time": "10:00",
                "end_time": "18:00",
                "pause_duration": 0.5,
            },
        )
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.start_time, time(9, 0))  # unchanged

    def test_add_entry_works_when_timer_mode_off(self):
        """Manual add_entry works when timer-only mode is off."""
        self.org.timer_only_mode = False
        self.org.save()

        response = self.client.post(
            reverse("add_entry", kwargs={"profile_id": self.profile.pk}),
            {
                "date": date.today(),
                "start_time": "09:00",
                "end_time": "17:00",
                "pause_duration": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TimeEntry.objects.filter(profile=self.profile).exists())

    def test_home_hides_add_time_in_timer_mode(self):
        """Home page does not show 'Add time' button in timer-only mode."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Add time")

    def test_home_shows_add_time_when_timer_mode_off(self):
        """Home page shows 'Add time' button when timer-only mode is off."""
        self.org.timer_only_mode = False
        self.org.save()

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add time")

    def test_monthly_table_hides_actions_in_timer_mode(self):
        """Monthly table does not show Edit/Delete in timer-only mode."""
        today = date.today()
        TimeEntry.objects.create(
            profile=self.profile,
            date=today,
            start_time=time(9, 0),
            end_time=time(17, 0),
            pause_duration=1,
        )
        response = self.client.get(
            reverse(
                "monthly_table",
                kwargs={
                    "profile_id": self.profile.pk,
                    "year": today.year,
                    "month": today.month,
                },
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Edit")
        self.assertNotContains(response, "Delete")

    def test_monthly_table_shows_actions_when_timer_mode_off(self):
        """Monthly table shows Edit/Delete when timer-only mode is off."""
        self.org.timer_only_mode = False
        self.org.save()

        today = date.today()
        TimeEntry.objects.create(
            profile=self.profile,
            date=today,
            start_time=time(9, 0),
            end_time=time(17, 0),
            pause_duration=1,
        )
        response = self.client.get(
            reverse(
                "monthly_table",
                kwargs={
                    "profile_id": self.profile.pk,
                    "year": today.year,
                    "month": today.month,
                },
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit")

