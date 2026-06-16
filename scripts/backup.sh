#!/bin/bash
# Generic Docker backup script for trackable.
#
# Usage:
#   1. Copy this file to your host (e.g. /opt/trackable/backup.sh)
#   2. Adjust the CONFIGURATION section below for your deployment
#   3. Make it executable: chmod +x /opt/trackable/backup.sh
#   4. Add to cron: crontab -e
#
# For Coolify deployments, set COOLIFY_PROJECT_NAME to your Coolify project name.
# For standard Docker Compose deployments, set CONTAINER_NAME_FILTER to your app container name.
# You need at least one of COOLIFY_PROJECT_NAME or CONTAINER_NAME_FILTER.

set -euo pipefail

# ── CONFIGURATION ───────────────────────────────────────────────────────────
PROJECT_NAME="trackable"                       # prefix for backup files
BACKUP_DIR="/opt/trackable/backups"            # backup destination on host
DB_CONTAINER_PATH="/app/data/db.sqlite3"       # database path inside container
MEDIA_CONTAINER_PATH="/app/media"              # media path inside container
BACKUP_MEDIA=true                              # set to false to skip media backup
RETENTION_DAYS=30                              # delete backups older than N days

# Container detection (at least one must be set)
COOLIFY_PROJECT_NAME=""                        # e.g. "trackable" — leave empty for plain Docker Compose
CONTAINER_NAME_FILTER="trackable-app"          # e.g. "trackable-app" or "django"

LOG_FILE="${BACKUP_DIR}/backup.log"
# ─────────────────────────────────────────────────────────────────────────────

log() {
    echo "$(date '+%F %T'): $*" | tee -a "$LOG_FILE"
}

fail() {
    log "FEHLER – $*"
    exit 1
}

# Find the running Django app container
find_container() {
    local container_id=""

    if [[ -n "${COOLIFY_PROJECT_NAME}" ]]; then
        container_id=$(docker ps \
            --filter "label=coolify.projectName=${COOLIFY_PROJECT_NAME}" \
            --filter "name=${CONTAINER_NAME_FILTER}" \
            --format "{{.ID}}" \
            | head -n1)
    fi

    if [[ -z "${container_id}" ]]; then
        container_id=$(docker ps \
            --filter "name=${CONTAINER_NAME_FILTER}" \
            --format "{{.ID}}" \
            | head -n1)
    fi

    if [[ -z "${container_id}" ]]; then
        fail "Kein laufender Container gefunden (Filter: name=${CONTAINER_NAME_FILTER}, Coolify: ${COOLIFY_PROJECT_NAME:-nicht gesetzt})"
    fi

    echo "$container_id"
}

mkdir -p "${BACKUP_DIR}/db"
mkdir -p "${BACKUP_DIR}/media"
mkdir -p "${BACKUP_DIR}/logs"
touch "$LOG_FILE"

CONTAINER=$(find_container)
log "Container gefunden: ${CONTAINER}"

# Verify database exists inside container
if ! docker exec "$CONTAINER" test -f "$DB_CONTAINER_PATH" 2>/dev/null; then
    log "Container-Mounts:"
    docker inspect "$CONTAINER" --format '{{json .Mounts}}' | python3 -m json.tool 2>/dev/null | tee -a "$LOG_FILE"
    fail "Datenbank ${DB_CONTAINER_PATH} nicht im Container gefunden"
fi

# Backup database
DB_BACKUP="${BACKUP_DIR}/db/${PROJECT_NAME}-db-$(date '+%F').sqlite3"
if docker cp "${CONTAINER}:${DB_CONTAINER_PATH}" "$DB_BACKUP"; then
    log "DB-Backup erfolgreich: ${DB_BACKUP}"
else
    fail "DB-Backup fehlgeschlagen"
fi

# Backup media
if [[ "${BACKUP_MEDIA}" == "true" ]]; then
    MEDIA_BACKUP="${BACKUP_DIR}/media/${PROJECT_NAME}-media-$(date '+%F').tar.gz"
    if docker exec "$CONTAINER" tar czf - -C "$MEDIA_CONTAINER_PATH" . > "$MEDIA_BACKUP"; then
        log "Media-Backup erfolgreich: ${MEDIA_BACKUP}"
    else
        fail "Media-Backup fehlgeschlagen"
    fi
fi

# Cleanup old backups
find "${BACKUP_DIR}/db"    -name "${PROJECT_NAME}-db-*.sqlite3"    -type f -mtime "+${RETENTION_DAYS}" -delete
find "${BACKUP_DIR}/media" -name "${PROJECT_NAME}-media-*.tar.gz"  -type f -mtime "+${RETENTION_DAYS}" -delete

log "Backup-Lauf abgeschlossen (Container ${CONTAINER})"
