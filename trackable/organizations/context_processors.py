def org_branding(request):
    """Stellt Branding-Daten für alle Templates bereit."""
    branding = {
        "org_logo_url": None,
        "org_favicon_url": None,
        "org_apple_touch_icon_url": None,
        "org_primary_color": "",
        "org_accent_color": "",
        "org_custom_css": "",
        "has_branding": False,
    }
    membership = getattr(request.user, "organization_membership", None)
    if not membership:
        return branding
    org = membership.organization

    has_branding = False
    if org.logo:
        branding["org_logo_url"] = org.logo.url
        has_branding = True
    if org.favicon:
        branding["org_favicon_url"] = org.favicon.url
        has_branding = True
    if org.apple_touch_icon:
        branding["org_apple_touch_icon_url"] = org.apple_touch_icon.url
        has_branding = True
    if org.primary_color:
        branding["org_primary_color"] = org.primary_color
        has_branding = True
    if org.accent_color:
        branding["org_accent_color"] = org.accent_color
        has_branding = True
    if org.custom_css:
        branding["org_custom_css"] = org.custom_css
        has_branding = True

    branding["has_branding"] = has_branding
    return branding
