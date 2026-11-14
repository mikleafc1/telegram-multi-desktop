#!/usr/bin/env python3
# Adapt the official tdesktop Inno Setup script (Telegram/build/setup.iss)
# for our unlimited-accounts CI build and write setup-unlimited.iss next to
# the original.
#
# The official script unconditionally requires:
#   1. SignTool=sha256        -> we have no signing key; strip the directive
#                                so ISCC does not fail with "Unknown sign tool".
#   2. ReleasePath\Updater.exe-> DESKTOP_APP_DISABLE_AUTOUPDATE=ON means
#                                Updater.exe is never built; strip the entry
#                                when the file is absent.
#   3. ReleasePath\modules\x64\d3d\d3dcompiler_47.dll
#                             -> only copied by a POST_BUILD step when
#                                DESKTOP_APP_WIN7_BASELINE is on; strip the
#                                entry when the file is absent (Telegram then
#                                loads d3dcompiler_47.dll from System32, the
#                                default behaviour on Windows 10/11).
#
# Usage: make-setup-iss.py <path\to\setup.iss> <ReleasePath>
# Output: <same dir>\setup-unlimited.iss (always 0 exit; prints what changed).

import io
import os
import re
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: make-setup-iss.py <setup.iss> <ReleasePath>", file=sys.stderr)
        return 2

    iss_path, release_path = sys.argv[1], sys.argv[2]
    with io.open(iss_path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines(keepends=True)

    updater = os.path.join(release_path, "Updater.exe")
    d3d = os.path.join(release_path, "modules", "x64", "d3d", "d3dcompiler_47.dll")

    removed = []

    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("SignTool="):
            removed.append("SignTool=sha256 (no signing key)")
            continue
        if "Updater.exe" in stripped and "\\Updater.exe\"" in stripped and "Source:" in stripped:
            if not os.path.isfile(updater):
                removed.append("[Files] Updater.exe entry (file not built)")
                continue
        if "d3dcompiler_47.dll" in stripped and "Source:" in stripped:
            if not os.path.isfile(d3d):
                removed.append("[Files] d3dcompiler_47.dll entry (file absent)")
                continue
        out.append(line)

    dest = os.path.join(os.path.dirname(iss_path), "setup-unlimited.iss")
    with io.open(dest, "w", encoding="utf-8", newline="") as fh:
        fh.write("".join(out))

    print("Wrote", dest)
    if removed:
        for item in removed:
            print("removed:", item)
    else:
        print("no entries removed (all optional files present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
