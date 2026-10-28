# Xiaomi Redmi 12 5G / POCO M6 Pro 5G (`sky` / SM4450) Linux 6.12 GKI Kernel Builder

Automated CI/CD build system and comprehensive documentation for compiling **Linux 6.12 GKI LTS** (Google ACK `android16-6.12.52`) for Qualcomm Snapdragon 4 Gen 2 (SM4450 / `sky` / `parrot` / `ravelin`).

---

## 📱 Supported Devices
| Device Name | Codename | Platform | SoC |
| :--- | :--- | :--- | :--- |
| **Redmi 12 5G** | `sky` | Ravelin / Parrot | Qualcomm SM4450 (Snapdragon 4 Gen 2) |
| **POCO M6 Pro 5G** | `sky` | Ravelin / Parrot | Qualcomm SM4450 (Snapdragon 4 Gen 2) |
| **Redmi Note 12R** | `sky` | Ravelin / Parrot | Qualcomm SM4450 (Snapdragon 4 Gen 2) |

---

## 🗂️ Repositories & Branches

All sources are maintained and synchronized under [`@AltafYafai`](https://github.com/AltafYafai):

* **Kernel Source:** [`AltafYafai/android_kernel_xiaomi_sm4450-6.12`](https://github.com/AltafYafai/android_kernel_xiaomi_sm4450-6.12)  
  * **Branch:** `lineage-24.0-6.12`
  * **Base:** Google Android Common Kernel `android16-6.12.52` LTS
* **Devicetrees Source:** [`AltafYafai/android_kernel_xiaomi_sm4450-devicetrees-6.12`](https://github.com/AltafYafai/android_kernel_xiaomi_sm4450-devicetrees-6.12)  
  * **Branch:** `lineage-24.0-6.12`
  * **Base:** Qualcomm SM4450 Ravelin / Xiaomi BSP device trees
* **Modules Source:** [`AltafYafai/android_kernel_xiaomi_sm4450-modules-6.12`](https://github.com/AltafYafai/android_kernel_xiaomi_sm4450-modules-6.12)  
  * **Branch:** `lineage-24.0-6.12`
  * **Base:** Xiaomi Touch, Fingerprint, Misc, Display, Audio, WLAN drivers
* **CI/CD Builder:** [`AltafYafai/kernel_xiaomi_sky_builder`](https://github.com/AltafYafai/kernel_xiaomi_sky_builder)  
  * **Branch:** `main`

---

## 🛠️ Key Porting Fixes & Reconciliations

### 1. Frame Warning Threshold Expansion
- **Symptom:** Clang 18 stack analysis threw frame size warnings (`-Wframe-larger-than=2048`) in `crypto/ecc.c` and `kernel/bpf/verifier.c`.
- **Fix:** Configured `CONFIG_FRAME_WARN=4096` in `arch/arm64/configs/vendor/sky_GKI.config` and `parrot_perf.config`.

### 2. Devicetree Subtree Isolation
- **Symptom:** Generic ACK 6.12 attempted to compile 30+ non-Qualcomm architectures (Allwinner, Apple, NVIDIA, Rockchip), causing build failures on irrelevant trees.
- **Fix:** Configured `arch/arm64/boot/dts/Makefile` to unconditionally target `subdir-y += vendor`, and set `vendor/Makefile` to build `subdir-y += qcom`.

### 3. Qualcomm DTBO Suffix Pattern Support
- **Symptom:** Upstream Linux 6.12 expects `.dtso` for overlay targets, whereas downstream Qualcomm BSP names overlay targets `.dts` (e.g. `ravelin-audio-xiaomi-sky.dts`).
- **Fix:** Added `$(obj)/%.dtbo: $(src)/%.dts $(DTC) FORCE` to `scripts/Makefile.dtbs`.

### 4. Clock Header Definitions (`qcom,sm4450-gpucc.h` & `qcom,sm4450-gcc.h`)
- **Symptom:** `msm-arm-smmu-ravelin.dtsi:33: syntax error` due to missing `GPU_CC_HLOS1_VOTE_GPU_SMMU_CLK 34` and `GPUCC_GPU_CC_FREQUENCY_LIMITER_IRQ_CLEAR 11`.
- **Fix:** Synced clock headers with the reference SM4450 BSP.

### 5. Thermal & Audio Bindings
- **Symptom:** Missing `dt-bindings/thermal/thermal_qti.h` and `<bindings/qcom,audio-ext-clk.h>`.
- **Fix:** Imported missing header files into both `devicetrees/bindings/` and `kernel/include/bindings/`.

### 6. RPMh RSC Fast-Path Constant (`FAST_PATH_TCS`)
- **Symptom:** `ravelin.dtsi:540` failed with `Error: syntax error` on `<FAST_PATH_TCS 0>`.
- **Fix:** Added `#define FAST_PATH_TCS 4` to `include/dt-bindings/soc/qcom,rpmh-rsc.h`.

### 7. SoC Hardware Identifier & Power Domain Sync
- **Symptom:** Missing chipset platform identifiers and voltage performance levels in DTS parsing.
- **Fix:** Added `QCOM_ID_RAVELIN` (568), `QCOM_ID_RAVELINP` (602), `QCOM_ID_PARROT` (537), `QCOM_ID_PARROTP` (583), `QCOM_ID_SG_RAVELIN` (653) to `include/dt-bindings/arm/qcom,ids.h` and added `RPMH_REGULATOR_LEVEL_*` definitions to `include/dt-bindings/power/qcom,rpmhpd.h`.

---

## 🎯 Verified Devicetree Targets
The following devicetree targets are verified to compile cleanly with zero errors:
* `ravelin-sky-base.dtb` (Standard RAM Base DTB)
* `ravelin-sky-4gb-base.dtb` (4GB RAM Variant Base DTB)
* `ravelin-sky-overlay.dtbo` (Xiaomi Board Hardware Overlay)
* `ravelin-sky-4gb-overlay.dtbo` (4GB Board Hardware Overlay)
* `ravelin-audio-xiaomi-sky.dtbo` (Audio Routing & Codec Overlay)
* `ravelin-camera-sensor-sky.dtbo` (Camera Sensors Overlay)
* `ravelin-sde-display-sky-overlay.dtbo` (Snapdragon Display Engine Overlay)

---

## ⚡ How to Trigger CI/CD Build

1. Navigate to **Actions** in [`kernel_xiaomi_sky_builder`](https://github.com/AltafYafai/kernel_xiaomi_sky_builder/actions).
2. Select **Build Xiaomi Sky Kernel 6.12 (lineage-24.0-6.12)**.
3. Click **Run workflow** (accept default branches: `lineage-24.0-6.12`).
4. Real-time build progress and flashable ZIP delivery will be sent to the configured Telegram chat.

### GitHub Secrets Required
* `GH_TOKEN`: GitHub Personal Access Token (for cloning private/public org repos).
* `TELEGRAM_BOT_TOKEN`: Telegram Bot Token for notification delivery.
* `TELEGRAM_CHAT_ID`: Telegram Chat ID for real-time progress messages.

---

## 📦 Flashing Guide

1. Download the generated `sky-kernel-6.12-<commit>.zip` artifact.
2. Boot device into custom recovery (TWRP, OrangeFox, or Lineage Recovery).
3. (Optional but recommended) Perform a backup of your existing `boot` and `dtbo` partitions.
4. Select **Install** -> Choose `sky-kernel-6.12-<commit>.zip` -> **Swipe to Flash**.
5. Reboot system.

### 🛡️ Safety & A/B Rollback Protection
* Qualcomm SM4450 devices utilize dual-slot A/B partitioning (`boot_a`, `boot_b`, `dtbo_a`, `dtbo_b`).
* AnyKernel3 modifies only the active boot slot without touching bootloader partitions (`xbl`, `abl`, `tz`).
* If a boot issue occurs, Qualcomm watchdog hardware automatically rolls back to the previous boot slot after 7 failed attempts.
