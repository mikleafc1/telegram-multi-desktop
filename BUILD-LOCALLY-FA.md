# بیلد دستی روی ویندوز خودتان (جایگزین CI)

اگر نمی‌خواهید از GitHub Actions استفاده کنید، می‌توانید روی یک ویندوز ۶۴ بیتی خودتان همین نسخه را با **حدود ۲ تا ۶ ساعت** زمان بیلد کنید. این متن خلاصهٔ [مستند رسمی بیلد ویندوز](https://github.com/telegramdesktop/tdesktop/blob/dev/docs/building-win.md) + وصلهٔ ماست.

## پیش‌نیازها

- **Windows 10/11 64-bit**
- **Visual Studio 2026 یا 2022** با این کامپوننت‌ها:
  - Desktop development with C++
  - Windows 11 SDK نسخهٔ **10.0.26100.0** (یا جدیدتر)
  - MSVC v143 (ابزار 14.44) — در VS2026 موقع نصب تیک v143/v144 را هم بزنید
- **Python 3.10+** (با گزینهٔ Add to PATH)
- **Git** برای ویندوز
- حدود **۶۰ گیگ** فضای خالی (پوشهٔ Libraries سنگین است)

## مراحل

### ۱) آماده‌سازی پوشه

یک پوشهٔ خالی بسازید، مثلاً `D:\TBuild` و داخلش دو زیرپوشهٔ `ThirdParty` و `Libraries` بسازید.

### ۲) باز کردن ترمینال مناسب

«x64 Native Tools Command Prompt for VS» را باز کنید (یا در cmd دستور زیر):

```bat
"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" -vcvars_ver=14.44
```

(اگر VS2026 دارید مسیر `18\Community` است. برای پشتیبانی ویندوز ۷ حتماً `-vcvars_ver=14.44` لازم است؛ برای ویندوز ۱۰/۱۱ می‌توانید بدون آن هم بیلد کنید.)

### ۳) کلون سورس و آماده‌سازی کتابخانه‌ها

در همان ترمینال:

```bat
D:
cd \TBuild
git -c core.autocrlf=false clone --depth 1 --shallow-submodules --recurse-submodules https://github.com/telegramdesktop/tdesktop.git
cd tdesktop

rem ==== اعمال وصلهٔ حساب‌های نامحدود ====
git apply --whitespace=nowarn path\to\unlimited-accounts.patch
rem اگر فایل وصله را ندارید، همین دو خط را در
rem Telegram\SourceFiles\main\main_domain.h
rem دستی ویرایش کنید:  kMaxAccounts = 3  ←  999   و   kPremiumMaxAccounts = 6  ←  1000

rem ==== آماده‌سازی کتابخانه‌ها (ساعت‌ها طول می‌کشد، فقط یک بار) ====
cd Telegram\build\prepare
win.bat
cd ..\..\..
```

> نکته: `win.bat` را بدون `skip-release` اجرا کنید تا هر دو پیکربندی Debug و Release کتابخانه‌ها ساخته شوند (برای بیلد Release لازم است).

### ۴) Configure و بیلد

در ترمینال همان محیط VS:

```bat
cd Telegram
configure.bat x64 -D TDESKTOP_API_ID=6 -D TDESKTOP_API_HASH=eb06d4abfb49dc3eeb1aeb98ae0f581e -D DESKTOP_APP_DISABLE_AUTOUPDATE=ON
cmake --build ..\out --config Release --parallel
```

یا به‌جای دستور cmake: فایل `out\Telegram.sln` (یا `Telegram.slnx`) را در Visual Studio باز کنید، پلتفرم x64 و کانفیگ **Release** را انتخاب کنید و پروژهٔ Telegram را Build کنید.

اعتبارنامهٔ API بالا همان جفتِ عمومیِ خود کلاینت رسمی Telegram Desktop است؛ مثل CI می‌توانید با Secret جایگزینش کنید یا هر جفت دیگری که دارید بگذارید (در صورت نداشتن هیچ اعتبارنامه‌ای می‌توانید موقتاً `-D TDESKTOP_API_TEST=ON` بگذارید، اما آن حالت فقط برای تست است و در ورود واقعی خطای سرور می‌دهد).

### ۵) خروجی

فایل خروجی اینجاست:

```
D:\TBuild\tdesktop\out\Release\Telegram.exe
D:\TBuild\tdesktop\out\Release\Updater.exe
```

`Telegram.exe` مستقل و پرتابل است؛ کپی‌اش کنید و اجرا کنید. ورود با شمارهٔ تلفن + کد، اضافه کردن حساب‌های جدید از Settings ← Accounts (بدون سقف ۳تایی).

## مشکلات رایج

- **`Make sure to run from Native Tools Command Prompt`**: یعنی متغیر `Platform` ست نشده؛ ترمینال VS Tools را درست باز کنید.
- **خطای کمبود فضا**: پوشه‌های `out` و `Libraries` بزرگ‌اند؛ حداقل ۶۰ گیگ خالی داشته باشید.
- **خطای لینک در Release با کتابخانه‌های ناقص**: اگر قبلاً `win.bat` را با `skip-release` اجرا کرده‌اید، پوشهٔ `Libraries\win64\cache_keys` مربوط به مراحل سرویس‌محور (openssl3، zlib، mozjpeg، opus، rnnoise، tg_angle، qt) را پاک کنید و `win.bat` را دوباره اجرا کنید تا واریانت Release آن‌ها ساخته شود.
