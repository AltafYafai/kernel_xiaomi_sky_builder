#!/usr/bin/env python3
"""
patch_ramdisk.py: Clean, update, and harmonize kernel modules in Android vendor ramdisk.

1. Injects newly compiled Linux 6.12 kernel modules.
2. Creates platform compatibility aliases (sm4450 <-> parrot <-> ravelin).
3. Purges all stale non-6.12 modules (preventing vermagic panic / crash).
4. Generates clean modules.dep, modules.load (topologically sorted), and modules.alias.
"""

import sys
import os
import glob
import subprocess
import shutil

def parse_modinfo(data):
    info = {'depends': [], 'aliases': [], 'vermagic': None}
    
    # Extract vermagic
    v_idx = data.find(b'vermagic=')
    if v_idx != -1:
        info['vermagic'] = data[v_idx+9:].split(b'\x00')[0].decode('latin1', errors='ignore')
        
    # Extract depends
    d_idx = data.find(b'depends=')
    if d_idx != -1:
        d_str = data[d_idx+8:].split(b'\x00')[0].decode('latin1', errors='ignore')
        if d_str:
            info['depends'] = [d.strip() for d in d_str.split(',') if d.strip()]
            
    # Extract aliases
    idx = 0
    while True:
        a_idx = data.find(b'alias=', idx)
        if a_idx == -1:
            break
        a_str = data[a_idx+6:].split(b'\x00')[0].decode('latin1', errors='ignore')
        if a_str:
            info['aliases'].append(a_str)
        idx = a_idx + 6
        
    return info

