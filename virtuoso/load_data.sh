#!/bin/bash

set -euo pipefail

CONTAINER_NAME="semrepov2"
HOST_LOAD_DIR="/home/yunisusan/semrepov2/toLoad" # Host path (where the folders exist locally)
CONTAINER_LOAD_DIR="/opt/virtuoso-opensource/database/toLoad" # Container path (where Virtuoso accesses the files)
GRAPH_URI="https://semrepo.org"

echo "Checking directories..."

if [ ! -d "$HOST_LOAD_DIR" ]; then
    echo "ERROR: Host directory not found: $HOST_LOAD_DIR"
    exit 1
fi

if ! docker exec "$CONTAINER_NAME" test -d "$CONTAINER_LOAD_DIR"; then
    echo "ERROR: Container directory not found: $CONTAINER_LOAD_DIR"
    exit 1
fi

echo "Host and container directories OK."

echo "Registering RDF files..."

SQL_FILE=$(mktemp)
trap 'rm -f "$SQL_FILE"' EXIT

FOLDER_COUNT=0

for dir in "$HOST_LOAD_DIR"/*/; do

    [ -d "$dir" ] || continue

    FOLDER=$(basename "$dir")

    echo "Registering folder: $FOLDER"

    echo "ld_dir('$CONTAINER_LOAD_DIR/$FOLDER', '%.ttl', '$GRAPH_URI');" >> "$SQL_FILE"

    FOLDER_COUNT=$((FOLDER_COUNT + 1))

done

if [ "$FOLDER_COUNT" -eq 0 ]; then
    echo "ERROR: No subdirectories found!"
    exit 1
fi

echo "Found $FOLDER_COUNT folders."

echo "Sending registration commands to Virtuoso..."

docker exec -i "$CONTAINER_NAME" isql 1111 dba dba < "$SQL_FILE"

echo "Registration completed."

echo "Starting RDF loader..."

docker exec -i "$CONTAINER_NAME" isql 1111 dba dba <<EOF
rdf_loader_run();
checkpoint;
exit;
EOF

echo "RDF loader command completed."
