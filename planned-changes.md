# Planned Changes – trackable

> Datum: 2026-06-13
> Status: Phase 1 ✅ – Phase 2 ✅ – Phase 6 ⏳ Planung
> Branch: `main`

---

## Überblick

Sechs Arbeitspakete:

1. ✅ **Shared Weekly Calendar (Team-Kalender)** – Abgeschlossen
2. ✅ **Enhanced Role-Based Timer Mode** – Abgeschlossen
3. ⏳ **Zeitkonto (Time Account)** – Soll-/Ist-Stunden-Balance pro Profil
4. ⏳ **PDF-Export mit Native Share** – Web Share API für mobile Geräte
5. ⏳ **Mobile UI/UX Audit** – Durchgehendes mobiles Design-Review
6. 📋 **Company Branding (White-Label)** – Logo, Favicon, Farben, Custom CSS pro Organisation

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

## Phase 2: Enhanced Role-Based Timer Mode ✅

**Status: Abgeschlossen – Commit `145734a`**

### Umgesetzt

- **`time_tracking_mode`** (CharField: `classic`/`restricted`) ersetzt `timer_only_mode` (Boolean)
- **Datenmigration** transferiert bestehende Werte (`True` → `restricted`, `False` → `classic`)
- **Helper `can_edit_time_entries()`** in `organizations/helpers.py` – Manager umgehen Restricted-Modus
- **`timetracking/views.py`**: Alle Checks nutzen `can_edit_time_entries()`
- **`organizations/views.py`**: `toggle_time_tracking_mode` zyklisiert classic↔restricted
- **Dashboard**: Dropdown statt Checkbox, mit Klartext-Labels (Classic/Full Access, Restricted/Timer only)
- **Wochenkalender**: Context `timer_only` basiert auf `can_edit_time_entries()`
- **Übersetzungen**: Deutsch (8 neue Strings)
- **Tests**: 4 neue Manager-Ausnahme-Tests, alle bestehenden aktualisiert
- **103 Tests gesamt – alle grün**

### Änderungen

| Datei | Änderung |
|-------|----------|
| `organizations/models.py` | `timer_only_mode` → `time_tracking_mode` |
| `organizations/migrations/0004_time_tracking_mode.py` | Datenmigration |
| `organizations/helpers.py` | **Neu** – `can_edit_time_entries()` |
| `organizations/views.py` | Toggle + Import aktualisiert |
| `organizations/urls.py` | URL-Rename |
| `timetracking/views.py` | Alle Checks ersetzt |
| `templates/organizations/dashboard.html` | Dropdown-UI |
| `templates/timetracking/home.html` | `can_edit` statt `not org_timer_only` |
| `tests/test_organizations.py` | Angepasst |
| `tests/test_timetracking.py` | Angepasst + 4 neue Tests |
| `locale/de/LC_MESSAGES/django.po` | 8 neue Übersetzungen |

---

*(Siehe Commit `145734a` für die vollständige Implementierung)*

---

## Phase 3: Zeitkonto (Time Account) ⏳

### Ziel
Pro Profil wird für jeden Monat ein Zeitkonto berechnet:

- **Soll-Stunden** = `weekly_hours / 5 × Arbeitstage` (Mo–Fr, abzgl. Feiertage der Organisation)
- **Ist-Stunden** = gebuchte Stunden (bereits in `get_monthly_hours()`)
- **Saldo (Balance)** = Ist − Soll (positiv = Überstunden, negativ = Minusstunden)
- **Kumulierter Saldo** = aufsummiert über alle Monate (Vortrag)

Farbcodierung: 🟢 positiv / 🔴 negativ / ⚪ ausgeglichen

---

### Ausführungsplan

#### Schritt 1: Methoden auf `Profile`

**Datei:** `trackable/profiles/models.py`