def main():
    if len(sys.argv) < 3:
        print("Usage: patch_ramdisk.py <ramdisk_work_dir> <modules_dir> [target_kernel_prefix]")
        sys.exit(1)
        
    rd_dir = os.path.abspath(sys.argv[1])
    modules_src = os.path.abspath(sys.argv[2])
    target_kver = sys.argv[3] if len(sys.argv) > 3 else "6.12."
    
    mods_dst = os.path.join(rd_dir, "lib", "modules")
    os.makedirs(mods_dst, exist_ok=True)
    strip_bin = shutil.which("llvm-strip") or shutil.which("strip")
    
    print(f"[*] Patching vendor ramdisk at: {rd_dir}")
    print(f"[*] Source modules directory: {modules_src}")
    print(f"[*] Target kernel version prefix: {target_kver}")
    
    # 1. Copy all newly compiled modules into destination
    count_injected = 0
    for root, _, files in os.walk(modules_src):
        for f in files:
            if f.endswith(".ko"):
                src_path = os.path.join(root, f)
                dst_path = os.path.join(mods_dst, f)
                
                # Copy file
                with open(src_path, 'rb') as s_fp:
                    data = s_fp.read()
                with open(dst_path, 'wb') as d_fp:
                    d_fp.write(data)
                    
                # Strip debug symbols if tool is available
                if strip_bin:
                    subprocess.run([strip_bin, "--strip-debug", dst_path],
                                   stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                count_injected += 1
                
    print(f"[+] Injected {count_injected} modules from {modules_src}")
    
    # 2. Setup compatibility aliases for SM4450 / Parrot / Ravelin hardware
    aliases_map = {
        "pinctrl-sm4450.ko": ["pinctrl-parrot.ko", "pinctrl-ravelin.ko"],
        "gcc-sm4450.ko": ["gcc-parrot.ko"],
        "dispcc-sm4450.ko": ["dispcc-parrot.ko"],
        "camcc-sm4450.ko": ["camcc-parrot.ko"],
        "gpucc-sm4450.ko": ["gpucc-parrot.ko"],
    }
    for src_name, alias_list in aliases_map.items():
        src_file = os.path.join(mods_dst, src_name)
        if os.path.isfile(src_file):
            for alias_name in alias_list:
                alias_file = os.path.join(mods_dst, alias_name)
                with open(src_file, 'rb') as s_fp:
                    with open(alias_file, 'wb') as d_fp:
                        d_fp.write(s_fp.read())
                print(f"[+] Created compatibility alias: {alias_name} -> {src_name}")
                
    # 3. Scan all modules in lib/modules, purge stale non-matching modules
    modules = {}
    purged_count = 0
    for f in glob.glob(os.path.join(mods_dst, "*.ko")):
        fname = os.path.basename(f)
        mname = fname[:-3]
        
        with open(f, 'rb') as fp:
            data = fp.read()
            
        info = parse_modinfo(data)
        vm = info.get('vermagic')
        
        if not vm or not vm.startswith(target_kver):
            # Stale module from prior kernel! Purge it!
            os.remove(f)
            purged_count += 1
            continue
            
        modules[mname] = {
            'file': fname,
            'depends': [d.replace('_', '-') for d in info['depends']],
            'aliases': info['aliases'],
            'vermagic': vm
        }
        
    print(f"[+] Purged {purged_count} stale modules; retained {len(modules)} matching {target_kver}* modules.")
    
    # 4. Generate clean modules.dep
    dep_file = os.path.join(mods_dst, "modules.dep")
    with open(dep_file, 'w') as fp:
        for mname in sorted(modules.keys()):
            fname = modules[mname]['file']
            # Find dependencies that exist in our modules
            dep_paths = []
            for dep in modules[mname]['depends']:
                # Dep can be with '-' or '_'
                dep_alt = dep.replace('-', '_')
                dep_k = dep if dep in modules else (dep_alt if dep_alt in modules else None)
                if dep_k:
                    dep_paths.append(f"/lib/modules/{modules[dep_k]['file']}")
            fp.write(f"/lib/modules/{fname}: {' '.join(dep_paths)}\n")
    print(f"[+] Generated {dep_file}")
    
    # 5. Generate clean modules.alias
    alias_file = os.path.join(mods_dst, "modules.alias")
    with open(alias_file, 'w') as fp:
        for mname in sorted(modules.keys()):
            norm_name = mname.replace('-', '_')
            for a in modules[mname]['aliases']:
                fp.write(f"alias {a} {norm_name}\n")
    print(f"[+] Generated {alias_file}")
    
    # 6. Generate topologically sorted modules.load
    # Load critical hardware and storage modules first
    load_file = os.path.join(mods_dst, "modules.load")
    
    # Preserve original load order priorities if they were in modules.load
    orig_order = []
    if os.path.isfile(load_file):
        with open(load_file, 'r') as fp:
            for line in fp:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Strip .ko if present
                    if line.endswith('.ko'):
                        line = line[:-3]
                    orig_order.append(line)
                    
    # Priority hardware drivers for early mount
    priority_drivers = [
        "clk-qcom", "clk-rpmh", "gcc-sm4450", "gcc-parrot",
        "dispcc-sm4450", "dispcc-parrot", "camcc-sm4450", "camcc-parrot",
        "gpucc-sm4450", "gpucc-parrot",
        "pinctrl-msm", "pinctrl-sm4450", "pinctrl-parrot", "pinctrl-ravelin", "pinctrl-spmi-gpio",
        "qcom-scm", "qcom-ipcc", "qcom-pdc", "qcom_aoss", "qcom_rpmh", "cmd-db", "smem", "socinfo",
        "spmi-pmic-arb", "qcom-spmi-pmic", "rtc-pm8xxx",
        "arm_smmu", "cqhci", "sdhci-msm", "ufs-qcom",
        "zsmalloc", "zram", "qcom_hwspinlock", "qcom-tsens",
        "reboot-mode", "qcom-pon", "pm8941-pwrkey", "qrtr", "qrtr-smd"
    ]
    
    # Build candidate list
    candidate_set = set()
    for m in orig_order:
        if m in modules:
            candidate_set.add(m)
    for m in priority_drivers:
        if m in modules:
            candidate_set.add(m)
            
    # Add any module that was in modules directory
    for m in modules:
        candidate_set.add(m)
        
    # Topological sort
    visited = set()
    sorted_load = []
    
    def visit(m):
        if m not in visited and m in modules:
            visited.add(m)
            for dep in modules[m]['depends']:
                dep_alt = dep.replace('-', '_')
                dep_k = dep if dep in modules else (dep_alt if dep_alt in modules else None)
                if dep_k:
                    visit(dep_k)
            sorted_load.append(m)
            
    # Visit priority drivers first
    for m in priority_drivers:
        if m in candidate_set:
            visit(m)
    for m in orig_order:
        if m in candidate_set:
            visit(m)
    for m in sorted(candidate_set):
        visit(m)
        
    with open(load_file, 'w') as fp:
        for m in sorted_load:
            fp.write(f"{m}\n")
            
    print(f"[+] Generated {load_file} with {len(sorted_load)} modules in topological order")

if __name__ == "__main__":
    main()
