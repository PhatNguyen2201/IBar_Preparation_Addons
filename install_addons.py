"""
Bo cai dat tu dong cac add-on iBar vao Blender (Windows / Ubuntu / macOS):
  - Final_addon_Ibar_to_ORG.py     (panel iBar cu)
  - Gingiva_Teeth_Splitter.py      (tach Gingiva/Rang)
  - dental_lib.py                  (Dental-Lib: thu vien Connection/Attachment)
  - rmvb_bar.py                    (Rmvb-Bar: thiet ke bar, dung Dental-Lib)

Script se:
  1. Tu dong kich hoat license key tren may hien tai (ghi ~/addon_ibar.key)
  2. Quet cac phien ban Blender da tung chay (profile trong APPDATA /
     ~/.config/blender / ~/Library/Application Support/Blender)
  3. Hien danh sach cho nguoi dung chon phien ban can cai (hoac --all)
  4. Copy file add-on vao scripts/addons cua (cac) phien ban da chon
  5. Neu tim thay blender, tu dong bat add-on (theo thu tu phu thuoc) va
     luu preferences; neu khong thi huong dan bat thu cong.

Chay:
  Windows : python install_addons.py            (hoac double-click .bat)
  Ubuntu  : ./install_addons.sh                 (hoac python3 install_addons.py)
  Khong hoi: python3 install_addons.py --all
  Liệt kê  : python3 install_addons.py --list
"""

import argparse
import glob
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# THU TU RAT QUAN TRONG: rmvb_bar import dental_lib luc khoi dong.
ADDON_FILES = [
    SCRIPT_DIR / "Final_addon_Ibar_to_ORG.py",
    SCRIPT_DIR / "Gingiva_Teeth_Splitter.py",
    SCRIPT_DIR / "dental_lib.py",
    SCRIPT_DIR / "rmvb_bar.py",
]

# ---------------------------------------------------------------------------
# Kich hoat license key.
# QUAN TRONG: logic ben duoi phai giong het hw_read_key()/get_stable_hardware_id()/
# _build_machine_fingerprint() trong 2 file add-on iBar. Neu sua doi cach tinh hardware
# fingerprint trong add-on thi phai sua lai o day cho khop (ke ca tren Linux).
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
# Nen tang: Windows / Linux (Ubuntu) / macOS
# ---------------------------------------------------------------------------

def current_os() -> str:
    name = platform.system().lower()
    if name.startswith("win"):
        return "windows"
    if name == "darwin":
        return "macos"
    return "linux"


def profiles_base_dir() -> Path:
    """Thu muc cha cua cac profile Blender theo tung he dieu hanh."""
    system = current_os()
    if system == "windows":
        appdata = os.environ.get("APPDATA")
        return Path(appdata) / "Blender Foundation" / "Blender" if appdata else Path()
    if system == "macos":
        return Path.home() / "Library" / "Application Support" / "Blender"
    # Linux/Ubuntu: ~/.config/blender (ban snap classic cung dung $HOME that)
    candidates = []
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        candidates.append(Path(xdg) / "blender")
    candidates.append(Path.home() / ".config" / "blender")
    candidates.append(Path.home() / "snap" / "blender" / "current" / ".config" / "blender")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[1]


def addons_dir_for_version(version: str) -> Path:
    return profiles_base_dir() / version / "scripts" / "addons"


# ---------------------------------------------------------------------------
# Tim cac profile Blender da cai (thu muc chua scripts/addons).
# ---------------------------------------------------------------------------

def find_blender_profiles():
    base = profiles_base_dir()
    if not base.exists():
        return []
    profiles = []
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and re.match(r"^\d+\.\d+$", entry.name):
            profiles.append(entry.name)

    def as_number(name):
        major, minor = name.split(".")
        return (int(major), int(minor))

    return sorted(profiles, key=as_number)


# ---------------------------------------------------------------------------
# Tim file executable tuong ung tung phien ban (de tu dong bat add-on).
# ---------------------------------------------------------------------------

def _version_of(command):
    """Chay `<command> --version`, tra ve 'X.Y' hoac None."""
    try:
        result = subprocess.run(list(command) + ["--version"],
                                capture_output=True, text=True, timeout=25)
        match = re.search(r"Blender\s+(\d+)\.(\d+)", result.stdout)
        if match:
            return f"{match.group(1)}.{match.group(2)}"
    except Exception:
        pass
    return None


