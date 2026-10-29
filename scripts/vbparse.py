#!/usr/bin/env python3
"""Parse (and extract) a vendor_boot.img (header v3/v4) for verification.

Layout (header v4): header | vendor_ramdisk | dtb | ramdisk table | bootconfig
All sections are page aligned. vendor_boot images never carry a kernel.
"""
import struct, sys, os


def align(x, a):
    return (x + a - 1) & ~(a - 1)


def parse(path, extract_dir=None):
    data = open(path, 'rb').read()
    magic = data[:8]
    assert magic == b'VNDRBOOT', f'bad magic {magic!r}'
    hdr_ver, page_size, kaddr, raddr, vramdisk_size = struct.unpack('<5I', data[8:28])
    cmdline = data[28:28 + 2048].split(b'\0')[0].decode(errors='replace')
    tags_addr = struct.unpack('<I', data[28 + 2048:28 + 2052])[0]
    name = data[28 + 2052:28 + 2052 + 16].split(b'\0')[0].decode(errors='replace')
    header_size = struct.unpack('<I', data[2096:2100])[0]
    dtb_size = struct.unpack('<I', data[2100:2104])[0]
    dtb_addr = struct.unpack('<Q', data[2104:2112])[0]

    print(f'== {path} ({len(data)} bytes)')
    print(f'   magic={magic.decode()} header_version={hdr_ver} page_size={page_size} header_size={header_size}')
    print(f'   kernel_addr={kaddr:#x} ramdisk_addr={raddr:#x} tags_addr={tags_addr:#x}')
    print(f'   vendor_ramdisk_size={vramdisk_size} dtb_size={dtb_size} dtb_addr={dtb_addr:#x}')
    print(f'   cmdline: {cmdline!r}')
    print(f'   name: {name!r}')

    table_size = table_num = table_esize = bootconfig_size = 0
    if hdr_ver >= 4:
        table_size, table_num, table_esize, bootconfig_size = struct.unpack('<4I', data[2112:2128])
        print(f'   ramdisk_table_size={table_size} entries={table_num} entry_size={table_esize} bootconfig_size={bootconfig_size}')

    off = align(header_size, page_size)
    vramdisk_off = off
    off = align(off + vramdisk_size, page_size)
    dtb_off = off
    off = align(off + dtb_size, page_size)
    table_off = off
    off = align(off + table_size, page_size)
    bootconfig_off = off

    print(f'   sections: vendor_ramdisk@{vramdisk_off:#x} dtb@{dtb_off:#x} table@{table_off:#x} bootconfig@{bootconfig_off:#x}')
    print(f'   total image size {len(data)}; used {bootconfig_off + bootconfig_size}')

    entries = []
    if hdr_ver >= 4 and table_num:
        print('   -- vendor ramdisk table --')
        for i in range(table_num):
            e = data[table_off + i * table_esize: table_off + (i + 1) * table_esize]
            rsize, roff, rtype = struct.unpack('<3I', e[:12])
            rname = e[12:12 + 32].split(b'\0')[0].decode(errors='replace')
            entries.append((rsize, roff, rtype, rname))
            frag = data[vramdisk_off + roff: vramdisk_off + roff + min(rsize, 8)]
            print(f'      [{i}] size={rsize} offset={roff} type={rtype} name={rname!r} head={frag.hex()}')

    if dtb_size:
        p = dtb_off
        end = dtb_off + dtb_size
        print('   -- FDTs in dtb section --')
        n = 0
        while p + 8 <= end:
            if data[p:p + 4] != b'\xd0\x0d\xfe\xed':
                print(f'      [{n}] no FDT magic at {p - dtb_off:#x} (offset in dtb), stopping')
                break
            tot = struct.unpack('>I', data[p + 4:p + 8])[0]
            print(f'      [{n}] fdt@{p - dtb_off:#x} totalsize={tot}')
            p += tot
            n += 1
        print(f'      dtb section size={dtb_size}, FDT bytes consumed={p - dtb_off}')

    if extract_dir:
        os.makedirs(extract_dir, exist_ok=True)
        open(os.path.join(extract_dir, 'vendor_ramdisk.bin'), 'wb').write(data[vramdisk_off:vramdisk_off + vramdisk_size])
        if dtb_size:
            open(os.path.join(extract_dir, 'dtb.bin'), 'wb').write(data[dtb_off:dtb_off + dtb_size])
        if bootconfig_size:
            open(os.path.join(extract_dir, 'bootconfig.bin'), 'wb').write(
                data[bootconfig_off:bootconfig_off + bootconfig_size])
        for i, (rsize, roff, rtype, rname) in enumerate(entries):
            fn = f'fragment_{i}_{rname or "default"}_{rtype}.bin'
            open(os.path.join(extract_dir, fn), 'wb').write(data[vramdisk_off + roff: vramdisk_off + roff + rsize])
        print(f'   extracted sections + {len(entries)} fragments to {extract_dir}')


if __name__ == '__main__':
    parse(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
