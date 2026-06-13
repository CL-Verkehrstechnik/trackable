# Planned Changes – trackable

> Datum: 2026-06-13
> Status: Phase 1 ✅ – Phase 2 ✅ – Phase 3 ✅ – Phase 4 ✅ – Phase 5 ✅ – Phase 6 ✅
> Branch: `main`

---

## Überblick

Sechs Arbeitspakete:

1. ✅ **Shared Weekly Calendar (Team-Kalender)** – Abgeschlossen
2. ✅ **Enhanced Role-Based Timer Mode** – Abgeschlossen
3. ✅ **Zeitkonto (Time Account)** – Abgeschlossen
4. ✅ **PDF-Export mit Native Share** – Abgeschlossen
5. ✅ **Mobile UI/UX Audit** – Abgeschlossen
6. ✅ **Company Branding (White-Label)** – Abgeschlossen

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
- **Zugriff für alle Org-Mitglieder** – Team-Kalender ist nicht auf Manager beschränkt (jeder mit Org-Membership kann Events sehen, anlegen und eigene bearbeiten/löschen)
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

## Phase 3: Zeitkonto (Time Account) ✅

**Status: Abgeschlossen – Commits `43aa6ef` + `328b63d`**

### Ziel
Pro Profil wird für jeden Monat ein Zeitkonto berechnet:

- **Soll-Stunden** = `weekly_target_hours / 5 × Arbeitstage` (Mo–Fr, abzgl. Feiertage der Organisation)
- **Fallback**: Ist `weekly_target_hours` nicht gesetzt, wird `weekly_hours` verwendet
- **Ist-Stunden** = gebuchte Stunden (über `get_monthly_hours()`)
- **Saldo (Balance)** = Ist − Soll (positiv = Überstunden 🟢, negativ = Minusstunden 🔴)
- **Kumulierter Saldo** = aufsummiert über alle Monate (Vortrag)

**Besonderheit:** Manager/Org-Admins können die **wöchentlichen Soll-Stunden pro Mitarbeiter-Profil** überschreiben – direkt im Mitarbeiter-Profil über einen Inline-Edit-Button.

---

### Umgesetzt

#### Modell
- **Neues Feld** `weekly_target_hours` (nullable `DecimalField`) auf `Profile`
- Migration `0003_profile_weekly_target_hours`

#### Methoden auf Profile (profiles/models.py)
- `_get_working_days_in_month(year, month)` – zählt Mo–Fr abzgl. Feiertage
- `get_target_hours(year, month)` – nutzt `weekly_target_hours` wenn gesetzt, sonst `weekly_hours`
- `get_balance(year, month)` – Ist − Soll

#### Views
- **`profiles/views.py`**: `target_hours`, `balance`, `cumulative_balance` in month-dict
- **`organizations/views.py`**: Gleiche Logik in `employee_detail()` und `employee_profile_detail()`
- **`organizations/views.py`**: Neue `set_target_hours()` POST-View (nur Manager)
- **`organizations/views.py`**: `employee_create()` legt jetzt **automatisch ein Standard-Profil** für den neuen Mitarbeiter an (Titel = „Employee at <Org-Name>”, Position = „Employee”, 40h/Woche)
- **`timetracking/views.py`**: `target_hours` + `balance` im Context der `monthly_table()`

#### URLs
- `/org/employees/<user_id>/profiles/<profile_id>/set-target-hours/`

#### Templates
- **`profiles/detail.html`**: Monatskarten mit Soll / Ist / Saldo / Kumuliert (farbcodiert)
- **`organizations/employee_detail.html`**: Gleiches Muster pro Monat
- **`organizations/employee_profile_detail.html`**: Zusätzliche Karten für Soll + Saldo + Inline-Edit-Formular für `weekly_target_hours`
- **`timetracking/monthly_table.html`**: Soll- + Saldo-Karten oberhalb der Tabelle

#### Übersetzungen
- Neue Strings: „Wöchentliche Soll-Stunden”, „vom Profil”, „Ungültiger Wert für Soll-Stunden.”, „Wöchentliche Soll-Stunden aktualisiert.”

#### Tests – 9 neue (120 gesamt, alle grün)