def find_blender_executables():
    """Tra ve dict {'5.2': [['/snap/bin/blender'], ...], ...}."""
    system = current_os()
    paths = []

    if system == "windows":
        for pattern in [
            r"C:\Program Files\Blender Foundation\*\blender.exe",
            r"C:\Program Files (x86)\Blender Foundation\*\blender.exe",
            r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe",
            r"C:\Program Files\Steam\steamapps\common\Blender\blender.exe",
        ]:
            paths.extend(glob.glob(pattern))
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe",
            )
            value, _ = winreg.QueryValueEx(key, None)
            if value:
                paths.append(value)
        except Exception:
            pass
    elif system == "macos":
        paths.extend(glob.glob("/Applications/Blender*.app/Contents/MacOS/Blender"))
        paths.extend(glob.glob(str(Path.home() / "Applications" / "Blender*.app" /
                                   "Contents" / "MacOS" / "Blender")))
    else:
        # Linux / Ubuntu: PATH, snap, deb, tar.gz trong /opt, Steam
        for name in ("blender", "blender-lts"):
            found = shutil.which(name)
            if found:
                paths.append(found)
        paths.extend(["/snap/bin/blender", "/usr/bin/blender",
                      "/usr/local/bin/blender", "/opt/blender/blender"])
        for pattern in ("/opt/blender*/blender", "/opt/*blender*/blender",
                        str(Path.home() / ".local" / "bin" / "blender"),
                        str(Path.home() / "Applications" / "*blender*" / "blender"),
                        "/usr/lib/steam/steamapps/common/Blender/blender",
                        str(Path.home() / ".steam" / "steam" / "root" / "steamapps" /
                            "common" / "Blender" / "blender")):
            paths.extend(glob.glob(pattern))

    commands = []
    for path in paths:
        exe = Path(path)
        if exe.exists() and os.access(exe, os.X_OK):
            commands.append([str(exe)])

    if system == "linux" and shutil.which("flatpak"):
        try:
            listing = subprocess.run(["flatpak", "list", "--app", "--columns=application"],
                                     capture_output=True, text=True, timeout=25)
            if "org.blender.Blender" in listing.stdout:
                commands.append(["flatpak", "run", "org.blender.Blender"])
        except Exception:
            pass

    version_map = {}
    for command in commands:
        version = _version_of(command)
        if not version:
            continue
        seen = [existing[0] for existing in version_map.setdefault(version, [])]
        if command[0] not in seen:
            version_map[version].append(command)
    return version_map


def executable_for(version: str, version_map: dict):
    """Chon lenh blender KHOP DUNG phien ban `version`.

    Khong dung dai "chi co 1 ban blender" vi chay blender sai phien ban se bat
    add-on vao userpref cua ban khac, khong phai profile dang cai.
    """
    commands = version_map.get(version)
    return commands[0] if commands else None


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


def enable_addons_via_blender(blender_cmd, modules: list) -> bool:
    """Bat add-on bang chinh Blender (background) va kiem tra ket qua."""
    if not modules:
        return False
    enable_lines = "\n".join(
        f"bpy.ops.preferences.addon_enable(module={module!r})" for module in modules
    )
    script_content = (
        "import bpy\n"
        f"{enable_lines}\n"
        "wanted = " + repr(list(modules)) + "\n"
        "active = [a.module for a in bpy.context.preferences.addons]\n"
        "print('ADDON_STATE', [(m, m in active) for m in wanted])\n"
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
            list(blender_cmd) + ["--background", "--python", tmp_path],
            capture_output=True, text=True, timeout=180,
        )
        ok = "ADDON_ENABLE_OK" in result.stdout
        if not ok:
            print("---- Blender stdout ----")
            print(result.stdout[-2000:])
            print("---- Blender stderr ----")
            print(result.stderr[-2000:])
        else:
            for line in result.stdout.splitlines():
                if line.startswith("ADDON_STATE"):
                    print("   Trang thai:", line[len("ADDON_STATE"):].strip())
        return ok
    except Exception as exc:
        print(f"[LOI] Khong chay duoc Blender de bat add-on: {exc}")
        return False
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Cai dat add-on iBar / Dental-Lib / Rmvb-Bar vao Blender "
                    "(Windows, Ubuntu, macOS)")
    parser.add_argument("--all", action="store_true",
                        help="Cai cho moi phien ban Blender tim thay (khong hoi)")
    parser.add_argument("--versions", nargs="+", metavar="X.Y",
                        help="Chi cai cho cac phien ban liet ke, vi du: --versions 5.2 5.1")
    parser.add_argument("--list", action="store_true",
                        help="Liệt kê profile + duong dan blender roi thoat")
    parser.add_argument("--skip-license", action="store_true",
                        help="Khong sinh file ~/addon_ibar.key")
    parser.add_argument("--no-enable", action="store_true",
                        help="Chi copy file, khong tu bat add-on trong Blender")
    parser.add_argument("--no-pause", action="store_true",
                        help="Khong doi nhan Enter khi chay xong (dung cho .sh/CI)")
    return parser.parse_args(argv)


