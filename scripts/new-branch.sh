#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <type> <name>"
  echo "Types: feat | fix | refactor | docs | chore"
  exit 1
fi

TYPE="$1"
shift
NAME_RAW="$*"

case "$TYPE" in
  feat|fix|refactor|docs|chore) ;;
  *)
    echo "Invalid type: $TYPE"
    exit 1
    ;;
esac

SLUG="$(echo "$NAME_RAW" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
if [ -z "$SLUG" ]; then
  echo "Branch name cannot be empty"
  exit 1
fi

BASE="Main-NativeApp"
BRANCH="$TYPE/$SLUG"

CURRENT="$(git branch --show-current)"
if [ "$CURRENT" != "$BASE" ]; then
  echo "Switching to $BASE"
  git checkout "$BASE"
fi

git pull --ff-only

git checkout -b "$BRANCH"

echo "Created and switched to: $BRANCH"
echo "Next: git push -u origin $BRANCH"
