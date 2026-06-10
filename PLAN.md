# Weekly Calendar & Timer-Only Mode – Implementation Plan

## Übersicht

Zwei zusammenhängende Features für das trackable-Projekt:

1. **Timer-Only Mode** (pro Organisation schaltbar) – Erzwingt, dass Arbeitszeit nur via Start/Stop-Timer erfasst wird. Manuelle Einträge (Formular) und Editieren/Löschen werden deaktiviert.
2. **Weekly Calendar** – Eine Wochenübersicht pro Organisation, die alle Mitarbeiter und ihre Arbeitszeiten pro Tag in einem Grid anzeigt.

---

## Phase 1: Timer-Only Mode (Foundation)

### 1.1 Datenmodell: `Organization.timer_only_mode`

**Datei:** `trackable/organizations/models.py`

```python
class Organization(models.Model):
    # Bestehende Felder…
    timer_only_mode = models.BooleanField(default=False, verbose_name=_("Timer only mode"))
```

**Migration:** `python manage.py makemigrations organizations`

---

### 1.2 Toggle-View für Manager

**Datei:** `trackable/organizations/views.py`

Neue View `toggle_timer_mode(request)`:
- `@login_required, @org_manager_required`
- Nur POST
- Holt `organization` aus `request.user.organization_membership.organization`
- Togglet `organization.timer_only_mode`
- Gibt JSON `{"timer_only_mode": bool}` zurück → wird via fetch() vom Dashboard aus aufgerufen

**URL:** `trackable/organizations/urls.py` ein neuer Pfad:
```python
path("toggle-timer-mode/", views.toggle_timer_mode, name="toggle_timer_mode"),
```

---

### 1.3 Dashboard: Timer-Only Toggle-UI & Weekly-Link

**Datei:** `templates/organizations/dashboard.html`

Neue Sektion im Manager-Dashboard oberhalb der Mitarbeiterliste:
- Ein Toggle-Switch für Timer-Only Mode
- Ein Link zur Weekly Calendar (`/org/weekly/`)
- Der Toggle ruft `/org/toggle-timer-mode/` per POST auf und aktualisiert die UI

**Neues CSS in** `static/css/styles.css`: Toggle-Switch Styling (ca. 30 Zeilen am Ende der Datei vor `.timer-display`).

---

### 1.4 Home: Manuelle Einträge ausblenden

**Datei:** `templates/timetracking/home.html`

- Der `+ Add time` Button pro Profile-Card wird nur angezeigt, wenn für die Org (falls vorhanden) `timer_only_mode == False` ist
- Kontext-Variable in `timetracking/views.py` home-View: `org_timer_only = membership.organization.timer_only_mode if has_org else False`

---

### 1.5 Add/Edit Entry Views blocken

**Datei:** `trackable/timetracking/views.py`

In `add_entry` und `edit_entry`: Nach `get_object_or_404(Profile, ...)`, prüfen ob der User in einer Org ist und `timer_only_mode == True`. Falls ja:

```python
if hasattr(profile.user, "organization_membership") and \
   profile.user.organization_membership.organization.timer_only_mode:
    messages.error(request, _("Manual time entry is disabled. Please use the timer."))
    return redirect("home")
```

---

### 1.6 Monthly Table schreibgeschützt

**Datei:** `templates/timetracking/monthly_table.html`

- Die Spalte mit Edit/Delete-Buttons (`<td>`) wird nur gerendert, wenn `show_actions == True`
- Kontext in `monthly_table`-View: `show_actions = not (hasattr(user, 'organization_membership') and user.organization_membership.organization.timer_only_mode)`

---

### 1.7 Monthly Table (Manager-Ansicht) schreibgeschützt

**Datei:** `templates/organizations/employee_profile_detail.html`

Gleiche Logik: Die Edit/Delete-Spalte existiert in diesem Template nicht, daher keine Änderung nötig. Aber für Konsistenz keine Actions in Timer-Only Mode.

---

## Phase 2: Server-Authoritative Timer Enhancement

Der bestehende Timer (`timetracking/views.py` start_timer, pause_timer, resume_timer, stop_timer) ist bereits server-seitig timestamp-basiert. Start speichert `timezone.now()`, Stop rechnet korrekt.