```python
from django.db import models
from django.db.models import Q


class Profile(models.Model):
    # … bestehende Felder …
    
    def _get_working_days_in_month(self, year, month):
        """Count Mon-Fri days in a month, excluding org holidays."""
        import calendar
        from datetime import date
        from trackable.core.models import Holiday
        
        org = getattr(self.user, "organization_membership", None)
        org_obj = org.organization if org else None
        
        _, last_day = calendar.monthrange(year, month)
        
        holidays = Holiday.objects.filter(date__year=year, date__month=month)
        if org_obj:
            holidays = holidays.filter(
                Q(organization=org_obj) | Q(organization__isnull=True)
            )
        holiday_dates = set(holidays.values_list("date", flat=True))
        
        count = 0
        for day in range(1, last_day + 1):
            d = date(year, month, day)
            if d.weekday() < 5 and d not in holiday_dates:
                count += 1
        return count
    
    def get_target_hours(self, year, month):
        """Target hours (Soll) for the given month."""
        working_days = self._get_working_days_in_month(year, month)
        daily_hours = float(self.weekly_hours) / 5
        return round(daily_hours * working_days, 2)
    
    def get_balance(self, year, month):
        """Balance = actual hours − target hours for the month."""
        actual = self.get_monthly_hours(year, month)
        target = self.get_target_hours(year, month)
        return round(float(actual) - float(target), 2)
    
    def get_target_hours_for_date_range(self, start_date, end_date):
        """Target hours across an arbitrary date range (used for cumulative).
        
        Not needed initially – cumulative will sum per-month balances.
        """
        …
```

#### Schritt 2: Views aktualisieren

**`trackable/profiles/views.py`** – `profile_detail()`:

```python
months = []
cumulative_balance = 0
for year, month in sorted(entry_months, reverse=True):
    hours = profile.get_monthly_hours(year, month)
    target = profile.get_target_hours(year, month)
    balance = profile.get_balance(year, month)
    cumulative_balance += balance
    months.append({
        "year": year,
        "month": month,
        "month_name": datetime(year, month, 1).strftime("%B %Y"),
        "hours": hours,
        "target_hours": target,
        "balance": balance,
        "cumulative_balance": cumulative_balance,
        "earnings": profile.get_monthly_earnings(year, month),
    })
```

**`trackable/organizations/views.py`**:
- `employee_detail()`: Gleiche Logik wie profil_detail, füge target_hours und balance zu jedem month-dict hinzu
- `employee_profile_detail()`: target_hours + balance in den Context geben

**`trackable/timetracking/views.py`**:
- `monthly_table()`: target_hours + balance in den Context geben
- `employee_profile_detail()` (org view): gleiche Änderung

#### Schritt 3: Templates aktualisieren

**`templates/profiles/detail.html`**:

```html
<div class="card" style="text-align:center;">
    <p style="color:var(--ctp-subtext0); margin-bottom:10px;">{% trans "Weekly hours" %}</p>
    <p style="font-size:2rem; font-weight:bold; color:var(--ctp-mauve);">{{ profile.weekly_hours }}h</p>
</div>
<!-- … -->
{% for month in months %}
<div class="card">
    <h3 style="color:var(--ctp-mauve); margin-bottom:15px;">{{ month.month_name }}</h3>
    <p style="color:var(--ctp-subtext0); margin-bottom:5px;">
        <strong>{% trans "Target hours" %}:</strong> {{ month.target_hours|floatformat:2 }}h
    </p>
    <p style="color:var(--ctp-subtext0); margin-bottom:5px;">
        <strong>{% trans "Actual hours" %}:</strong> {{ month.hours|floatformat:2 }}h
    </p>
    <p style="color:var(--ctp-subtext0); margin-bottom:5px;">
        <strong>{% trans "Balance" %}:</strong>
        <span style="color:{% if month.balance > 0 %}var(--ctp-green){% elif month.balance < 0 %}var(--ctp-red){% else %}var(--ctp-subtext0){% endif %};
                     font-weight:bold;">
            {{ month.balance|floatformat:2 }}h
        </span>
    </p>
    <p style="color:var(--ctp-subtext0); margin-bottom:15px;">
        <strong>{% trans "Cumulative balance" %}:</strong>
        <span style="color:{% if month.cumulative_balance > 0 %}var(--ctp-green){% elif month.cumulative_balance < 0 %}var(--ctp-red){% else %}var(--ctp-subtext0){% endif %};">
            {{ month.cumulative_balance|floatformat:2 }}h
        </span>
    </p>
    <!-- earnings, detail link … -->
</div>
{% endfor %}
```

**`templates/organizations/employee_detail.html`**: Gleiches Muster für jeden Monat.

**`templates/organizations/employee_profile_detail.html`**:

