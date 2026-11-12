'''
cmake_helpers' run_cmake.py (the version pinned by tdesktop) appends
`-T v143` unconditionally -- it predates the explicit-toolset handling
that the master branch has. On the windows-2025-vs2026 runner image
`v143` resolves to the side-by-side MSVC 14.44.35207, while every
cached library (Qt 6.11.2, tg_angle, jxl, heif, openssl, ...) is
compiled with the env toolset MSVC 14.51.36231 selected by vcvars.
Linking 14.51-built objects against 14.44's static STL (libcpmt.lib)
dies with LNK2019/LNK1120 on the __std_* vectorized algorithm helpers
(run 14: __std_rotate, __std_minmax_element_2u, __std_unique_4, ...).

This patch makes the toolset follow the VCToolsVersion exported by
ilammy/msvc-dev-cmd via `-T version=<VCToolsVersion>` (CMake forwards
it to MSBuild as a global VCToolsVersion property, overriding the
v143 default), falling back to plain v143 when the variable is unset.

Usage: python pin-run-cmake-toolset.py <path-to-run_cmake.py>
Idempotent: safe to run on an already-patched copy.
'''
import io
import sys

path = sys.argv[1]
s = io.open(path, encoding='utf-8').read()

OLD = "cmake.append('-T v143')"
# The replaced token sits at a 12-space indent inside both the x64
# branch and the Win32-default branch, so the first NEW line carries no
# leading spaces and the second line re-indents itself.
NEW = (
    "vt = os.environ.get('VCToolsVersion', '')\n"
    "            cmake.append('-T version=' + vt if vt else '-T v143')"
)

if OLD not in s:
    if 'VCToolsVersion' in s:
        print('run_cmake.py already patched; nothing to do.')
        sys.exit(0)
    print('ERROR: expected "cmake.append(\'-T v143\')" not found in ' + path)
    sys.exit(1)

s = s.replace(OLD, NEW)
io.open(path, 'w', encoding='utf-8', newline='').write(s)
print('run_cmake.py patched: toolset now follows env VCToolsVersion.')
