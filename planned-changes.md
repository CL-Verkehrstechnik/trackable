# Planned Changes – trackable

> Datum: 2026-06-13
> Status: Phase 1 ✅ – Phase 2 ✅ – Phase 3 ✅ – Phase 6 ⏳ Planung
> Branch: `main`

---

## Überblick

Sechs Arbeitspakete:

1. ✅ **Shared Weekly Calendar (Team-Kalender)** – Abgeschlossen
2. ✅ **Enhanced Role-Based Timer Mode** – Abgeschlossen
3. ✅ **Zeitkonto (Time Account)** – Abgeschlossen
4. ✅ **PDF-Export mit Native Share** – Abgeschlossen
5. 📋 **Mobile UI/UX Audit** – Detailplan fertig
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

## Phase 5: Mobile UI/UX Audit 📋

### Ziel
Die App auf mobilen Geräten (Smartphones < 480px Breite) durchgehend benutzbar machen:

- Touch-Targets ≥ 44×44px (Apple HIG / Material Design Guideline)
- Keine abgeschnittenen Inhalte, kein Horizontal-Scroll der Seite (nur Tabellen)
- Ausreichende Schriftgrößen (≥ 14px für Fließtext)
- Safe-Area-Padding für Notch/Home-Indicator (iOS)
- Kalender, Timer und Tabellen auf kleinem Bildschirm bedienbar

---

### Audit-Ergebnisse (Juni 2026)

| Bereich | Status | Details |
|---------|--------|--------|
| Viewport Meta | ✅ | `width=device-width, initial-scale=1.0` in `base.html` |
| Responsive Breakpoints | ⚠️ | Nur 480px, 640px, 768px – fehlt 360px (kleine Geräte) |
| Touch-Targets Standard Buttons | ❌ | `.btn` = ~38px Höhe (≥44px nötig) |
| Touch-Targets btn-sm | ❌ | `.btn-sm` = ~30px Höhe – viel zu klein, aber überall verwendet |
| Timer-Buttons (Start/Stopp) | ❌ | `btn-sm` ~30px – kritisch, da häufigster Touch-Use-Case |
| Table Horizontal-Scroll | ✅ | `overflow-x: auto` auf allen Tabellen-Wrappern |
| Form Inputs | ✅ | `padding: 11px 15px` = ~37px – grenzwertig aber OK |
| Schriftgrößen | ❌ | `.card-label` 11.2px, `.badge` 12px, Kalender-Events 10.4px |
| Safe Areas | ❌ | Kein `env(safe-area-inset-*)` Padding |
| Calendar Mobile | ⚠️ | 640px Breakpoint mit 48px Cells, aber Events 10.4px Schrift |
| Dashboard Employee Cards | ❌ | `btn-sm` für View/Remove |
| Profile Detail | ⚠️ | `btn-sm` für Edit/Delete |
| Hamburger Menu | ✅ | Funktioniert auf mobil (fixed overlay) |
| Landing Page | ✅ | Eigene Breakpoints (600px, 900px) |

---

### Ausführungsplan

#### Schritt 1: Touch-Targets auf ≥ 44px vergrößern

**Datei:** `static/css/styles.css`

- `.btn` padding von `9px 20px` auf `11px 22px` erhöhen (→ ~42px Höhe, plus border ≈ 44px)
- `.btn-sm` padding von `6px 13px` auf `9px 16px` (→ ~38px, aber Kombination oft in `flex:1`-Buttons)
- `.btn-sm` auf mobilen Viewports (≤ 480px) per Media Query auf `padding: 10px 18px; font-size: .9rem` hochstufen
- `.btn-lg` bleibt (`13px 30px` ≈ 47px – OK)

```css
@media (max-width: 480px) {
    .btn {
        padding: 11px 22px;
        min-height: 44px;
    }
    .btn-sm {
        padding: 10px 18px;
        font-size: .9rem;
        min-height: 44px;
    }
}
```

**Optional:** `min-height: 44px` auf alle Button-Klassen setzen, damit jede zukünftige Button-Variante automatisch die Mindestgröße einhält.

#### Schritt 2: Timer-Buttons optimieren

**Datei:** `templates/timetracking/home.html`

- Timer Start/Pause/Resume/Stop von `btn-sm` auf `btn` ändern (oder `btn` mit `flex:1` + `min-height: 44px`)
- Zusätzlich CSS-Regel, dass Timer-Buttons mindestens 44px hoch sind:

```css
.timer-controls .btn { min-height: 48px; }
```

#### Schritt 3: Schriftgrößen anpassen

**Datei:** `static/css/styles.css`

| Selektor | Alt | Neu (Mobile) |
|----------|-----|-------------|
| `.card-label` | `.7rem` (11.2px) | `.75rem` (12px) |
| `.badge` | `.75rem` (12px) | `.8rem` (12.8px) |
| `.footer-link, .footer-copy` | `.78rem` (12.5px) | `.82rem` (13.1px) |
| `.table th` | `.74rem` (11.8px) | `.8rem` (12.8px) |
| `.alert` | `.87rem` (13.9px) | `.9rem` (14.4px) |

