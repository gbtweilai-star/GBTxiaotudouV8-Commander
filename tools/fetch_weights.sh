#!/bin/sh
# 下载中文权重（断点续传 · 后台跑）
# 用法: sh tools/fetch_weights.sh [1.5b|7b]
set -e
cd /var/minis/shared/gbtv8
mkdir -p holo_pet_w3/wgpu/models

case "${1:-1.5b}" in
  1.5b)
    URL="https://modelscope.cn/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/master/qwen2.5-1.5b-instruct-q4_k_m.gguf"
    OUT="holo_pet_w3/wgpu/models/qwen2.5-1.5b-q4.gguf"
    ;;
  7b)
    URL="https://modelscope.cn/models/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/master/qwen2.5-7b-instruct-q4_k_m.gguf"
    OUT="holo_pet_w3/wgpu/models/qwen2.5-7b-q4.gguf"
    ;;
  *) echo "用法: $0 [1.5b|7b]"; exit 2 ;;
esac

echo "  目标: $OUT"
echo "  源:   $URL"
# -C - 断点续传 · --retry 5 抗抖 · 输出进度到日志
curl -L -C - --retry 5 --retry-delay 3 --retry-all-errors \
     -o "$OUT" "$URL" \
     > logs/fetch_weights.log 2>&1
echo "  完成: $(ls -lh "$OUT" | awk '{print $5}')"
