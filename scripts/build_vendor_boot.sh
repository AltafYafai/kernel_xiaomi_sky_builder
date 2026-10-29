#!/usr/bin/env bash
set -e

DTB_DIR="$1"
MODULES_DIR="$2"
OUTPUT_IMG="${3:-vendor_boot.img}"
BASE_VB="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve base vendor_boot.img
if [ -z "$BASE_VB" ] || [ ! -f "$BASE_VB" ]; then
    if [ -f "/home/altaf/6.12/vendor_boot.img" ]; then
        BASE_VB="/home/altaf/6.12/vendor_boot.img"
    elif [ -f "/tmp/base_vendor_boot.img" ]; then
        BASE_VB="/tmp/base_vendor_boot.img"
    else
        BASE_VB="/tmp/base_vendor_boot.img"
        echo "Attempting to download LineageOS reference vendor_boot.img..."
        gh release download lineageos-24.0-reference -p "vendor_boot.img" -O "$BASE_VB" -R AltafYafai/kernel_xiaomi_sky_builder 2>/dev/null || \
        curl -sL "https://github.com/AltafYafai/OrangeFox-Builder-Sky/releases/download/20261019-39267552832/vendor_boot.img" -o "$BASE_VB"
    fi
fi

echo "Using base vendor_boot: $BASE_VB"
rm -rf /tmp/vb_unpack /tmp/rd00_work
mkdir -p /tmp/vb_unpack

# Unpack base vendor_boot
python3 "$SCRIPT_DIR/unpack_bootimg.py" --boot_img "$BASE_VB" --out /tmp/vb_unpack > /tmp/vb_unpack/info.txt
cat /tmp/vb_unpack/info.txt

# Extract base parameters
KERNEL_ADDR=$(grep "kernel load address:" /tmp/vb_unpack/info.txt | awk '{print $NF}')
RAMDISK_ADDR=$(grep "ramdisk load address:" /tmp/vb_unpack/info.txt | awk '{print $NF}')
TAGS_ADDR=$(grep "kernel tags load address:" /tmp/vb_unpack/info.txt | awk '{print $NF}')
DTB_ADDR=$(grep "dtb address:" /tmp/vb_unpack/info.txt | awk '{print $NF}')
PAGE_SIZE=$(grep "page size:" /tmp/vb_unpack/info.txt | awk '{print $NF}')
CMDLINE=$(grep "vendor command line args:" /tmp/vb_unpack/info.txt | sed 's/vendor command line args: //')

echo "Base parameters parsed:"
echo "  KERNEL_ADDR:  $KERNEL_ADDR"
echo "  RAMDISK_ADDR: $RAMDISK_ADDR"
echo "  TAGS_ADDR:    $TAGS_ADDR"
echo "  DTB_ADDR:     $DTB_ADDR"
echo "  PAGE_SIZE:    $PAGE_SIZE"
echo "  CMDLINE:      $CMDLINE"

# Process DTB
echo "Processing DTB..."
if [ -n "$DTB_DIR" ] && [ -d "$DTB_DIR" ]; then
    SKY_DTBS=$(find "$DTB_DIR" -name "*sky*base.dtb" 2>/dev/null | sort -r | tr '\n' ' ')
    if [ -z "${SKY_DTBS// }" ]; then
        SKY_DTBS=$(find "$DTB_DIR" -name "*sky*.dtb" ! -name "*.dtbo" 2>/dev/null | sort -r | tr '\n' ' ')
    fi
    if [ -z "${SKY_DTBS// }" ]; then
        echo "Warning: No sky base dtb found in $DTB_DIR, keeping base dtb"
    else
        cat $SKY_DTBS > /tmp/vb_unpack/dtb
        echo "Compiled DTB size: $(wc -c < /tmp/vb_unpack/dtb) bytes"
    fi
else
    echo "Keeping base DTB"
fi

# Extract and patch vendor_ramdisk00
echo "Extracting vendor ramdisk 0 (Fragment 0)..."
python3 "$SCRIPT_DIR/lz4cpio.py" extract /tmp/vb_unpack/vendor_ramdisk00 /tmp/rd00_work

if [ -n "$MODULES_DIR" ] && [ -d "$MODULES_DIR" ]; then
    echo "Running patch_ramdisk.py to harmonize 6.12 modules, purge stale 6.6 modules, and regenerate dep/load..."
    python3 "$SCRIPT_DIR/patch_ramdisk.py" /tmp/rd00_work "$MODULES_DIR" "6.12."

    echo "Repacking updated vendor ramdisk 0..."
    python3 "$SCRIPT_DIR/lz4cpio.py" pack /tmp/rd00_work /tmp/vb_unpack/ramdisk00_updated.cpio
    lz4 -f -l -12 /tmp/vb_unpack/ramdisk00_updated.cpio /tmp/vb_unpack/vendor_ramdisk00
fi

# Build arguments for mkbootimg.py
MKBOOT_ARGS=(
    --header_version 4
    --pagesize "${PAGE_SIZE:-0x00001000}"
    --base 0x00000000
    --kernel_offset "${KERNEL_ADDR:-0x00008000}"
    --ramdisk_offset "${RAMDISK_ADDR:-0x01000000}"
    --tags_offset "${TAGS_ADDR:-0x00000100}"
    --dtb_offset "${DTB_ADDR:-0x0000000001f00000}"
    --vendor_cmdline "$CMDLINE"
    --board ""
    --dtb /tmp/vb_unpack/dtb
    --ramdisk_type 1
    --ramdisk_name ""
    --vendor_ramdisk_fragment /tmp/vb_unpack/vendor_ramdisk00
    --vendor_boot "$OUTPUT_IMG"
)

if [ -s /tmp/vb_unpack/bootconfig ]; then
    if ! grep -q "androidboot.selinux=permissive" /tmp/vb_unpack/bootconfig; then
        echo "androidboot.selinux=permissive" >> /tmp/vb_unpack/bootconfig
    fi
    MKBOOT_ARGS+=(--vendor_bootconfig /tmp/vb_unpack/bootconfig)
fi

# If Fragment 1 exists (e.g. OrangeFox recovery ramdisk), preserve it!
if [ -f /tmp/vb_unpack/vendor_ramdisk01 ]; then
    echo "Preserving secondary ramdisk fragment (recovery)..."
    MKBOOT_ARGS+=(
        --ramdisk_type 2
        --ramdisk_name recovery
        --vendor_ramdisk_fragment /tmp/vb_unpack/vendor_ramdisk01
    )
fi

echo "Repacking vendor_boot.img with mkbootimg.py..."
python3 "$SCRIPT_DIR/mkbootimg.py" "${MKBOOT_ARGS[@]}"

truncate -s 100663296 "$OUTPUT_IMG"
echo "vendor_boot.img generated successfully at $OUTPUT_IMG ($(ls -lh "$OUTPUT_IMG" | awk '{print $5}'))"

echo "Verifying generated vendor_boot structure..."
python3 "$SCRIPT_DIR/vbparse.py" "$OUTPUT_IMG"
