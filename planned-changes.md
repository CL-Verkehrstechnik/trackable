# Planned Changes – trackable

> Datum: 2026-06-13
> Status: Phase 1 ✅ abgeschlossen – Phase 2 in Planung
> Branch: `main`

---

## Überblick

Fünf Arbeitspakete:

1. ✅ **Shared Weekly Calendar (Team-Kalender)** – Abgeschlossen
2. 📋 **Enhanced Role-Based Timer Mode** – In Planung (dieses Dokument)
3. ⏳ **Zeitkonto (Time Account)** – Soll-/Ist-Stunden-Balance pro Profil
4. ⏳ **PDF-Export mit Native Share** – Web Share API für mobile Geräte
5. ⏳ **Mobile UI/UX Audit** – Durchgehendes mobiles Design-Review

---

## Phase 1: Shared Weekly Calendar (Team-Kalender) ✅

**Status: Abgeschlossen – Commit `d0f91b3`**

### Umgesetzt

- **CalendarEvent-Modell** in `organizations/models.py` mit title, notes, color (6 Presets), day_id, start_time, duration_minutes, week_start, created_by
- **Kalender-Settings** auf `Organization` (week_starts_on, included_days, time_interval, start_time, end_time)
- **Migration** `0003_organization_cal_end_time_and_more` (kalter Name wegen Merge – enthält beide Änderungen)
- **Views** in `organizations/calendar_views.py`:
  - `team_calendar` – Hauptansicht mit Wochen-Navigation und positionierten Event-Blöcken
  - `calendar_add_event` – AJAX-Anlage (form-json)
  - `calendar_update_event` – AJAX-Update (form-json)
  - `calendar_delete_event` – AJAX-Löschen (Owner oder Manager)
  - `calendar_get_events` – JSON-Liste einer Woche
- **URLs** unter `/org/team-calendar/` mit API-Endpunkten
- **Template** `team_calendar.html`:
  - Tage‑×‑Stunden‑Grid (CSS Flexbox)
  - Event-Blöcke absolut positioniert, farbcodiert, mit Start/Endzeit
  - SortableJS Drag&Drop zwischen Tagen/Zeiten
  - Event-Editor-Modal (Title, Notes, Color-Picker, Day, Startzeit, Dauer)
  - Mobile-Responsive (kleinere Slots, kurze Wochentags-Labels)
- **Dashboard-Button** "Team Calendar" neben bestehendem "Weekly Calendar"
- **21 neue Tests** in `tests/test_calendar.py` (Model + API + View)
- **99 Tests gesamt – alle grün**

---

## Phase 2: Enhanced Role-Based Timer Mode (Geplant)

### Ziel

Das aktuelle `timer_only_mode` (Boolean) wird ersetzt durch `time_tracking_mode` mit zwei Modi:
- **`classic`** – uneingeschränkte Zeiterfassung (Timer + manuelle Einträge)
- **`restricted`** – Timer-Pflicht für normale Mitglieder (Employee), aber **Manager behalten vollen CRUD-Zugriff**

**Problem des aktuellen Systems:** Wenn `timer_only_mode = True` ist, werden **alle** Nutzer blockiert – auch Manager. Das ist zu restriktiv. Ein Manager soll im Restricted-Modus weiterhin Einträge anlegen, bearbeiten oder löschen können.

---

### Änderungen im Detail

#### 1. Model: `time_tracking_mode` statt `timer_only_mode` 🔧

**Datei:** `trackable/organizations/models.py`

```python
class Organization(models.Model):
    # Ersetze:
    # timer_only_mode = models.BooleanField(default=False, verbose_name="Timer only mode")
    
    # Mit:
    time_tracking_mode = models.CharField(
        max_length=20,
        default="classic",
        choices=[
            ("classic", "Classic – Full CRUD access"),
            ("restricted", "Restricted – Timer only (except managers)"),
        ],
        verbose_name="Time tracking mode",
    )
```

**Datenmigration:** Bestehende `timer_only_mode=True` → `time_tracking_mode="restricted"`, `False` → `"classic"`.

#### 2. Helper-Funktion `can_edit_time_entries()` 🧩

**Neu in:** `trackable/organizations/helpers.py` (oder in `models.py`)

```python
def can_edit_time_entries(user):
    """Prüft, ob ein User manuelle Zeiteinträge erstellen/bearbeiten/löschen darf.
    
    - Ohne Org-Mitgliedschaft: immer erlaubt
    - Org-Modus 'classic': immer erlaubt
    - Org-Modus 'restricted': nur Manager/Owner dürfen
    """
    membership = getattr(user, "organization_membership", None)
    if not membership:
        return True  # Keine Org → kein Timer-Mode
    org = membership.organization
    if org.time_tracking_mode == "classic":
        return True
    # restricted mode
    return membership.is_manager
```

#### 3. Views aktualisieren 🔁

**Datei:** `trackable/timetracking/views.py`

