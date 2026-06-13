# Planned Changes – trackable

> Datum: 2026-06-13
> Status: Entwurf (Revision 1 – nach weekly-planner-web Analyse)
> Branch: `main`

---

## Überblick

Fünf Arbeitspakete:

1. **Shared Weekly Calendar (Team-Kalender)** – Inspiriert von [weekly-planner-web](https://github.com/LStoneyy/weekly-planner-web)
2. **Enhanced Role-Based Timer Mode** – Rollenbasierte Zeiterfassung (Classic/Restricted)
3. **Zeitkonto (Time Account)** – Soll-/Ist-Stunden-Balance pro Profil
4. **PDF-Export mit Native Share** – Web Share API für mobile Geräte
5. **Mobile UI/UX Audit** – Durchgehendes mobiles Design-Review

---

## Phase 1: Shared Weekly Calendar (Team-Kalender)

### Ziel
Ein visueller Wochenkalender pro Organisation, ähnlich wie weekly-planner-web:  
Tage × Stunden-Raster, Events als positionierte, farbcodierte Blöcke, Drag&Drop zum Verschieben, Klick zum Editieren per Modal.

Das **bestehende** `org_weekly_calendar` (Tabellen-Layout) bleibt erhalten – der neue Kalender ist ein **alternativer, moderner Team-Kalender** unter einer neuen URL.

### Inspirierte Features aus weekly-planner-web

| Feature | weekly-planner-web | Unsere Umsetzung |
|---------|-------------------|------------------|
| Grid-Layout | Tage als Spalten, Stunden als Zeilen | Gleiches Konzept mit Django-Templates + CSS Grid |
| Drag & Drop | `@dnd-kit` React | **HTMX + SortableJS** (bereits für org_weekly_calendar genutzt) oder **Alpine.js** für lightweight DnD |
| Event-Editor | Modal mit Title, Notes, Color, Time, Duration | Modal (CSS-only oder Alpine.js) |
| Farbcodierung | Preset-Farben + Custom Hex | Preset-Farben (Catppuccin-Palette) |
| Überlappungs-Layout | Lane-basiert für gleichzeitige Events | Erstmal einfache Liste pro Tag, später Lane-Logik |
| Undo/Redo | Zustands-History | Nicht in V1 – zu komplex für Django-Templates |
| Cloud-Sync | Auto-Save per API | Django ORM – Save bei jeder Änderung |
| Mobile Bottom Nav | 3-Tab-Navigation | Mobile Navigation verbessern (Phase 5) |
| Export | PNG, PDF, CSV | Bestehender PDF-Export, später PNG (Phase 4) |

### 1.1 Modelle

```python
# organizations/models.py – NEU
class CalendarEvent(models.Model):
    """Ein Event im Team-Kalender einer Organisation."""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="calendar_events"
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="created_calendar_events"
    )
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=20, default="blue")
    # Zeitliche Verortung:
    day_id = models.CharField(max_length=20)  # 'Monday', 'Tuesday', …
    start_time = models.TimeField()            # HH:MM
    duration_minutes = models.PositiveIntegerField(default=60)
    # Datum der Kalenderwoche (ISO week):
    week_start = models.DateField()            # Montag der Woche, zu der dieses Event gehört
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["week_start", "day_id", "start_time"]

    def __str__(self):
        return f"{self.title} ({self.day_id} {self.start_time})"
```

**Begründung `week_start`:** Der weekly-planner-web speichert Events mit `dayId` (z.B. "Monday") ohne Datumsbezug – das ist ein "ewiger" Wochenplaner. Wir brauchen aber persistente Events pro konkreter Woche, damit der Kalender dauerhaft genutzt werden kann. `week_start` ist immer ein Montag.

#### Migration

```python
# organizations/migrations/0004_calendarevent.py
```

**Optional (V2):** `CalendarEventTemplate` – ein "ewiger" Plan, der pro Woche geklont wird (für wiederkehrende Events).

### 1.2 Views

**Neue Datei:** `organizations/calendar_views.py` (ausgelagert, weil `views.py` schon 440+ Zeilen hat)

```python
@login_required
def team_calendar(request, year=None, month=None, week=None):
    """Zeigt den Team-Kalender für eine bestimmte Woche an.
    
    URL: /org/calendar/<int:year>/<int:month>/<int:day>/
    Fallback: aktuelle Woche.
    """
    # 1. Woche bestimmen (Parameter oder aktuelle Woche)
    # 2. week_start (Montag) berechnen
    # 3. Organisations-Mitgliedschaft prüfen
    # 4. Events für diese Woche laden
    # 5. Settings für den Kalender laden (week_starts_on, included_days, start_time, end_time, interval)
    # 6. Template rendern

@login_required
@require_http_methods(["POST"])
def calendar_add_event(request):
    """AJAX: Neues Event erstellen."""
    # Parameter: day_id, start_time, title, duration_minutes, color
    # Validierung: organisation membership
    # created_by = request.user
    # Return: JSON mit Event-ID

@login_required
@require_http_methods(["POST"])
def calendar_update_event(request, event_id):
    """AJAX: Event aktualisieren (Title, Notes, Color, Time, Duration, Day)."""
    # Wird auch für Drag&Drop verwendet (day_id + start_time ändern)

@login_required
@require_http_methods(["POST"])
def calendar_delete_event(request, event_id):
    """AJAX: Event löschen."""

@login_required
def calendar_get_events(request):
    """JSON: Events für eine bestimmte Woche abrufen (für Initialisierung)."""
    week_start = request.GET.get("week_start")
    events = CalendarEvent.objects.filter(
        organization=membership.organization,
        week_start=week_start,
    )
    return JsonResponse([...], safe=False)
```

**Validator für DnD:**  
Da wir `week_start` speichern, muss Drag&Drop über mehrere Wochen hinweg den `week_start` aktualisieren. Innerhalb derselben Woche ändern sich nur `day_id` und `start_time`.

### 1.3 URL-Routen

```python
# organizations/urls.py
path("calendar/", views_calendar.team_calendar, name="team_calendar"),
path(
    "calendar/<int:year>/<int:month>/<int:day>/",
    views_calendar.team_calendar,
    name="team_calendar_date",
),
path(
    "calendar/api/events/",
    views_calendar.calendar_get_events,
    name="calendar_get_events",
),
path(
    "calendar/api/events/add/",
    views_calendar.calendar_add_event,
    name="calendar_add_event",
),
path(
    "calendar/api/events/<int:event_id>/update/",
    views_calendar.calendar_update_event,
    name="calendar_update_event",
),
path(
    "calendar/api/events/<int:event_id>/delete/",
    views_calendar.calendar_delete_event,
    name="calendar_delete_event",
),
```

### 1.4 Template – Grid-Layout

**Datei:** `templates/organizations/team_calendar.html`

Das Grid ist ein **CSS-Grid** mit fixen Zeiten links und Tages-Spalten:

```
┌──────────┬──────────┬──────────┬──────┬──────────┐
│  Zeiten  │  Mon     │  Die     │  …   │  Fr      │
├──────────┼──────────┼──────────┼──────┼──────────┤
│  08:00   │          │          │      │          │
│  08:30   │          │  [Event] │      │          │
│  09:00   │          │          │      │          │
│  09:30   │ [Event]  │          │      │          │
│  …       │          │          │      │          │
│  20:00   │          │          │      │          │
└──────────┴──────────┴──────────┴──────┴──────────┘
```

**HTML-Struktur (inspiriert von CalendarGrid.tsx):**

```html
<div id="calendar-container">
  <div id="calendar-scroll-area" class="overflow-auto">
    <div class="grid" style="min-width: ...">
      <!-- Sticky Time-Header -->
      <div class="time-labels sticky left-0">
        {% for time in time_slots %}
          <div class="time-label">{{ time }}</div>
        {% endfor %}
      </div>
      
      {% for day in days %}
        <div class="day-column" data-day="{{ day.id }}">
          <div class="day-header">{{ day.name }}</div>
          <div class="day-slots">
            {% for slot in time_slots %}
              <div class="time-slot"
                   hx-post="{% url 'calendar_add_event' %}"
                   hx-trigger="click"
                   hx-vals='{"day_id": "{{ day.id }}", "start_time": "{{ slot }}"}'
                   hx-swap="none">
              </div>
            {% endfor %}
          </div>
          <!-- Events (absolut positioniert) -->
          {% for event in day.events %}
            <div class="calendar-event" style="top: {{ event.top_px }}px; height: {{ event.height_px }}px; background: {{ event.bg_color }};">
              <div class="event-title">{{ event.title }}</div>
              <div class="event-time">{{ event.start_time }} – {{ event.end_time }}</div>
            </div>
          {% endfor %}
        </div>
      {% endfor %}
    </div>
  </div>
</div>
```

**Drag & Drop** via **SortableJS** (bereits im Projekt für `org_weekly_calendar` genutzt) oder **Alpine.js** mit Maus/Touch-Events.

**Vorteil SortableJS:** Bereits vorhanden, Multi-Container (Tage) unterstützt, Touch-freundlich.  
→ Events zwischen Tagen und Zeitslots verschiebbar machen.

**Event-Editor Modal:**  
- Ein einfaches Modal (CSS `:target` oder Alpine.js)
- Felder: Titel, Notizen, Farbe (Preset-Radios + Hex-Picker), Startzeit, Dauer
- Bei Klick auf Event → Modal öffnen

### 1.5 Kalender-Einstellungen

**Pro Organization speicherbar** – analog zu weekly-planner-web Settings:

```python
# Ergänzung Organization-Modell
class Organization(models.Model):
    # ... bestehende Felder
    cal_week_starts_on = models.IntegerField(default=1, choices=[(0, "Sunday"), (1, "Monday")])
    cal_included_days = models.CharField(max_length=10, default="workdays", choices=[("all", "All Days"), ("workdays", "Workdays")])
    cal_time_interval = models.IntegerField(default=60)  # Minuten zwischen Zeitslots: 15, 30, 60
    cal_start_time = models.TimeField(default=time(8, 0))
    cal_end_time = models.TimeField(default=time(20, 0))
```

### 1.6 CSS / Styling

Inspiriert von weekly-planner-web (Tailwind → Catppuccin-CSS-Variablen):

```css
/* team_calendar.css */
.calendar-event {
    position: absolute;
    border-radius: 6px;
    padding: 4px 8px;
    border-left: 3px solid;
    cursor: grab;
    user-select: none;
    overflow: hidden;
    transition: box-shadow 0.15s;
}
.calendar-event:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}
.calendar-event:active {
    cursor: grabbing;
}
.time-slot {
    height: 48px;  /* 60 Min → 48px = 0.8px/min */
    border-bottom: 1px solid var(--ctp-surface0);
}
.time-slot:hover {
    background: var(--ctp-mantle);
}
.time-slot.droppable-over {
    background: var(--ctp-overlay0);
}
```

**Mobile:** `@media (max-width: 640px)` – Zeitslot-Höhe auf 36px reduzieren, Schrift kleiner.

### 1.7 Navigation

- Neuer Eintrag im Org-Dashboard: "📅 Team Calendar"
- Eigener Tab in der Org-Navigation

### 1.8 i18n

- Alle UI-Strings in `locale/de/LC_MESSAGES/django.po` eintragen

### 1.9 Tests

Neue Test-Datei: `tests/test_calendar.py`

- `test_add_event`
- `test_update_event`
- `test_delete_event`
- `test_events_are_org_scoped`
- `test_only_org_members_can_see_events`
- `test_drag_event_to_other_day`
- `test_calendar_shows_correct_week`

### 1.10 Abgrenzung zum bestehenden org_weekly_calendar

| Aspekt | org_weekly_calendar (bestehend) | Team Calendar (NEU) |
|--------|--------------------------------|---------------------|
| Zweck | Zeiterfassung pro Mitarbeiter | Team-Planung / Availabilities |
| Datenbasis | `TimeEntry` (gebuchte Stunden) | `CalendarEvent` (geplante Blöcke) |
| Interaktion | Read-only für Employees | Alle Member können add/edit/delete |
| Drag&Drop | Nur Manager für TimeEntries | Alle Member für CalendarEvents |
| Layout | Tabelle mit Einträgen pro Tag | Tage × Stunden Grid mit positionierten Blöcken |
| Zielgruppe | Manager (Übersicht) | Alle Teammitglieder |

---

## Phase 2: Enhanced Role-Based Timer Mode

*(unverändert zur vorherigen Planung)*

### Ziel
Statt des binären `timer_only_mode` (der für ALLE gilt) ein rollenbasiertes System:

| Rolle | Timer | Manuelles Add/Edit/Delete |
|-------|-------|---------------------------|
| Manager | ✅ | ✅ (für alle Org-Mitglieder) |
| Employee | ✅ | ❌ (nur Timer + Ansicht) |

Die Organisation kann zwischen zwei Modi wählen:
1. **"Classic"** – jeder kann manuell Einträge erstellen (heutiges Verhalten ohne `timer_only_mode`)
2. **"Restricted"** – Employees nur Timer + View, Manager voller Zugriff (neues Verhalten)

### 2.1 Model – Organization erweitern

```python
class Organization(models.Model):
    TIME_TRACKING_MODE_CHOICES = [
        ("classic", "Classic – Everyone can add/edit entries"),
        ("restricted", "Restricted – Employees: timer only, Managers: full access"),
    ]
    # timer_only_mode (ALT) wird ersetzt durch:
    time_tracking_mode = models.CharField(
        max_length=20,
        choices=TIME_TRACKING_MODE_CHOICES,
        default="classic",
        verbose_name="Time tracking mode",
    )
```

**Migration:** Bestehende Orgs mit `timer_only_mode=True` → `"restricted"`, danach `timer_only_mode` entfernen.

### 2.2 Helper in `organizations/utils.py`

```python
def can_edit_time_entries(user):
    """Prüft, ob ein User Einträge manuell anlegen/bearbeiten/löschen darf."""
    membership = getattr(user, "organization_membership", None)
    if not membership:
        return True
    if membership.is_manager:
        return True
    return membership.organization.time_tracking_mode == "classic"
```

### 2.3 Views anpassen

- `timetracking/views.py`: `add_entry`, `edit_entry`, `delete_entry`, `monthly_table`
- `organizations/views.py`: Dashboard-Anzeige, Toggle-View

### 2.4 Templates

- Dashboard: Radio-Buttons statt Toggle-Switch
- Home: "Add time" Button konditional
- Monthly Table: `show_actions` konditional

### 2.5 Manager kann Einträge für Mitarbeiter bearbeiten

- `edit_entry` in `timetracking/views.py` erweitern für Manager

### 2.6 Tests

- `test_manager_can_add_entry_when_restricted`
- `test_employee_blocked_when_restricted`
- `test_employee_can_add_when_classic`

---

## Phase 3: Zeitkonto (Time Account)

*(unverändert)*

### Ziel
Ein dauerhaft geführtes Zeitkonto pro Profil, das die Soll-Stunden (basierend auf `weekly_hours`) den Ist-Stunden (gebuchte `TimeEntry`s) gegenüberstellt und ein Saldo (`+`/`-` Stunden) anzeigt.

### 3.1 Berechnungs-Logik auf `Profile`

```python
def get_target_hours(self, year, month):
    """Soll-Stunden = Arbeitstage im Monat × (weekly_hours / 5)."""
    import calendar
    from datetime import date, timedelta
    from trackable.core.models import Holiday
    
    last_day = calendar.monthrange(year, month)[1]
    weekly_target = float(self.weekly_hours)
    daily_target = weekly_target / 5
    target = 0
    
    org = getattr(self.user, 'organization_membership', None)
    
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        if d.weekday() >= 5:  # Wochenende
            continue
        # Feiertag?
        is_holiday = Holiday.objects.filter(date=d).filter(
            Q(organization__isnull=True) |
            Q(organization=org.organization if org else None)
        ).exists()
        if is_holiday:
            continue
        target += daily_target
    
    return round(target, 2)

def get_balance(self, year, month):
    """Saldo = Ist - Soll."""
    return round(self.get_monthly_hours(year, month) - self.get_target_hours(year, month), 2)
```

### 3.2 Views & Templates

- `profiles/detail.html`: Neue Tabelle mit Monat × Soll/Ist/Saldo
- Farbcodierung: 🟢 Plus / 🔴 Minus
- Kumuliertes Jahressaldo

### 3.3 Tests

- `test_target_hours_calculation`
- `test_balance_positive/negative/zero`
- `test_target_hours_considers_holidays`

---

## Phase 4: PDF-Export mit Native Share (Web Share API)

*(unverändert)*

### 4.1 Neuer API-Endpunkt

```python
# timetracking/views.py
@login_required
def export_pdf_json(request, profile_id, year, month):
    """Gibt PDF als Base64-JSON zurück, für Web Share API."""
    profile = get_object_or_404(Profile, pk=profile_id, user=request.user)
    pdf_buffer = self.generate_pdf(...)
    pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode()
    return JsonResponse({
        "pdf": pdf_base64,
        "filename": f"arbeitszeiten_{profile.title}_{year}_{month}.pdf",
        "content_type": "application/pdf",
    })
```

### 4.2 Frontend-JS

```javascript
async function sharePDF(profileId, year, month) {
    const response = await fetch(`/api/export-pdf/${profileId}/${year}/${month}/`);
    const data = await response.json();
    const blob = base64ToBlob(data.pdf, data.content_type);
    const file = new File([blob], data.filename, {type: data.content_type});
    
    if (navigator.share && navigator.canShare({files: [file]})) {
        await navigator.share({files: [file], title: data.filename});
    } else {
        // Fallback: Download
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename;
        a.click();
        URL.revokeObjectURL(url);
    }
}
```

### 4.3 Tests

- `test_export_pdf_json_returns_base64`
- `test_export_pdf_json_requires_login`

---

## Phase 5: Mobile UI/UX Audit

*(erweitert um Team-Kalender-Checkpoints)*

### 5.1 Prüfpunkte

**Navigation:**
- Hamburger-Menü: alle wichtigen Links? Schließt nach Klick?
- Neue "Team Calendar"-Links auch im Hamburger?

**Team Calendar (neu):**
- Horizontales Scrollen des Grids funktioniert auf 375px?
- Zeit-Slot Höhe ausreichend für Touch (48px = 14mm)?
- Event-Blöcke tippbar (min 44×44px)?
- Drag&Drop per Touch funktioniert (SortableJS Multi-Container)?
- Modal-Editor mobil nutzbar?

**Timer:**
- Touch-Targets min 44×44px?
- Timer-Display ausreichend groß?

**Tabellen:**
- `overflow-x: auto` funktioniert?
- Sticky erste Spalte?
- Edit/Delete-Icons statt Text-Buttons?

**Formulare:**
- `type="date"`/`type="time"` auf iOS?
- `16px` Font-Size (iOS Zoom-Schutz)?

**Allgemein:**
- `env(safe-area-inset-*)` für Notch-Geräte
- `-webkit-tap-highlight-color`
- `color-scheme: light dark`

### 5.2 Konkrete CSS-Änderungen

```css
@media (max-width: 768px) {
    .btn {
        padding: 12px 20px;
        font-size: 16px;
    }
    .grid-card {
        grid-template-columns: 1fr;
    }
    .timer-display {
        font-size: 1.5rem;
    }
    .site-header {
        padding-left: max(16px, env(safe-area-inset-left));
        padding-right: max(16px, env(safe-area-inset-right));
    }
}
```

---

## Zusammenfassung & Reihenfolge

| Phase | Thema | Aufwand | Abhängigkeiten |
|-------|-------|---------|----------------|
| **1** | **Shared Weekly Calendar** | ~10–14h | Keine (eigenständiges Feature) |
| **2** | **Enhanced Role-Based Timer Mode** | ~4–6h | Migration `timer_only_mode` |
| **3** | **Zeitkonto (Time Account)** | ~4–5h | Keine |
| **4** | **PDF-Export mit Native Share** | ~3–4h | Keine |
| **5** | **Mobile UI/UX Audit** | ~4–6h | Nach Phase 1 (neue UI prüfen) |

**Empfohlen:** Phase 1 (weil aufwändigste Änderung, User-Vorbild weekly-planner-web) → Phase 2 → Phase 3 → Phase 4 → Phase 5

---

## Migration & Datenbank (alle Phasen)

### Phase 1 Migration
```python
# organizations/migrations/0004_calendarevent.py
migrations.CreateModel(
    name="CalendarEvent",
    fields=[
        ("id", models.BigAutoField(primary_key=True)),
        ("organization", models.ForeignKey(to="organizations.Organization")),
        ("created_by", models.ForeignKey(to="accounts.User")),
        ("title", models.CharField(max_length=200)),
        ("notes", models.TextField(blank=True, null=True)),
        ("color", models.CharField(max_length=20, default="blue")),
        ("day_id", models.CharField(max_length=20)),
        ("start_time", models.TimeField()),
        ("duration_minutes", models.PositiveIntegerField(default=60)),
        ("week_start", models.DateField()),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ],
)
```

### Phase 2 Migration
```python
# organizations/migrations/0005_add_time_tracking_mode.py
def forward(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    for org in Organization.objects.filter(timer_only_mode=True):
        org.time_tracking_mode = "restricted"
        org.save()

class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0004_calendarevent"),
    ]
    operations = [
        migrations.AddField(... time_tracking_mode ...),
        migrations.RunPython(forward, ...),
        migrations.RemoveField("timer_only_mode"),
    ]
```

---

## Offene Fragen

1. **Team Calendar:** Soll der Kalender "ewig" sein (immer aktuelle Woche) oder historisch (man kann vor/zurück blättern)? → Vorschlag: Beides. Default auf aktuelle Woche, Navigation vor/zurück und Sprung zu Datum.
2. **Team Calendar:** Soll es ein "ewiges Template" geben (weekly-planner-web Stil) oder werden Events pro konkreter Woche gespeichert? → Oben entschieden: konkrete Woche mit `week_start`.
3. **Zeitkonto:** Wunsch nach Jahres-/Gesamtsaldo oder nur monatsweise? → Monatsweise mit kumuliertem Total.
4. **PDF-Share:** Soll der bestehende PDF-Download-Button ersetzt oder ergänzt werden? → Ergänzt (Share-Versuch, Fallback Download).

---

*Dieses Dokument wird während der Implementierung aktualisiert.*
