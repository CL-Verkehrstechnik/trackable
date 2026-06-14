from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from trackable.core.models import Holiday, SiteConfiguration
from trackable.core.admin_site import custom_admin_site


@admin.register(Holiday, site=custom_admin_site)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ["date", "name", "organization"]
    list_filter = ["date", "organization"]
    search_fields = ["name"]
    ordering = ["date"]


@admin.register(SiteConfiguration, site=custom_admin_site)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ["setup_completed", "registration_enabled"]
    fieldsets = (
        (None, {
            "fields": ("setup_completed", "registration_enabled"),
        }),
        (_("Email configuration"), {
            "fields": ("email_host", "email_port", "email_use_tls", "email_host_user", "email_host_password", "default_from_email"),
            "description": _("Leave empty to use environment variable defaults."),
        }),
    )
