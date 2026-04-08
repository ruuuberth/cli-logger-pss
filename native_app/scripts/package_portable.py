from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _bundle_mitmproxy(target_dir: Path, bundle_dir: Path | None, fallback_binary: str | None) -> bool:
    mitmproxy_dst = target_dir / "third_party" / "mitmproxy"
    mitmproxy_dst.mkdir(parents=True, exist_ok=True)

    if bundle_dir is not None and bundle_dir.exists():
        _copy_tree(bundle_dir, mitmproxy_dst)
        return True

    if fallback_binary:
        resolved = shutil.which(fallback_binary)
        if resolved:
            src = Path(resolved).resolve()
            _copy_file(src, mitmproxy_dst / src.name)
            return True

    return False


def _zip_dir(source_dir: Path, output_zip: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build portable package folder + zip.")
    parser.add_argument("--platform", choices=["linux", "windows"], required=True)
    parser.add_argument("--app-binary", required=True)
    parser.add_argument("--output-dir", default="dist")
    parser.add_argument("--mitmproxy-bundle-dir", default="")
    parser.add_argument("--mitmproxy-fallback-binary", default="mitmdump")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    native_root = Path(__file__).resolve().parents[1]
    output_dir = (native_root / args.output_dir).resolve()
    app_binary = Path(args.app_binary).resolve()
    bundle_dir = Path(args.mitmproxy_bundle_dir).resolve() if args.mitmproxy_bundle_dir else None

    package_name = "pss-logger-native-windows" if args.platform == "windows" else "pss-logger-native-linux"
    package_root = output_dir / package_name
    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True, exist_ok=True)

    binary_name = "pss-logger-native.exe" if args.platform == "windows" else "pss-logger-native"
    _copy_file(app_binary, package_root / binary_name)

    bundled = _bundle_mitmproxy(package_root, bundle_dir, args.mitmproxy_fallback_binary)
    if args.platform != "windows":
        app_out = package_root / binary_name
        os.chmod(app_out, app_out.stat().st_mode | 0o111)
        mitmdump_path = package_root / "third_party" / "mitmproxy" / "mitmdump"
        if mitmdump_path.exists():
            os.chmod(mitmdump_path, mitmdump_path.stat().st_mode | 0o111)

    notices_src = repo_root / "THIRD_PARTY_NOTICES.txt"
    runtime_src = native_root / "README_RUNTIME.txt"
    if notices_src.exists():
        _copy_file(notices_src, package_root / "THIRD_PARTY_NOTICES.txt")
    if runtime_src.exists():
        _copy_file(runtime_src, package_root / "README_RUNTIME.txt")

    zip_name = "pss-logger-native-windows-portable.zip" if args.platform == "windows" else "pss-logger-native-linux-portable.zip"
    zip_path = output_dir / zip_name
    _zip_dir(package_root, zip_path)

    if not bundled:
        print("WARNING: mitmproxy binary was not bundled. Portable package will not capture until mitmdump is available.")

    print(str(zip_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