**Alternativ:** Per Media-Query nur auf Mobile hochsetzen:

```css
@media (max-width: 480px) {
    body { font-size: 16px; }  /* aktuell 15px, auf 16px für bessere Lesbarkeit */
}
```

#### Schritt 4: Safe Areas für iOS-Notch/Home-Indicator

**Datei:** `static/css/styles.css`

```css
/* Safe Areas für iOS-Notch und Home-Indicator */
.site-header {
    padding-left: max(18px, env(safe-area-inset-left));
    padding-right: max(18px, env(safe-area-inset-right));
}

.page-main {
    padding-left: max(20px, env(safe-area-inset-left));
    padding-right: max(20px, env(safe-area-inset-right));
    padding-bottom: max(40px, env(safe-area-inset-bottom));
}

.site-footer {
    padding-bottom: max(16px, env(safe-area-inset-bottom));
}

@media (max-width: 480px) {
    .container {
        padding-left: max(14px, env(safe-area-inset-left));
        padding-right: max(14px, env(safe-area-inset-right));
    }
}
```

#### Schritt 5: Kalender für kleine Displays optimieren

**Datei:** `templates/organizations/team_calendar.html` (im `<style>`-Block)

- Event-Schrift von `.65rem` (10.4px) auf `.72rem` (11.5px) erhöhen
- 48px Cells → 52px für bessere Touch-Ziele
- Buttons in der Navigation auf mindestens 44px bringen
- Mobile Navigation: Pfeil-Buttons von `btn-sm` auf normale Größe

```css
@media (max-width: 640px) {
    .time-slot-label,
    .time-slot-cell {
        height: 52px;
    }
    .day-col {
        min-width: 110px;
    }
    .cal-event {
        font-size: .72rem;
        padding: 3px 5px;
    }
    .team-cal-nav .btn {
        min-height: 44px;
        padding: 10px 16px;
    }
}

/* Zusätzlich: 360px Breakpoint für sehr kleine Geräte */
@media (max-width: 360px) {
    .day-col {
        min-width: 90px;
    }
    .cal-event {
        font-size: .65rem;
        padding: 2px 3px;
    }
    .time-slot-label,
    .time-slot-cell {
        height: 44px;
    }
}
```

#### Schritt 6: Dashboard & Employee-Karten auf Mobile

**Datei:** `templates/organizations/dashboard.html`

- View/Remove Buttons von `btn-sm` auf `btn` hochstufen (oder per CSS `min-height: 44px`)
- `auto-fill`-Grids (`minmax(200px, 1fr)`) werden auf kleinen Screens automatisch Single-Column
- Team-Settings Bereich: Dropdown und Buttons in eigener Zeile (aktuell `flex-wrap: wrap` – funktioniert)

#### Schritt 7: Profile-Detail Buttons

**Datei:** `templates/profiles/detail.html`

- Edit/Delete von `btn-sm` auf normale `btn`-Größe (durch Schritt 1 bereits abgedeckt)
- „Log time“-Button bereits `btn` mit großen Padding – OK

#### Schritt 8: Formulare auf Mobile

**Datei:** `static/css/styles.css`

- Input/Select/Textarea bereits `width: 100%` – gut
- `padding: 11px 15px` gibt ~37px Höhe – grenzwertig, per Media-Query auf 13px padding erhöhen:

```css
@media (max-width: 480px) {
    .form-group input,
    .form-group textarea,
    .form-group select {
        padding: 13px 16px;
        font-size: 1rem;
    }
}
```

#### Schritt 9: Tests

Manuelles Test-Script (keine Unit-Tests für UI):

```bash
# iPhone SE (375×667) – minimal supported width
# iPhone 14 Pro (390×844) – typical modern device
# Galaxy S22 (360×780) – Android equivalent
# iPad Mini (768×1024) – tablet
```

Checkliste pro Seite:
- [ ] Kein horizontales Scrollen der gesamten Seite
- [ ] Alle Buttons ≥ 44px Höhe
- [ ] Formularfelder voller Breite
- [ ] Timer-Buttons gut tippbar
- [ ] Kalender-Events lesbar
- [ ] Tabellen horizontal scrollbar
- [ ] Kein Text abgeschnitten
- [ ] Hamburger-Menü öffnet/schließt

#### Umsetzungsreihenfolge

| # | Schritt | Dateien |
|---|---------|--------|
| 1 | Touch-Targets CSS | `static/css/styles.css` |
| 2 | Timer-Buttons größer | `templates/timetracking/home.html` |
| 3 | Schriftgrößen Mobile | `static/css/styles.css` |
| 4 | Safe Areas | `static/css/styles.css` |
| 5 | Kalender Mobile | `templates/organizations/team_calendar.html` |
| 6 | Dashboard-Karten | `templates/organizations/dashboard.html` |
| 7 | Profile-Detail | `templates/profiles/detail.html` |
| 8 | Form Inputs Mobile | `static/css/styles.css` |
| 9 | Manuelle Prüfung | Browser DevTools |

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
