import argparse
import hashlib
from pathlib import Path


def create_hash(data: str, algorithm: str = "sha512") -> str:
    hash_func = hashlib.new(algorithm)
    hash_func.update(data.encode("utf-8"))
    return hash_func.hexdigest()


def read_hardware_id(hwid_path: Path) -> str:
    if not hwid_path.exists():
        raise FileNotFoundError(f"Khong tim thay file HWID: {hwid_path}")

    text = hwid_path.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        value = line.strip()
        if value:
            return value

    raise ValueError("File HWID rong hoac khong co du lieu hop le")


def generate_license_key(hardware_id: str) -> str:
    # Giong 100% voi logic trong addon.
    return create_hash(hardware_id * 2)


def build_parser() -> argparse.ArgumentParser:
    default_hwid = Path.home() / "Desktop" / "IbarPrep.hwid"
    default_output = Path.cwd() / "addon_ibar.key"

    parser = argparse.ArgumentParser(
        description="Tao file key tu IbarPrep.hwid"
    )
    parser.add_argument(
        "--hwid",
        type=Path,
        default=default_hwid,
        help=f"Duong dan file HWID (mac dinh: {default_hwid})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=default_output,
        help=f"Noi luu file key (mac dinh: {default_output})",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Chi in key, khong ghi file",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    hardware_id = read_hardware_id(args.hwid)
    license_key = generate_license_key(hardware_id)

    if args.print_only:
        print(license_key)
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(license_key + "\n", encoding="utf-8")

    print("Da tao key thanh cong")
    print(f"HWID file: {args.hwid}")
    print(f"Key file:  {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
