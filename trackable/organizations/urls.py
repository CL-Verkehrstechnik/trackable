from django.urls import path
from . import views
from . import calendar_views

urlpatterns = [
    path("", views.org_dashboard, name="org_dashboard"),
    path("create/", views.org_create, name="org_create"),
    path("employees/create/", views.employee_create, name="employee_create"),
    path("employees/<int:user_id>/", views.employee_detail, name="employee_detail"),
    path(
        "employees/<int:user_id>/profiles/<int:profile_id>/",
        views.employee_profile_detail,
        name="employee_profile_detail",
    ),
    path(
        "employees/<int:user_id>/profiles/<int:profile_id>/set-target-hours/",
        views.set_target_hours,
        name="set_target_hours",
    ),
    path(
        "employees/<int:user_id>/profiles/<int:profile_id>/set-contract-dates/",
        views.set_contract_dates,
        name="set_contract_dates",
    ),
    path(
        "employees/<int:user_id>/remove/", views.employee_remove, name="employee_remove"
    ),
    path("weekly/", views.org_weekly_calendar, name="org_weekly_calendar"),
    path("weekly/create-entry/", views.create_entry, name="create_entry"),
    path("weekly/update-entry/<int:entry_id>/", views.update_entry, name="update_entry"),
    path("weekly/move-entry/<int:entry_id>/", views.move_entry, name="move_entry"),
    path("toggle-time-tracking-mode/", views.toggle_time_tracking_mode, name="toggle_time_tracking_mode"),
    path("holidays/", views.holiday_list, name="org_holidays"),
    path("holidays/add/", views.holiday_create, name="org_holiday_add"),
    path("holidays/<int:pk>/delete/", views.holiday_delete, name="org_holiday_delete"),

    # Team Calendar
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

    # Branding
    path("branding/", views.org_branding, name="org_branding"),
]
