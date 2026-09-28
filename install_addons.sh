#!/usr/bin/env bash
#
# Cai dat add-on iBar / Dental-Lib / Rmvb-Bar tren Ubuntu (va cac ban Linux khac).
# Toan bo logic nam trong install_addons.py - file nay chi tim Python va truyen tham so.
#
#   ./install_addons.sh                 # hoi chon phien ban Blender
#   ./install_addons.sh --all           # cai cho moi phien ban tim thay
#   ./install_addons.sh --versions 5.2  # chi cai Blender 5.2
#   ./install_addons.sh --list          # xem profile + duong dan blender
#   ./install_addons.sh --no-enable     # chi copy file, khong tu bat add-on
#
set -euo pipefail

cd "$(dirname "$0")"

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[LOI] Khong tim thay Python 3. Cai dat truoc:" >&2
    echo "      sudo apt update && sudo apt install -y python3" >&2
    exit 1
fi

# Bao som neu may chua co Blender (script Python van tu tim lai chinh xac hon)
if ! command -v blender >/dev/null 2>&1 && [ ! -x /snap/bin/blender ]; then
    echo "[CANH BAO] Khong tim thay lenh 'blender' trong PATH hay /snap/bin."
    echo "           Script se van copy file add-on, nhung can bat add-on thu cong trong Blender."
fi

exec "$PYTHON" install_addons.py --no-pause "$@"