```html
<div class="card" style="text-align:center;">
    <p style="color:var(--ctp-subtext0); margin-bottom:10px;">{% trans "Total hours" %}</p>
    <p style="font-size:2.5rem; font-weight:bold; color:var(--ctp-mauve);">{{ total_hours|floatformat:2 }}h</p>
</div>
<div class="card" style="text-align:center;">
    <p style="color:var(--ctp-subtext0); margin-bottom:10px;">{% trans "Target hours" %}</p>
    <p style="font-size:2rem; font-weight:bold; color:var(--ctp-blue);">{{ target_hours|floatformat:2 }}h</p>
</div>
<div class="card" style="text-align:center;">
    <p style="color:var(--ctp-subtext0); margin-bottom:10px;">{% trans "Balance" %}</p>
    <p style="font-size:2.5rem; font-weight:bold;
              color:{% if balance > 0 %}var(--ctp-green){% elif balance < 0 %}var(--ctp-red){% else %}var(--ctp-subtext0){% endif %};">
        {{ balance|floatformat:2 }}h
    </p>
</div>
```

**`templates/timetracking/monthly_table.html`**: Ähnliche Karten oberhalb der Tabelle.

#### Schritt 4: monthly_table View erweitern

In `timetracking/views.py`:

```python
def monthly_table(request, profile_id, year, month):
    # … bestehende Logik …
    target_hours = profile.get_target_hours(year, month)
    balance = profile.get_balance(year, month)
    # in den Context aufnehmen
```

#### Schritt 5: i18n

```bash
uv run django-admin makemessages -l de
# Neue Strings übersetzen: "Target hours", "Actual hours", "Balance",
# "Cumulative balance", "Time account", "Overtime", "Hours"
uv run django-admin compilemessages
```

#### Schritt 6: Tests

**Datei:** `tests/test_profiles.py` (oder `tests/test_timetracking.py`):

```python
class TimeAccountTests(TestCase):
    def setUp(self):
        # 1 User + Profile mit weekly_hours=40
        # 1 Organization + Membership
        pass
    
    def test_get_target_hours_returns_correct_value(self):
        # weekly_hours=40 → daily=8
        # Mai 2026 hat z.B. 21 workdays → 8*21=168h
        pass
    
    def test_get_target_hours_excludes_weekends(self):
        pass
    
    def test_get_target_hours_excludes_holidays(self):
        pass
    
    def test_get_balance_positive(self):
        pass
    
    def test_get_balance_negative(self):
        pass
    
    def test_get_balance_zero(self):
        pass
    
    def test_profile_detail_shows_balance(self):
        pass
```

#### Umsetzungsreihenfolge

| # | Schritt | Dateien |
|---|---------|--------|
| 1 | Methoden auf Profile-Modell | `profiles/models.py` |
| 2 | Views aktualisieren | `profiles/views.py`, `organizations/views.py`, `timetracking/views.py` |
| 3 | Templates aktualisieren | `profiles/detail.html`, `organizations/employee_detail.html`, `organizations/employee_profile_detail.html`, `timetracking/monthly_table.html` |
| 4 | i18n | `django.po` / `.mo` |
| 5 | Tests | `tests/` |
| 6 | Test-Suite | `make test` |

### Phase 4: PDF-Export mit Native Share
- Neuer API-Endpunkt: `/api/export-pdf/<id>/<year>/<month>/` → Base64-JSON
- Frontend: `navigator.share()` für PDF-Blob, Fallback Download

### Phase 5: Mobile UI/UX Audit
- Touch-Targets (min 44px), Safe Areas, Tabellen-Scroll
- Calendar-Grid auf Mobile testen

---

*Dieses Dokument wird während der Implementierung aktualisiert.*

---

## Phase 6: Company Branding (White-Label) 🎨

### Ziel
Manager/Org-Admins sollen die App-Oberfläche an das Corporate Design ihrer Firma anpassen können:

- **Logo** oben links in der Navbar (statt fixem `trackable-logo.png`)
- **Favicon** im Browser-Tab + Apple-Touch-Icon
- **Primär-/Akzentfarbe** überschreibt CSS-Variablen (Button-Farben, Links, Akzente)
- **Custom CSS** für Feintuning ohne Entwickler-Beteiligung

Pro Organisation konfigurierbar im Org-Dashboard.

---

### Ausführungsplan

#### Schritt 1: Branding-Felder auf `Organization`

**Datei:** `trackable/organizations/models.py`

