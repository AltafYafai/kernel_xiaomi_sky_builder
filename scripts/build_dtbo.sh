#!/usr/bin/env bash
set -e

OUTPUT_IMG="${1:-artifacts/dtbo-6.12.img}"
DTBO_DIR="${2:-kernel/out/arch/arm64/boot/dts}"
BASE_DTBO="${3:-/home/altaf/6.12/dtbo.img}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$BASE_DTBO" ]; then
    BASE_DTBO="/tmp/base_dtbo.img"
    if [ ! -f "$BASE_DTBO" ]; then
        echo "Attempting to download LineageOS reference dtbo.img..."
        gh release download lineageos-24.0-reference -p "dtbo.img" -O "$BASE_DTBO" -R AltafYafai/kernel_xiaomi_sky_builder 2>/dev/null || true
    fi
fi

# Audit compiled DTBOs if DTBO_DIR exists
CAN_PACK_COMPILED=0
if [ -n "$DTBO_DIR" ] && [ -d "$DTBO_DIR" ]; then
    # Loose overlays (such as display or audio fragments) require their respective base DTBOs
    # (e.g. ravelin-sde.dtbo and ravelin-audio.dtbo). If only loose fragments are present,
    # libufdt will abort in ABL with unresolved phandles (causing instant 0.5s power off).
    # Check if compiled DTBOs form a complete, self-contained set:
    if find "$DTBO_DIR" -name "ravelin-sde.dtbo" 2>/dev/null | grep -q .; then
        CAN_PACK_COMPILED=1
    fi
fi

if [ "$CAN_PACK_COMPILED" -eq 1 ]; then
    echo "Compiled DTBOs contain full prerequisite base overlays. Packing compiled DTBOs..."
    SKY_DTBOS=$(find "$DTBO_DIR" -name "*sky*.dtbo" 2>/dev/null | sort -r | tr '\n' ' ')
    python3 "$SCRIPT_DIR/mkdtboimg.py" create "$OUTPUT_IMG" --page_size=4096 $SKY_DTBOS
else
    echo "Notice: Compiled DTBOs are loose fragments without base hardware definitions."
    echo "Using verified reference dtbo.img to ensure clean ABL overlay application without unresolved symbols."
    if [ -f "$BASE_DTBO" ]; then
        cp "$BASE_DTBO" "$OUTPUT_IMG"
    else
        echo "ERROR: Reference dtbo.img not found at $BASE_DTBO"
        exit 1
    fi
fi

echo "Verifying generated dtbo structure..."
python3 "$SCRIPT_DIR/mkdtboimg.py" dump "$OUTPUT_IMG"
echo "dtbo.img generated successfully at $OUTPUT_IMG ($(ls -lh "$OUTPUT_IMG" | awk '{print $5}'))"
