# Planned Changes – trackable

> Datum: 2026-06-13
> Status: Final (Revision 2 – Ausführungsplan Phase 1)
> Branch: `main`

---

## Überblick

Fünf Arbeitspakete:

1. **Shared Weekly Calendar (Team-Kalender)** – Inspiriert von [weekly-planner-web](https://github.com/LStoneyy/weekly-planner-web)
2. **Enhanced Role-Based Timer Mode** – Rollenbasierte Zeiterfassung (Classic/Restricted)
3. **Zeitkonto (Time Account)** – Soll-/Ist-Stunden-Balance pro Profil
4. **PDF-Export mit Native Share** – Web Share API für mobile Geräte
5. **Mobile UI/UX Audit** – Durchgehendes mobiles Design-Review

---

## Phase 1: Shared Weekly Calendar (Team-Kalender)

### Ziel
Ein visueller Wochenkalender pro Organisation, ähnlich wie weekly-planner-web:  
Tage × Stunden-Raster, Events als positionierte, farbcodierte Blöcke, Drag&Drop zum Verschieben zwischen Tagen/Zeiten, Klick zum Editieren per Modal.

Das **bestehende** `org_weekly_calendar` (Tabellen-Layout mit TimeEntries) bleibt erhalten – der neue Kalender ist ein **alternativer Team-Kalender** unter `/org/team-calendar/`.

---

## Ausführungsplan

### Schritt 1: Model `CalendarEvent` + Migration

**Datei:** `trackable/organizations/models.py`

```python
class CalendarEvent(models.Model):
    """Ein Event im Team-Kalender einer Organisation."""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="calendar_events"
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="created_calendar_events"
    )
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=20, default="blue")   # Preset: blue, red, green, yellow, purple, gray
    day_id = models.CharField(max_length=20)                   # Monday, Tuesday, …
    start_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    week_start = models.DateField()                            # Montag der Woche
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["week_start", "day_id", "start_time"]

    def __str__(self):
        return f"{self.title} ({self.day_id} {self.start_time})"

    @property
    def end_time(self):
        """Endzeit berechnen."""
        from datetime import datetime, timedelta, date
        dummy = datetime.combine(date.today(), self.start_time)
        end = dummy + timedelta(minutes=self.duration_minutes)
        return end.time()

    def to_json(self):
        """Für AJAX-Responses."""
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
```

**Neu erstellen:** `organizations/migrations/0004_calendarevent.py`

```bash
python manage.py makemigrations organizations
python manage.py migrate
```

---

### Schritt 2: Kalender-Settings auf `Organization`

**Datei:** `trackable/organizations/models.py` – bestehendes `Organization`-Model ergänzen:

```python
from datetime import time as time_obj  # oben importieren

class Organization(models.Model):
    # … bestehende Felder …
    
    # Team Calendar Settings
    cal_week_starts_on = models.IntegerField(
        default=1, choices=[(0, "Sunday"), (1, "Monday")]
    )
    cal_included_days = models.CharField(
        max_length=10, default="workdays",
        choices=[("all", "All days"), ("workdays", "Workdays (Mon–Fri)")],
    )
    cal_time_interval = models.IntegerField(
        default=60, choices=[(15, "15 min"), (30, "30 min"), (60, "60 min")],
    )
    cal_start_time = models.TimeField(default=time_obj(8, 0))
    cal_end_time = models.TimeField(default=time_obj(20, 0))
```

**Migration erstellen:** `organizations/migrations/0005_organization_cal_settings.py`

---

### Schritt 3: Neue View-Datei `calendar_views.py`

**Neu erstellen:** `trackable/organizations/calendar_views.py`

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime, timedelta, date, time
from trackable.organizations.models import Organization, OrganizationMembership
from trackable.organizations.models import CalendarEvent
import calendar as cal_mod

# ── Helpers ──────────────────────────────────────────────

def _get_membership_or_redirect(user):
    membership = getattr(user, "organization_membership", None)
    if not membership:
        return None, redirect("org_create")
    return membership, None

def _get_week_start(year, month, day):
    """Berechne Montag der Woche, in die das Datum fällt."""
    d = date(year, month, day)
    return d - timedelta(days=d.weekday())

def _generate_time_slots(start: time, end: time, interval_minutes: int):
    """Erzeuge Liste von HH:MM-Strings zwischen start und end im gegebenen Intervall."""
    slots = []
    current = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    while current <= end_dt:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=interval_minutes)
    return slots

PRESET_COLORS = {
    "blue": {"bg": "rgba(137,180,250,0.18)", "border": "#89b4fa"},
    "red": {"bg": "rgba(243,139,168,0.18)", "border": "#f38ba8"},
    "green": {"bg": "rgba(166,227,161,0.18)", "border": "#a6e3a1"},
    "yellow": {"bg": "rgba(249,226,175,0.18)", "border": "#f9e2af"},
    "purple": {"bg": "rgba(202,158,230,0.18)", "border": "#ca9ee6"},
    "gray": {"bg": "rgba(186,194,222,0.18)", "border": "#bac2de"},
}

# ── Views ────────────────────────────────────────────────

@login_required
def team_calendar(request):
    """Hauptansicht: Team-Kalender für eine bestimmte Woche anzeigen."""
    membership, error = _get_membership_or_redirect(request.user)
    if error:
        return error

    organization = membership.organization
    today = timezone.now().date()

    # Woche aus Query-Param oder aktuelle Woche
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))
    day = int(request.GET.get("day", today.day))
    
    try:
        week_start = _get_week_start(year, month, day)
    except (ValueError, TypeError):
        week_start = _get_week_start(today.year, today.month, today.day)
    
    week_end = week_start + timedelta(days=6)
    
    # Settings aus der Organisation
    settings = {
        "week_starts_on": organization.cal_week_starts_on,
        "included_days": organization.cal_included_days,
        "time_interval": organization.cal_time_interval,
        "start_time": organization.cal_start_time,
        "end_time": organization.cal_end_time,
    }
    
    # Wochentage bestimmen
    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if settings["week_starts_on"] == 0:  # Sunday
        all_days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    
    days_to_show = all_days
    if settings["included_days"] == "workdays":
        days_to_show = [d for d in all_days if d not in ("Saturday", "Sunday")]
    
    # Zeit-Slots
    time_slots = _generate_time_slots(
        settings["start_time"], settings["end_time"], settings["time_interval"]
    )
    
    # Events für diese Woche laden
    events_qs = CalendarEvent.objects.filter(
        organization=organization,
        week_start=week_start,
    ).select_related("created_by")
    
    # Events pro Tag gruppieren + Position berechnen
    pixels_per_hour = 64
    minutes_per_slot = settings["time_interval"]
    px_per_min = pixels_per_hour / 60
    
    first_slot_minutes = settings["start_time"].hour * 60 + settings["start_time"].minute
    
    days_data = []
    for day_name in days_to_show:
        day_events = []
        for ev in events_qs.filter(day_id=day_name).order_by("start_time"):
            start_minutes = ev.start_time.hour * 60 + ev.start_time.minute
            top_px = (start_minutes - first_slot_minutes) * px_per_min
            height_px = max(ev.duration_minutes * px_per_min, 20)  # min 20px
            
            color_info = PRESET_COLORS.get(ev.color, PRESET_COLORS["blue"])
            
            day_events.append({
                "id": ev.id,
                "title": ev.title,
                "notes": ev.notes,
                "color": ev.color,
                "bg_color": color_info["bg"],
                "border_color": color_info["border"],
                "start_time": ev.start_time.strftime("%H:%M"),
                "end_time": ev.end_time.strftime("%H:%M"),
                "duration_minutes": ev.duration_minutes,
                "top_px": round(top_px, 1),
                "height_px": round(height_px, 1),
                "created_by_id": ev.created_by_id,
                "is_owner": ev.created_by == request.user,
            })
        
        days_data.append({
            "id": day_name,
            "label": _(day_name),  # Übersetzter Name
            "short_label": _(day_name[:2]),  # "Mo", "Di", …
            "events": day_events,
        })
    
    # Navigation
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)
    
    context = {
        "organization": organization,
        "membership": membership,
        "is_manager": membership.is_manager,
        "days_data": days_data,
        "time_slots": time_slots,
        "week_start": week_start,
        "week_end": week_end,
        "week_number": week_start.isocalendar()[1],
        "prev_url": f"?year={prev_week.year}&month={prev_week.month}&day={prev_week.day}",
        "next_url": f"?year={next_week.year}&month={next_week.month}&day={next_week.day}",
        "today_url": f"?year={today.year}&month={today.month}&day={today.day}",
        "settings": settings,
        "pixels_per_hour": pixels_per_hour,
        "first_slot_minutes": first_slot_minutes,
        "px_per_min": px_per_min,
    }
    
    return render(request, "organizations/team_calendar.html", context)


