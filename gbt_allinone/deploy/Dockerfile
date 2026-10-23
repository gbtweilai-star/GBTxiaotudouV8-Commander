# =============================================================================
#  Dockerfile — gbt_wallet 收款钱包服务镜像
# -----------------------------------------------------------------------------
#  构建上下文必须是仓库根(Autoclaw/), 因为要同时拷贝 gbt_wallet/ 与 gbt_allinone/:
#    docker build -f gbt_allinone/deploy/Dockerfile -t gbt-wallet:local .
#    (或直接用 docker-compose.yml, 其中 context: ../..)
#
#  安全设计:
#    * 容器内绑 0.0.0.0(容器网络命名空间内), 但 compose 只把端口发布到宿主 127.0.0.1;
#    * 非 root 用户运行; 根文件系统只读(compose 里 read_only: true), 仅 /data 卷可写;
#    * 不写入任何密钥; 口令通过环境变量注入(Docker secret / env_file 自行取舍)。
# =============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先装依赖(利用层缓存); 依赖清单来自框架仓库
COPY gbt_allinone/requirements.txt /app/gbt_allinone/requirements.txt
RUN pip install --no-cache-dir -r /app/gbt_allinone/requirements.txt

# 再拷代码(业务代码零修改)
COPY gbt_wallet /app/gbt_wallet
COPY gbt_allinone /app/gbt_allinone

# 非 root 运行 + 数据卷目录
RUN useradd --system --uid 10001 --create-home --home-dir /home/gbtwallet gbtwallet \
    && mkdir -p /data \
    && chown -R gbtwallet:gbtwallet /data /home/gbtwallet

USER gbtwallet

# 容器内监听 0.0.0.0; 对宿主的暴露面由 compose 的端口映射控制(仅 127.0.0.1)
ENV GBT_WALLET_DIR=/data \
    GBT_WALLET_PORT=8097 \
    GBT_WALLET_BIND_HOST=0.0.0.0

VOLUME ["/data"]
EXPOSE 8097

# 健康检查: 设置了 GBT_WALLET_API_TOKEN 时自动带 Bearer 头
HEALTHCHECK --interval=30s --timeout=6s --start-period=25s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request as u;t=os.environ.get('GBT_WALLET_API_TOKEN','');h={'Authorization':'Bearer '+t} if t else {};r=u.urlopen(u.Request('http://127.0.0.1:8097/api/gbtwallet/health',headers=h),timeout=5);raise SystemExit(0 if r.status==200 else 1)"]

CMD ["python", "-m", "gbt_wallet.api", "--host", "0.0.0.0", "--port", "8097"]