### 2.1 Source-Flag in TimeEntry (optional, für später)

Ein `source`-Feld (`"timer"` vs `"manual"`) erlaubt es zu unterscheiden, ob ein Eintrag vom Timer oder Formular stammt. In Phase 1 noch nicht nötig, da Timer-Only Mode alle Einträge schreibgeschützt macht – egal woher sie kommen.

**Zurückgestellt** – wird nur gebraucht, wenn wir gemischte Modi erlauben wollen.

### 2.2 Robusterer Timer – Client-Server-Sync

**Datei:** `static/js/timer.js`

Optimierungen:
- Nach `stop` wird die monthly_table-Seite (falls sichtbar) automatisch aktualisiert
- Poll-Intervall bleibt bei 5s, Timer-Display-Updates lokal jede Sekunde
- Beim Seiten-Load: alle Timer-Status über `/timer/{profileId}/status/` abrufen

→ **Keine großen Änderungen nötig**, der bestehende Code ist solide.

### 2.3 Timer erzeugt Eintrag mit korrektem Datum

Im `stop_timer`-View:
```python
entry_date = timer.start_time.date()
```
Dieses Datum wird für den TimeEntry verwendet. Das ist korrekt. Auch wenn der Timer über Mitternacht läuft, wird der Eintrag dem Start-Datum zugeordnet. Das sollte dokumentiert werden.

---

## Phase 3: Weekly Calendar

### 3.1 Neue View: `org_weekly_calendar`

**Datei:** `trackable/organizations/views.py`

```python
@login_required
def org_weekly_calendar(request):
    membership = getattr(request.user, "organization_membership", None)
    if not membership:
        return redirect("org_create")

    organization = membership.organization
    
    # ISO-Woche aus URL (default: aktuelle Woche)
    year = int(request.GET.get("year", timezone.now().year))
    week = int(request.GET.get("week", timezone.now().isocalendar()[1]))
    
    # Wochen-Montag & -Sonntag berechnen
    monday = datetime.fromisocalendar(year, week, 1).date()
    sunday = monday + timedelta(days=6)
    
    # Alle Mitglieder + ihre Profile
    memberships = organization.memberships.select_related("user").all()
    
    # Für jedes Mitglied: TimeEntries in der Woche
    week_data = []
    for m in memberships:
        user = m.user
        profiles = user.profiles.all()
        entries_by_day = {d: [] for d in range(7)}  # 0=Mon … 6=Sun
        
        for profile in profiles:
            day_entries = profile.time_entries.filter(
                date__gte=monday, date__lte=sunday
            ).order_by("date", "start_time")
            
            for entry in day_entries:
                day_idx = entry.date.weekday()  # 0=Mon … 6=Sun
                entries_by_day[day_idx].append({
                    "entry": entry,
                    "profile_title": profile.title,
                })
        
        week_data.append({
            "membership": m,
            "user": user,
            "entries_by_day": entries_by_day,
        })
    
    # Vorherige / Nächste Woche
    prev_monday = monday - timedelta(days=7)
    next_monday = monday + timedelta(days=7)
    
    return render(request, "organizations/weekly_calendar.html", {
        "organization": organization,
        "membership": membership,
        "week_data": week_data,
        "year": year,
        "week": week,
        "monday": monday,
        "sunday": sunday,
        "week_days": [
            (monday + timedelta(days=i))
            for i in range(7)
        ],
        "prev_url": f"?year={prev_monday.isocalendar()[0]}&week={prev_monday.isocalendar()[1]}",
        "next_url": f"?year={next_monday.isocalendar()[0]}&week={next_monday.isocalendar()[1]}",
        "today_url": f"?year={timezone.now().year}&week={timezone.now().isocalendar()[1]}",
        "timer_only": organization.timer_only_mode,
    })
```

### 3.2 URL-Pattern

**Datei:** `trackable/organizations/urls.py`

```python
path("weekly/", views.org_weekly_calendar, name="org_weekly_calendar"),
```

### 3.3 Template: `templates/organizations/weekly_calendar.html`