@login_required
@require_http_methods(["POST"])
def calendar_add_event(request):
    """AJAX: Neues Event erstellen (auch via Klick auf leeren Slot)."""
    membership, error = _get_membership_or_redirect(request.user)
    if error:
        return JsonResponse({"error": str(error)}, status=403)

    import json
    data = json.loads(request.body) if request.body else request.POST
    
    day_id = data.get("day_id")
    start_time_str = data.get("start_time")
    title = data.get("title", _("New Event"))
    duration_minutes = int(data.get("duration_minutes", 60))
    color = data.get("color", "blue")
    week_start_str = data.get("week_start")

    if not day_id or not start_time_str or not week_start_str:
        return JsonResponse({"error": _("day_id, start_time, and week_start are required.")}, status=400)

    try:
        start_time = datetime.strptime(start_time_str, "%H:%M").time()
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return JsonResponse({"error": _("Invalid date/time format.")}, status=400)

    event = CalendarEvent.objects.create(
        organization=membership.organization,
        created_by=request.user,
        title=title,
        notes=data.get("notes", ""),
        color=color,
        day_id=day_id,
        start_time=start_time,
        duration_minutes=duration_minutes,
        week_start=week_start,
    )

    return JsonResponse({"status": "ok", "event": event.to_json()})


@login_required
@require_http_methods(["POST"])
def calendar_update_event(request, event_id):
    """AJAX: Event aktualisieren (Title, Notes, Color, Time, Day)."""
    membership, error = _get_membership_or_redirect(request.user)
    if error:
        return JsonResponse({"error": str(error)}, status=403)

    event = get_object_or_404(
        CalendarEvent, pk=event_id, organization=membership.organization
    )

    import json
    data = json.loads(request.body) if request.body else request.POST

    if "title" in data:
        event.title = data["title"]
    if "notes" in data:
        event.notes = data["notes"]
    if "color" in data:
        event.color = data["color"]
    if "day_id" in data:
        event.day_id = data["day_id"]
    if "start_time" in data:
        try:
            event.start_time = datetime.strptime(data["start_time"], "%H:%M").time()
        except (ValueError, TypeError):
            return JsonResponse({"error": _("Invalid time format.")}, status=400)
    if "duration_minutes" in data:
        event.duration_minutes = int(data["duration_minutes"])
    if "week_start" in data:
        try:
            event.week_start = datetime.strptime(data["week_start"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return JsonResponse({"error": _("Invalid date format.")}, status=400)

    event.save()
    return JsonResponse({"status": "ok", "event": event.to_json()})


@login_required
@require_http_methods(["POST"])
def calendar_delete_event(request, event_id):
    """AJAX: Event löschen. Nur Owner oder Manager dürfen."""
    membership, error = _get_membership_or_redirect(request.user)
    if error:
        return JsonResponse({"error": str(error)}, status=403)

    event = get_object_or_404(
        CalendarEvent, pk=event_id, organization=membership.organization
    )

    if event.created_by != request.user and not membership.is_manager:
        return JsonResponse({"error": _("You can only delete your own events.")}, status=403)

    event.delete()
    return JsonResponse({"status": "ok"})


@login_required
def calendar_get_events(request):
    """JSON: Alle Events einer Woche abrufen (für Initialisierung)."""
    membership, error = _get_membership_or_redirect(request.user)
    if error:
        return JsonResponse({"error": str(error)}, status=403)

    week_start_str = request.GET.get("week_start")
    if not week_start_str:
        return JsonResponse({"error": _("week_start is required.")}, status=400)

    try:
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": _("Invalid date format.")}, status=400)

    events = CalendarEvent.objects.filter(
        organization=membership.organization,
        week_start=week_start,
    )

    return JsonResponse({
        "events": [ev.to_json() for ev in events],
        "week_start": week_start_str,
    })
```

---

### Schritt 4: URLs registrieren

**Datei:** `trackable/organizations/urls.py`

```python
from django.urls import path
from . import views
from . import calendar_views  # NEU

urlpatterns = [
    # … bestehende Routen …
    
    # Team Calendar (NEU)
    path("team-calendar/", calendar_views.team_calendar, name="team_calendar"),
    path(
        "team-calendar/api/events/",
        calendar_views.calendar_get_events,
        name="calendar_get_events",
    ),
    path(
        "team-calendar/api/events/add/",
        calendar_views.calendar_add_event,
        name="calendar_add_event",
    ),
    path(
        "team-calendar/api/events/<int:event_id>/update/",
        calendar_views.calendar_update_event,
        name="calendar_update_event",
    ),
    path(
        "team-calendar/api/events/<int:event_id>/delete/",
        calendar_views.calendar_delete_event,
        name="calendar_delete_event",
    ),
]
```

---

### Schritt 5: Team-Calendar Template

**Neu erstellen:** `templates/organizations/team_calendar.html`

```html
{% extends 'base.html' %}
{% load i18n %}

{% block title %}{% trans "Team Calendar" %} – {{ organization.name }}{% endblock %}
{% block nav_org %}active{% endblock %}

{% block extra_css %}
<style>
/* ── Container ── */
.team-cal-wrap {
    display: flex;
    flex-direction: column;
    gap: 16px;
}
.team-cal-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
}
.team-cal-nav .week-label {
    font-weight: 700;
    font-size: 1rem;
    min-width: 200px;
    text-align: center;
}
/* ── Scroll-Container ── */
.team-cal-scroll {
    overflow: auto;
    border-radius: 12px;
    border: 1px solid var(--ctp-overlay0);
    background: var(--ctp-base);
    position: relative;
    max-height: calc(100vh - 220px);
}
.team-cal-grid {
    display: flex;
    min-width: 700px;
    position: relative;
}
/* ── Time Column ── */
.time-col {
    flex: 0 0 70px;
    position: sticky;
    left: 0;
    z-index: 10;
    background: var(--ctp-mantle);
    border-right: 1px solid var(--ctp-overlay0);
}
.time-slot-label {
    height: 64px;           /* 1h = 64px */
    display: flex;
    align-items: flex-start;
    justify-content: flex-end;
    padding: 2px 12px 0 4px;
    font-size: .72rem;
    font-weight: 600;
    color: var(--ctp-subtext0);
    border-bottom: 1px solid var(--ctp-surface0);
}
/* ── Day Columns ── */
.day-col {
    flex: 1;
    min-width: 120px;
    position: relative;
    border-right: 1px solid var(--ctp-surface0);
}
.day-col:last-child {
    border-right: none;
}
.day-col-header {
    position: sticky;
    top: 0;
    z-index: 5;
    background: var(--ctp-mantle);
    padding: 10px 0;
    text-align: center;
    font-size: .78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .05em;
    color: var(--ctp-mauve);
    border-bottom: 2px solid var(--ctp-overlay0);
}
.day-col-header .short {
    display: none;
}
.day-slots {
    position: relative;
}
.time-slot-cell {
    height: 64px;           /* 1h = 64px, bei 30min=32px, 15min=16px */
    border-bottom: 1px solid var(--ctp-surface0);
    cursor: pointer;
    transition: background .1s;
}
.time-slot-cell:hover {
    background: var(--ctp-mantle);
}
.time-slot-cell.droppable-over {
    background: var(--ctp-overlay0);
}
/* ── Event Blocks ── */
.cal-event {
    position: absolute;
    left: 3px;
    right: 3px;
    border-radius: 6px;
    padding: 3px 6px;
    border-left: 3px solid;
    font-size: .72rem;
    line-height: 1.3;
    overflow: hidden;
    cursor: grab;
    user-select: none;
    transition: box-shadow .15s, transform .1s;
    z-index: 2;
}
.cal-event:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,.15);
    transform: translateY(-1px);
    z-index: 3;
}
.cal-event:active {
    cursor: grabbing;
}
.cal-event .ev-title {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.cal-event .ev-time {
    font-size: .65rem;
    opacity: .7;
}
.cal-event.sortable-ghost {
    opacity: .4;
    border-color: var(--ctp-mauve) !important;
    background: rgba(202,158,230,.3) !important;
}
.cal-event.sortable-chosen {
    box-shadow: 0 4px 16px rgba(0,0,0,.25);
    transform: scale(1.03);
    z-index: 20;
}
/* ── Modal ── */
.modal-overlay {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 100;
    background: rgba(0,0,0,.4);
    align-items: center;
    justify-content: center;
}
.modal-overlay.open {
    display: flex;
}
.modal-content {
    background: var(--ctp-base);
    border-radius: 16px;
    padding: 24px;
    width: 90%;
    max-width: 440px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0,0,0,.3);
}
.modal-content h3 {
    margin: 0 0 16px 0;
    color: var(--ctp-text);
}
.modal-content label {
    display: block;
    font-size: .82rem;
    font-weight: 600;
    color: var(--ctp-subtext0);
    margin-bottom: 4px;
}
.modal-content input,
.modal-content textarea,
.modal-content select {
    width: 100%;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid var(--ctp-overlay0);
    background: var(--ctp-mantle);
    color: var(--ctp-text);
    font-size: .9rem;
    margin-bottom: 12px;
    box-sizing: border-box;
}
.modal-content .color-picker {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
}
.modal-content .color-dot {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 3px solid transparent;
    cursor: pointer;
    transition: transform .1s;
}
.modal-content .color-dot.selected {
    border-color: var(--ctp-text);
    transform: scale(1.15);
}
.modal-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 12px;
}
/* ── Responsive ── */
@media (max-width: 640px) {
    .time-slot-label, .time-slot-cell {
        height: 48px;
    }
    .day-col {
        min-width: 100px;
    }
    .day-col-header .full { display: none; }
    .day-col-header .short { display: inline; }
    .cal-event {
        font-size: .65rem;
        padding: 2px 4px;
    }
    .cal-event .ev-time { display: none; }
}
</style>
{% endblock %}

