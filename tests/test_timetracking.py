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


class TimeTrackingModeTest(TestCase):
    """Tests for time-tracking mode (classic/restricted) blocking manual entries for employees."""

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
        self.org.time_tracking_mode = "restricted"
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
        """Manual add_entry is blocked for employees when mode is restricted."""
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
        """Edit entry is blocked for employees when mode is restricted."""
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
        """Manual add_entry works when mode is classic."""
        self.org.time_tracking_mode = "classic"
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
        """Home page does not show 'Add time' button for employees in restricted mode."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Add time")

    def test_home_shows_add_time_when_timer_mode_off(self):
        """Home page shows 'Add time' button when mode is classic."""
        self.org.time_tracking_mode = "classic"
        self.org.save()

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add time")

    def test_monthly_table_hides_actions_in_timer_mode(self):
        """Monthly table hides Edit/Delete for employees in restricted mode."""
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
        """Monthly table shows Edit/Delete when mode is classic."""
        self.org.time_tracking_mode = "classic"
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

    def test_manager_can_add_in_restricted_mode(self):
        """Manager can add entries even in restricted mode."""
        self.client.login(username="manager", password="pass123")
        # Manager needs own profile for add_entry
        mgr_profile = Profile.objects.create(
            user=self.manager,
            title="Manager Profile",
            position="Boss",
            weekly_hours=40,
            hourly_rate=100,
        )
        response = self.client.post(
            reverse("add_entry", kwargs={"profile_id": mgr_profile.pk}),
            {
                "date": date.today(),
                "start_time": "09:00",
                "end_time": "17:00",
                "pause_duration": 0.5,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TimeEntry.objects.filter(profile=mgr_profile).exists())

    def test_manager_can_edit_in_restricted_mode(self):
        """Manager can edit entries even in restricted mode."""
        self.client.login(username="manager", password="pass123")
        mgr_profile = Profile.objects.create(
            user=self.manager,
            title="Manager Profile",
            position="Boss",
            weekly_hours=40,
            hourly_rate=100,
        )
        entry = TimeEntry.objects.create(
            profile=mgr_profile,
            date=date.today(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            pause_duration=0.5,
        )
        response = self.client.post(
            reverse("edit_entry", kwargs={"pk": entry.pk}),
            {
                "date": date.today(),
                "start_time": "10:00",
                "end_time": "18:00",
                "pause_duration": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.start_time, time(10, 0))

    def test_home_shows_add_time_for_manager_in_restricted_mode(self):
        """Home page shows 'Add time' for manager even in restricted mode."""
        self.client.login(username="manager", password="pass123")
        mgr_profile = Profile.objects.create(
            user=self.manager,
            title="Manager Profile",
            position="Boss",
            weekly_hours=40,
            hourly_rate=100,
        )
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add time")

    def test_monthly_table_shows_actions_for_manager_in_restricted_mode(self):
        """Monthly table shows Edit/Delete for manager even in restricted mode."""
        self.client.login(username="manager", password="pass123")
        mgr_profile = Profile.objects.create(
            user=self.manager,
            title="Manager Profile",
            position="Boss",
            weekly_hours=40,
            hourly_rate=100,
        )
        today = date.today()
        TimeEntry.objects.create(
            profile=mgr_profile,
            date=today,
            start_time=time(9, 0),
            end_time=time(17, 0),
            pause_duration=0.5,
        )
        response = self.client.get(
            reverse(
                "monthly_table",
                kwargs={
                    "profile_id": mgr_profile.pk,
                    "year": today.year,
                    "month": today.month,
                },
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit")


class TimerAPITest(TestCase):
    """Tests for the timer API endpoints (start, pause, resume, stop, status)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="timeruser", email="timer@example.com", password="testpass123"
        )
        self.profile = Profile.objects.create(
            user=self.user,
            title="Timer Profile",
            position="Tester",
            weekly_hours=40,
            hourly_rate=50,
        )
        self.client.login(username="timeruser", password="testpass123")

    def test_start_timer(self):
        """POST start creates an ActiveTimer."""
        from trackable.timetracking.models import ActiveTimer
        response = self.client.post(
            reverse("start_timer", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "started")
        self.assertEqual(data["profile_id"], self.profile.id)
        self.assertTrue(ActiveTimer.objects.filter(profile=self.profile, user=self.user).exists())

    def test_start_timer_twice_returns_400(self):
        """Starting a timer when one is already running returns 400."""
        from trackable.timetracking.models import ActiveTimer
        ActiveTimer.objects.create(
            profile=self.profile, user=self.user, start_time=timezone.now()
        )
        response = self.client.post(
            reverse("start_timer", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 400)

    def test_pause_timer(self):
        """POST pause pauses a running timer."""
        from trackable.timetracking.models import ActiveTimer
        timer = ActiveTimer.objects.create(
            profile=self.profile, user=self.user, start_time=timezone.now()
        )
        response = self.client.post(
            reverse("pause_timer", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "paused")
        timer.refresh_from_db()
        self.assertTrue(timer.is_paused)

    def test_pause_no_timer_returns_404(self):
        """Pausing when no timer exists returns 404."""
        response = self.client.post(
            reverse("pause_timer", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_resume_timer(self):
        """POST resume resumes a paused timer."""
        from trackable.timetracking.models import ActiveTimer
        timer = ActiveTimer.objects.create(
            profile=self.profile,
            user=self.user,
            start_time=timezone.now(),
            is_paused=True,
            pause_time=timezone.now(),
            total_paused_seconds=60,
        )
        response = self.client.post(
            reverse("resume_timer", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "resumed")
        timer.refresh_from_db()
        self.assertFalse(timer.is_paused)

    def test_resume_not_paused_returns_400(self):
        """Resuming a non-paused timer returns 400."""
        from trackable.timetracking.models import ActiveTimer
        ActiveTimer.objects.create(
            profile=self.profile, user=self.user, start_time=timezone.now()
        )
        response = self.client.post(
            reverse("resume_timer", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 400)

    def test_stop_timer_creates_time_entry(self):
        """POST stop creates a TimeEntry and deletes the ActiveTimer."""
        from trackable.timetracking.models import ActiveTimer, TimeEntry
        timer = ActiveTimer.objects.create(
            profile=self.profile, user=self.user, start_time=timezone.now()
        )
        response = self.client.post(
            reverse("stop_timer", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "stopped")
        self.assertIn("hours_worked", data)
        self.assertTrue(TimeEntry.objects.filter(profile=self.profile).exists())
        self.assertFalse(ActiveTimer.objects.filter(profile=self.profile).exists())

    def test_stop_no_timer_returns_404(self):
        """Stopping when no timer exists returns 404."""
        response = self.client.post(
            reverse("stop_timer", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_timer_status_no_timer(self):
        """GET status returns has_timer: false when no timer is running."""
        response = self.client.get(
            reverse("timer_status", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["has_timer"])

    def test_timer_status_with_running_timer(self):
        """GET status returns timer state for a running timer."""
        from trackable.timetracking.models import ActiveTimer
        start = timezone.now()
        ActiveTimer.objects.create(
            profile=self.profile, user=self.user, start_time=start
        )
        response = self.client.get(
            reverse("timer_status", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["has_timer"])
        self.assertFalse(data["is_paused"])
        self.assertIn("elapsed_seconds", data)

    def test_timer_status_with_paused_timer(self):
        """GET status returns is_paused: true for a paused timer."""
        from trackable.timetracking.models import ActiveTimer
        ActiveTimer.objects.create(
            profile=self.profile,
            user=self.user,
            start_time=timezone.now(),
            is_paused=True,
            pause_time=timezone.now(),
            total_paused_seconds=120,
        )
        response = self.client.get(
            reverse("timer_status", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["has_timer"])
        self.assertTrue(data["is_paused"])

    def test_start_timer_requires_post(self):
        """GET request to start endpoint is rejected."""
        response = self.client.get(
            reverse("start_timer", kwargs={"profile_id": self.profile.pk})
        )
        self.assertEqual(response.status_code, 405)  # Method Not Allowed


class PdfExportApiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="test123")
        self.profile = Profile.objects.create(
            user=self.user, title="Eng", position="Dev",
            weekly_hours=40, hourly_rate=50,
        )
        TimeEntry.objects.create(
            profile=self.profile, date=date(2026, 5, 4),
            start_time=time(8, 0), end_time=time(12, 0), pause_duration=0,
        )

    def test_api_export_pdf_returns_base64(self):
        self.client.login(username="testuser", password="test123")
        r = self.client.get(
            reverse("api_export_pdf",
                    kwargs={"profile_id": self.profile.id, "year": 2026, "month": 5})
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("pdf_base64", data)
        import base64
        decoded = base64.b64decode(data["pdf_base64"])
        self.assertTrue(decoded.startswith(b"%PDF"))

    def test_api_export_pdf_requires_login(self):
        r = self.client.get(
            reverse("api_export_pdf",
                    kwargs={"profile_id": self.profile.id, "year": 2026, "month": 5})
        )
        self.assertEqual(r.status_code, 302)

    def test_api_export_pdf_wrong_user_404(self):
        other = User.objects.create_user(username="other", password="pass123")
        op = Profile.objects.create(
            user=other, title="O", position="X",
            weekly_hours=40, hourly_rate=0,
        )
        self.client.login(username="testuser", password="test123")
        r = self.client.get(
            reverse("api_export_pdf",
                    kwargs={"profile_id": op.id, "year": 2026, "month": 5})
        )
        self.assertEqual(r.status_code, 404)

    def test_old_export_pdf_still_works(self):
        self.client.login(username="testuser", password="test123")
        r = self.client.get(
            reverse("export_pdf",
                    kwargs={"profile_id": self.profile.id, "year": 2026, "month": 5})
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("Content-Disposition", r)