| Test | Beschreibung |
|------|-------------|
| `test_get_target_hours_full_month` | Mai 2026: 21 Tage → 168h (40h/Woche) |
| `test_target_hours_uses_weekly_target_hours_when_set` | 30h/Woche → 126h |
| `test_target_hours_falls_back_to_weekly_hours` | None → 168h |
| `test_target_hours_cleared_to_none` | Rücksetzen auf None → Fallback |
| `test_set_target_hours_saves_value` | POST setzt 30h |
| `test_set_target_hours_clears_to_none` | Leerer String → None |
| `test_set_target_hours_requires_manager` | Employee kann nicht setzen |
| `test_set_target_hours_wrong_org_manager_cant_set` | Fremder Manager → 404 |
| `test_set_target_hours_updates_target_calculation` | 30h → get_target_hours() gibt 126h |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `trackable/profiles/models.py` | +`weekly_target_hours`-Feld, `get_target_hours()`-Override |
| `trackable/profiles/migrations/0003_profile_weekly_target_hours.py` | Migration |
| `trackable/profiles/views.py` | +target_hours, balance, cumulative_balance |
| `trackable/organizations/views.py` | +set_target_hours-View, Context-Erweiterungen |
| `trackable/organizations/urls.py` | +set-target-hours-Route |
| `trackable/timetracking/views.py` | +target_hours, balance im Context |
| `templates/profiles/detail.html` | Soll/Ist/Saldo/Kumuliert-Karten |
| `templates/organizations/employee_detail.html` | Soll/Ist/Saldo in Monatskarten |
| `templates/organizations/employee_profile_detail.html` | Saldo + Inline-Edit-Formular |
| `templates/timetracking/monthly_table.html` | Soll/Saldo-Karten |
| `locale/de/LC_MESSAGES/django.po` | 4 neue/angepasste Übersetzungen |
| `tests/test_profiles.py` | 3 neue Modelltests |
| `tests/test_organizations.py` | 6 neue View-Tests |

---

*(Siehe Commits `43aa6ef` + `328b63d` für die vollständige Implementierung)*

## Phase 4: PDF-Export mit Native Share ✅

### Ziel
PDF-Export auf mobilen Geräten soll das native **Share-Sheet** des Betriebssystems öffnen (iOS/Android), statt die PDF direkt im Browser anzuzeigen. So kann der Nutzer die PDF teilen (Mail, WhatsApp, AirDrop, …) oder speichern.

- **Web Share API** (`navigator.share()`) für kompatible Geräte
- **Fallback**: Direkter Download (wie bisher) auf Desktop-Browsern
- PDF wird serverseitig erzeugt (bestehende Logik via reportlab)

---

### Ausführungsplan

#### Schritt 1: API-Endpoint für Base64-PDF

**Neu:** `trackable/core/api_views.py` (oder in `timetracking/views.py`)

```python
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def api_export_pdf(request, profile_id, year, month):
    """Generiert PDF, gibt Base64 + Dateiname als JSON zurück."""
    profile = get_object_or_404(Profile, pk=profile_id, user=request.user)
    
    # Bestehende PDF-Generierung nutzen (aus timetracking/views.py export_pdf)
    pdf_buffer = generate_pdf(profile, year, month)  # already exists
    pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode()
    
    filename = f"trackable_{profile.title}_{year}_{month}.pdf"
    
    return JsonResponse({
        "pdf_base64": pdf_base64,
        "filename": filename,
        "mime_type": "application/pdf",
    })
```

**Wichtig:** Bestehende PDF-Logik in `timetracking/views.py` (`export_pdf`) in eine wiederverwendbare Helper-Funktion extrahieren.

#### Schritt 2: URL registrieren

**`trackable/urls.py`**:

```python
path("api/export-pdf/<int:profile_id>/<int:year>/<int:month>/", api_views.api_export_pdf, name="api_export_pdf"),
```

#### Schritt 3: Frontend-JS für Web Share API

**Neu/Erweitert:** `static/js/pdf_export.js`

