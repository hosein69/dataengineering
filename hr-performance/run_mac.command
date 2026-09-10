#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# راه‌انداز HRPerf روی مک — دوبار کلیک کنید.
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
export HRP_HOME="${HRP_HOME:-$HOME/.hrperf}"
mkdir -p "$HRP_HOME"

# HRPerf داده را از کنارِ خودِ پکیج می‌خواند: پوشهٔ input_files در همین
# پوشه، یا در $HRP_HOME. اگر فایل‌ها روی اشتراک شبکه‌اند، آن اشتراک را
# در Finder سوار کنید و پوشه را زیر یکی از این دو بگذارید.

echo "HRPerf — مرورگر خودش باز می‌شود. برای بستن: Ctrl+C"
exec "$VENV/bin/python" "app/run_dashboard.py"
