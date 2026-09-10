#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# راه‌انداز AIBL روی مک — دوبار کلیک کنید.
#
# چرا این فایل هست: راه‌اندازِ ویندوز روی مک اجرا نمی‌شود، و پایتونِ
# خودِ مک (۳٫۹) برای این پکیج قدیمی است. این اسکریپت نسخه را می‌سنجد،
# یک محیط مجازیِ کنارِ پکیج می‌سازد، وابستگی‌ها را یک بار نصب می‌کند و
# پلتفرم را بالا می‌آورد.
#
# اگر مک اجازهٔ اجرا نداد:  chmod +x run_mac.command
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)' 2>/dev/null; then
      PY="$c"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "پایتون ۳٫۱۱ یا بالاتر پیدا نشد."
  echo "نصب: brew install python    یا از python.org"
  echo "(پایتون ۳٫۹ که همراه مک می‌آید برای این پکیج کافی نیست.)"
  read -r -p "برای بستن Enter بزنید..." _; exit 1
fi

VENV="$ROOT/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  echo "ساخت محیط مجازی با $PY ..."
  "$PY" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r requirements.txt

# پوشهٔ خانه — خروجی و لاگ و صندوقِ ارسال اینجا می‌نشینند، نه روی اشتراک.
export AIBL_HOME="${AIBL_HOME:-$HOME/.aibl}"
mkdir -p "$AIBL_HOME"

# اشتراک سازمانی روی مک زیر /Volumes سوار می‌شود. اگر نامِ نقطهٔ اتصالِ
# شما فرق دارد، همین‌جا مقدارش را عوض کنید یا پیش از اجرا export کنید.
# export AIBL_NET="/Volumes/data-share/Global Sourcing"

echo "AIBL — مرورگر خودش باز می‌شود. برای بستن: Ctrl+C"
exec "$VENV/bin/python" "app/run_platform.py"
