import base64
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from trackable.profiles.models import Profile
from trackable.core.pdf_export import generate_pdf_report


@login_required
def api_export_pdf(request, profile_id, year, month):
    """Return PDF as Base64 JSON for use with Web Share API."""
    profile = get_object_or_404(Profile, pk=profile_id, user=request.user)

    buffer = generate_pdf_report(profile, year, month)
    pdf_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    buffer.close()

    filename = f"arbeitszeiten_{profile.title}_{year}_{month}.pdf"

    return JsonResponse({"pdf_base64": pdf_base64, "filename": filename})