{% block content %}
<div class="team-cal-wrap">
    {# CSRF Token (für fetch) #}
    <input type="hidden" id="csrf-token" value="{{ csrf_token }}">

    {# Navigation #}
    <div class="team-cal-nav">
        <div>
            <a href="/org/" class="btn btn-secondary btn-sm">← {% trans "Back" %}</a>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
            <a href="{{ prev_url }}" class="btn btn-secondary btn-sm">←</a>
            <span class="week-label">
                {% trans "Week" %} {{ week_number }} – {{ week_start|date:"d.m." }}–{{ week_end|date:"d.m.Y" }}
            </span>
            <a href="{{ next_url }}" class="btn btn-secondary btn-sm">→</a>
            <a href="{{ today_url }}" class="btn btn-primary btn-sm">{% trans "Today" %}</a>
        </div>
        <div></div>
    </div>

    {# Kalender-Grid #}
    <div class="team-cal-scroll" id="team-cal-scroll">
        <div class="team-cal-grid" data-week-start="{{ week_start|date:'Y-m-d' }}">
            {# Zeit-Spalte #}
            <div class="time-col">
                <div class="day-col-header" style="visibility:hidden;">&nbsp;</div>
                {% for slot in time_slots %}
                <div class="time-slot-label">{{ slot }}</div>
                {% endfor %}
            </div>

            {# Tages-Spalten #}
            {% for day in days_data %}
            <div class="day-col" data-day-id="{{ day.id }}">
                <div class="day-col-header">
                    <span class="full">{{ day.label }}</span>
                    <span class="short">{{ day.short_label }}</span>
                </div>
                <div class="day-slots sortable-container" data-day-id="{{ day.id }}">
                    {% for slot in time_slots %}
                    <div class="time-slot-cell" data-time="{{ slot }}"
                         hx-post="{% url 'calendar_add_event' %}"
                         hx-trigger="click"
                         hx-vals='{"day_id": "{{ day.id }}", "start_time": "{{ slot }}", "week_start": "{{ week_start|date:'Y-m-d' }}"}'
                         hx-swap="none"
                         hx-target="this">
                    </div>
                    {% endfor %}

                    {# Events (absolut positioniert) #}
                    {% for ev in day.events %}
                    <div class="cal-event"
                         data-event-id="{{ ev.id }}"
                         data-day-id="{{ day.id }}"
                         data-start-time="{{ ev.start_time }}"
                         data-duration="{{ ev.duration_minutes }}"
                         style="top: {{ ev.top_px }}px; height: {{ ev.height_px }}px; background: {{ ev.bg_color }}; border-left-color: {{ ev.border_color }};">
                        <div class="ev-title">{{ ev.title }}</div>
                        <div class="ev-time">{{ ev.start_time }}–{{ ev.end_time }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>

{# Modal: Event-Editor #}
<div class="modal-overlay" id="event-modal">
    <div class="modal-content">
        <h3 id="modal-title">{% trans "Edit Event" %}</h3>
        <input type="hidden" id="modal-event-id" value="">
        
        <label for="modal-event-title">{% trans "Title" %}</label>
        <input type="text" id="modal-event-title" maxlength="200">
        
        <label for="modal-event-notes">{% trans "Notes" %}</label>
        <textarea id="modal-event-notes" rows="3"></textarea>
        
        <label>{% trans "Color" %}</label>
        <div class="color-picker" id="modal-color-picker">
            <div class="color-dot selected" data-color="blue"    style="background:#89b4fa;"></div>
            <div class="color-dot"         data-color="red"     style="background:#f38ba8;"></div>
            <div class="color-dot"         data-color="green"   style="background:#a6e3a1;"></div>
            <div class="color-dot"         data-color="yellow"  style="background:#f9e2af;"></div>
            <div class="color-dot"         data-color="purple"  style="background:#ca9ee6;"></div>
            <div class="color-dot"         data-color="gray"    style="background:#bac2de;"></div>
        </div>

        <label for="modal-event-day">{% trans "Day" %}</label>
        <select id="modal-event-day">
            {% for day in days_data %}
            <option value="{{ day.id }}">{{ day.label }}</option>
            {% endfor %}
        </select>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            <div>
                <label for="modal-event-start">{% trans "Start" %}</label>
                <input type="time" id="modal-event-start">
            </div>
            <div>
                <label for="modal-event-duration">{% trans "Duration (min)" %}</label>
                <input type="number" id="modal-event-duration" min="15" step="15" value="60">
            </div>
        </div>

        <div class="modal-actions">
            <button class="btn btn-sm btn-danger-light" id="modal-delete-btn">{% trans "Delete" %}</button>
            <button class="btn btn-sm btn-secondary" id="modal-cancel-btn">{% trans "Cancel" %}</button>
            <button class="btn btn-sm btn-primary" id="modal-save-btn">{% trans "Save" %}</button>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
<script>
(function() {
    'use strict';

    // ── Globals ──
    var csrfToken = document.getElementById('csrf-token').value;
    var weekStart = document.querySelector('.team-cal-grid').getAttribute('data-week-start');

    // ── Modal Elements ──
    var modal = document.getElementById('event-modal');
    var modalEventId = document.getElementById('modal-event-id');
    var modalTitle = document.getElementById('modal-event-title');
    var modalNotes = document.getElementById('modal-event-notes');
    var modalColorPicker = document.getElementById('modal-color-picker');
    var modalDay = document.getElementById('modal-event-day');
    var modalStart = document.getElementById('modal-event-start');
    var modalDuration = document.getElementById('modal-event-duration');
    var modalSaveBtn = document.getElementById('modal-save-btn');
    var modalCancelBtn = document.getElementById('modal-cancel-btn');
    var modalDeleteBtn = document.getElementById('modal-delete-btn');

    var selectedColor = 'blue';

    // ── Color Picker ──
    modalColorPicker.addEventListener('click', function(e) {
        var dot = e.target.closest('.color-dot');
        if (!dot) return;
        modalColorPicker.querySelectorAll('.color-dot').forEach(function(d) {
            d.classList.remove('selected');
        });
        dot.classList.add('selected');
        selectedColor = dot.getAttribute('data-color');
    });

    // ── Open Modal (for editing) ──
    function openModal(eventData) {
        modalEventId.value = eventData.id || '';
        modalTitle.value = eventData.title || '';
        modalNotes.value = eventData.notes || '';
        modalDay.value = eventData.day_id || 'Monday';
        modalStart.value = eventData.start_time || '09:00';
        modalDuration.value = eventData.duration_minutes || 60;
        selectedColor = eventData.color || 'blue';
        modalColorPicker.querySelectorAll('.color-dot').forEach(function(d) {
            d.classList.toggle('selected', d.getAttribute('data-color') === selectedColor);
        });
        modalDeleteBtn.style.display = eventData.id ? 'inline-block' : 'none';
        modal.classList.add('open');
        modalTitle.focus();
    }

    // ── Close Modal ──
    function closeModal() {
        modal.classList.remove('open');
    }

    modalCancelBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', function(e) {
        if (e.target === modal) closeModal();
    });
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
    });

    // ── Save Event ──
    modalSaveBtn.addEventListener('click', function() {
        var eventId = modalEventId.value;
        var payload = JSON.stringify({
            title: modalTitle.value,
            notes: modalNotes.value,
            color: selectedColor,
            day_id: modalDay.value,
            start_time: modalStart.value,
            duration_minutes: parseInt(modalDuration.value) || 60,
            week_start: weekStart,
        });

        var url = eventId
            ? '/org/team-calendar/api/events/' + eventId + '/update/'
            : '/org/team-calendar/api/events/add/';

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json',
            },
            body: payload,
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status === 'ok') {
                closeModal();
                location.reload();
            } else {
                alert('Error: ' + (data.error || 'Unknown'));
            }
        })
        .catch(function(err) {
            alert('Error saving event.');
            console.error(err);
        });
    });

    // ── Delete Event ──
    modalDeleteBtn.addEventListener('click', function() {
        var eventId = modalEventId.value;
        if (!eventId) return;
        if (!confirm('{% trans "Delete this event?" %}')) return;

        fetch('/org/team-calendar/api/events/' + eventId + '/delete/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json',
            },
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status === 'ok') {
                closeModal();
                location.reload();
            } else {
                alert('Error: ' + (data.error || 'Unknown'));
            }
        })
        .catch(function(err) {
            alert('Error deleting event.');
            console.error(err);
        });
    });

    // ── Click on Event → Open Modal ──
    document.querySelectorAll('.cal-event').forEach(function(el) {
        el.addEventListener('click', function(e) {
            e.stopPropagation();
            var eventId = el.getAttribute('data-event-id');
            var dayId = el.getAttribute('data-day-id');
            var startTime = el.getAttribute('data-start-time');
            var duration = el.getAttribute('data-duration');
            var title = el.querySelector('.ev-title').textContent.trim();

            openModal({
                id: eventId,
                title: title,
                notes: '',
                color: el.style.borderLeftColor ? 'blue' : 'blue',
                day_id: dayId,
                start_time: startTime,
                duration_minutes: parseInt(duration) || 60,
            });

            // Notes via AJAX nachladen
            fetch('/org/team-calendar/api/events/?week_start=' + weekStart)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                data.events.forEach(function(ev) {
                    if (String(ev.id) === eventId) {
                        modalNotes.value = ev.notes || '';
                        // Farbe aus API setzen
                        selectedColor = ev.color || 'blue';
                        modalColorPicker.querySelectorAll('.color-dot').forEach(function(d) {
                            d.classList.toggle('selected', d.getAttribute('data-color') === selectedColor);
                        });
                    }
                });
            })
            .catch(function() {});
        });
    });

    // ── Double-click on empty slot → Quick-Add ──
    document.querySelectorAll('.time-slot-cell').forEach(function(el) {
        el.addEventListener('dblclick', function() {
            var dayId = el.parentElement.getAttribute('data-day-id');
            var time = el.getAttribute('data-time');
            openModal({
                id: '',
                title: '{% trans "New Event" %}',
                notes: '',
                color: 'blue',
                day_id: dayId,
                start_time: time,
                duration_minutes: 60,
            });
        });
    });

    // ── Init Modal: Prevent HTMX form submit for quick-add ──
    document.querySelectorAll('[hx-post]').forEach(function(el) {
        el.addEventListener('htmx:beforeRequest', function(evt) {
            evt.preventDefault();  // Block HTMX – wir machen AJAX selbst via Modal
        });
    });
})();
</script>
{% endblock %}
```

---

### Schritt 6: SortableJS Drag&Drop für Events

Der `extra_js`-Block oben endet mit Modal-Setup. **Am Ende des Blocks** (vor `})();`) wird SortableJS aktiviert:

```javascript
// ── Drag & Drop: Events zwischen Tagen verschieben ──
(function initSortable() {
    var containers = document.querySelectorAll('.sortable-container');
    containers.forEach(function(container) {
        new Sortable(container, {
            group: 'team-calendar',
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            filter: '.time-slot-cell',  // Nur .cal-event verschieben
            onEnd: function(evt) {
                var eventEl = evt.item;
                var eventId = eventEl.getAttribute('data-event-id');
                if (!eventId) return;

                // Neue Position bestimmen
                var newDayId = evt.to.getAttribute('data-day-id');
                var slotCells = evt.to.querySelectorAll('.time-slot-cell');
                var newIndex = Math.min(evt.newIndex || 0, slotCells.length - 1);
                var newTime = slotCells[newIndex]?.getAttribute('data-time') || '09:00';

                // Falls innerhalb derselben Position → nichts tun
                var oldDayId = eventEl.getAttribute('data-day-id');
                if (oldDayId === newDayId && eventEl.getAttribute('data-start-time') === newTime) {
                    location.reload();  // zurück in Ursprungsposition
                    return;
                }

                var payload = JSON.stringify({
                    day_id: newDayId,
                    start_time: newTime,
                    week_start: weekStart,
                });

                fetch('/org/team-calendar/api/events/' + eventId + '/update/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/json',
                    },
                    body: payload,
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.status === 'ok') {
                        location.reload();
                    } else {
                        console.error('Move failed:', data.error);
                        location.reload();
                    }
                })
                .catch(function() {
                    location.reload();
                });
            }
        });
    });
})();
```

---

### Schritt 7: Quick-Add per einfachem Klick

Die HTMX-Attribute auf `.time-slot-cell` werden durch JS ersetzt. Der einfache Klick öffnet das Modal (vorgefüllt). **Entferne die `hx-*`-Attribute** aus dem Template oben und ersetze durch:

```javascript
// ── Single click on slot → Quick-Add Modal ──
document.querySelectorAll('.time-slot-cell').forEach(function(el) {
    el.addEventListener('click', function() {
        var dayId = el.parentElement.getAttribute('data-day-id');
        var time = el.getAttribute('data-time');
        openModal({
            id: '',
            title: '{% trans "New Event" %}',
            notes: '',
            color: 'blue',
            day_id: dayId,
            start_time: time,
            duration_minutes: 60,
        });
    });
});
```

---

### Schritt 8: Navigation in der Organisation

**Datei:** `templates/organizations/dashboard.html`

Im Settings-Block den Button "Weekly Calendar" ergänzen um einen zweiten Button:

```html
<div style="display:flex; gap:8px; flex-wrap:wrap;">
    <a href="/org/weekly/" class="btn btn-primary btn-sm">📅 {% trans "Weekly Calendar" %}</a>
    <a href="/org/team-calendar/" class="btn btn-secondary btn-sm">👥 {% trans "Team Calendar" %}</a>
