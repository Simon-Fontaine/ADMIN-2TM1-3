#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR=~/backups
mkdir -p $BACKUP_DIR

cd ~/web-secure
PASSWORD=$(grep MARIADB_ROOT_PASSWORD db/root.env | cut -d= -f2)
docker exec db mariadb-dump --all-databases -uroot -p"$PASSWORD" | gzip > $BACKUP_DIR/woodytoys-$DATE.sql.gz

# Nettoyage des sauvegardes anciennes (plus de 30 jours)
find $BACKUP_DIR -name "woodytoys-*.sql.gz" -type f -mtime +30 -delete