from django.db import models
from django.utils.translation import gettext_lazy as _


class Holiday(models.Model):
    date = models.DateField()
    name = models.CharField(max_length=200)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="holidays",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["date"]
        verbose_name = "Holiday"
        verbose_name_plural = "Holidays"
        unique_together = [("date", "organization")]

    def __str__(self):
        return f"{self.date} – {self.name}"


class SiteConfiguration(models.Model):
    """Singleton configuration for the trackable instance."""
    setup_completed = models.BooleanField(default=False, verbose_name=_("Setup completed"))
    registration_enabled = models.BooleanField(default=True, verbose_name=_("Registration enabled"))
    
    # Email configuration (overrides env vars when set)
    email_host = models.CharField(max_length=200, blank=True, default="", verbose_name=_("Email host"))
    email_port = models.IntegerField(default=587, verbose_name=_("Email port"))
    email_use_tls = models.BooleanField(default=True, verbose_name=_("Email use TLS"))
    email_host_user = models.CharField(max_length=200, blank=True, default="", verbose_name=_("Email host user"))
    email_host_password = models.CharField(max_length=200, blank=True, default="", verbose_name=_("Email host password"))
    default_from_email = models.CharField(max_length=200, blank=True, default="", verbose_name=_("Default from email"))
    allowed_hosts = models.CharField(
        max_length=500, blank=True, default="",
        verbose_name=_("Allowed hosts"),
        help_text=_("Comma-separated list of allowed hostnames. Leave empty to use the ALLOWED_HOSTS env var."),
    )

    class Meta:
        verbose_name = _("Site configuration")
        verbose_name_plural = _("Site configuration")

    def __str__(self):
        return _("Site configuration")

    @classmethod
    def get(cls):
        """Return the singleton instance, creating it if necessary."""
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj
