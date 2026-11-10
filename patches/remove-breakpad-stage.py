#!/usr/bin/env python3
"""Remove the `breakpad` stage from tdesktop's Telegram/build/prepare/prepare.py.

Why: upstream tdesktop links the breakpad crash client on Windows, but the
GitHub `windows-latest` runner ships VS 2026 whose v143 (14.44) toolset has
NO ATL component, so the breakpad `dump_syms` MSBuild part always dies with
C1083: 'atlbase.h' not found.

The workflow configures with -D DESKTOP_APP_DISABLE_CRASH_REPORTS=ON, which
makes cmake_helpers skip the `external_crash_reports` -> breakpad link
target entirely, so removing the prepare stage is safe.

Note: renaming the stage is NOT enough — `filterByPlatform` still registers
it on Windows (it has win commands) and a full `win.bat silent` prepare
iterates over every registered stage. The block must be deleted outright.

Usage: python remove-breakpad-stage.py <path-to-prepare.py>
Exits non-zero (failing the CI step) unless exactly one block was removed.
"""

import io
import re
import sys


def main():
    if len(sys.argv) < 2:
        print('usage: remove-breakpad-stage.py <prepare.py>')
        sys.exit(2)
    path = sys.argv[1]
    with io.open(path, encoding='utf-8') as f:
        s = f.read()

    # The block ends with `""" + macBreakpadBuild)` (stage() call, no comma).
    pattern = re.compile(
        r"stage\('breakpad',\s*\"\"\".*?\"\"\"\s*\+\s*macBreakpadBuild\)\s*",
        re.S)
    new, n = pattern.subn('', s)
    if n != 1:
        print('ERROR: expected exactly 1 breakpad stage block, matched %d' % n)
        sys.exit(1)
    if "stage('breakpad'" in new:
        print("ERROR: stage('breakpad' still present after removal")
        sys.exit(1)

    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    print('breakpad stage removed OK (%d bytes -> %d bytes)'
          % (len(s), len(new)))


if __name__ == '__main__':
    main()