def report_profiles(profiles, version_map):
    base = profiles_base_dir()
    print(f"He dieu hanh      : {current_os()}")
    print(f"Thu muc profile   : {base}")
    if not profiles:
        print("  (khong tim thay profile Blender nao)")
    for version in profiles:
        command = executable_for(version, version_map)
        exe = " ".join(command) if command else "(khong tim thay blender)"
        print(f"  Blender {version:<5} -> {addons_dir_for_version(version)}")
        print(f"  {' ' * 13}executable: {exe}")


def main(argv=None):
    args = parse_args(argv)
    print("=== Cai dat tu dong add-on iBar / Dental-Lib / Rmvb-Bar ===\n")

    missing = [f.name for f in ADDON_FILES if not f.exists()]
    if missing:
        print("[LOI] Thieu file add-on trong thu muc script:", ", ".join(missing))
        if not args.no_pause:
            try:
                input("\nNhan Enter de thoat...")
            except EOFError:
                pass
        return 1

    profiles = find_blender_profiles()
    version_map = find_blender_executables()

    if args.list:
        report_profiles(profiles, version_map)
        return 0

    if not profiles:
        print(f"\n[LOI] Khong tim thay profile Blender nao trong {profiles_base_dir()}")
        print("Hay mo Blender it nhat 1 lan roi chay lai script nay.")
        if not args.no_pause:
            try:
                input("\nNhan Enter de thoat...")
            except EOFError:
                pass
        return 1

    if args.versions:
        unknown = [v for v in args.versions if v not in profiles]
        if unknown:
            print("[LOI] Phien ban khong ton tai tren may:", ", ".join(unknown))
            print("Co the chon:", ", ".join(profiles))
            return 1
        chosen = [v for v in profiles if v in args.versions]
    elif args.all:
        chosen = profiles
    else:
        chosen = prompt_choice(profiles)

    if not args.skip_license:
        activate_license_key()

    failures = []
    for version in chosen:
        print(f"\n--- Cai dat cho Blender {version} ---")
        addons_dir = addons_dir_for_version(version)
        modules = install_addons_to_profile(addons_dir)
        if not modules:
            failures.append(version)
            continue

        command = executable_for(version, version_map)
        if args.no_enable:
            print("[BO QUA] Tu bat add-on (--no-enable). Mo Blender > Edit > "
                  "Preferences > Add-ons va bat:")
            for module in modules:
                print(f"    - {module}")
            continue
        if command:
            print("Tim thay blender:", " ".join(command))
            print("Dang tu dong bat add-on...")
            if enable_addons_via_blender(command, modules):
                print(f"[OK] Da bat add-on cho Blender {version}")
            else:
                failures.append(version)
                print(f"[CANH BAO] Khong the tu bat add-on cho Blender {version}. "
                      "Vui long bat thu cong trong Edit > Preferences > Add-ons.")
        else:
            failures.append(version)
            print(f"[CANH BAO] Khong tim thay executable cho phien ban {version}. "
                  "Mo Blender va bat thu cong trong Edit > Preferences > Add-ons:")
            for module in modules:
                print(f"    - {module}")

    print("\n=== Hoan tat ===")
    if failures:
        print("Can kiem tra lai:", ", ".join(failures))
    if not args.no_pause:
        try:
            input("Nhan Enter de thoat...")
        except EOFError:
            pass
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
