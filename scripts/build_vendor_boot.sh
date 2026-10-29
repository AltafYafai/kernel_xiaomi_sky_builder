#!/usr/bin/env bash
set -e

DTB_DIR="$1"
OUTPUT_IMG="${2:-vendor_boot.img}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_VB="/tmp/base_vendor_boot.img"

if [ ! -f "$BASE_VB" ]; then
    echo "Downloading reference base vendor_boot.img..."
    curl -sL "https://github.com/AltafYafai/OrangeFox-Builder-Sky/releases/download/20261019-39267552832/vendor_boot.img" -o "$BASE_VB"
fi

echo "Unpacking base vendor_boot.img..."
rm -rf /tmp/vb_unpack
mkdir -p /tmp/vb_unpack
python3 "$SCRIPT_DIR/unpack_bootimg.py" --boot_img "$BASE_VB" --out /tmp/vb_unpack > /dev/null

echo "Collecting compiled Sky 6.12 DTBs..."
SKY_DTBS=$(find "$DTB_DIR" -name "*sky*base.dtb" 2>/dev/null | sort -r | tr '\n' ' ')
if [ -z "${SKY_DTBS// }" ]; then
    echo "Warning: No sky base dtb found in $DTB_DIR, keeping base dtb"
else
    cat $SKY_DTBS > /tmp/vb_unpack/dtb
    echo "Compiled DTB size: $(wc -c < /tmp/vb_unpack/dtb) bytes"
fi

echo "Repacking vendor_boot.img with 6.12 DTB..."
python3 "$SCRIPT_DIR/mkbootimg.py" \
  --header_version 4 \
  --pagesize 0x00001000 \
  --base 0x00000000 \
  --kernel_offset 0x10008000 \
  --ramdisk_offset 0x11000000 \
  --tags_offset 0x10000100 \
  --dtb_offset 0x0000000011f00000 \
  --vendor_cmdline "androidboot.selinux=permissive buildvariant=eng" \
  --board "" \
  --dtb /tmp/vb_unpack/dtb \
  --vendor_bootconfig /tmp/vb_unpack/bootconfig \
  --ramdisk_type 1 \
  --ramdisk_name "" \
  --vendor_ramdisk_fragment /tmp/vb_unpack/vendor_ramdisk00 \
  --ramdisk_type 2 \
  --ramdisk_name recovery \
  --vendor_ramdisk_fragment /tmp/vb_unpack/vendor_ramdisk01 \
  --vendor_boot "$OUTPUT_IMG"

truncate -s 100663296 "$OUTPUT_IMG"
echo "vendor_boot.img generated successfully at $OUTPUT_IMG ($(ls -lh "$OUTPUT_IMG" | awk '{print $5}'))"