```python
class Organization(models.Model):
    # … bestehende Felder (name, slug, time_tracking_mode, cal_* …)

    # Branding
    logo = models.ImageField(
        upload_to="org_logos/",
        blank=True, null=True,
        verbose_name="Logo (Navbar)",
        help_text=_("Empfohlen: 180×40 px, PNG oder SVG."),
    )
    favicon = models.ImageField(
        upload_to="org_favicons/",
        blank=True, null=True,
        verbose_name="Favicon",
        help_text=_("Empfohlen: 32×32 px, ICO oder PNG."),
    )
    apple_touch_icon = models.ImageField(
        upload_to="org_favicons/",
        blank=True, null=True,
        verbose_name="Apple Touch Icon",
        help_text=_("Empfohlen: 180×180 px, PNG."),
    )
    primary_color = models.CharField(
        max_length=7,
        default="", blank=True,
        verbose_name=_("Primärfarbe"),
        help_text=_("Hex-Farbe (z. B. #8caaee). Überschreibt die Haupt-Akzentfarbe."),
    )
    accent_color = models.CharField(
        max_length=7,
        default="", blank=True,
        verbose_name=_("Akzentfarbe"),
        help_text=_("Hex-Farbe (z. B. #ca9ee6). Überschreibt sekundäre Akzente."),
    )
    custom_css = models.TextField(
        blank=True, null=True,
        verbose_name=_("Custom CSS"),
        help_text=_("Beliebige CSS-Regeln, nach den Standard-Styles geladen."),
    )
```

#### Schritt 2: Migration

```bash
uv run python manage.py makemigrations organizations --name org_branding
uv run python manage.py migrate
```

#### Schritt 3: Media-Serving sicherstellen

`MEDIA_URL` und `MEDIA_ROOT` sind bereits in `settings/base.py`:

```python
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR.parent / "media"
```

**trackable/urls.py** prüfen: Media-Serving für Dev muss aktiv sein:

```python
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

Für **Produktion**: Whitenoise servt keine Media-Files. Einfachster Weg: Media-View in `core/views.py` mit `if settings.DEBUG or settings.SERVE_MEDIA`. Oder nginx vorschalten.

#### Schritt 4: Context Processor

**Neu:** `trackable/organizations/context_processors.py`

```python
def org_branding(request):
    """Stellt Branding-Daten für alle Templates bereit."""
    branding = {
        "org_logo_url": None,
        "org_favicon_url": None,
        "org_apple_touch_icon_url": None,
        "org_primary_color": "",
        "org_accent_color": "",
        "org_custom_css": "",
    }
    membership = getattr(request.user, "organization_membership", None)
    if not membership:
        return branding
    org = membership.organization
    if org.logo:
        branding["org_logo_url"] = org.logo.url
    if org.favicon:
        branding["org_favicon_url"] = org.favicon.url
    if org.apple_touch_icon:
        branding["org_apple_touch_icon_url"] = org.apple_touch_icon.url
    if org.primary_color:
        branding["org_primary_color"] = org.primary_color
    if org.accent_color:
        branding["org_accent_color"] = org.accent_color
    if org.custom_css:
        branding["org_custom_css"] = org.custom_css
    return branding
```

**In `settings/base.py` registrieren:**

```python
TEMPLATES[0]["OPTIONS"]["context_processors"].append(
    "trackable.organizations.context_processors.org_branding"
)
```

#### Schritt 5: Base-Template aktualisieren

**Favicon** (`templates/base.html`):

```html
{% if org_favicon_url %}
<link rel="icon" type="image/x-icon" href="{{ org_favicon_url }}">
<link rel="icon" type="image/png" sizes="32x32" href="{{ org_favicon_url }}">
{% else %}
<link rel="icon" type="image/x-icon"  href="{% static 'img/favicon.ico' %}">
<link rel="icon" type="image/png" sizes="32x32" href="{% static 'img/favicon-32x32.png' %}">
{% endif %}
```

**Apple Touch Icon:**

```html
<link rel="apple-touch-icon" href="{% if org_apple_touch_icon_url %}{{ org_apple_touch_icon_url }}{% else %}{% static 'img/apple-touch-icon.png' %}{% endif %}">
```

**Meta theme-color:**

```html
<meta name="theme-color" content="{% if org_primary_color %}{{ org_primary_color }}{% else %}#292c3c{% endif %}">
```

**Branding-CSS-Variablen injizieren:**

```html
{% if org_primary_color or org_accent_color %}
<style>
    :root {
        {% if org_primary_color %}
        --brand-primary: {{ org_primary_color }};
        --ctp-blue: {{ org_primary_color }};
        --ctp-lavender: {{ org_primary_color }};
        {% endif %}
        {% if org_accent_color %}
        --brand-accent: {{ org_accent_color }};
        --ctp-mauve: {{ org_accent_color }};
        --ctp-pink: {{ org_accent_color }};
        {% endif %}
    }