Grid-Layout:
- **Kopfzeile:** Wochen-Navigation (`← KW 23 · KW 24 · KW 25 →`), "Heute"-Button
- **1. Spalte:** Mitarbeitername
- **Spalten 2–8:** Montag bis Sonntag (Datum als Subheader)
- **Jede Zelle:** Summe der Stunden (`X.Xh`) + kurze Eintragsliste (Start-End, Profilname)
- **Timer-Only Mode:** Zellen sind rein informativ, kein Add/Edit
- **Normaler Modus:** Klick auf Zelle öffnet Modal mit Einträgen + "Eintrag hinzufügen"
- **Drag & Drop:** Mit SortableJS (siehe Phase 3.5)

```html
{% extends 'base.html' %}
{% load i18n %}

{% block title %}{% trans "Weekly Calendar" %} – {{ organization.name }}{% endblock %}

{% block content %}
<div class="content">
    <!-- Navigation -->
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:20px;">
        <a href="/org/" class="btn btn-secondary btn-sm">← {% trans "Back to organization" %}</a>
        <div style="display:flex; gap:8px; align-items:center;">
            <a href="{{ prev_url }}" class="btn btn-secondary btn-sm">←</a>
            <span style="font-weight:600;">{% trans "Week" %} {{ week }} – {{ monday|date:"d.m." }}–{{ sunday|date:"d.m.Y" }}</span>
            <a href="{{ next_url }}" class="btn btn-secondary btn-sm">→</a>
            <a href="{{ today_url }}" class="btn btn-primary btn-sm">{% trans "Today" %}</a>
        </div>
    </div>

    <!-- Grid -->
    <div style="overflow-x:auto;">
        <table class="table" style="min-width:800px;">
            <thead>
                <tr>
                    <th style="width:160px; position:sticky; left:0; background:var(--ctp-mantle); z-index:2;">{% trans "Employee" %}</th>
                    {% for day in week_days %}
                    <th style="text-align:center; min-width:120px;">
                        <div>{{ day|date:"D" }}</div>
                        <div style="font-size:.8rem; font-weight:400; color:var(--ctp-subtext0);">{{ day|date:"d.m." }}</div>
                    </th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for wd in week_data %}
                <tr>
                    <td style="position:sticky; left:0; background:var(--ctp-mantle); z-index:1; font-weight:600;">
                        {{ wd.user.get_full_name|default:wd.user.username }}
                    </td>
                    {% for day_idx, entries in wd.entries_by_day.items %}
                    <td style="vertical-align:top; padding:8px;" data-user-id="{{ wd.user.id }}" data-day="{{ day_idx }}" data-date="{{ week_days|slice:':7'|first|add_days:day_idx|date:'Y-m-d' }}">
                        {% if entries %}
                        <div style="display:flex; flex-direction:column; gap:3px;">
                            {% for e in entries %}
                            <div class="entry-chip" data-entry-id="{{ e.entry.id }}"
                                 style="background:rgba(202,158,230,.12); border-radius:4px; padding:3px 6px; font-size:.74rem; cursor:grab;">
                                <div style="font-weight:600;">{{ e.entry.start_time|time:"H:i" }}–{{ e.entry.end_time|time:"H:i" }}</div>
                                <div style="color:var(--ctp-subtext0);">{{ e.profile_title }}</div>
                                <div style="font-size:.7rem; color:var(--ctp-mauve);">{{ e.entry.hours_worked|floatformat:1 }}h</div>
                            </div>
                            {% endfor %}
                        </div>
                        {% endif %}
                        <div style="text-align:center; margin-top:4px; font-size:.85rem; font-weight:600; color:var(--ctp-mauve);">
                            {{ entries|sum_hours|floatformat:1 }}h
                        </div>
                    </td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
```

**Template-Filter:** `add_days` und `sum_hours` müssen als custom template tags oder inline gelöst werden.

Vereinfachung für `add_days`: Statt custom Filter, in der View `week_days` als Liste von Date-Objekten übergeben, und im Template per `week_days[day_idx]` darauf zugreifen – aber der Index ist der weekday (0-6), der passt direkt. Also:

