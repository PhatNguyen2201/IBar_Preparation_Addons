import argparse
import shutil
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    default_source = Path.cwd() / "addon_ibar.key"
    default_target = Path.home() / "addon_ibar.key"

    parser = argparse.ArgumentParser(
        description="Chep file addon_ibar.key vao thu muc user"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=default_source,
        help=f"File key nguon (mac dinh: {default_source})",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=default_target,
        help=f"File key dich (mac dinh: {default_target})",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.source.exists():
        raise FileNotFoundError(f"Khong tim thay file key nguon: {args.source}")

    args.target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.source, args.target)

    print("Da chep key vao thu muc user thanh cong")
    print(f"Source: {args.source}")
    print(f"Target: {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