</div>
```

---

### Schritt 9: i18n / Übersetzungen

Nachdem alle Templates erstellt sind:

```bash
cd /home/lukas/code/cl-verkehrstechnik/trackable
django-admin makemessages -l de
```

Neue Strings in `locale/de/LC_MESSAGES/django.po` übersetzen:

```
msgid "Team Calendar"
msgstr "Team-Kalender"

msgid "New Event"
msgstr "Neues Event"

msgid "Edit Event"
msgstr "Event bearbeiten"

msgid "Delete this event?"
msgstr "Dieses Event löschen?"

# … alle weiteren neuen Strings …
```

Dann kompilieren:

```bash
django-admin compilemessages
```

---

### Schritt 10: Tests

**Neu erstellen:** `tests/test_calendar.py`

```python
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import date, time
from trackable.organizations.models import Organization, OrganizationMembership, CalendarEvent
from trackable.profiles.models import Profile

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

    def test_to_json(self):
        event = CalendarEvent.objects.create(
            organization=self.org,
            created_by=self.user,
            title="JSON Event",
            day_id="Tuesday",
            start_time=time(10, 30),
            duration_minutes=30,
            week_start=date(2026, 6, 15),
        )
        data = event.to_json()
        self.assertEqual(data["title"], "JSON Event")
        self.assertEqual(data["day_id"], "Tuesday")
        self.assertEqual(data["start_time"], "10:30")
        self.assertEqual(data["duration_minutes"], 30)


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

    def test_get_events(self):
        CalendarEvent.objects.create(
            organization=self.org,
            created_by=self.user,
            title="Visible Event",
            day_id="Thursday",
            start_time=time(11, 0),
            duration_minutes=30,
            week_start=self.week_start,
        )
        response = self.client.get(
            reverse("calendar_get_events"),
            {"week_start": self.week_start.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["events"][0]["title"], "Visible Event")

    def test_update_event(self):
        event = CalendarEvent.objects.create(
            organization=self.org,
            created_by=self.user,
            title="Original",
            day_id="Friday",
            start_time=time(8, 0),
            duration_minutes=60,
            week_start=self.week_start,
        )
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

    def test_delete_event(self):
        event = CalendarEvent.objects.create(
            organization=self.org,
            created_by=self.user,
            title="Delete Me",
            day_id="Monday",
            start_time=time(10, 0),
            duration_minutes=30,
            week_start=self.week_start,
        )
        response = self.client.post(
            reverse("calendar_delete_event", args=[event.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CalendarEvent.objects.filter(pk=event.pk).exists()
        )

    def test_events_are_org_scoped(self):
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
        self.assertEqual(len(data["events"]), 0)  # shouldn't see other org's events

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
        # Should redirect to login (302) or return 403
        self.assertIn(response.status_code, [302, 403])
```

---

## Zusammenfassung Phase 1 – Dateien & Änderungen

| # | Aktion | Datei |
|---|--------|-------|
| 1 | **Neu** Model `CalendarEvent` | `organizations/models.py` |
| 2 | **Neu** Kalender-Settings auf `Organization` | `organizations/models.py` |
| 3 | **Migration** `0004_calendarevent` | `organizations/migrations/` |
| 4 | **Migration** `0005_org_cal_settings` | `organizations/migrations/` |
| 5 | **Neu** View-Datei | `organizations/calendar_views.py` |
| 6 | **Erweitern** URLs | `organizations/urls.py` |
| 7 | **Neu** Template | `templates/organizations/team_calendar.html` |
| 8 | **Ändern** Dashboard-Link | `templates/organizations/dashboard.html` |
| 9 | **Neu** Tests | `tests/test_calendar.py` |
| 10 | **Aktualisieren** Übersetzungen | `locale/de/LC_MESSAGES/django.po` |

---

## Phasen 2–5: Kurzreferenz

*(Details siehe ursprüngliche Planung – diese werden nach Phase 1 umgesetzt)*

### Phase 2: Enhanced Role-Based Timer Mode
- `timer_only_mode` → `time_tracking_mode` ("classic" / "restricted")
- Nur Manager dürfen bei "restricted" manuell Einträge erstellen
- Helper: `can_edit_time_entries(user)`

### Phase 3: Zeitkonto
- `Profile.get_target_hours(year, month)` – Soll basierend auf `weekly_hours / 5 × Arbeitstage`
- `Profile.get_balance(year, month)` – Ist − Soll
- Anzeige in Profil-Detail und Employee-Detail

### Phase 4: PDF-Export mit Native Share
- Neuer API-Endpunkt: `/api/export-pdf/<id>/<year>/<month>/` → Base64-JSON
- Frontend: `navigator.share()` für PDF-Blob, Fallback Download

### Phase 5: Mobile UI/UX Audit
- Touch-Targets (min 44px), Safe Areas, Tabellen-Scroll
- Calendar-Grid auf Mobile testen (48px Slot-Höhe, horizontales Scrollen)

---

*Dieses Dokument wird während der Implementierung aktualisiert.*
