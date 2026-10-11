#!/usr/bin/env sh
set -eu

adlab_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$adlab_directory"

for adlab_python in python3 python; do
  if command -v "$adlab_python" >/dev/null 2>&1 && \
     "$adlab_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    exec "$adlab_python" -X utf8 app.py --open "$@"
  fi
done

printf '%s\n' 'Python 3.10 or newer was not found. Install Python and try again.' >&2
exit 1
