#!/usr/bin/env python3
"""Patch tdesktop's Telegram/build/prepare/prepare.py for the GitHub runner.

Transformation 1: remove the `breakpad` stage.
Why: the windows-latest runner image has NO ATL for the v143 toolset, so the
breakpad `dump_syms` MSBuild part always dies with C1083 'atlbase.h' not
found. The workflow configures with -D DESKTOP_APP_DISABLE_CRASH_REPORTS=ON,
which makes cmake_helpers skip the `external_crash_reports` -> breakpad link
target entirely, so the libraries are never needed.

Transformation 2: build/install only the release configuration of Qt 6.
Why: run 8 died with "No space left on device" while INSTALLING the Debug
configuration of Qt. Qt's configure.bat maps -debug-and-release to
CMAKE_CONFIGURATION_TYPES = RelWithDebInfo;Debug (see run 9 log), so plain
`Release` does NOT exist in the Qt build and `--config Release` would fail.
The release configuration of Qt IS RelWithDebInfo (-force-debug-info), and
that is exactly what the official Telegram builds consume (upstream build.bat
produces out/Release against the same Qt), so building+installing ONLY
RelWithDebInfo keeps the Release Telegram.exe link working while skipping
the expensive and disk-hungry Debug Qt entirely.

Note: renaming the breakpad stage is NOT enough — `filterByPlatform` still
registers it on Windows (it has win commands) and a full `win.bat silent`
prepare iterates over every registered stage. The block must be deleted
outright.

Usage: python remove-breakpad-stage.py <path-to-prepare.py>
Exits non-zero (failing the CI step) unless every expected edit applied.
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

    # 1. Drop the breakpad stage block entirely.
    # The block ends with `""" + macBreakpadBuild)` (stage() call, no comma).
    pattern = re.compile(
        r"stage\('breakpad',\s*\"\"\".*?\"\"\"\s*\+\s*macBreakpadBuild\)\s*",
        re.S)
    s, n = pattern.subn('', s)
    if n != 1:
        print('ERROR: expected exactly 1 breakpad stage block, matched %d' % n)
        sys.exit(1)
    if "stage('breakpad'" in s:
        print("ERROR: stage('breakpad' still present after removal")
        sys.exit(1)
    print('breakpad stage removed OK')

    # 2. Qt 6 stage: install the RelWithDebInfo (release) config only.
    qt_build_tail = re.compile(
        r"cmake --build \. --config Debug\r?\n"
        r"[ \t]*cmake --install \. --config Debug\r?\n"
        r"[ \t]*cmake --build \.\r?\n"
        r"[ \t]*cmake --install \.")
    s, n = qt_build_tail.subn(
        'cmake --build . --config RelWithDebInfo\n'
        '    cmake --install . --config RelWithDebInfo', s)
    if n != 1:
        print('ERROR: expected exactly 1 Qt Debug build tail, matched %d' % n)
        sys.exit(1)
    if qt_build_tail.search(s):
        print('ERROR: Qt Debug build tail still present after trim')
        sys.exit(1)
    print('Qt stage trimmed to RelWithDebInfo-only OK')

    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


if __name__ == '__main__':
    main()
