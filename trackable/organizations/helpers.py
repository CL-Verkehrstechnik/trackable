def can_edit_time_entries(user):
    """Check if a user can manually create/edit/delete time entries.

    - Without org membership: always allowed
    - Org mode 'classic': always allowed
    - Org mode 'restricted': only managers/owners allowed
    """
    membership = getattr(user, "organization_membership", None)
    if not membership:
        return True
    org = membership.organization
    if org.time_tracking_mode == "classic":
        return True
    # restricted mode
    return membership.is_manager