| Zeile(n) | Aktuell | Neu |
|----------|---------|-----|
| `home()` | `org_timer_only = ...timer_only_mode` | `can_edit = can_edit_time_entries(request.user)` → Template-Context |
| `add_entry()` | `if membership and membership.organization.timer_only_mode:` | `if not can_edit_time_entries(request.user):` |
| `edit_entry()` | gleiches Pattern | gleiches Pattern |
| `monthly_table()` | `show_actions = not (membership and membership.organization.timer_only_mode)` | `show_actions = can_edit_time_entries(request.user)` |

**Datei:** `trackable/organizations/views.py`

- `toggle_timer_mode` → umbenennen/erweitern zu `toggle_time_tracking_mode`:
  - Zyklus: `classic` → `restricted` → `classic`
  - Manager-Only bleibt erhalten (`@org_manager_required`)
  - Erfolgsmeldung aktualisiert

**Datei:** `trackable/organizations/calendar_views.py` (weekly calendar)

- Die alte `org_weekly_calendar`-View (in `organizations/views.py`) nutzt `timer_only` im Context
  - Aktuell: `"timer_only": organization.timer_only_mode`
  - Neu: `"timer_only": not can_edit_time_entries(request.user)`
  - → Achtung: `timer_only` heisst hier "Timer-Zugriff blockiert", nicht "nur Timer erlaubt"

#### 4. Templates aktualisieren 🎨

**`templates/timetracking/home.html`:**
```html
{# Aktuell #}
{% if not org_timer_only %}
    <a href="…">Add time</a>
{% endif %}

{# Neu #}
{% if can_edit %}
    <a href="…">Add time</a>
{% endif %}
```

**`templates/timetracking/monthly_table.html`:**
- Keine Änderung nötig – nutzt bereits `show_actions` aus View-Context

**`templates/organizations/dashboard.html`:**
```html
{# Aktuell: Timer only mode toggle #}
<label class="toggle-switch">
    <input type="checkbox" onchange="this.form.submit()"
           {% if organization.timer_only_mode %}checked{% endif %}>
    <span class="toggle-slider"></span>
</label>

{# Neu: Zeit-Erfassungs-Modus mit Label #}
<form method="post" action="/org/toggle-time-tracking-mode/" style="display:inline;">
    {% csrf_token %}
    <select name="mode" onchange="this.form.submit()"
            style="padding:6px 12px; border-radius:8px;
                   border:1px solid var(--ctp-overlay0);
                   background:var(--ctp-mantle); color:var(--ctp-text);
                   font-size:.9rem;">
        <option value="classic" {% if organization.time_tracking_mode == "classic" %}selected{% endif %}>
            🟢 {% trans "Classic – Full access" %}
        </option>
        <option value="restricted" {% if organization.time_tracking_mode == "restricted" %}selected{% endif %}>
            🔴 {% trans "Restricted – Timer only (except managers)" %}
        </option>
    </select>
</form>
```

(Alternativ: Umschalt-Button mit Textanzeige, je nach UX-Präferenz)

**`templates/organizations/weekly_calendar.html`:**
- Aktuell nutzt `timer_only` aus Context – dieser Wert wird in der View auf `not can_edit_time_entries(request.user)` geändert, daher Template-Code unverändert

#### 5. Migration schreiben 📦

```bash
cd /home/lukas/code/cl-verkehrstechnik/trackable
python manage.py makemigrations organizations --name time_tracking_mode
```

Manuelle Migration (`0004_time_tracking_mode.py`):
```python
from django.db import migrations, models

def migrate_timer_only_to_mode(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    for org in Organization.objects.all():
        if org.timer_only_mode:
            org.time_tracking_mode = "restricted"
        else:
            org.time_tracking_mode = "classic"
        org.save()

def reverse_migrate(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    for org in Organization.objects.all():
        org.timer_only_mode = (org.time_tracking_mode == "restricted")
        org.save()

class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0003_organization_cal_end_time_and_more"),
    ]
    operations = [
        migrations.AddField(
            model_name="organization",
            name="time_tracking_mode",
            field=models.CharField(
                default="classic",
                max_length=20,
                choices=[
                    ("classic", "Classic – Full CRUD access"),
                    ("restricted", "Restricted – Timer only (except managers)"),
                ],
                verbose_name="Time tracking mode",
            ),
        ),
        migrations.RunPython(migrate_timer_only_to_mode, reverse_migrate),
        migrations.RemoveField(
            model_name="organization",
            name="timer_only_mode",
        ),
    ]
```

#### 6. Tests aktualisieren 🧪

**Datei:** `tests/test_timetracking.py` – Klasse `TimerOnlyBlockingTest`

Bestehende Tests anpassen:
- `setUp()`: Statt `self.org.timer_only_mode = True` → `self.org.time_tracking_mode = "restricted"` + `.save()`
- Analog für `timer_only_mode = False` → `time_tracking_mode = "classic"`

Neue Testfälle:

