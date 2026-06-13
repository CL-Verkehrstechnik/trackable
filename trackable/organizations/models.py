from django.db import models
from django.utils.text import slugify
from datetime import time as time_obj


class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="created_organizations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    timer_only_mode = models.BooleanField(default=False, verbose_name="Timer only mode")

    # Team Calendar Settings
    cal_week_starts_on = models.IntegerField(
        default=1,
        choices=[(0, "Sunday"), (1, "Monday")],
        verbose_name="Calendar week starts on",
    )
    cal_included_days = models.CharField(
        max_length=10,
        default="workdays",
        choices=[("all", "All days"), ("workdays", "Workdays (Mon\u2013Fri)")],
        verbose_name="Calendar included days",
    )
    cal_time_interval = models.IntegerField(
        default=60,
        choices=[(15, "15 min"), (30, "30 min"), (60, "60 min")],
        verbose_name="Calendar time interval",
    )
    cal_start_time = models.TimeField(default=time_obj(8, 0), verbose_name="Calendar start time")
    cal_end_time = models.TimeField(default=time_obj(20, 0), verbose_name="Calendar end time")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            original_slug = self.slug
            counter = 1
            while Organization.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)



class CalendarEvent(models.Model):
    """Ein Event im Team-Kalender einer Organisation."""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="calendar_events"
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="created_calendar_events",
    )
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True, null=True)
    color = models.CharField(
        max_length=20,
        default="blue",
        choices=[
            ("blue", "Blue"),
            ("red", "Red"),
            ("green", "Green"),
            ("yellow", "Yellow"),
            ("purple", "Purple"),
            ("gray", "Gray"),
        ],
    )
    day_id = models.CharField(max_length=20, verbose_name="Day of week")
    start_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    week_start = models.DateField(verbose_name="Monday of the week")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["week_start", "day_id", "start_time"]
        verbose_name = "Calendar event"
        verbose_name_plural = "Calendar events"

    def __str__(self):
        return f"{self.title} ({self.day_id} {self.start_time})"

    @property
    def end_time(self):
        from datetime import datetime, timedelta, date
        dummy = datetime.combine(date.today(), self.start_time)
        end = dummy + timedelta(minutes=self.duration_minutes)
        return end.time()

    def to_json(self):
        return {
            "id": self.id,
            "title": self.title,
            "notes": self.notes,
            "color": self.color,
            "day_id": self.day_id,
            "start_time": self.start_time.strftime("%H:%M"),
            "duration_minutes": self.duration_minutes,
            "week_start": self.week_start.isoformat(),
            "created_by": self.created_by_id,
        }


class OrganizationMembership(models.Model):
    ROLE_CHOICES = [
        ("manager", "Manager"),
        ("employee", "Employee"),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="organization_membership",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="employee")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["role", "joined_at"]

    def __str__(self):
        return f"{self.user} – {self.get_role_display()} @ {self.organization}"

    @property
    def is_manager(self):
        return self.role == "manager"
