#!/usr/bin/env bash
set +e
f="$1"; stem=$(basename "$f" .py); root="$PWD"; tmp="$root/review/final_feedback_fix/internal_remaining/tmp/$stem"; mkdir -p "$tmp"
export PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export GSI_DWH_PATH="$tmp/warehouse.sqlite" GSI_HOME="$tmp/gsi_home"
export NO_PROXY="${NO_PROXY:+$NO_PROXY,}127.0.0.1,localhost,::1"
export no_proxy="${no_proxy:+$no_proxy,}127.0.0.1,localhost,::1"
timeout 120s python -B -m pytest -q --basetemp "$tmp/pytest" "$f" > "$root/review/final_feedback_fix/internal_remaining/logs/$stem.log" 2>&1
rc=$?
if [ $rc -eq 0 ]; then st=PASS; elif [ $rc -eq 5 ]; then st=NO_TESTS; elif [ $rc -eq 124 ]; then st=TIMEOUT; else st=FAIL; fi
printf '%s\t%s\t%s\n' "$st" "$rc" "$f" > "$root/review/final_feedback_fix/internal_remaining/$stem.result"
echo "$st $f"
exit 0
