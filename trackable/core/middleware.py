from django.shortcuts import redirect
from django.urls import reverse


class SetupRedirectMiddleware:
    """Redirect unauthenticated users to the setup wizard if setup is not complete.
    
    The middleware checks SiteConfiguration.setup_completed. If False,
    all unauthenticated requests (except to /setup/, /health/, /static/,
    /media/, /admin/) are redirected to the setup wizard.
    
    Once setup_completed is True, this middleware is effectively a no-op.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for authenticated users
        if request.user.is_authenticated:
            return self.get_response(request)

        path = request.path_info

        # Skip URLs that must remain accessible during setup
        skip_prefixes = ("/setup/", "/health/", "/static/", "/media/", "/admin/")
        if any(path.startswith(prefix) for prefix in skip_prefixes):
            return self.get_response(request)

        # Check if setup is completed
        try:
            from trackable.core.models import SiteConfiguration
            config = SiteConfiguration.get()
            if not config.setup_completed:
                return redirect("setup_step1")
        except Exception:
            # SiteConfiguration table might not exist yet — redirect to setup
            try:
                return redirect("setup_step1")
            except Exception:
                pass

        return self.get_response(request)
