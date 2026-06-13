from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from trackable.organizations.models import Organization, OrganizationMembership
from trackable.organizations.forms import (
    OrganizationForm,
    EmployeeCreateForm,
    HolidayForm,
)
from trackable.organizations.decorators import org_manager_required
from trackable.organizations.helpers import can_edit_time_entries
from trackable.profiles.models import Profile
from trackable.core.models import Holiday
from trackable.accounts.models import User
from datetime import datetime, timedelta
from django.utils import timezone as tz
import calendar


@login_required
def org_dashboard(request):
    membership = getattr(request.user, "organization_membership", None)
    if not membership:
        return redirect("org_create")

    organization = membership.organization
    if not membership.is_manager:
        return render(
            request,
            "organizations/employee_dashboard.html",
            {"organization": organization, "membership": membership},
        )

    memberships = organization.memberships.select_related("user").all()
    employee_memberships = [m for m in memberships if m.role == "employee"]
    manager_memberships = [m for m in memberships if m.role == "manager"]

    return render(
        request,
        "organizations/dashboard.html",
        {
            "organization": organization,
            "employee_memberships": employee_memberships,
            "manager_memberships": manager_memberships,
            "total_employees": len(employee_memberships),
        },
    )


@login_required
def org_create(request):
    if hasattr(request.user, "organization_membership"):
        messages.info(request, _("You are already part of an organization."))
        return redirect("org_dashboard")

    if request.method == "POST":
        form = OrganizationForm(request.POST)
        if form.is_valid():
            organization = form.save(commit=False)
            organization.created_by = request.user
            organization.save()
            OrganizationMembership.objects.create(
                organization=organization,
                user=request.user,
                role="manager",
            )
            messages.success(
                request,
                _('Organization "%(name)s" created successfully!')
                % {"name": organization.name},
            )
            return redirect("org_dashboard")
    else:
        form = OrganizationForm()

    return render(request, "organizations/create.html", {"form": form})


@login_required
@org_manager_required
def toggle_time_tracking_mode(request):
    membership = request.user.organization_membership
    organization = membership.organization
    if organization.time_tracking_mode == "classic":
        organization.time_tracking_mode = "restricted"
        status = _("restricted")
    else:
        organization.time_tracking_mode = "classic"
        status = _("classic")
    organization.save()
    messages.success(
        request,
        _("Time tracking mode set to %(mode)s.") % {"mode": status},
    )
    return redirect("org_dashboard")


@login_required
@org_manager_required
def employee_create(request):
    membership = request.user.organization_membership
    organization = membership.organization

    if request.method == "POST":
        form = EmployeeCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            OrganizationMembership.objects.create(
                organization=organization,
                user=user,
                role="employee",
            )
            # Automatisch ein Standard-Profil für den Mitarbeiter anlegen
            from trackable.profiles.models import Profile
            Profile.objects.create(
                user=user,
                title=_("Employee at %(org)s") % {"org": organization.name},
                position=_("Employee"),
                weekly_hours=40,
                hourly_rate=0,
            )
            messages.success(
                request,
                _('Employee "%(name)s" created successfully!')
                % {"name": user.get_full_name() or user.username},
            )
            return redirect("org_dashboard")
    else:
        form = EmployeeCreateForm()

    return render(
        request,
        "organizations/employee_create.html",
        {"form": form, "organization": organization},
    )


@login_required
@org_manager_required
def employee_detail(request, user_id):
    membership = request.user.organization_membership
    organization = membership.organization

    employee_membership = get_object_or_404(
        OrganizationMembership,
        organization=organization,
        user_id=user_id,
    )
    employee = employee_membership.user

    profiles = employee.profiles.all()

    current_date = datetime.now().date()
    profile_data = []
    for profile in profiles:
        entry_months = set(
            profile.time_entries.values_list("date__year", "date__month").distinct()
        )
        entry_months.add((current_date.year, current_date.month))

        months = []
        cumulative_balance = 0
        for year, month in sorted(entry_months, reverse=True):
            hours = profile.get_monthly_hours(year, month)
            target = profile.get_target_hours(year, month)
            balance = profile.get_balance(year, month)
            cumulative_balance += balance
            months.append(
                {
                    "year": year,
                    "month": month,
                    "month_name": datetime(year, month, 1).strftime("%B %Y"),
                    "hours": hours,
                    "target_hours": target,
                    "balance": balance,
                    "cumulative_balance": cumulative_balance,
                    "earnings": profile.get_monthly_earnings(year, month),
                }
            )

        profile_data.append({"profile": profile, "months": months})

    return render(
        request,
        "organizations/employee_detail.html",
        {
            "organization": organization,
            "employee": employee,
            "employee_membership": employee_membership,
            "profile_data": profile_data,
        },
    )


@login_required
@login_required
@org_manager_required
@require_http_methods(["POST"])
def set_target_hours(request, user_id, profile_id):
    """Set weekly_target_hours for an employee's profile (manager only)."""
    membership = request.user.organization_membership
    organization = membership.organization

    employee_membership = get_object_or_404(
        OrganizationMembership,
        organization=organization,
        user_id=user_id,
    )
    employee = employee_membership.user
    profile = get_object_or_404(Profile, pk=profile_id, user=employee)

    value = request.POST.get("weekly_target_hours", "").strip()
    if value == "":
        profile.weekly_target_hours = None
    else:
        try:
            profile.weekly_target_hours = float(value)
        except (ValueError, TypeError):
            messages.error(request, _("Invalid value for target hours."))
            return redirect("employee_profile_detail", user_id=user_id, profile_id=profile_id)

    profile.save()
    messages.success(request, _("Weekly target hours updated."))
    return redirect("employee_profile_detail", user_id=user_id, profile_id=profile_id)


@login_required
@org_manager_required
def employee_profile_detail(request, user_id, profile_id):
    membership = request.user.organization_membership
    organization = membership.organization

    employee_membership = get_object_or_404(
        OrganizationMembership,
        organization=organization,
        user_id=user_id,
    )
    employee = employee_membership.user

    profile = get_object_or_404(Profile, pk=profile_id, user=employee)

    import calendar
    from django.utils import timezone

    year = int(request.GET.get("year", timezone.now().year))
    month = int(request.GET.get("month", timezone.now().month))

    time_entries = list(profile.get_monthly_entries(year, month).order_by("date"))
    last_day = calendar.monthrange(year, month)[1]
    from trackable.timetracking.models import VacationEntry

    vacation_entries = list(
        profile.vacation_entries.filter(
            start_date__lte=datetime(year, month, last_day).date(),
            end_date__gte=datetime(year, month, 1).date(),
        ).order_by("start_date")
    )
    total_hours = profile.get_monthly_hours(year, month)
    total_earnings = profile.get_monthly_earnings(year, month)
    target_hours = profile.get_target_hours(year, month)
    balance = profile.get_balance(year, month)
    total_vacation_days = sum(v.workdays for v in vacation_entries)
    month_name = datetime(year, month, 1).strftime("%B %Y")

    entry_months = set(
        profile.time_entries.values_list("date__year", "date__month").distinct()
    )
    entry_months.add((timezone.now().year, timezone.now().month))
    available_months = sorted(entry_months, reverse=True)

    return render(
        request,
        "organizations/employee_profile_detail.html",
        {
            "organization": organization,
            "employee": employee,
            "profile": profile,
            "time_entries": time_entries,
            "vacation_entries": vacation_entries,
            "year": year,
            "month": month,
            "month_name": month_name,
            "total_hours": total_hours,
            "total_earnings": total_earnings,
            "target_hours": target_hours,
            "balance": balance,
            "total_vacation_days": total_vacation_days,
            "available_months": available_months,
        },
    )


