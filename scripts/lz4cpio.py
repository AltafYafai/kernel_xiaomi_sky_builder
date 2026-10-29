#!/usr/bin/env python3
"""Pure-python LZ4 legacy-frame decompressor + cpio(newc) extractor and packer.

Android's mkbootimg compresses the vendor_boot ramdisks with `lz4 -l`
(legacy format): magic 0x184C2102 followed by [u32le blocksize][block data].

Usage:
    lz4cpio.py decompress <in> <out>
    lz4cpio.py extract <in_lz4_or_cpio> <out_dir>
    lz4cpio.py pack <src_dir> <out_cpio>
    lz4cpio.py list <file> [--all|--grep PATTERN]
"""
import os
import struct
import sys

MAGIC = 0x184C2102


def lz4_block_decompress(src, max_size=None):
    out = bytearray()
    ip = 0
    n = len(src)
    while ip < n:
        token = src[ip]
        ip += 1
        lit_len = token >> 4
        if lit_len == 15:
            while True:
                b = src[ip]
                ip += 1
                lit_len += b
                if b != 255:
                    break
        out += src[ip:ip + lit_len]
        ip += lit_len
        if ip >= n:
            break  # last sequence: literals only
        offset = src[ip] | (src[ip + 1] << 8)
        ip += 2
        if offset == 0 or offset > len(out):
            raise ValueError(f'bad match offset {offset} (out {len(out)})')
        match_len = token & 0x0F
        if match_len == 15:
            while True:
                b = src[ip]
                ip += 1
                match_len += b
                if b != 255:
                    break
        match_len += 4
        start = len(out) - offset
        for i in range(match_len):
            out.append(out[start + i])  # supports overlapping matches
    if max_size and len(out) > max_size:
        raise ValueError('block output too large')
    return bytes(out)


def lz4_legacy_decompress(data):
    # If already a cpio archive, return directly
    if data[:6] == b'070701':
        return data

    cands = []
    start = 0
    while True:
        idx = data.find(struct.pack('<I', MAGIC), start)
        if idx < 0:
            break
        cands.append(idx)
        start = idx + 1
    if not cands:
        raise ValueError('no lz4 legacy magic found')
    last_err = None
    for idx in cands[:24]:
        try:
            p = idx + 4
            out = bytearray()
            while p + 4 <= len(data):
                size = struct.unpack('<I', data[p:p + 4])[0]
                p += 4
                if size == 0:
                    break
                if size & 0x80000000:
                    n = size & 0x7FFFFFFF
                    out += data[p:p + n]
                    p += n
                else:
                    if p + size > len(data):
                        raise ValueError('truncated lz4 block')
                    out += lz4_block_decompress(data[p:p + size])
                    p += size
            if out[:6] == b'070701' or out[:2] == b'\x1f\x8b' or len(out) > (1 << 20):
                return bytes(out)
            last_err = ValueError(f'offset {idx}: output does not look like a ramdisk ({bytes(out[:8])!r})')
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise last_err if last_err else ValueError('failed to decode lz4 stream')


def cpio_entries(buf):
    p = 0
    while p + 110 <= len(buf):
        if buf[p:p + 6] != b'070701':
            nxt = buf.find(b'070701', p)
            if nxt < 0:
                break
            p = nxt
        fields = [int(buf[p + 6 + i * 8:p + 6 + (i + 1) * 8], 16) for i in range(13)]
        filesize = fields[6]
        namesize = fields[11]
        name = buf[p + 110:p + 110 + namesize - 1].decode(errors='replace')
        p += 110 + namesize
        p = (p + 3) & ~3
        data = buf[p:p + filesize]
        p += filesize
        p = (p + 3) & ~3
        yield name, data
        if name == 'TRAILER!!!':
            break


def extract_cpio(buf, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    count = 0
    for name, data in cpio_entries(buf):
        if name == 'TRAILER!!!':
            break
        target = os.path.join(out_dir, name)
        if len(data) == 0 and not name.endswith('.ko') and '.' not in os.path.basename(name):
            os.makedirs(target, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, 'wb') as f:
                f.write(data)
        count += 1
    return count


def pack_cpio(src_dir):
    out = bytearray()
    ino = 1
    for root, dirs, files in os.walk(src_dir):
        dirs.sort()
        files.sort()
        for d in dirs:
            rel = os.path.relpath(os.path.join(root, d), src_dir)
            path_bytes = rel.encode('utf-8') + b'\x00'
            namesize = len(path_bytes)
            hdr = f'070701{ino:08X}{0o040755:08X}000000000000000000000002000000000000000000000000000000000000000000000000{namesize:08X}00000000'.encode('ascii')
            ino += 1
            out += hdr + path_bytes
            pad = (4 - len(out) % 4) % 4
            out += b'\x00' * pad
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), src_dir)
            with open(os.path.join(root, f), 'rb') as fp:
                data = fp.read()
            path_bytes = rel.encode('utf-8') + b'\x00'
            namesize = len(path_bytes)
            filesize = len(data)
            hdr = f'070701{ino:08X}{0o100644:08X}00000000000000000000000100000000{filesize:08X}00000000000000000000000000000000{namesize:08X}00000000'.encode('ascii')
            ino += 1
            out += hdr + path_bytes
            pad = (4 - len(out) % 4) % 4
            out += b'\x00' * pad
            out += data
            pad2 = (4 - len(out) % 4) % 4
            out += b'\x00' * pad2

    # Trailer
    path_bytes = b'TRAILER!!!\x00'
    namesize = len(path_bytes)
    hdr = f'070701{ino:08X}00000000000000000000000000000001000000000000000000000000000000000000000000000000{namesize:08X}00000000'.encode('ascii')
    out += hdr + path_bytes
    pad = (4 - len(out) % 4) % 4
    out += b'\x00' * pad
    pad512 = (512 - len(out) % 512) % 512
    out += b'\x00' * pad512
    return bytes(out)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'decompress':
        data = open(sys.argv[2], 'rb').read()
        out = lz4_legacy_decompress(data)
        open(sys.argv[3], 'wb').write(out)
        print(f'decompressed {len(data)} -> {len(out)} bytes')
    elif cmd == 'extract':
        data = open(sys.argv[2], 'rb').read()
        decompressed = lz4_legacy_decompress(data)
        count = extract_cpio(decompressed, sys.argv[3])
        print(f'extracted {count} entries to {sys.argv[3]}')
    elif cmd == 'pack':
        cpio_bytes = pack_cpio(sys.argv[2])
        open(sys.argv[3], 'wb').write(cpio_bytes)
        print(f'packed {len(cpio_bytes)} bytes into {sys.argv[3]}')
    elif cmd == 'list':
        buf = open(sys.argv[2], 'rb').read()
        if buf[:8] != b'070701' and struct.pack('<I', MAGIC) in buf[:16]:
            buf = lz4_legacy_decompress(buf)
        show_all = '--all' in sys.argv
        pat = None
        if '--grep' in sys.argv:
            pat = sys.argv[sys.argv.index('--grep') + 1]
        n = kos = 0
        modload = []
        for name, data in cpio_entries(buf):
            n += 1
            if name.endswith('.ko'):
                kos += 1
            if 'modules.load' in name:
                modload.append((name, len(data)))
            if show_all or (pat and pat in name) or (not pat and not show_all and n <= 20):
                print(f'  {name} ({len(data)} bytes)')
        for name, size in modload:
            print(f'  [modules.load] {name} ({size} bytes)')
        print(f'total entries: {n}, .ko entries: {kos}')
