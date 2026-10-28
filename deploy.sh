#!/bin/sh
set -eu

SERVER_HOST="${SERVER_HOST:-127.0.0.1}"
SERVER_USER="${SERVER_USER:-ubuntu}"
SSH_KEY="${SSH_KEY:-.ssh/project_ed25519}"
REMOTE_DIR="${REMOTE_DIR:-/opt/crypto-bot}"

if [ ! -f "$SSH_KEY" ]; then
  echo "SSH key not found: $SSH_KEY" >&2
  exit 1
fi

SSH_COMMAND="ssh -F /dev/null -i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"

$SSH_COMMAND "$SERVER_USER@$SERVER_HOST" "sudo install -d -o $SERVER_USER -g $SERVER_USER $REMOTE_DIR"
rsync -az --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '.env' \
  --exclude '.env.production' \
  --exclude '.ssh/' \
  --exclude 'db.sqlite3' \
  --exclude '__pycache__/' \
  -e "$SSH_COMMAND" ./ "$SERVER_USER@$SERVER_HOST:$REMOTE_DIR/"

$SSH_COMMAND "$SERVER_USER@$SERVER_HOST" "cd $REMOTE_DIR && test -f .env.production && docker compose up -d --build --remove-orphans"
$SSH_COMMAND "$SERVER_USER@$SERVER_HOST" "cd $REMOTE_DIR && docker compose restart nginx"
$SSH_COMMAND "$SERVER_USER@$SERVER_HOST" "curl --fail --silent --show-error --retry 5 --retry-delay 3 --retry-all-errors http://127.0.0.1/ready/ >/dev/null"
$SSH_COMMAND "$SERVER_USER@$SERVER_HOST" "cd $REMOTE_DIR && docker compose exec -T web python manage.py record_activity release"
$SSH_COMMAND "$SERVER_USER@$SERVER_HOST" "cd $REMOTE_DIR && docker compose ps"

echo "Deployed to http://$SERVER_HOST/"
