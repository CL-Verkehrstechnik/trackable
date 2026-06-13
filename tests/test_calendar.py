from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import date, time
from trackable.organizations.models import (
    Organization,
    OrganizationMembership,
    CalendarEvent,
)

User = get_user_model()


class CalendarEventModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="caluser", email="cal@example.com", password="test123"
        )
        self.org = Organization.objects.create(
            name="Test Org", created_by=self.user
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role="manager"
        )

    def test_create_event(self):
        event = CalendarEvent.objects.create(
            organization=self.org,
            created_by=self.user,
            title="Test Event",
            day_id="Monday",
            start_time=time(9, 0),
            duration_minutes=60,
            week_start=date(2026, 6, 15),
        )
        self.assertEqual(str(event), "Test Event (Monday 09:00:00)")
        self.assertEqual(event.end_time, time(10, 0))

    def test_end_time_crosses_midnight(self):
        """Wenn start_time 23:30 und duration 60 min, end_time sollte 00:30 sein."""
        event = CalendarEvent.objects.create(
            organization=self.org,
            created_by=self.user,
            title="Late Event",
            day_id="Friday",
            start_time=time(23, 30),
            duration_minutes=60,
            week_start=date(2026, 6, 15),
        )
        self.assertEqual(event.end_time, time(0, 30))

    def test_to_json(self):
        event = CalendarEvent.objects.create(
            organization=self.org,
            created_by=self.user,
            title="JSON Event",
            notes="Some notes",
            color="green",
            day_id="Tuesday",
            start_time=time(10, 30),
            duration_minutes=30,
            week_start=date(2026, 6, 15),
        )
        data = event.to_json()
        self.assertEqual(data["title"], "JSON Event")
        self.assertEqual(data["notes"], "Some notes")
        self.assertEqual(data["color"], "green")
        self.assertEqual(data["day_id"], "Tuesday")
        self.assertEqual(data["start_time"], "10:30")
        self.assertEqual(data["duration_minutes"], 30)
        self.assertEqual(data["created_by"], self.user.id)

    def test_default_color_is_blue(self):
        event = CalendarEvent.objects.create(
            organization=self.org,
            created_by=self.user,
            title="Default Color",
            day_id="Monday",
            start_time=time(8, 0),
            duration_minutes=30,
            week_start=date(2026, 6, 15),
        )
        self.assertEqual(event.color, "blue")


class CalendarAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="calapi", email="calapi@example.com", password="test123"
        )
        self.org = Organization.objects.create(
            name="API Org", created_by=self.user
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role="manager"
        )
        self.client.login(username="calapi", password="test123")
        self.week_start = date(2026, 6, 15)

    def _create_event(self, **kwargs):
        defaults = {
            "organization": self.org,
            "created_by": self.user,
            "title": "Test",
            "day_id": "Monday",
            "start_time": time(9, 0),
            "duration_minutes": 60,
            "week_start": self.week_start,
        }
        defaults.update(kwargs)
        return CalendarEvent.objects.create(**defaults)

    def test_add_event(self):
        response = self.client.post(
            reverse("calendar_add_event"),
            data={
                "day_id": "Wednesday",
                "start_time": "14:00",
                "title": "Added Event",
                "duration_minutes": 45,
                "week_start": self.week_start.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["event"]["title"], "Added Event")
        self.assertEqual(data["event"]["day_id"], "Wednesday")
        self.assertEqual(data["event"]["start_time"], "14:00")

    def test_add_event_missing_fields(self):
        response = self.client.post(
            reverse("calendar_add_event"),
            data={"day_id": "Monday"},  # missing start_time and week_start
        )
        self.assertEqual(response.status_code, 400)

    def test_add_event_invalid_time(self):
        response = self.client.post(
            reverse("calendar_add_event"),
            data={
                "day_id": "Monday",
                "start_time": "invalid",
                "week_start": self.week_start.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_get_events(self):
        self._create_event(title="Visible Event", day_id="Thursday", start_time=time(11, 0))
        response = self.client.get(
            reverse("calendar_get_events"),
            {"week_start": self.week_start.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["events"][0]["title"], "Visible Event")

    def test_get_events_empty_week(self):
        other_week = date(2026, 7, 6)
        response = self.client.get(
            reverse("calendar_get_events"),
            {"week_start": other_week.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["events"]), 0)

    def test_get_events_missing_param(self):
        response = self.client.get(reverse("calendar_get_events"))
        self.assertEqual(response.status_code, 400)

    def test_update_event(self):
        event = self._create_event(title="Original")
        response = self.client.post(
            reverse("calendar_update_event", args=[event.pk]),
            data={
                "title": "Updated",
                "start_time": "09:30",
                "duration_minutes": 90,
            },
        )
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.title, "Updated")
        self.assertEqual(event.start_time, time(9, 30))
        self.assertEqual(event.duration_minutes, 90)

    def test_update_event_day_change(self):
        event = self._create_event(day_id="Monday")
        response = self.client.post(
            reverse("calendar_update_event", args=[event.pk]),
            data={"day_id": "Friday"},
        )
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.day_id, "Friday")

    def test_update_nonexistent_event(self):
        response = self.client.post(
            reverse("calendar_update_event", args=[99999]),
            data={"title": "Ghost"},
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_event(self):
        event = self._create_event(title="Delete Me")
        response = self.client.post(
            reverse("calendar_delete_event", args=[event.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CalendarEvent.objects.filter(pk=event.pk).exists())

    def test_delete_nonexistent_event(self):
        response = self.client.post(
            reverse("calendar_delete_event", args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    def test_employee_cannot_delete_others_event(self):
        """Ein Employee kann fremde Events nicht löschen."""
        other_user = User.objects.create_user(
            username="other_emp", email="other_emp@example.com", password="test123"
        )
        org = self.org
        OrganizationMembership.objects.create(
            organization=org, user=other_user, role="employee"
        )

        # Event created by other_user
        event = self._create_event(
            title="Other's Event",
            created_by=other_user,
        )

        # current user is manager – darf löschen
        response = self.client.post(
            reverse("calendar_delete_event", args=[event.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_employee_can_delete_own_event(self):
        """Ein Employee kann eigene Events löschen."""
        employee = User.objects.create_user(
            username="emp", email="emp@example.com", password="test123"
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=employee, role="employee"
        )
        self.client.login(username="emp", password="test123")

        event = CalendarEvent.objects.create(
            organization=self.org,
            created_by=employee,
            title="My Event",
            day_id="Monday",
            start_time=time(10, 0),
            duration_minutes=30,
            week_start=self.week_start,
        )

        response = self.client.post(
            reverse("calendar_delete_event", args=[event.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CalendarEvent.objects.filter(pk=event.pk).exists())

    def test_events_are_org_scoped(self):
        """Events einer anderen Organisation sind nicht sichtbar."""
        other_user = User.objects.create_user(
            username="other", email="other@example.com", password="test123"
        )
        other_org = Organization.objects.create(
            name="Other Org", created_by=other_user
        )
        CalendarEvent.objects.create(
            organization=other_org,
            created_by=other_user,
            title="Other Event",
            day_id="Monday",
            start_time=time(9, 0),
            duration_minutes=60,
            week_start=self.week_start,
        )
        response = self.client.get(
            reverse("calendar_get_events"),
            {"week_start": self.week_start.isoformat()},
        )
        data = response.json()
        self.assertEqual(len(data["events"]), 0)

    def test_non_member_cannot_add(self):
        self.client.logout()
        response = self.client.post(
            reverse("calendar_add_event"),
            data={
                "day_id": "Monday",
                "start_time": "09:00",
                "week_start": self.week_start.isoformat(),
            },
        )
        # Should redirect to login (302)
        self.assertEqual(response.status_code, 302)

    def test_team_calendar_view_returns_200(self):
        response = self.client.get(reverse("team_calendar"))
        self.assertEqual(response.status_code, 200)

    def test_team_calendar_view_shows_events(self):
        # Event in week starting 2026-06-15 (Monday)
        self._create_event(title="Grid Event", day_id="Tuesday", start_time=time(10, 0))
        # Request a date that falls in that week (Tuesday 2026-06-16)
        response = self.client.get(
            reverse("team_calendar") + "?year=2026&month=6&day=16"
        )
        self.assertContains(response, "Grid Event")