```python
# In der View:
week_days = [(monday + timedelta(days=i)) for i in range(7)]
# Dann im Template: week_days[forloop.counter0] statt add_days
```

Aber im inneren Loop (entries_by_day.items) haben wir day_idx (0-6) als Key. Ein dict access `week_days[day_idx]` geht nicht direkt im Template. Daher:

**Bessere Vereinfachung:** Statt Dict `{0: [...], ..., 6: [...]}`, eine Liste `[ [], [], [], [], [], [], [] ]` für entries_by_day.

### 3.4 Wochen-Daten in der View

**Datei:** `trackable/organizations/views.py`

Anpassung der View, `entries_by_day` als Liste (nicht Dict):

```python
entries_by_day = [[] for _ in range(7)]
for entry in day_entries:
    day_idx = entry.date.weekday()
    entries_by_day[day_idx].append({...})
```

Im Template dann:

```python
{% for day_entries in wd.entries_by_day %}
<td data-day="{{ forloop.counter0 }}" …>
    {% if day_entries %}
        {% for e in day_entries %}
        …
        {% endfor %}
    {% endif %}
    → Total hours berechnen in View
</td>
{% endfor %}
```

Total hours pro Tag pro Person: in der View berechnen.

### 3.5 Drag & Drop (Phase 3b – nach Basis-Weekly)

