#!/usr/bin/env python3
"""
Unlimited-accounts patch for DrKLO/Telegram (Android) master.

Mirrors the proven Nagram (NextAlone/Nagram) approach adapted to master:
  1. UserConfig.MAX_ACCOUNT_COUNT : 4 -> 999
  2. Every eager per-account loop that instantiates heavy singletons
     (MessagesController/ConnectionsManager/LocationController/NotificationCenter/...)
     is guarded with isClientActivated() so we never build 999 controller sets
     (that OOMs and crashes the app at startup).
  3. tgnet (native): ConnectionsManager::getInstance switch (hardcoded 5 slots)
     replaced with a dynamic, lazy, mutex-protected vector (truly unlimited).
  4. tgnet (native): per-instance delegate setup native_setJava(int) with bounds
     check instead of the eager 0..MAX loop in setJava(boolean).
  5. jni Defines.h native cap raised to 999 (jniEnv array etc.).

Idempotent: safe to run multiple times.
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')

GUARD = 'if (!{v} != 0 && '.rstrip()  # placeholder, unused


def sub(path, old, new, count=1):
    p = ROOT / path
    src = p.read_text(encoding='utf-8')
    if new in src:
        print(f'  already patched: {path}')
        return
    n = src.count(old)
    if n != count:
        raise SystemExit(f'FAIL {path}: anchor found {n}x (expected {count}x):\n---\n{old}\n---')
    p.write_text(src.replace(old, new), encoding='utf-8')
    print(f'  patched: {path}')


def guard_loop(path, header, first_body_line, guard, count=1):
    """Insert `guard` between loop header and its first body line."""
    anchor = header + '\n' + first_body_line
    replacement = header + '\n' + guard + '\n' + first_body_line
    sub(path, anchor, replacement, count)


print('== 1) UserConfig: MAX_ACCOUNT_COUNT 4 -> 999 ==')
sub('TMessagesProj/src/main/java/org/telegram/messenger/UserConfig.java',
    'public final static int MAX_ACCOUNT_COUNT = 4;',
    'public final static int MAX_ACCOUNT_COUNT = 999;')

print('== 2) ApplicationLoader: guard startup eager loops ==')
AL = 'TMessagesProj/src/main/java/org/telegram/messenger/ApplicationLoader.java'
G0 = 'if (a != 0 && !UserConfig.getInstance(a).isClientActivated()) continue;'
guard_loop(AL,
    '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) { //TODO improve account',
    '            UserConfig.getInstance(a).loadConfig();',
    '            ' + G0)
guard_loop(AL,
    '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) { //TODO improve account',
    '            ContactsController.getInstance(a).checkAppAccount();',
    '            ' + G0)
guard_loop(AL,
    '                    for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
    '                        ConnectionsManager.getInstance(a).checkConnection();',
    '                        ' + G0)

print('== 3) tgnet Java: per-instance delegate + guarded setters ==')
CM = 'TMessagesProj/src/main/java/org/telegram/tgnet/ConnectionsManager.java'
sub(CM,
    '    public ConnectionsManager(int instance) {\n        super(instance);',
    '    public ConnectionsManager(int instance) {\n        super(instance);\n        native_setJava(instance);')
sub(CM,
    '    public static native void native_setJava(boolean useJavaByteBuffers);',
    '    public static native void native_setJava(boolean useJavaByteBuffers);\n'
    '    public static native void native_setJava(int instanceNum);')
for first in (
    '            native_setLangCode(a, langCode);',
    '            native_setRegId(a, pushString);',
    '            native_setSystemLangCode(a, langCode);',
):
    guard_loop(CM,
        '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
        first,
        '            ' + G0)
guard_loop(CM,
    '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
    '            if (enabled && settings != null && settings.isValid()) {',
    '            ' + G0)

print('== 4) tgnet native: dynamic getInstance (Nagram-style) ==')
NCPP = 'TMessagesProj/jni/tgnet/ConnectionsManager.cpp'
sub(NCPP,
    '#include <chrono>\n#include <algorithm>',
    '#include <chrono>\n#include <algorithm>\n#include <mutex>\n#include <vector>')
sub(NCPP,
    '''ConnectionsManager& ConnectionsManager::getInstance(int32_t instanceNum) {
    switch (instanceNum) {
        case 0:
            static ConnectionsManager instance0(0);
            return instance0;
        case 1:
            static ConnectionsManager instance1(1);
            return instance1;
        case 2:
            static ConnectionsManager instance2(2);
            return instance2;
        case 3:
            static ConnectionsManager instance3(3);
            return instance3;
        case 4:
        default:
            static ConnectionsManager instance4(4);
            return instance4;
    }
}''',
    '''std::vector<ConnectionsManager *> ConnectionsManager::_instances = std::vector<ConnectionsManager *>(10);

ConnectionsManager& ConnectionsManager::getInstance(int32_t instanceNum) {
    static std::mutex _new_mutex;
    std::lock_guard<std::mutex> lock(_new_mutex);
    if (instanceNum < 0) {
        instanceNum = 0;
    }
    if (instanceNum >= static_cast<int32_t>(_instances.size())) {
        _instances.resize(instanceNum + 10, nullptr);
    }
    if (_instances[instanceNum] == nullptr) {
        _instances[instanceNum] = new ConnectionsManager(instanceNum);
    }
    return *_instances[instanceNum];
}''')

print('== 5) tgnet native header: _instances member ==')
NH = 'TMessagesProj/jni/tgnet/ConnectionsManager.h'
sub(NH,
    '    static ConnectionsManager &getInstance(int32_t instanceNum);',
    '    static ConnectionsManager &getInstance(int32_t instanceNum);\n'
    '    static std::vector<ConnectionsManager *> _instances;')
hdr = (ROOT / NH).read_text(encoding='utf-8')
if '#include <vector>' not in hdr:
    hdr = hdr.replace('#include "Defines.h"', '#include <vector>\n#include "Defines.h"', 1)
    (ROOT / NH).write_text(hdr, encoding='utf-8')
    print('  patched: %s (+<vector>)' % NH)

print('== 6) tgnet native: per-instance setJava1 + registration ==')
NW = 'TMessagesProj/jni/TgNetWrapper.cpp'
sub(NW,
    '''void setJava(JNIEnv *env, jclass c, jboolean useJavaByteBuffers) {
    ConnectionsManager::useJavaVM(java, useJavaByteBuffers);
    for (int a = 0; a < MAX_ACCOUNT_COUNT; a++) {
        ConnectionsManager::getInstance(a).setDelegate(new Delegate());
    }
}''',
    '''void setJava(JNIEnv *env, jclass c, jboolean useJavaByteBuffers) {
    ConnectionsManager::useJavaVM(java, useJavaByteBuffers);
}

void setJava1(JNIEnv *env, jclass c, jint instanceNum) {
    if (instanceNum < 0 || instanceNum >= MAX_ACCOUNT_COUNT) {
        return;
    }
    ConnectionsManager::getInstance(instanceNum).setDelegate(new Delegate());
}''')
sub(NW,
    '        {"native_setJava", "(Z)V", (void *) setJava},',
    '        {"native_setJava", "(Z)V", (void *) setJava},\n'
    '        {"native_setJava", "(I)V", (void *) setJava1},')

print('== 7) native cap 5 -> 999 ==')
sub('TMessagesProj/jni/tgnet/Defines.h',
    '#define MAX_ACCOUNT_COUNT 5',
    '#define MAX_ACCOUNT_COUNT 999')

print('== 8) guard remaining eager per-account loops (services/UI) ==')
GENERIC = [
    # (file, header, first body line)
    ('TMessagesProj/src/main/java/org/telegram/messenger/ContactsController.java',
     '                            for (int b = 0; b < UserConfig.MAX_ACCOUNT_COUNT; b++) {',
     '                                TLRPC.User user = UserConfig.getInstance(b).getCurrentUser();'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/ImageLoader.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            final int currentAccount = a;'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/ImportingService.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            NotificationCenter.getInstance(a).removeObserver(this, NotificationCenter.historyImportProgressChanged);'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/ImportingService.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            if (SendMessagesHelper.getInstance(a).isImportingHistory()) {'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/ImportingService.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            if (SendMessagesHelper.getInstance(a).isImportingStickers()) {'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/LocationController.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            count += LocationController.getInstance(a).sharingLocationsUI.size();'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/LocationSharingService.java',
     '                for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '                    LocationController.getInstance(a).update();'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/LocationSharingService.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            ArrayList<LocationController.SharingLocationInfo> arrayList = LocationController.getInstance(a).sharingLocationsUI;'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/LocationSharingService.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            final ArrayList<LocationController.SharingLocationInfo> infos = LocationController.getInstance(a).sharingLocationsUI;'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/MediaController.java',
     '            for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '                NotificationCenter.getInstance(a).addObserver(MediaController.this, NotificationCenter.fileLoaded);'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/MediaController.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            DownloadController.getInstance(a).cleanup();'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/MusicPlayerService.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            NotificationCenter.getInstance(a).addObserver(this, NotificationCenter.messagePlayingDidSeek);'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/MusicPlayerService.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            NotificationCenter.getInstance(a).removeObserver(this, NotificationCenter.messagePlayingDidSeek);'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/ProxyRotationController.java',
     '        for (int i = 0; i < UserConfig.MAX_ACCOUNT_COUNT; i++) {',
     '            NotificationCenter.getInstance(i).addObserver(this, NotificationCenter.didUpdateConnectionState);'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/StopLiveLocationReceiver.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            LocationController.getInstance(a).removeAllLocationSharings();'),
    ('TMessagesProj/src/main/java/org/telegram/messenger/voip/VoIPPreNotificationService.java',
     '            for (int i = 0; i < UserConfig.MAX_ACCOUNT_COUNT; ++i) {',
     '                MessagesController.getInstance(i).ignoreSetOnline = false;'),
    ('TMessagesProj/src/main/java/org/telegram/ui/Components/FragmentContextView.java',
     '                        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '                            LocationController.getInstance(a).removeAllLocationSharings();'),
    ('TMessagesProj/src/main/java/org/telegram/ui/Components/FragmentContextView.java',
     '                    for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '                        ArrayList<LocationController.SharingLocationInfo> arrayList = LocationController.getInstance(a).sharingLocationsUI;'),
    ('TMessagesProj/src/main/java/org/telegram/ui/Components/FragmentContextView.java',
     '            for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '                GroupCallMessagesController.getInstance(a).unsubscribeFromCallMessages(0, this);'),
    ('TMessagesProj/src/main/java/org/telegram/ui/Components/FragmentContextView.java',
     '            for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '                observersGroup[a] = NotificationCenter.getInstance(a)'),
    ('TMessagesProj/src/main/java/org/telegram/ui/Components/FragmentContextView.java',
     '                for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '                    infos.addAll(LocationController.getInstance(a).sharingLocationsUI);'),
    ('TMessagesProj/src/main/java/org/telegram/ui/Components/SharingLocationsAlert.java',
     '            for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '                LocationController.getInstance(a).removeAllLocationSharings();'),
    ('TMessagesProj/src/main/java/org/telegram/ui/Components/SharingLocationsAlert.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            ArrayList<LocationController.SharingLocationInfo> infos = LocationController.getInstance(a).sharingLocationsUI;'),
    ('TMessagesProj/src/main/java/org/telegram/ui/NotificationPermissionDialog.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; ++a) {',
     '            try {\n                NotificationCenter.getInstance(a).addWeakObserver(this, NotificationCenter.updateInterfaces);'),
    ('TMessagesProj/src/main/java/org/telegram/ui/NotificationPermissionDialog.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; ++a) {',
     '            MessagesStorage messagesStorage = MessagesStorage.getInstance(a);'),
    ('TMessagesProj/src/main/java/org/telegram/ui/NotificationsSettingsActivity.java',
     '                for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '                    if (SharedConfig.showNotificationsForAllAccounts) {'),
    ('TMessagesProj/src/main/java/org/telegram/ui/PopupNotificationActivity.java',
     '        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {',
     '            NotificationCenter.getInstance(a).addWeakObserver(this, NotificationCenter.appDidLogout);'),
    ('TMessagesProj/src/main/java/org/telegram/ui/RestrictedLanguagesSelectActivity.java',
     '                for (int i = 0; i < UserConfig.MAX_ACCOUNT_COUNT; ++i) {',
     '                    final int account = i;'),
]
for (f, header, body) in GENERIC:
    # indentation of the guard = indentation of the first body line
    indent = body[: len(body) - len(body.lstrip())]
    var = 'b' if 'int b = 0' in header else ('i' if 'int i = 0' in header else 'a')
    g = f'{indent}if (!UserConfig.getInstance({var}).isClientActivated()) continue;'
    guard_loop(f, header, body, g)

print('== 9) remove premium/free account-count gates (Nagram-style) ==')
# Master gates "Add account" behind Telegram Premium:
#   MainTabsActivity / LogoutActivity / UserInfoActivity all do
#     freeAccounts -= (MAX_ACCOUNT_COUNT - MAX_ACCOUNT_DEFAULT_COUNT)   # 999-3
#   when no account has premium, so without premium the user hits the
#   LimitReachedBottomSheet(TYPE_ACCOUNTS) after MAX_ACCOUNT_DEFAULT_COUNT=3
#   accounts. Nagram raises both constants (8/10/128); we go to 999 and
#   neutralize getMaxAccountCount() too (UserInfoActivity upsell text).
sub('TMessagesProj/src/main/java/org/telegram/messenger/UserConfig.java',
    'public final static int MAX_ACCOUNT_DEFAULT_COUNT = 3;',
    'public final static int MAX_ACCOUNT_DEFAULT_COUNT = 999;')
sub('TMessagesProj/src/main/java/org/telegram/messenger/UserConfig.java',
    'return hasPremiumOnAccounts() ? 5 : 3;',
    'return MAX_ACCOUNT_COUNT;')

print('ALL PATCHES APPLIED OK')