```javascript
function exportAndShare(profileId, year, month) {
    fetch(`/api/export-pdf/${profileId}/${year}/${month}/`)
        .then(res => res.json())
        .then(data => {
            const byteCharacters = atob(data.pdf_base64);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'application/pdf' });
            
            if (navigator.share && navigator.canShare && navigator.canShare({ files: [new File([blob], data.filename, { type: 'application/pdf' })] })) {
                // Web Share API with file (iOS/Android)
                navigator.share({
                    title: data.filename,
                    files: [new File([blob], data.filename, { type: 'application/pdf' })],
                }).catch(err => console.warn('Share failed', err));
            } else if (navigator.share) {
                // Fallback: share without file (URL-based)
                const url = URL.createObjectURL(blob);
                navigator.share({ url }).catch(() => {
                    window.open(url, '_blank');
                });
            } else {
                // Desktop-Fallback: PDF in neuem Tab öffnen
                const url = URL.createObjectURL(blob);
                window.open(url, '_blank');
            }
        })
        .catch(err => {
            console.error('Export failed', err);
            alert('Export fehlgeschlagen.');
        });
}
```

#### Schritt 4: Export-Buttons aktualisieren

In `templates/timetracking/monthly_table.html` den bestehenden PDF-Export-Button ändern:

```html
<button onclick="exportAndShare({{ profile.id }}, {{ year }}, {{ month }})" class="btn btn-primary">
    📄 {% trans "Export PDF" %}
</button>
```

Statt direktem Link zu `/export/…/`.

**`templates/profiles/detail.html`**: Gleicher Button (falls vorhanden).

#### Schritt 5: Fallback für Drucken/Desktop

Für Desktop-Nutzer ohne Share-API: PDF in neuem Tab öffnen (wie bisher).

Die bestehende `/export/<profile_id>/<year>/<month>/`-Route bleibt erhalten und wird als Fallback genutzt.

#### Schritt 6: i18n

Keine neuen Übersetzungen nötig (bestehende Strings).

#### Schritt 7: Tests

```python
def test_api_export_pdf_returns_base64(self):
    self.client.login(username="testuser", password="test123")
    response = self.client.get(
        reverse("api_export_pdf", kwargs={
            "profile_id": self.profile.id,
            "year": 2026,
            "month": 5,
        })
    )
    self.assertEqual(response.status_code, 200)
    data = response.json()
    self.assertIn("pdf_base64", data)
    self.assertIn("filename", data)
    self.assertTrue(len(data["pdf_base64"]) > 0)

def test_api_export_pdf_requires_login(self):
    response = self.client.get(
        reverse("api_export_pdf", kwargs={
            "profile_id": self.profile.id,
            "year": 2026,
            "month": 5,
        })
    )
    self.assertEqual(response.status_code, 302)  # Redirect to login

def test_api_export_pdf_wrong_user_404(self):
    # User A kann nicht PDF von User B exportieren
    pass
```

#### Umsetzungsreihenfolge

| # | Schritt | Dateien |
|---|---------|--------|
| 1 | PDF-Generierung in Helper extrahieren | `timetracking/views.py` → `core/pdf_export.py` |
| 2 | API-Endpoint `api_export_pdf` | `core/api_views.py`, `urls.py` |
| 3 | JS `pdf_export.js` | `static/js/pdf_export.js` |
| 4 | Export-Buttons aktualisieren | `templates/timetracking/monthly_table.html` |
| 5 | Tests | `tests/` |
| 6 | Test-Suite | `make test` |

## Phase 5: Mobile UI/UX Audit ✅

**Status: Abgeschlossen – Commit `8de3539`**

### Umgesetzt

