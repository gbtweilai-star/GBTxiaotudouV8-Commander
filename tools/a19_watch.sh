#!/bin/sh
# 只报"状态变化"：仍 DOWN 且与上次相同 ⇒ 只输出 SAME_DOWN（一个字都不多说）
S=/var/minis/shared/gbtv8/state/a19_last_state
NOW=$(nc -z -w2 127.0.0.1 1234 2>/dev/null && echo UP || echo DOWN)
LAST=$(cat "$S" 2>/dev/null || echo NONE)
echo "$NOW" > "$S"
if [ "$NOW" = "$LAST" ]; then echo "SAME_$NOW"; else echo "CHANGED_${LAST}_TO_$NOW"; fi
if [ "$NOW" = "UP" ]; then cd /var/minis/shared/gbtv8/tools && ./a19_accept.sh 2>&1 | tail -25; fi
