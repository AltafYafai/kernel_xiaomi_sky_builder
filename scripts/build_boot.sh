#!/usr/bin/env bash
set -e

KERNEL_IMAGE="$1"
OUTPUT_IMG="${2:-boot-6.12.img}"
BASE_BOOT="${3:-/home/altaf/6.12/boot.img}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$BASE_BOOT" ]; then
    BASE_BOOT="/tmp/base_boot.img"
    if [ ! -f "$BASE_BOOT" ]; then
        echo "Attempting to download LineageOS reference boot.img..."
        gh release download lineageos-24.0-reference -p "boot.img" -O "$BASE_BOOT" -R AltafYafai/kernel_xiaomi_sky_builder 2>/dev/null || true
    fi
fi

rm -rf /tmp/boot_unpack
mkdir -p /tmp/boot_unpack

RAMDISK_ARG=()
OS_VERSION="17.0.0"
OS_PATCH_LEVEL="2026-10"

if [ -f "$BASE_BOOT" ]; then
    echo "Unpacking base boot image: $BASE_BOOT..."
    python3 "$SCRIPT_DIR/unpack_bootimg.py" --boot_img "$BASE_BOOT" --out /tmp/boot_unpack > /tmp/boot_unpack/info.txt
    cat /tmp/boot_unpack/info.txt

    if [ -f /tmp/boot_unpack/ramdisk ] && [ -s /tmp/boot_unpack/ramdisk ]; then
        echo "Found base ramdisk ($(wc -c < /tmp/boot_unpack/ramdisk) bytes)"
        RAMDISK_ARG=(--ramdisk /tmp/boot_unpack/ramdisk)
    fi
    PARSED_VER=$(grep "os version:" /tmp/boot_unpack/info.txt | awk '{print $NF}')
    PARSED_LVL=$(grep "os patch level:" /tmp/boot_unpack/info.txt | awk '{print $NF}')
    [ -n "$PARSED_VER" ] && OS_VERSION="$PARSED_VER"
    [ -n "$PARSED_LVL" ] && OS_PATCH_LEVEL="$PARSED_LVL"
fi

echo "Repacking boot.img (Header v4, kernel: $KERNEL_IMAGE)..."
python3 "$SCRIPT_DIR/mkbootimg.py" \
  --header_version 4 \
  --kernel "$KERNEL_IMAGE" \
  "${RAMDISK_ARG[@]}" \
  --os_version "$OS_VERSION" \
  --os_patch_level "$OS_PATCH_LEVEL" \
  --output "$OUTPUT_IMG"

truncate -s 100663296 "$OUTPUT_IMG"
echo "boot.img generated successfully at $OUTPUT_IMG ($(ls -lh "$OUTPUT_IMG" | awk '{print $5}'))"
