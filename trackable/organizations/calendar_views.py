from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime, timedelta, date, time
from trackable.organizations.models import Organization, OrganizationMembership, CalendarEvent
import json


# ── Helpers ──────────────────────────────────────────────────


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

DAYS_ALL = [
    ("Monday", "Monday"),
    ("Tuesday", "Tuesday"),
    ("Wednesday", "Wednesday"),
    ("Thursday", "Thursday"),
    ("Friday", "Friday"),
    ("Saturday", "Saturday"),
    ("Sunday", "Sunday"),
]

SHORT_DAY_LABELS = {
    "Monday": "Mo",
    "Tuesday": "Di",
    "Wednesday": "Mi",
    "Thursday": "Do",
    "Friday": "Fr",
    "Saturday": "Sa",
    "Sunday": "So",
}


# ── Views ────────────────────────────────────────────────────


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
    if settings["week_starts_on"] == 0:  # Sunday
        all_days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    else:
        all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

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
    first_slot_minutes = settings["start_time"].hour * 60 + settings["start_time"].minute
    px_per_min = pixels_per_hour / 60

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
            "label": _(day_name),
            "short_label": SHORT_DAY_LABELS.get(day_name, day_name[:2]),
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
    """AJAX: Neues Event erstellen."""
    membership, error = _get_membership_or_redirect(request.user)
    if error:
        return JsonResponse({"error": str(error)}, status=403)

    if request.content_type == "application/json":
        data = json.loads(request.body)
    else:
        data = request.POST

    day_id = data.get("day_id")
    start_time_str = data.get("start_time")
    title = data.get("title", _("New Event"))
    duration_minutes = int(data.get("duration_minutes", 60))
    color = data.get("color", "blue")
    week_start_str = data.get("week_start")
    notes = data.get("notes", "")

    if not day_id or not start_time_str or not week_start_str:
        return JsonResponse(
            {"error": _("day_id, start_time, and week_start are required.")}, status=400
        )

    try:
        start_time = datetime.strptime(start_time_str, "%H:%M").time()
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return JsonResponse({"error": _("Invalid date/time format.")}, status=400)

    event = CalendarEvent.objects.create(
        organization=membership.organization,
        created_by=request.user,
        title=title,
        notes=notes,
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
    """AJAX: Event aktualisieren (Title, Notes, Color, Time, Day, Duration)."""
    membership, error = _get_membership_or_redirect(request.user)
    if error:
        return JsonResponse({"error": str(error)}, status=403)

    event = get_object_or_404(
        CalendarEvent, pk=event_id, organization=membership.organization
    )

    if request.content_type == "application/json":
        data = json.loads(request.body)
    else:
        data = request.POST

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
        return JsonResponse(
            {"error": _("You can only delete your own events.")}, status=403
        )

    event.delete()
    return JsonResponse({"status": "ok"})


@login_required
def calendar_get_events(request):
    """JSON: Alle Events einer Woche abrufen."""
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
