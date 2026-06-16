#!/bin/bash
# Backup-Script für die CL-Seminare Seite (Coolify / Docker)
#
# Sichert die SQLite-Datenbank und die Media-Uploads.
# Aufruf per Host-Cronjob (z. B. täglich um 3:00 Uhr):
#   0 3 * * * /root/backups/backup-seminare.sh
#
# Dieses Script liegt als Referenz im Git-Repo unter scripts/backup-seminare.sh
# und muss auf den Server nach /root/backups/ kopiert werden.

set -euo pipefail

# ── Konfiguration ────────────────────────────────────────────────────────────
BACKUP_DIR="/root/backups/seminare"
DB_CONTAINER_PATH="/app/data/db.sqlite3"
MEDIA_CONTAINER_PATH="/app/media"
RETENTION_DAYS=30          # Backups älter als 30 Tage werden gelöscht
LOG_FILE="${BACKUP_DIR}/backup.log"

# ── Container identifizieren ─────────────────────────────────────────────────
# Nutzt Coolify-Labels, die bei jedem Deployment gleich bleiben.
# Alternativ: --filter "ancestor=m5wkwnpnt9f5th648tmwmcvs_django"
DJANGO_CONTAINER=$(docker ps \
  --filter "label=coolify.projectName=cl-seminare" \
  --filter "label=coolify.type=application" \
  --format "{{.ID}}" \
  | head -n1)

if [ -z "$DJANGO_CONTAINER" ]; then
  echo "$(date '+%F %T'): FEHLER – Django-Container für cl-seminare nicht gefunden!" \
    | tee -a "$LOG_FILE"
  exit 1
fi

# ── Verzeichnisse anlegen ────────────────────────────────────────────────────
mkdir -p "${BACKUP_DIR}/db"
mkdir -p "${BACKUP_DIR}/media"
mkdir -p "${BACKUP_DIR}/logs"

# ── Datenbank sichern (via docker cp) ────────────────────────────────────────
DB_BACKUP="${BACKUP_DIR}/db/seminare-db-$(date '+%F').sqlite3"
if docker cp "${DJANGO_CONTAINER}:${DB_CONTAINER_PATH}" "$DB_BACKUP"; then
  echo "$(date '+%F %T'): DB-Backup erfolgreich (${DB_BACKUP})" | tee -a "$LOG_FILE"
else
  echo "$(date '+%F %T'): FEHLER – DB-Backup fehlgeschlagen!" | tee -a "$LOG_FILE"
  exit 2
fi

# ── Media-Dateien sichern (als tar.gz via docker exec) ───────────────────────
MEDIA_BACKUP="${BACKUP_DIR}/media/seminare-media-$(date '+%F').tar.gz"
if docker exec "$DJANGO_CONTAINER" tar czf - -C "$MEDIA_CONTAINER_PATH" . \
  > "$MEDIA_BACKUP"; then
  echo "$(date '+%F %T'): Media-Backup erfolgreich (${MEDIA_BACKUP})" | tee -a "$LOG_FILE"
else
  echo "$(date '+%F %T'): FEHLER – Media-Backup fehlgeschlagen!" | tee -a "$LOG_FILE"
  exit 3
fi

# ── Alte Backups aufräumen (älter als RETENTION_DAYS) ────────────────────────
find "${BACKUP_DIR}/db"    -name "seminare-db-*.sqlite3"    -type f -mtime "+${RETENTION_DAYS}" -delete
find "${BACKUP_DIR}/media" -name "seminare-media-*.tar.gz"  -type f -mtime "+${RETENTION_DAYS}" -delete

echo "$(date '+%F %T'): Backup-Lauf abgeschlossen (Container ${DJANGO_CONTAINER})" | tee -a "$LOG_FILE"
