#!/usr/bin/env bash
set -e

DTB_DIR="$1"
OUTPUT_IMG="${2:-vendor_boot.img}"
BASE_VB="${3:-/tmp/base_vendor_boot.img}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$BASE_VB" ]; then
    echo "Downloading reference base vendor_boot.img..."
    curl -sL "https://github.com/AltafYafai/OrangeFox-Builder-Sky/releases/download/20261019-39267552832/vendor_boot.img" -o "$BASE_VB"
fi

BASE_SIZE=$(stat -c%s "$BASE_VB" 2>/dev/null || wc -c < "$BASE_VB")

echo "Unpacking base vendor_boot.img ($BASE_VB, size: $BASE_SIZE bytes)..."
rm -rf /tmp/vb_unpack
mkdir -p /tmp/vb_unpack

python3 "$SCRIPT_DIR/unpack_bootimg.py" --boot_img "$BASE_VB" --out /tmp/vb_unpack --format mkbootimg > /tmp/mkbootimg_args

echo "mkbootimg base arguments:"
cat /tmp/mkbootimg_args
echo ""

echo "Collecting compiled Sky 6.12 DTBs from $DTB_DIR..."
SKY_DTBS=$(find "$DTB_DIR" -name "*sky*base.dtb" 2>/dev/null | sort -r | tr '\n' ' ')
if [ -z "${SKY_DTBS// }" ]; then
    echo "Warning: No sky base dtb found in $DTB_DIR, keeping base dtb"
else
    echo "Found DTBs: $SKY_DTBS"
    cat $SKY_DTBS > /tmp/vb_unpack/dtb
    echo "Compiled DTB size: $(wc -c < /tmp/vb_unpack/dtb) bytes"
fi

echo "Repacking vendor_boot.img with 6.12 DTB..."
MK_ARGS=$(cat /tmp/mkbootimg_args)
sh -c "python3 \"$SCRIPT_DIR/mkbootimg.py\" $MK_ARGS --vendor_boot \"$OUTPUT_IMG\""

# Match base image size
truncate -s "$BASE_SIZE" "$OUTPUT_IMG"
echo "vendor_boot.img generated successfully at $OUTPUT_IMG ($(ls -lh "$OUTPUT_IMG" | awk '{print $5}'))"

# Generate empty disabled vbmeta image (flags = 3: verification disabled)
VBMETA_OUT="$(dirname "$OUTPUT_IMG")/vbmeta_disabled.img"
echo "Generating vbmeta_disabled.img at $VBMETA_OUT..."
python3 -c "
import struct
buf = bytearray(4096)
buf[0:4] = b'AVB0'
struct.pack_into('>II', buf, 4, 1, 3)
struct.pack_into('>I', buf, 120, 3)
buf[128:128+len(b'avbtool 1.3.0')] = b'avbtool 1.3.0'
with open('$VBMETA_OUT', 'wb') as f:
    f.write(buf)
"
echo "vbmeta_disabled.img generated successfully ($(ls -lh "$VBMETA_OUT" | awk '{print $5}'))"
