#!/bin/bash
# PocketBase setup script for abcdLLM
# Run this once to download PocketBase and create collections

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PB_DIR="$SCRIPT_DIR/pocketbase"
PB_VERSION="0.22.29"

# Detect OS and arch
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$ARCH" in
  x86_64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
esac

if [ "$OS" = "darwin" ]; then
  PB_FILE="pocketbase_${PB_VERSION}_${OS}_${ARCH}.zip"
else
  PB_FILE="pocketbase_${PB_VERSION}_${OS}_${ARCH}.zip"
fi

PB_URL="https://github.com/pocketbase/pocketbase/releases/download/v${PB_VERSION}/${PB_FILE}"

echo "=== abcdLLM PocketBase Setup ==="

# Download PocketBase if not exists
if [ ! -f "$PB_DIR/pocketbase" ]; then
  echo "Downloading PocketBase v${PB_VERSION}..."
  mkdir -p "$PB_DIR"
  curl -L "$PB_URL" -o "$PB_DIR/pocketbase.zip"
  cd "$PB_DIR"
  unzip -o pocketbase.zip
  rm pocketbase.zip
  chmod +x pocketbase
  cd "$SCRIPT_DIR"
  echo "PocketBase downloaded to $PB_DIR/pocketbase"
else
  echo "PocketBase already exists at $PB_DIR/pocketbase"
fi

echo ""
echo "=== Next Steps ==="
echo "1. Start PocketBase:"
echo "   cd $PB_DIR && ./pocketbase serve"
echo ""
echo "2. Open admin UI: http://127.0.0.1:8090/_/"
echo "   Create admin account on first visit."
echo ""
echo "3. Create the following collections in PocketBase Admin UI:"
echo ""
echo "   [users] (extend the built-in Auth collection):"
echo "   - name (text)"
echo "   - role (select: ADMIN, USER) default=USER"
echo "   - primaryApiKey (text)"
echo "   - dailyUsage (number) default=0"
echo "   - dailyQuota (number) default=5000"
echo "   - totalUsage (number) default=0"
echo "   - totalQuota (number) default=50000"
echo "   - lastActive (date)"
echo "   - lastIp (text)"
echo "   - status (select: active, blocked) default=active"
echo "   - accessCount (number) default=0"
echo ""
echo "   [api_keys]:"
echo "   - user (relation -> users)"
echo "   - name (text)"
echo "   - keyHash (text)"
echo "   - keyPrefix (text)"
echo "   - dailyRequests (number)"
echo "   - dailyTokens (number)"
echo "   - totalTokens (number)"
echo "   - usedRequests (number)"
echo "   - usedTokens (number)"
echo "   - totalUsedTokens (number)"
echo "   - lastResetDate (date)"
echo "   - isActive (bool)"
echo ""
echo "   [security_events]:"
echo "   - type (select: failed_login, unusual_traffic, brute_force, ddos_attempt)"
echo "   - severity (select: low, medium, high, critical)"
echo "   - description (text)"
echo "   - ip (text)"
echo "   - userId (relation -> users, optional)"
echo ""
echo "   [api_applications]:"
echo "   - user (relation -> users)"
echo "   - userName (text)"
echo "   - projectName (text)"
echo "   - useCase (text)"
echo "   - requestedQuota (number)"
echo "   - targetModel (text)"
echo "   - status (select: pending, approved, rejected)"
echo "   - adminNote (text)"
echo ""
echo "   [usage_logs]:"
echo "   - user (relation -> users)"
echo "   - apiKey (relation -> api_keys, optional)"
echo "   - model (text)"
echo "   - endpoint (text)"
echo "   - promptTokens (number)"
echo "   - completionTokens (number)"
echo "   - totalTokens (number)"
echo "   - responseTimeMs (number)"
echo "   - statusCode (number)"
echo "   - ip (text)"
echo "   - isError (bool)"
echo ""
echo "   [user_settings]:"
echo "   - user (relation -> users, unique)"
echo "   - autoModelUpdate (bool)"
echo "   - detailedLogging (bool)"
echo "   - ipWhitelist (text)"
echo "   - emailSecurityAlerts (bool)"
echo "   - usageThresholdAlert (bool)"
echo ""
echo "4. Set API rules for each collection:"
echo "   - users: List/View/Update require @request.auth.id != ''"
echo "   - api_keys: All rules require @request.auth.id != ''"
echo "   - Other collections: Same pattern"
echo ""
echo "5. Start the FastAPI backend:"
echo "   cd $SCRIPT_DIR && uvicorn main:app --reload --port 8000"
