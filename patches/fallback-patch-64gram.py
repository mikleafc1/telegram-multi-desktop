#!/usr/bin/env python3
"""Fallback patcher for the 64Gram v1.2.12 unlimited-accounts build.

Used only if `git apply` fails on patches/unlimited-accounts-64gram.patch.
It regex-patches ALL FOUR account-limit points in the v1.2.12 source:

  1. Telegram/SourceFiles/main/main_domain.h
       kMaxAccounts 100 -> 999, kPremiumMaxAccounts 6 -> 1000
  2. Telegram/SourceFiles/main/main_domain.cpp
       Domain::maxAccounts() hardcodes `return 100;` -> `return 999;`
  3. Telegram/SourceFiles/settings/sections/settings_information.cpp
       "Add account" click handler hardcodes `size() >= 10` -> `>= 999`
  4. Telegram/SourceFiles/boxes/premium_limits_box.cpp
       AccountsLimitBox display `defaultLimit = 10` -> `999`

Exits non-zero if any replacement did not match, so CI fails loudly
instead of silently producing a still-limited build.
"""

import io
import os
import re
import sys


def read(path):
    with io.open(path, encoding='utf-8') as f:
        return f.read()


def write(path, s):
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def patch_header(s):
    s2, n1 = re.subn(
        r'static constexpr auto kMaxAccounts = \d+;',
        'static constexpr auto kMaxAccounts = 999;',
        s)
    s2, n2 = re.subn(
        r'static constexpr auto kPremiumMaxAccounts = \d+;',
        'static constexpr auto kPremiumMaxAccounts = 1000;',
        s2)
    return s2, n1 + n2


def patch_maxaccounts_impl(s):
    # Only inside Domain::maxAccounts() — the commented-out lines above the
    # real return start with "\t//" so they are not matched.
    return re.subn(
        r'(int Domain::maxAccounts\(\) const \{.*?\n\t)return \d+;',
        r'\1return 999;',
        s,
        count=1,
        flags=re.S)


def patch_add_account_check(s):
    return re.subn(
        r'domain\.accounts\(\)\.size\(\) >= \d+',
        'domain.accounts().size() >= 999',
        s,
        count=1)


def patch_default_limit(s):
    return re.subn(
        r'const auto defaultLimit = 10;',
        'const auto defaultLimit = 999;',
        s,
        count=1)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.environ.get('TBUILD', ''), 'tdesktop')
    if not os.path.isdir(root):
        print('ERROR: tdesktop source dir not found: %r' % root)
        sys.exit(2)

    jobs = [
        (os.path.join(root, 'Telegram', 'SourceFiles', 'main', 'main_domain.h'),
         patch_header, 'kMaxAccounts = 999'),
        (os.path.join(root, 'Telegram', 'SourceFiles', 'main', 'main_domain.cpp'),
         patch_maxaccounts_impl, 'return 999;'),
        (os.path.join(root, 'Telegram', 'SourceFiles', 'settings', 'sections',
                      'settings_information.cpp'),
         patch_add_account_check, 'size() >= 999'),
        (os.path.join(root, 'Telegram', 'SourceFiles', 'boxes',
                      'premium_limits_box.cpp'),
         patch_default_limit, 'defaultLimit = 999'),
    ]

    ok = True
    for path, fn, marker in jobs:
        if not os.path.isfile(path):
            print('ERROR: missing file: %s' % path)
            ok = False
            continue
        s = read(path)
        if marker in s:
            print('SKIP (already patched): %s' % path)
            continue
        s2, n = fn(s)
        if n < 1:
            print('ERROR: no match while patching %s' % path)
            ok = False
            continue
        write(path, s2)
        if marker not in read(path):
            print('ERROR: marker %r missing after patching %s' % (marker, path))
            ok = False
        else:
            print('PATCHED: %s' % path)

    if not ok:
        sys.exit(1)
    print('FALLBACK PATCH OK')


if __name__ == '__main__':
    main()
