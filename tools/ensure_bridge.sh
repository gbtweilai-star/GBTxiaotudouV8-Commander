#!/bin/sh
# 桥自愈：不在就起，起来就返回。任何需要桥的命令先调它。
PORT=8791
if nc -z -w1 127.0.0.1 $PORT 2>/dev/null; then
  curl -s -m 3 http://127.0.0.1:$PORT/health | grep -q gbt-model-bridge && exit 0
fi
cd /var/minis/shared/gbtv8/runtime || exit 1
setsid nohup python3 model_bridge.py --port $PORT > /tmp/bridge.log 2>&1 < /dev/null &
i=0
while [ $i -lt 30 ]; do
  sleep 0.5
  curl -s -m 2 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q gbt-model-bridge && exit 0
  i=$((i+1))
done
exit 1
