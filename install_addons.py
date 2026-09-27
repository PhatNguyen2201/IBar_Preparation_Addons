"""
Bo cai dat tu dong 2 add-on iBar vao Blender:
  - Final_addon_Ibar_to_ORG.py
  - Gingiva_Teeth_Splitter.py

Script se:
  1. Tu dong kich hoat license key tren may hien tai (ghi ~/addon_ibar.key)
  2. Quet cac phien ban Blender da tung chay tren may (thu muc profile trong %APPDATA%)
  3. Hien danh sach cho nguoi dung chon phien ban can cai add-on
  4. Copy 2 file add-on vao thu muc scripts/addons cua (cac) phien ban da chon
  5. Neu tim thay blender.exe tuong ung, tu dong bat (enable) 2 add-on va luu preferences;
     neu khong tim thay se huong dan bat thu cong.

Chay: python install_addons.py  (hoac double-click install_addons.bat)
"""

import glob
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ADDON_FILES = [
    SCRIPT_DIR / "Final_addon_Ibar_to_ORG.py",
    SCRIPT_DIR / "Gingiva_Teeth_Splitter.py",
]

# ---------------------------------------------------------------------------
# Kich hoat license key.
# QUAN TRONG: logic ben duoi phai giong het hw_read_key()/get_stable_hardware_id()/
# _build_machine_fingerprint() trong 2 file add-on. Neu sua doi cach tinh hardware
# fingerprint trong add-on thi phai sua lai o day cho khop.
# ---------------------------------------------------------------------------

def create_hash(data: str, algorithm: str = "sha512") -> str:
    hash_func = hashlib.new(algorithm)
    hash_func.update(data.encode("utf-8"))
    return hash_func.hexdigest()


def _read_windows_machine_guid() -> str:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return str(value).strip()
    except Exception:
        return ""


def _build_machine_fingerprint() -> str:
    machine_guid = _read_windows_machine_guid()
    mac_address = str(uuid.getnode())
    host_name = os.environ.get("COMPUTERNAME", "") or os.environ.get("HOSTNAME", "")
    processor = os.environ.get("PROCESSOR_IDENTIFIER", "")
    cpu_count = os.environ.get("NUMBER_OF_PROCESSORS", "")

    parts = [machine_guid, mac_address, host_name, processor, cpu_count]
    raw_fingerprint = "|".join(part for part in parts if part)
    if not raw_fingerprint:
        raw_fingerprint = mac_address

    return create_hash(raw_fingerprint, "sha256")[:32].upper()


def get_stable_hardware_id() -> str:
    machine_id_path = Path.home() / ".ibar_machine_id"

    if machine_id_path.exists():
        try:
            cached_id = machine_id_path.read_text(encoding="utf-8").strip()
            if cached_id:
                return cached_id
        except Exception:
            pass

    hardware_id = _build_machine_fingerprint()
    try:
        machine_id_path.write_text(hardware_id, encoding="utf-8")
    except Exception:
        pass
    return hardware_id


def activate_license_key() -> bool:
    """Tu sinh va ghi addon_ibar.key cho may hien tai (tuong duong ibar_keygen.py)."""
    hardware_id = get_stable_hardware_id()
    license_key = create_hash(hardware_id * 2)
    license_path = Path.home() / "addon_ibar.key"
    try:
        license_path.write_text(license_key + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"[LOI] Khong the ghi file key: {exc}")
        return False
    print(f"[OK] Da kich hoat key tai: {license_path}")
    return True


# ---------------------------------------------------------------------------
# Tim cac profile Blender da cai (thu muc chua scripts/addons).
# ---------------------------------------------------------------------------

def find_blender_profiles():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    base = Path(appdata) / "Blender Foundation" / "Blender"
    if not base.exists():
        return []
    profiles = []
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and re.match(r"^\d+\.\d+$", entry.name):
            profiles.append(entry.name)
    return profiles


# ---------------------------------------------------------------------------
# Tim file blender.exe tuong ung tung phien ban (de tu dong bat add-on).
# ---------------------------------------------------------------------------

def find_blender_executables():
    """Tra ve dict {'4.2': 'C:\\...\\blender.exe', ...}"""
    candidates = set()
    for pattern in [
        r"C:\Program Files\Blender Foundation\*\blender.exe",
        r"C:\Program Files (x86)\Blender Foundation\*\blender.exe",
        r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe",
        r"C:\Program Files\Steam\steamapps\common\Blender\blender.exe",
    ]:
        candidates.update(glob.glob(pattern))

    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe",
        )
        value, _ = winreg.QueryValueEx(key, None)
        if value:
            candidates.add(value)
    except Exception:
        pass

    version_map = {}
    for exe in candidates:
        exe_path = Path(exe)
        if not exe_path.exists():
            continue
        try:
            result = subprocess.run(
                [str(exe_path), "--version"],
                capture_output=True, text=True, timeout=15,
            )
            match = re.search(r"Blender\s+(\d+)\.(\d+)", result.stdout)
            if match:
                version_key = f"{match.group(1)}.{match.group(2)}"
                version_map.setdefault(version_key, str(exe_path))
        except Exception:
            continue
    return version_map


