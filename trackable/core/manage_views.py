from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from trackable.core.models import SiteConfiguration
from trackable.accounts.models import User


@staff_member_required
def manage_dashboard(request):
    """Management dashboard overview."""
    config = SiteConfiguration.get()
    user_count = User.objects.count()
    staff_count = User.objects.filter(is_staff=True).count()
    superuser_count = User.objects.filter(is_superuser=True).count()
    
    return render(request, "core/manage/dashboard.html", {
        "config": config,
        "user_count": user_count,
        "staff_count": staff_count,
        "superuser_count": superuser_count,
    })


@staff_member_required
def manage_settings(request):
    """Edit SiteConfiguration settings."""
    config = SiteConfiguration.get()
    
    if request.method == "POST":
        config.registration_enabled = request.POST.get("registration_enabled") == "on"
        
        email_host = request.POST.get("email_host", "").strip()
        config.email_host = email_host
        
        email_port_str = request.POST.get("email_port", "").strip()
        if email_port_str:
            try:
                config.email_port = int(email_port_str)
            except (ValueError, TypeError):
                pass
        
        config.email_use_tls = request.POST.get("email_use_tls") == "on"
        config.email_host_user = request.POST.get("email_host_user", "").strip()
        
        # Only update password if a new value is provided (otherwise keep existing)
        new_password = request.POST.get("email_host_password", "").strip()
        if new_password:
            config.email_host_password = new_password
        
        config.default_from_email = request.POST.get("default_from_email", "").strip()
        config.save()
        
        messages.success(request, _("Settings saved."))
        return redirect("manage_settings")
    
    return render(request, "core/manage/settings.html", {
        "config": config,
    })


@staff_member_required
def manage_reset_setup(request):
    """Reset the setup wizard (set setup_completed=False)."""
    if request.method == "POST":
        config = SiteConfiguration.get()
        config.setup_completed = False
        config.save()
        messages.success(
            request,
            _("Setup wizard has been reset. New users will be guided through setup again."),
        )
    return redirect("manage_dashboard")


@staff_member_required
def manage_user_list(request):
    """List all users."""
    users = User.objects.all().order_by("-date_joined")
    return render(request, "core/manage/user_list.html", {
        "users": users,
    })


@staff_member_required
def manage_user_create(request):
    """Create a new user (staff can create staff/superuser accounts)."""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        is_staff = request.POST.get("is_staff") == "on"
        # Only superusers can create other superusers (privilege escalation protection)
        is_superuser = request.user.is_superuser and request.POST.get("is_superuser") == "on"
        
        errors = []
        if not username:
            errors.append(_("Username is required."))
        if not email:
            errors.append(_("Email is required."))
        if not password:
            errors.append(_("Password is required."))
        
        if User.objects.filter(username=username).exists():
            errors.append(_("Username is already taken."))
        if email and User.objects.filter(email=email).exists():
            errors.append(_("Email is already in use."))
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, "core/manage/user_form.html", {
                "is_create": True,
            })
        
        user = User.objects.create(
            username=username,
            email=email,
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=True,
            email_confirmed=True,
        )
        user.set_password(password)
        user.save()
        
        messages.success(
            request,
            _('User "%(username)s" created.') % {"username": username},
        )
        return redirect("manage_user_list")
    
    return render(request, "core/manage/user_form.html", {
        "is_create": True,
    })


@staff_member_required
def manage_user_detail(request, user_id):
    """View and edit a single user."""
    user = get_object_or_404(User, pk=user_id)
    
    if request.method == "POST":
        user.email = request.POST.get("email", "").strip()
        user.is_active = request.POST.get("is_active") == "on"
        user.is_staff = request.POST.get("is_staff") == "on"
        # Only superusers can grant superuser status
        if request.user.is_superuser:
            user.is_superuser = request.POST.get("is_superuser") == "on"
        
        new_password = request.POST.get("password", "").strip()
        if new_password:
            user.set_password(new_password)
        
        user.save()
        messages.success(
            request,
            _('User "%(username)s" updated.') % {"username": user.username},
        )
        return redirect("manage_user_detail", user_id=user.id)
    
    return render(request, "core/manage/user_detail.html", {
        "managed_user": user,
    })