</style>
{% endif %}
{% if org_custom_css %}
<style>{{ org_custom_css }}</style>
{% endif %}
```

**Logo in der Navbar:**

```html
<a href="/" class="logo">
    {% if org_logo_url %}
    <img src="{{ org_logo_url }}" alt="{{ organization.name }}" class="logo-img org-logo" style="max-height:40px; width:auto;">
    {% else %}
    <img src="{% static 'img/trackable-logo.png' %}" alt="trackable." class="logo-img">
    <span class="logo-name">trackable.</span>
    {% endif %}
</a>
```

#### Schritt 6: Branding-View + Form + Template

**Formular** in `trackable/organizations/forms.py` (oder eigene Datei):

```python
class OrganizationBrandingForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ["logo", "favicon", "apple_touch_icon", "primary_color", "accent_color", "custom_css"]
        widgets = {
            "primary_color": forms.TextInput(attrs={"type": "color"}),
            "accent_color": forms.TextInput(attrs={"type": "color"}),
            "custom_css": forms.Textarea(attrs={"rows": 8, "class": "css-editor", "placeholder": "/* Custom CSS */"}),
        }
```

**View** in `trackable/organizations/views.py`:

```python
@login_required
@org_manager_required
def org_branding(request):
    org = request.user.organization_membership.organization
    if request.method == "POST":
        form = OrganizationBrandingForm(request.POST, request.FILES, instance=org)
        if form.is_valid():
            form.save()
            messages.success(request, _("Branding saved."))
            return redirect("org_branding")
    else:
        form = OrganizationBrandingForm(instance=org)
    return render(request, "organizations/branding.html", {"form": form, "organization": org})
```

**URL** in `trackable/organizations/urls.py`:

```python
path("branding/", views.org_branding, name="org_branding"),
```

**Dashboard-Link** im Settings-Block der Org:

```html
<a href="/org/branding/" class="btn btn-secondary btn-sm">🎨 {% trans "Branding" %}</a>
```

**Template** `templates/organizations/branding.html`:

```html
{% extends 'base.html' %}
{% load i18n %}

{% block title %}{% trans "Branding" %} – {{ organization.name }}{% endblock %}

{% block content %}
<div class="card" style="max-width:700px; margin:0 auto;">
    <h2>🎨 {% trans "Company Branding" %}</h2>
    <p class="help-text">{% trans "Customize the appearance for your organization." %}</p>
    
    <form method="post" enctype="multipart/form-data">
        {% csrf_token %}
        {{ form.as_p }}
        <button type="submit" class="btn btn-primary">{% trans "Save" %}</button>
        <a href="/org/" class="btn btn-secondary">{% trans "Cancel" %}</a>
    </form>
</div>
{% endblock %}
```

#### Schritt 7: i18n / Übersetzungen

```bash
uv run django-admin makemessages -l de
```

Strings: `Branding`, `Company Branding`, `Primary Color`, `Accent Color`, `Custom CSS`, `Logo`, `Favicon`, `Apple Touch Icon`, `Branding saved.`, u. a.

```bash
uv run django-admin compilemessages
```

#### Schritt 8: Tests

**tests/test_organizations.py** erweitern:

```python
class OrganizationBrandingTest(TestCase):
    def test_branding_view_requires_login(self): ...
    def test_branding_view_requires_manager(self): ...
    def test_branding_view_renders_200(self): ...
    def test_branding_saves_logo(self): ...
    def test_branding_saves_colors(self): ...
    def test_branding_defaults_empty(self): ...
    def test_context_processor_returns_branding(self): ...
    def test_logo_appears_in_navbar_when_set(self): ...
    def test_favicon_appears_in_head_when_set(self): ...
```

#### Umsetzungsreihenfolge

| # | Schritt | Datei(en) |
|---|---------|-----------|
| 1 | Model-Felder + Migration | `organizations/models.py`, `migrations/` |
| 2 | Media-Serving verifizieren | `trackable/urls.py` |
| 3 | Context Processor | `organizations/context_processors.py`, `settings/base.py` |
| 4 | Base-Template (Favicon, Logo, CSS-Vars) | `templates/base.html` |
| 5 | Formular + View + URL | `organizations/forms.py`, `views.py`, `urls.py` |
| 6 | Branding-Template | `templates/organizations/branding.html` |
| 7 | Dashboard-Link | `templates/organizations/dashboard.html` |
| 8 | Übersetzungen | `locale/de/LC_MESSAGES/django.po` |
| 9 | Tests | `tests/test_organizations.py` |
| 10 | Vollständigen Test-Suite laufen lassen | `make test` |