# ---------------------------------------------------------------------------
# Cai dat + bat add-on.
# ---------------------------------------------------------------------------

def install_addons_to_profile(addons_dir: Path):
    addons_dir.mkdir(parents=True, exist_ok=True)
    installed_modules = []
    for addon_file in ADDON_FILES:
        if not addon_file.exists():
            print(f"[LOI] Khong tim thay file add-on: {addon_file}")
            continue
        dest = addons_dir / addon_file.name
        shutil.copy2(addon_file, dest)
        installed_modules.append(addon_file.stem)
        print(f"[OK] Da copy {addon_file.name} -> {dest}")
    return installed_modules


def enable_addons_via_blender(blender_exe: str, modules: list) -> bool:
    if not modules:
        return False
    enable_lines = "\n".join(
        f"bpy.ops.preferences.addon_enable(module={module!r})" for module in modules
    )
    script_content = (
        "import bpy\n"
        f"{enable_lines}\n"
        "bpy.ops.wm.save_userpref()\n"
        "print('ADDON_ENABLE_OK')\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(script_content)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [blender_exe, "--background", "--python", tmp_path],
            capture_output=True, text=True, timeout=90,
        )
        ok = "ADDON_ENABLE_OK" in result.stdout
        if not ok:
            print("---- Blender stdout ----")
            print(result.stdout[-2000:])
            print("---- Blender stderr ----")
            print(result.stderr[-2000:])
        return ok
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def prompt_choice(profiles):
    print("\nCac phien ban Blender tim thay tren may:")
    for i, version in enumerate(profiles, start=1):
        print(f"  [{i}] Blender {version}")
    all_index = len(profiles) + 1
    print(f"  [{all_index}] Tat ca cac phien ban tren")

    while True:
        try:
            raw = input("\nChon phien ban de cai add-on (nhap so): ").strip()
        except EOFError:
            print("\n[LOI] Khong nhan duoc lua chon (khong co input). Huy cai dat.")
            raise SystemExit(1)
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(profiles):
                return [profiles[idx - 1]]
            if idx == all_index:
                return profiles
        print("Lua chon khong hop le, vui long thu lai.")


def main():
    print("=== Cai dat tu dong add-on iBar ===\n")

    missing = [f.name for f in ADDON_FILES if not f.exists()]
    if missing:
        print("[LOI] Thieu file add-on trong thu muc script:", ", ".join(missing))
        try:
            input("\nNhan Enter de thoat...")
        except EOFError:
            pass
        return

    activate_license_key()

    profiles = find_blender_profiles()
    if not profiles:
        appdata = os.environ.get("APPDATA", "")
        print(f"\n[LOI] Khong tim thay profile Blender nao trong "
              f"{appdata}\\Blender Foundation\\Blender")
        print("Hay mo Blender it nhat 1 lan roi chay lai script nay.")
        try:
            input("\nNhan Enter de thoat...")
        except EOFError:
            pass
        return

    chosen = prompt_choice(profiles)
    blender_exes = find_blender_executables()
    appdata = Path(os.environ["APPDATA"])

    for version in chosen:
        print(f"\n--- Cai dat cho Blender {version} ---")
        addons_dir = appdata / "Blender Foundation" / "Blender" / version / "scripts" / "addons"
        modules = install_addons_to_profile(addons_dir)
        if not modules:
            continue

        blender_exe = blender_exes.get(version)
        if blender_exe:
            print(f"Tim thay blender.exe: {blender_exe}")
            print("Dang tu dong bat add-on...")
            if enable_addons_via_blender(blender_exe, modules):
                print(f"[OK] Da bat add-on cho Blender {version}")
            else:
                print(f"[CANH BAO] Khong the tu bat add-on cho Blender {version}. "
                      "Vui long bat thu cong trong Edit > Preferences > Add-ons.")
        else:
            print(f"[CANH BAO] Khong tim thay blender.exe cho phien ban {version}. "
                  "Vui long mo Blender va bat add-on thu cong trong Edit > Preferences > Add-ons.")

    print("\n=== Hoan tat ===")
    try:
        input("Nhan Enter de thoat...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