- **Touch-Targets ≥44px** für alle Button-Größen (`btn`, `btn-sm`, `btn-lg`, Kalenderzellen)
- **Größere Form-Inputs** (13px 16px padding, `1rem` Font-Size)
- **Font-Size-Bumps**: Body `16px`, Card-Label `.75rem`, Badge `.78rem`, Tabellen-Kopf `.78rem` (mobile)
- **iOS Safe-Area-Insets** via `env(safe-area-inset-*)` auf Header, Main, Footer, Container
- **360px Breakpoint** hinzugefügt
- **Timer-Buttons** in `home.html`: von `btn-sm` auf `btn` mit `min-height:48px`
- **Team-Kalender**: Zellen auf `52px`, Event-Font `.72rem`, Nav-Buttons `min-height:44px`, 360px-Breakpoint
- **Dashboard-Aktionsbuttons** (`View`/`Remove`): `min-height:44px`
- **Profil-Detail-Buttons** (`Edit`/`Delete`): `min-height:44px`
- **124 Tests – alle grün`

---
---

## Phase 6: Company Branding (White-Label) ✅

**Status: Abgeschlossen – Commit `155fb9a`**

### Ziel
Manager/Org-Admins sollen die App-Oberfläche an das Corporate Design ihrer Firma anpassen können, ohne Code zu ändern.

Konfigurierbare Elemente pro Organisation:

- **Logo** in der Navbar (ersetzt `trackable-logo.png` + Schriftzug)
- **Favicon** + **Apple Touch Icon** (Browser-Tab, Lesezeichen, Homescreen)
- **Primärfarbe** – überschreibt `--ctp-mauve`, `--ctp-pink` (Buttons, Badges, Akzente)
- **Akzentfarbe** – überschreibt `--ctp-blue`, `--ctp-lavender` (Links, sekundäre Akzente)
- **Custom CSS** für beliebiges Feintuning (ohne Entwickler)

**Wichtig – CSS-Strategie:** Die Branding-Farben überschreiben ausgewählte `--ctp-*`-Variablen, sodass Buttons, Badges, Links und andere UI-Elemente automatisch die Firmenfarben annehmen. Der Fallback auf die Catppuccin-Palette bleibt erhalten.


### Umgesetzt

- **6 neue Model-Felder** auf `Organization`: `logo`, `favicon`, `apple_touch_icon`, `primary_color`, `accent_color`, `custom_css`
- **Migration** `0005_org_branding`
- **Context Processor** `trackable/organizations/context_processors.py` – injected `org_branding`-Dict mit Logo-URL, Farben, CSS, und `has_branding`-Flag
- **Dynamische CSS-Variablen** in `base.html`: `--nav-bg`, `--ctp-mauve`, `--ctp-blue`, `--glow-*` werden durch Branding-Farben ueberschrieben
- **Dynamisches Favicon, Apple Touch Icon, theme-color** in `base.html` – Fallback auf Catppuccin-Standard
- **Logo in der Navbar** – ersetzt das statische Logo + Schriftzug bei Verfuegbarkeit
- **Footer bleibt unveraendert** – App-eigenes Logo
- **`OrganizationBrandingForm`** in `organizations/forms.py` mit HTML5 Color-Pickern
- **View `org_branding`** in `organizations/views.py` mit `@org_manager_required`
- **Template** `templates/organizations/branding.html`
- **Dashboard-Link** `🎨 Branding` in `templates/organizations/dashboard.html`
- **Production Media-Serving** via `SERVE_MEDIA` + `staff_member_required`-Static-View
- **10 deutsche Uebersetzungen** fuer alle Field-Labels, Help-Texts und Messages
- **7 neue Tests** in `tests/test_organizations.py`
- **131 Tests – alle gruen**

| Datei | Aenderung |
|-------|----------|
| `trackable/organizations/models.py` | 6 Branding-Felder |
| `trackable/organizations/migrations/0005_org_branding.py` | Migration |
| `trackable/organizations/context_processors.py` | **NEU** |
| `trackable/settings/base.py` | Context-Processor registriert |
| `templates/base.html` | Dynamische Favicon/Logo/CSS-Vars/theme-color |
| `trackable/organizations/forms.py` | `OrganizationBrandingForm` |
| `trackable/organizations/views.py` | `org_branding`-View |
| `trackable/organizations/urls.py` | `branding/`-URL |
| `templates/organizations/branding.html` | **NEU** |
| `templates/organizations/dashboard.html` | Branding-Button |
| `trackable/urls.py` | Production Media-Serving |
| `locale/de/LC_MESSAGES/django.po` | 10 neue Uebersetzungen |
| `tests/test_organizations.py` | 7 Branding-Tests |

---

*(Geplante Commits: `docs: detail Phase 6 Company Branding plan`, dann `feat: Phase 6 - Company Branding/White-Label`)*