@login_required
def org_weekly_calendar(request):
    membership = getattr(request.user, "organization_membership", None)
    if not membership:
        return redirect("org_create")

    organization = membership.organization
    is_manager = membership.is_manager

    # ISO-Kalenderwoche aus URL
    today = tz.now().date()
    iso = today.isocalendar()
    year = int(request.GET.get("year", iso[0]))
    week = int(request.GET.get("week", iso[1]))

    # Wochen-Montag & -Sonntag
    try:
        monday = datetime.fromisocalendar(year, week, 1).date()
    except (ValueError, TypeError):
        monday = today - timedelta(days=today.weekday())
        year, week, _ = monday.isocalendar()

    sunday = monday + timedelta(days=6)
    week_dates = [monday + timedelta(days=i) for i in range(7)]

    # Alle Mitglieder holen
    memberships = organization.memberships.select_related("user").all()

    week_data = []
    for m in memberships:
        user = m.user
        day_cells = [{"entries": [], "total": 0.0} for _ in range(7)]

        profiles = user.profiles.all()
        for profile in profiles:
            day_entries = profile.time_entries.filter(
                date__gte=monday, date__lte=sunday
            ).order_by("date", "start_time")

            for entry in day_entries:
                day_idx = entry.date.weekday()  # 0=Mon … 6=Sun
                day_cells[day_idx]["entries"].append({
                    "entry": entry,
                    "profile_title": profile.title,
                })
                day_cells[day_idx]["total"] += float(entry.hours_worked)

        total_weekly = sum(cell["total"] for cell in day_cells)

        week_data.append({
            "membership": m,
            "user": user,
            "day_cells": day_cells,
            "total_weekly": round(total_weekly, 2),
        })

    # Vorherige / Nächste Woche
    prev_monday = monday - timedelta(days=7)
    next_monday = monday + timedelta(days=7)
    prev_iso = prev_monday.isocalendar()
    next_iso = next_monday.isocalendar()
    today_iso = today.isocalendar()

    return render(
        request,
        "organizations/weekly_calendar.html",
        {
            "organization": organization,
            "is_manager": is_manager,
            "week_data": week_data,
            "year": year,
            "week": week,
            "monday": monday,
            "sunday": sunday,
            "week_dates": week_dates,
            "prev_url": f"?year={prev_iso[0]}&week={prev_iso[1]}",
            "next_url": f"?year={next_iso[0]}&week={next_iso[1]}",
            "today_url": f"?year={today_iso[0]}&week={today_iso[1]}",
            "timer_only": not can_edit_time_entries(request.user),
        },
    )


@login_required
@org_manager_required
def move_entry(request, entry_id):
    from trackable.timetracking.models import TimeEntry

    entry = get_object_or_404(TimeEntry, pk=entry_id)
    membership = request.user.organization_membership

    # Prüfen: entry gehört zur gleichen Organisation
    entry_org = getattr(
        entry.profile.user, "organization_membership", None
    )
    if not entry_org or entry_org.organization != membership.organization:
        return JsonResponse({"error": _("Entry does not belong to your organization.")}, status=403)

    new_date_str = request.POST.get("new_date")
    if not new_date_str:
        return JsonResponse({"error": _("new_date is required.")}, status=400)

    try:
        entry.date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": _("Invalid date format.")}, status=400)

    entry.save()
    return JsonResponse({"status": "ok"})


@login_required
@org_manager_required
def employee_remove(request, user_id):
    membership = request.user.organization_membership
    organization = membership.organization

    employee_membership = get_object_or_404(
        OrganizationMembership,
        organization=organization,
        user_id=user_id,
    )
    employee = employee_membership.user

    if request.method == "POST":
        employee_membership.delete()
        messages.success(
            request,
            _("%(name)s has been removed from the organization.")
            % {"name": employee.get_full_name() or employee.username},
        )
        return redirect("org_dashboard")

    return render(
        request,
        "organizations/employee_remove.html",
        {"organization": organization, "employee": employee},
    )


@login_required
@org_manager_required
def holiday_list(request):
    membership = request.user.organization_membership
    organization = membership.organization
    from django.utils import timezone

    current_year = timezone.now().year
    year = int(request.GET.get("year", current_year))
    holidays = organization.holidays.filter(date__year=year).order_by("date")
    year_range = range(current_year - 1, current_year + 3)
    return render(
        request,
        "organizations/holiday_list.html",
        {
            "organization": organization,
            "holidays": holidays,
            "year": year,
            "year_range": year_range,
        },
    )


@login_required
@org_manager_required
def holiday_create(request):
    membership = request.user.organization_membership
    organization = membership.organization

    if request.method == "POST":
        form = HolidayForm(request.POST)
        if form.is_valid():
            holiday = form.save(commit=False)
            holiday.organization = organization
            holiday.save()
            messages.success(
                request,
                _('Holiday "%(name)s" added successfully!') % {"name": holiday.name},
            )
            return redirect("org_holidays")
    else:
        form = HolidayForm()

    return render(
        request,
        "organizations/holiday_form.html",
        {"form": form, "organization": organization},
    )


@login_required
@org_manager_required
def holiday_delete(request, pk):
    membership = request.user.organization_membership
    organization = membership.organization

    holiday = get_object_or_404(Holiday, pk=pk, organization=organization)
    if request.method == "POST":
        holiday.delete()
        messages.success(request, _("Holiday deleted."))
    return redirect("org_holidays")
