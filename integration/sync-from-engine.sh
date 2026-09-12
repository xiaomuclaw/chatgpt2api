#!/usr/bin/env bash
# Refresh the embedded register page from the register-engine repo.
#
# Use this when the register engine's FRONTEND changed (new fields/buttons) and
# you want the page embedded in chatgpt2api to match.  Registration LOGIC lives
# in the engine's backend and needs no sync at all — this only updates the
# copied Vue page.
#
# Note: chatgpt2api's own api/proxy.ts models proxy references differently, so
# the embedded page imports the shim `@/api/proxyRegister`.  The engine's own
# source imports `@/api/proxy`.  This script rewrites that on copy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE="${1:-$ROOT/register-engine}"
DEST="$ROOT/integration/assets"
SRC="$ENGINE/web-vue/src"

[ -d "$SRC" ] || { echo "register engine source not found: $SRC"; exit 1; }

echo "engine: $ENGINE"
FILES=(
  "views/Register.vue"
  "views/register/CheckoutTaskTable.vue"
  "views/register/RegisterProviderCard.vue"
  "views/register/RegisterRuntimePanel.vue"
  "views/register/RegisterTaskSettingsPanel.vue"
  "views/register/registerConfigRuntime.ts"
  "views/register/registerGptMailRuntime.ts"
  "views/register/registerLiveRuntime.ts"
  "views/register/registerOutlookPoolRuntime.ts"
  "views/register/registerProviderRuntime.ts"
  "views/register/registerProviderView.ts"
  "api/register.ts"
  "components/ai/RuntimeLogPanel.vue"
  "components/ui/GroupedSelectMenu.vue"
  "composables/useExclusiveFloatingMenu.ts"
  "lib/pillTones.ts"
)

# files whose proxy import must be re-pointed at the chatgpt2api shim
SHIM_FILES=(
  "views/register/registerConfigRuntime.ts"
  "views/register/registerProviderView.ts"
  "views/register/RegisterTaskSettingsPanel.vue"
)

n=0
for rel in "${FILES[@]}"; do
  if [ -f "$SRC/$rel" ]; then
    mkdir -p "$DEST/web-vue/src/$(dirname "$rel")"
    cp "$SRC/$rel" "$DEST/web-vue/src/$rel"
    n=$((n+1))
  else
    echo "  skip (missing): $rel"
  fi
done
echo "refreshed $n file(s) in integration/assets"

# re-point proxy imports for the chatgpt2api side
for rel in "${SHIM_FILES[@]}"; do
  f="$DEST/web-vue/src/$rel"
  [ -f "$f" ] && sed -i "s|from '@/api/proxy'|from '@/api/proxyRegister'|g" "$f"
done
echo "proxy imports re-pointed to @/api/proxyRegister"

[ -f "$ROOT/web-vue/src/api/proxyRegister.ts" ] || echo "  WARN: web-vue/src/api/proxyRegister.ts missing"

echo
echo "now run:  python3 integration/attach.py"
echo "then:     docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d --build"