**Bibliothek:** SortableJS (https://github.com/SortableJS/Sortable) – 5KB gzipped, kein Framework nötig.

Einbindung via CDN in `templates/organizations/weekly_calendar.html`:

```html
{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
<script>
// Weekly Calendar JS – Drag & Drop, Modal
(function() {
    'use strict';

    // Sortable: entries zwischen days verschieben
    document.querySelectorAll('tbody tr').forEach(function(row) {
        var cells = row.querySelectorAll('td[data-date]');
        cells.forEach(function(cell) {
            new Sortable(cell.querySelector('.entries-container') || cell, {
                group: 'week-grid',
                animation: 150,
                onEnd: function(evt) {
                    var entryId = evt.item.dataset.entryId;
                    var newDate = evt.to.closest('td').dataset.date;
                    if (!entryId || !newDate) return;

                    fetch('/org/weekly/move-entry/' + entryId + '/', {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrfToken(),
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                        body: 'new_date=' + newDate,
                    })
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (data.status === 'ok') {
                            // Neu laden
                            location.reload();
                        }
                    });
                }
            });
        });
    });

    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
               document.cookie.split('; ').find(function(row) {
                   return row.startsWith('csrftoken=');
               })?.split('=')[1];
    }
})();
</script>
{% endblock %}
```

### 3.6 Move-Entry-API

**Datei:** `trackable/organizations/views.py`

```python
@login_required
@require_http_methods(["POST"])
def move_entry(request, entry_id):
    from trackable.timetracking.models import TimeEntry
    
    entry = get_object_or_404(TimeEntry, pk=entry_id)
    membership = getattr(request.user, "organization_membership", None)
    
    # Nur Manager der gleichen Organisation dürfen verschieben
    if not membership or not membership.is_manager:
        return JsonResponse({"error": "Nur Manager können Einträge verschieben"}, status=403)
    
    if entry.profile.user.organization_membership.organization != membership.organization:
        return JsonResponse({"error": "Nicht Ihre Organisation"}, status=403)
    
    new_date_str = request.POST.get("new_date")
    if not new_date_str:
        return JsonResponse({"error": "new_date required"}, status=400)
    
    from datetime import datetime
    entry.date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
    entry.save()
    
    return JsonResponse({"status": "ok"})
```

**URL:**
```python
path("weekly/move-entry/<int:entry_id>/", views.move_entry, name="move_entry"),
```

---

## Phase 4: Translationen (Deutsch)

**Datei:** `locale/de/LC_MESSAGES/django.po`

Neue Einträge (ca. 25 Strings):
- "Timer only mode" → "Nur Timer-Modus"
- "Manual time entry is disabled. Please use the timer." → "Manuelle Zeiteinträge sind deaktiviert. Bitte nutzen Sie den Timer."
- "Weekly Calendar" → "Wochenkalender"
- "Week" → "Woche"
- "Today" → "Heute"
- "Employee" → "Mitarbeiter"
- "Move entry" / "Entry moved" → "Eintrag verschoben"
- "Timer-only mode activated" / "deactivated" → "Nur Timer-Modus aktiviert" / "deaktiviert"
- etc.

Nach Änderung: `python manage.py compilemessages`

---

## Phase 5: Tests

### 5.1 Timer-Only Mode Tests

**Datei:** `tests/test_organizations.py`

- Test `test_timer_only_mode_default`: Neue Organisation hat `timer_only_mode = False`
- Test `test_toggle_timer_mode`: Manager kann toggeln
- Test `test_toggle_timer_mode_non_manager`: Employee kann nicht toggeln

### 5.2 Timer-Only Blocking Tests

**Datei:** `tests/test_timetracking.py`

- Test `test_add_entry_blocked_in_timer_mode`: POST auf add_entry mit timer_only_mode=True → Redirect
- Test `test_edit_entry_blocked_in_timer_mode`: POST auf edit_entry mit timer_only_mode=True → Redirect

### 5.3 Weekly Calendar Tests

**Datei:** `tests/test_organizations.py`

- Test `test_weekly_calendar_view`: 200 OK, richtige Woche
- Test `test_weekly_calendar_no_org`: Redirect wenn kein Org-Member
- Test `test_move_entry_as_manager`: Eintrag verschieben funktioniert
- Test `test_move_entry_as_employee`: 403 Forbidden

---

## Datei-Änderungen: Zusammenfassung

| Datei | Änderung |
|-------|----------|
| `organizations/models.py` | + `timer_only_mode` Field |
| `organizations/views.py` | + `org_weekly_calendar`, `toggle_timer_mode`, `move_entry` |
| `organizations/urls.py` | + 3 neue URL-Patterns |
| `timetracking/views.py` | Block in `add_entry`/`edit_entry`, `show_actions` in `monthly_table` |
| `templates/organizations/dashboard.html` | + Toggle-Switch, + Weekly-Link |
| `templates/organizations/weekly_calendar.html` | **NEU** – Weekly Grid |
| `templates/timetracking/home.html` | Conditional `+ Add time` |
| `templates/timetracking/monthly_table.html` | Conditional Action-Spalte |
| `static/css/styles.css` | + Weekly Calendar Styles & Toggle-Switch |
| `locale/de/LC_MESSAGES/django.po` | + Übersetzungen |
| `Makefile` | ggf. `compilemessages`-Target ergänzen |

---

## Reihenfolge der Implementierung

1. **Models + Migration** (Phase 1.1)
2. **Toggle-View + Dashboard UI** (Phase 1.2–1.3)
3. **Timer-Only Blocking** (Phase 1.4–1.6)
4. **Weekly Calendar View + Template** (Phase 3.1–3.4)
5. **Drag & Drop** (Phase 3.5–3.6)
6. **Übersetzungen** (Phase 4)
7. **Tests** (Phase 5)

---

## Aufwandsabschätzung

| Schritt | Geschätzter Aufwand |
|---------|---------------------|
| Models + Migration | ~15 Min |
| Toggle-View + Dashboard | ~30 Min |
| Timer-Only Blocking (Views + Templates) | ~30 Min |
| Weekly Calendar View + Logik | ~45 Min |
| Weekly Calendar Template (HTML+CSS) | ~45 Min |
| Drag & Drop (JS + API) | ~30 Min |
| Übersetzungen | ~15 Min |
| Tests | ~30 Min |
| **Gesamt** | **~3–4 Stunden** |

---

## Offene Fragen / Entscheidungen

1. **Drag & Drop nur für Manager oder auch für Employee (eigene Einträge)?** → Vorschlag: Nur Manager
2. **Soll die Weekly Calendar auch Timer-Start/Stop erlauben?** → Vorschlag: Nein, nur Dashboard
3. **Soll der Timer-Only Mode vom Manager pro Organisation oder global schaltbar sein?** → Pro Organisation
4. **Verhalten bei gemischten Modi (User hat mehrere Orgas)?** → Derzeit 1:1 User↔Membership, daher nicht relevant
