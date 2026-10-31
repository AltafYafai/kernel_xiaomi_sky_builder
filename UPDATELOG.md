# Project Update Log: Xiaomi SM4450 (Sky) Linux 6.12 Kernel Bringup

**Target Device:** Xiaomi Redmi 12 5G / POCO M6 Pro 5G / Redmi Note 12R (Codename: `sky`)  
**SoC Platform:** Qualcomm Snapdragon 4 Gen 2 (SM4450 / "Ravelin" / "Parrot" architecture)  
**Target Kernel:** Linux 6.12 LTS (Android 16 GKI / ACK `android16-6.12`)  
**ROM Base:** LineageOS (`lineage-24.0`) / HyperOS 2.0 (Android 15 Vendor Base, API 35)  
**Lead Developer:** Altaf Yafai ([@AltafYafai](https://github.com/AltafYafai))  

---

## 📋 Table of Contents
1. [Milestones & Overall Progress](#milestones--overall-progress)
2. [Chronological Step-by-Step Log](#chronological-step-by-step-log)
3. [Architecture Decisions & Rationale](#architecture-decisions--rationale)
4. [GitHub Infrastructure & Repositories](#github-infrastructure--repositories)
5. [CI/CD Build Runs & Troubleshooting Log](#cicd-build-runs--troubleshooting-log)
6. [Known Subsystem API Breakers (6.6 ➔ 6.12)](#known-subsystem-api-breakers-66--612)

---

## 1. Milestones & Overall Progress

| Milestone | Target | Status | Notes |
| :--- | :--- | :---: | :--- |
| **M1: Source Audit & Architecture** | Audit `xiaomi-ravelin` & Qualcomm trees | ✅ **Completed** | Discovered Qualcomm 6.12 dropped Parrot; chose ACK 6.12 rebase |
| **M2: Infrastructure Setup** | Create private 6.12 repos & branches | ✅ **Completed** | Devicetrees & Modules pushed with full history |
| **M3: CI/CD Build Pipeline** | GitHub Actions Clang 18 LLVM=1 | 🟡 **In Progress** | Run 1 identified shallow push fix; DTB build next |
| **M4: Core Image & DTB Compilation** | `Image` + `ravelin-sky-*.dtb` / `dtbo` | ⏳ Pending | Next target in CI |
| **M5: Out-of-Tree Modules Porting** | Xiaomi Touch, Display DRM, Audio | ⏳ Pending | Patching 6.12 DRM & thermal breaks |
| **M6: Boot Image Packaging** | AnyKernel3 & Fastboot Bundle | ⏳ Pending | Pipeline scripts ready in builder |
| **M7: Hardware Bringup & Boot Verification** | Test boot on device | ⏳ Pending | Validation with ramoops / pstore |

---

## 2. Chronological Step-by-Step Log

### Phase 1: Exploration & Technical Audit
* **Step 1.1**: Analyzed upstream organization [`xiaomi-ravelin`](https://github.com/xiaomi-ravelin) maintained by Venkat Yadlapati (`Venkat3620`).
  * Cataloged 5 core repositories:
    1. `android_device_xiaomi_sky`: Device makefiles, overlays, board IDs.
    2. `android_device_xiaomi_sm4450-common`: SoC common tree, VAB, audio HAL, init.
    3. `android_kernel_xiaomi_sm4450`: Core Linux 6.6.127 kernel tree.
    4. `android_kernel_xiaomi_sm4450-devicetrees`: Devicetrees for `sky`, `breeze`, `mist`.
    5. `android_kernel_xiaomi_sm4450-modules`: DLKM modules (`xiaomi/` touch/fingerprint, `qcom/` display/audio/camera/wlan).
* **Step 1.2**: Inspected current local workspace `/home/altafyafai/6.12` and detected Google ACK `android16-6.12` checkout.
* **Step 1.3**: Evaluated Qualcomm CLO 6.12 reference tree (`kernel.lnx.6.12.r1-rel` / `i-am-wolfi/android_kernel_qcom_sm8450-6.12`).
  * **Critical Discovery**: Qualcomm 6.12 CLO only ported `sun`, `canoe`, `shikra`, `waipio`, `hamoa`, and `lahaina`. **`parrot` (SM6450/SM4450) was completely absent.**
  * **Decision**: Adopt Path A (rebase working SM4450 6.6 tree onto ACK 6.12) to retain all working SoC power, clock, and Xiaomi charging hooks.

### Phase 2: Private Repository Creation & Seeding
* **Step 2.1**: User confirmed Option 1: Create dedicated private repositories under `AltafYafai` with branch `lineage-24.0-6.12`.
* **Step 2.2**: Created private repositories via `gh repo create`:
  * `AltafYafai/android_kernel_xiaomi_sm4450-6.12` (Private)
  * `AltafYafai/android_kernel_xiaomi_sm4450-devicetrees-6.12` (Private)
  * `AltafYafai/android_kernel_xiaomi_sm4450-modules-6.12` (Private)
* **Step 2.3**: Cloned and pushed full branch history for Devicetrees:
  * Pushed `AltafYafai/android_kernel_xiaomi_sm4450-devicetrees:lineage-24.0` ➔ `android_kernel_xiaomi_sm4450-devicetrees-6.12:lineage-24.0-6.12` (Verified ✅).
* **Step 2.4**: Cloned and pushed full branch history for Modules:
  * Pushed `AltafYafai/android_kernel_xiaomi_sm4450-modules:lineage-24.0` ➔ `android_kernel_xiaomi_sm4450-modules-6.12:lineage-24.0-6.12` (Verified ✅).
* **Step 2.5**: Extracted `sky_GKI.config` from `AltafYafai/kernel_xiaomi_sky` and placed into `arch/arm64/configs/vendor/sky_GKI.config`.

### Phase 3: CI/CD Pipeline Configuration
* **Step 3.1**: Discovered `AltafYafai/kernel_xiaomi_sky_builder` already had a dedicated `build-kernel-6.12.yml` workflow.
* **Step 3.2**: Optimized workflow to handle uninitialized 6.12 kernel repo automatically by pulling Google ACK `android16-6.12` in the runner cloud.
* **Step 3.3**: Dispatched Run 1 (`41218758838`).

---

## 3. CI/CD Build Runs & Troubleshooting Log

### Run 1 (`41218758838`)
* **Triggered:** 2026-10-31 21:45 UTC
* **Result:** ❌ Failed at step `Clone 6.12 Kernel, Devicetrees & Modules (30%)`
* **Error Log:**
  ```text
  Pushing seeded lineage-24.0-6.12 branch to AltafYafai/android_kernel_xiaomi_sm4450-6.12...
  remote: fatal: did not receive expected object f0f982d193227d13e5a1c9e6bc6c8c6f7e689503
  error: remote unpack failed: index-pack failed
  ! [remote rejected] lineage-24.0-6.12 -> lineage-24.0-6.12 (failed)
  error: failed to push some refs to 'https://github.com/AltafYafai/android_kernel_xiaomi_sm4450-6.12.git'
  ```
* **Root Cause Analysis:**
  * When cloning with `--depth=1` inside GitHub Actions, git creates a shallow commit graph.
  * Pushing a shallow commit graph into an empty remote GitHub repository causes GitHub's server-side `index-pack` to reject the push because of missing root commit connectivity.
* **Fix Action:**
  * In `build-kernel-6.12.yml`, simply checkout ACK `android16-6.12` and build directly without performing a shallow push inside the CI job. Once the kernel compiles cleanly, the tree is seeded with proper full commit history.

---

## 4. Known Subsystem API Breakers (6.6 ➔ 6.12)
These items will be patched during module compilation:

1. **DRM / MSM Display Drivers:**
   * Linux 6.8+ refactored atomic plane helpers (`drm_atomic_helper_check_plane_state`).
   * Linux 6.10+ updated connector initialization and GEM object allocators.
2. **Thermal Subsystem:**
   * `thermal_zone_device_register()` signature changed in 6.8+ (trip point handling migrated to core structures).
3. **Memory Management (MM):**
   * Direct assignment to `vma->vm_flags` replaced by `vm_flags_set()` / `vm_flags_clear()`.
   * Removal of `follow_pfn()`.
4. **Power Supply:**
   * Porting Xiaomi battery input suspend and SDP 450mA charging limits into `qti_battery_charger`.

---

*(Log maintained continuously across every build and bringup step)*