```python
def test_manager_can_add_in_restricted_mode(self):
    """Ein Manager kann auch im Restricted-Modus manuell Einträge anlegen."""
    self.client.login(username="manager", password="pass123")
    profile = Profile.objects.create(
        user=self.manager,
        title="Manager",
        position="Boss",
        weekly_hours=40,
        hourly_rate=100,
    )
    response = self.client.post(
        reverse("add_entry", kwargs={"profile_id": profile.pk}),
        {
            "date": date.today(),
            "start_time": "09:00",
            "end_time": "17:00",
            "pause_duration": 0.5,
        },
    )
    self.assertEqual(response.status_code, 302)
    self.assertTrue(TimeEntry.objects.filter(profile=profile).exists())

def test_manager_can_edit_in_restricted_mode(self):
    """Ein Manager kann im Restricted-Modus Einträge bearbeiten."""
    self.client.login(username="manager", password="pass123")
    profile = Profile.objects.create(
        user=self.manager, title="Mgr", position="Mgr",
        weekly_hours=40, hourly_rate=100,
    )
    entry = TimeEntry.objects.create(
        profile=profile, date=date.today(),
        start_time=time(9,0), end_time=time(17,0), pause_duration=0.5,
    )
    response = self.client.post(
        reverse("edit_entry", kwargs={"pk": entry.pk}),
        {"date": date.today(), "start_time": "10:00", "end_time": "18:00"},
    )
    self.assertEqual(response.status_code, 302)
    entry.refresh_from_db()
    self.assertEqual(entry.start_time, time(10, 0))

def test_manager_sees_actions_in_restricted_mode(self):
    """Manager sieht Edit/Delete-Buttons in der Monatstabelle auch im Restricted-Modus."""
    self.client.login(username="manager", password="pass123")
    profile = Profile.objects.create(
        user=self.manager, title="Mgr", position="Mgr",
        weekly_hours=40, hourly_rate=100,
    )
    TimeEntry.objects.create(
        profile=profile, date=date.today(),
        start_time=time(9,0), end_time=time(17,0), pause_duration=0.5,
    )
    response = self.client.get(reverse("home"))
    self.assertContains(response, "Add time")
```

**Datei:** `tests/test_organizations.py` – Klasse `TimerOnlyModeTest`

- `test_timer_only_mode_default_false` → `test_time_tracking_mode_default_classic`
- `test_toggle_timer_only_mode` → `test_toggle_time_tracking_mode`
- Neuer Test: `test_toggle_cycles_correctly`
- Neuer Test: `test_only_manager_can_toggle`

#### 7. i18n / Übersetzungen 🌍

Nach Code-Änderungen:

```bash
cd /home/lukas/code/cl-verkehrstechnik/trackable
django-admin makemessages -l de
```

Neue Strings in `locale/de/LC_MESSAGES/django.po`:

```
msgid "Classic – Full CRUD access"
msgstr "Klassisch – uneingeschränkter Zugriff"

msgid "Restricted – Timer only (except managers)"
msgstr "Eingeschränkt – Nur Timer (außer Manager)"

msgid "Time tracking mode"
msgstr "Zeiterfassungsmodus"

msgid "Classic – Full access"
msgstr "🔵 Klassisch – Volle Bearbeitung"

msgid "Restricted – Timer only"
msgstr "🔴 Eingeschränkt – Nur Timer"
```

Dann kompilieren:

```bash
django-admin compilemessages
```

---

### Umsetzungsreihenfolge

| # | Schritt | Datei(en) |
|---|---------|-----------|
| 1 | Model ändern + Migration schreiben | `organizations/models.py` + `migrations/0004_time_tracking_mode.py` |
| 2 | Helper `can_edit_time_entries()` | `organizations/helpers.py` (neu) |
| 3 | Views aktualisieren (timetracking) | `timetracking/views.py` |
| 4 | Views aktualisieren (organizations) | `organizations/views.py` (+ calendar_views.py) |
| 5 | Templates aktualisieren | `home.html`, `dashboard.html`, `weekly_calendar.html` |
| 6 | Übersetzungen | `locale/de/LC_MESSAGES/django.po` |
| 7 | Tests aktualisieren + erweitern | `tests/test_timetracking.py`, `tests/test_organizations.py` |
| 8 | Vollständigen Test-Suite laufen lassen | `make test` |

---

## Phasen 3–5: Kurzreferenz

### Phase 3: Zeitkonto (Time Account)
- `Profile.get_target_hours(year, month)` – Soll basierend auf `weekly_hours / 5 × Arbeitstage`
- `Profile.get_balance(year, month)` – Ist − Soll (plus/minus)
- Anzeige in Profil-Detail und Employee-Detail

### Phase 4: PDF-Export mit Native Share
- Neuer API-Endpunkt: `/api/export-pdf/<id>/<year>/<month>/` → Base64-JSON
- Frontend: `navigator.share()` für PDF-Blob, Fallback Download

### Phase 5: Mobile UI/UX Audit
- Touch-Targets (min 44px), Safe Areas, Tabellen-Scroll
- Calendar-Grid auf Mobile testen

---

*Dieses Dokument wird während der Implementierung aktualisiert.*
