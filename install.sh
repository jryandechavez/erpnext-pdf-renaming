#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="erpnext_pdf_renaming"
APP_REPOSITORY="https://github.com/jryandechavez/erpnext-pdf-renaming.git"
BENCH_PATH="/home/frappe/frappe-bench"
SITE_NAME=""
BRANCH="main"

usage() {
  cat <<'EOF'
Install or update ERPNext PDF Renaming safely.

Usage:
  bash install.sh --site SITE_NAME [--bench BENCH_PATH] [--branch BRANCH]

Options:
  --site     Required Frappe site directory name.
  --bench    Bench directory (default: /home/frappe/frappe-bench).
  --branch   Git branch to install or update (default: main).
  -h, --help Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site)
      [[ $# -ge 2 ]] || { echo "Missing value for --site" >&2; exit 2; }
      SITE_NAME="$2"
      shift 2
      ;;
    --bench)
      [[ $# -ge 2 ]] || { echo "Missing value for --bench" >&2; exit 2; }
      BENCH_PATH="$2"
      shift 2
      ;;
    --branch)
      [[ $# -ge 2 ]] || { echo "Missing value for --branch" >&2; exit 2; }
      BRANCH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "$SITE_NAME" ]] || { echo "--site is required." >&2; usage >&2; exit 2; }
[[ -d "$BENCH_PATH" ]] || { echo "Bench directory not found: $BENCH_PATH" >&2; exit 1; }
[[ -f "$BENCH_PATH/sites/apps.txt" ]] || { echo "This is not a valid Bench directory: $BENCH_PATH" >&2; exit 1; }
[[ -d "$BENCH_PATH/sites/$SITE_NAME" ]] || { echo "Frappe site not found: $BENCH_PATH/sites/$SITE_NAME" >&2; exit 1; }

BENCH_OWNER="$(stat -c '%U' "$BENCH_PATH" 2>/dev/null || stat -f '%Su' "$BENCH_PATH")"
CURRENT_USER="$(id -un)"

if [[ "$CURRENT_USER" != "$BENCH_OWNER" ]]; then
  if [[ "$(id -u)" -eq 0 ]] && command -v sudo >/dev/null 2>&1; then
    echo "Switching from root to Bench owner: $BENCH_OWNER"
    exec sudo -H -u "$BENCH_OWNER" bash "$0" \
      --site "$SITE_NAME" --bench "$BENCH_PATH" --branch "$BRANCH"
  fi
  echo "Run this installer as the Bench owner ($BENCH_OWNER), not $CURRENT_USER." >&2
  exit 1
fi

cd "$BENCH_PATH"
APP_PATH="$BENCH_PATH/apps/$APP_NAME"
LEGACY_APP_PATH="$BENCH_PATH/apps/erpnext-pdf-renaming"

echo "[1/7] Preparing $APP_NAME"
if [[ ! -e "$APP_PATH" && -d "$LEGACY_APP_PATH/.git" ]]; then
  mv "$LEGACY_APP_PATH" "$APP_PATH"
fi

if [[ -d "$APP_PATH/.git" ]]; then
  if git -C "$APP_PATH" remote get-url origin >/dev/null 2>&1; then
    APP_REMOTE="origin"
  elif git -C "$APP_PATH" remote get-url upstream >/dev/null 2>&1; then
    APP_REMOTE="upstream"
  else
    git -C "$APP_PATH" remote add origin "$APP_REPOSITORY"
    APP_REMOTE="origin"
  fi
  git -C "$APP_PATH" fetch "$APP_REMOTE" "$BRANCH"
  git -C "$APP_PATH" checkout "$BRANCH"
  git -C "$APP_PATH" pull --ff-only "$APP_REMOTE" "$BRANCH"
elif [[ -e "$APP_PATH" ]]; then
  echo "App path exists but is not a Git checkout: $APP_PATH" >&2
  exit 1
else
  bench get-app --skip-assets --branch "$BRANCH" "$APP_REPOSITORY"
fi

echo "[2/7] Registering the app with Bench"
APPS_FILE="$BENCH_PATH/sites/apps.txt"
TEMP_APPS="$(mktemp "$BENCH_PATH/sites/apps.txt.XXXXXX")"
awk -v app="$APP_NAME" '
  NF && $0 != app && $0 != "erpnext-pdf-renaming" { print }
  END { print app }
' "$APPS_FILE" > "$TEMP_APPS"
mv "$TEMP_APPS" "$APPS_FILE"

# Bench normally creates this link during asset setup. Create it explicitly as
# well because some v15 Bench releases calculate the app list before get-app
# finishes registering a new app, leaving every /assets URL as a 404.
PUBLIC_PATH="$APP_PATH/$APP_NAME/public"
ASSET_LINK="$BENCH_PATH/sites/assets/$APP_NAME"
[[ -d "$PUBLIC_PATH" ]] || { echo "App public directory not found: $PUBLIC_PATH" >&2; exit 1; }
mkdir -p "$BENCH_PATH/sites/assets"
ln -sfn "$PUBLIC_PATH" "$ASSET_LINK"
[[ -f "$ASSET_LINK/css/pdf_renamer.css" ]] || { echo "App stylesheet was not linked correctly." >&2; exit 1; }

echo "[3/7] Installing Python package"
"$BENCH_PATH/env/bin/python" -m pip install --quiet --upgrade -e "$APP_PATH"

echo "[4/7] Linking and building app assets"
bench build --app "$APP_NAME"
[[ -f "$ASSET_LINK/css/pdf_renamer.css" ]] || { echo "App stylesheet is missing after build." >&2; exit 1; }

echo "[5/7] Installing app on site when needed"
if ! bench --site "$SITE_NAME" list-apps --format text | grep -qxF "$APP_NAME"; then
  bench --site "$SITE_NAME" install-app "$APP_NAME"
else
  echo "$APP_NAME is already installed on $SITE_NAME"
fi

echo "[6/7] Migrating and clearing cache"
bench --site "$SITE_NAME" migrate
bench --site "$SITE_NAME" clear-cache

echo "[7/7] Restarting Bench"
bench restart

echo
echo "ERPNext PDF Renaming is ready: /app/pdf-renamer"
