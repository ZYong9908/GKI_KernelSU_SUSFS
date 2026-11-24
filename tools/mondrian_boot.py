"""Pack a kernel built by the Redmi K60 workflow with the local ZhuiMeng ROM."""

import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zipfile


STOCK_SHA256 = "5f038cb4cb71985be5c358aa8ec8e21db52ee41f90d738e73c21559876c20f94"
PAGE = 4096


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def boot_sections(path):
    with path.open("rb") as file:
        header = file.read(PAGE)
        if header[:8] != b"ANDROID!" or struct.unpack_from("<I", header, 40)[0] != 4:
            raise ValueError("Expected an Android boot v4 image")
        kernel_size, ramdisk_size = struct.unpack_from("<II", header, 8)
        kernel = file.read(kernel_size)
        file.seek(PAGE + ((kernel_size + PAGE - 1) // PAGE) * PAGE)
        ramdisk = file.read(ramdisk_size)
    return header, kernel, ramdisk


def footer_options(path):
    """Read the stock unsigned AVB hash settings and build properties."""
    with path.open("rb") as file:
        file.seek(-64, 2)
        footer = file.read(64)
        if footer[:4] != b"AVBf":
            raise ValueError("Missing AVB footer")
        offset, size = struct.unpack_from(">QQ", footer, 20)
        file.seek(offset)
        vbmeta = file.read(size)
    if vbmeta[:4] != b"AVB0" or struct.unpack_from(">I", vbmeta, 28)[0] != 0:
        raise ValueError("Expected an unsigned boot hash footer")
    if struct.unpack_from(">QII", vbmeta, 112) != (0, 0, 0):
        raise ValueError("Unexpected rollback index, flags or rollback location")
    auth_size = struct.unpack_from(">Q", vbmeta, 12)[0]
    desc_offset, desc_size = struct.unpack_from(">QQ", vbmeta, 96)
    cursor = 256 + auth_size + desc_offset
    end = cursor + desc_size
    options = ["--partition_size", str(path.stat().st_size), "--algorithm", "NONE"]
    while cursor < end:
        tag, size = struct.unpack_from(">QQ", vbmeta, cursor)
        desc = vbmeta[cursor + 16:cursor + 16 + size]
        if tag == 2:
            alg = desc[8:40].split(b"\0", 1)[0].decode()
            name_len, salt_len, _, flags = struct.unpack_from(">4I", desc, 40)
            name = desc[116:116 + name_len].decode()
            salt_start = 116 + name_len
            if (name, alg, flags) != ("boot", "sha256", 0):
                raise ValueError("Unexpected boot hash descriptor")
            options += ["--partition_name", name, "--hash_algorithm", alg,
                        "--salt", desc[salt_start:salt_start + salt_len].hex()]
        elif tag == 0:
            key_len, value_len = struct.unpack_from(">QQ", desc)
            key = desc[16:16 + key_len].decode()
            value = desc[17 + key_len:17 + key_len + value_len].decode()
            options += ["--prop", key + ":" + value]
        else:
            raise ValueError(f"Unexpected AVB descriptor {tag}")
        cursor += 16 + size
    return options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", required=True, type=Path, help="images/miboot.img from ZhuiMeng 24.7.28")
    parser.add_argument("--kernel-zip", required=True, type=Path, help="AnyKernel3 artifact from the device workflow")
    parser.add_argument("--mkbootimg", required=True, type=Path, help="AOSP mkbootimg.py")
    parser.add_argument("--avbtool", required=True, type=Path, help="AOSP avbtool.py")
    parser.add_argument("--output", required=True, type=Path, help="new boot image path")
    args = parser.parse_args()
    if sha256(args.stock) != STOCK_SHA256:
        parser.error("Stock input must be the clean mondrian ZhuiMeng 24.7.28 miboot.img")
    if args.output.exists():
        parser.error("Choose a new output path")
    stock_header, _, ramdisk = boot_sections(args.stock)
    with zipfile.ZipFile(args.kernel_zip) as artifact:
        kernels = [name for name in artifact.namelist() if Path(name).name == "Image"]
        if len(kernels) != 1:
            parser.error("Expected one uncompressed Image in the kernel artifact")
        kernel = artifact.read(kernels[0])
    if kernel[56:60] != b"ARM\x64" or b"Linux version 5.10.198-android12" not in kernel:
        parser.error("Unexpected kernel architecture or release family")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as tmp:
        folder = Path(tmp).resolve()
        kernel_file, ramdisk_file, boot = folder / "Image", folder / "ramdisk", folder / "boot.img"
        kernel_file.write_bytes(kernel)
        ramdisk_file.write_bytes(ramdisk)
        # The v4 header of this specific ROM carries Android 12 / November 2023.
        # The original GKI certificate covers different bytes after a kernel replacement.
        subprocess.run([sys.executable, str(args.mkbootimg), "--header_version", "4",
                        "--kernel", str(kernel_file), "--ramdisk", str(ramdisk_file),
                        "--os_version", "12.0.0", "--os_patch_level", "2023-11",
                        "--output", str(boot)], check=True)
        avb = [sys.executable, str(args.avbtool)]
        options = footer_options(args.stock)
        subprocess.run(avb + ["add_hash_footer", "--image", str(boot)] + options, check=True)
        subprocess.run(avb + ["verify_image", "--image", str(boot)], check=True)
        header, packed_kernel, packed_ramdisk = boot_sections(boot)
        if packed_kernel != kernel or packed_ramdisk != ramdisk or header[12:1580] != stock_header[12:1580]:
            raise ValueError("Repacked boot header or payload differs from the selected inputs")
        if struct.unpack_from("<I", header, 1580)[0] != 0 or footer_options(boot) != options:
            raise ValueError("Repacked boot signatures or footer settings are inconsistent")
        print(f"{sha256(boot)}  {args.output.name}")
        boot.replace(args.output)


if __name__ == "__main__":
    main()
