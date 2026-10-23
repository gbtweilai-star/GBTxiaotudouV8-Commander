/* GBT小土豆V8 · 数据库编队数据件 —— **生成产物**，由 db-fleet.py render 覆盖，不许手改。
 * 重生成：py -3.14 tools/codex-scripts/db-fleet.py render
 * 口径：一切来自 deploy/cloud-10/db-fleet.json；额度与稳定性逐条带出处。 */
window.GBT_DB_FLEET = {
 "generated_at": "2026-10-08T00:27:37+08:00",
 "regen": "py -3.14 tools/codex-scripts/db-fleet.py render",
 "check": "py -3.14 tools/codex-scripts/db-fleet.py check",
 "source": "deploy/cloud-10/db-fleet.json（单一真源）",
 "honesty": [
  "🔴 **这些库一个都还没开通**：status 一律是 `未开通`，页面与文档都明写。本文件是**设计 + 指向 + 开通清单**，不是部署凭证。",
  "额度与稳定性**逐条带出处**（sources[] 里有 url 与取证日期 2026-10-07），措辞与官方页一致；官方没写的字段写 null 并说明「官网未列」——不许拿印象补数。",
  "「最稳」是**相对**的：免费档普遍无 SLA。因此本文件把「谁当主库」订成两条硬标准：① 按量计费、不因闲置被暂停 ② 有版本化/回滚面。会因闲置暂停的一律降为备。"
 ],
 "pointers": {
  "note": "指向 = 哪类数据走哪个库。**写入路径单一**：一个数据类只有一个写主，其余是读副本/缓存/归档——双写必冲突，不许两处都能写。",
  "map": [
   {
    "data": "审计账本 · 记录本索引",
    "write_to": "db-neon-pg",
    "read_from": [
     "db-tidb"
    ],
    "why": "审计/账本要能追溯与时间点恢复 ⇒ 主库必须带分支与历史窗口（Neon 免费档 6 小时历史 + 分支）"
   },
   {
    "data": "记忆分片（每实体一个小库）",
    "write_to": "db-turso",
    "read_from": [
     "db-turso"
    ],
    "why": "Turso 免费档 100 库 ⇒ 一个实体一个库、互相隔离；主库只放汇总索引，不放原始分片"
   },
   {
    "data": "边缘热表 · 配置 · 路由表",
    "write_to": "db-d1",
    "read_from": [
     "db-d1"
    ],
    "why": "D1 与现役 Worker 同网络，边缘读延迟最低；只放**能重建**的配置类数据，不放唯一副本"
   },
   {
    "data": "缓存 · 限流计数 · 任务队列",
    "write_to": "db-upstash",
    "read_from": [
     "db-upstash"
    ],
    "why": "Redis 语义（TTL / 原子计数 / 队列）；**只放可丢的数据**，丢了不影响事实"
   },
   {
    "data": "向量（语义检索）",
    "write_to": "db-supabase",
    "read_from": [
     "db-supabase"
    ],
    "why": "pgvector 与 Postgres 同库，做向量最省事；但免费档仅 500MB 且**闲置一周会暂停** ⇒ 只当向量层，绝不当主库"
   },
   {
    "data": "工件 · 帧 · 模型 · 冷归档",
    "write_to": "obj-r2",
    "read_from": [
     "obj-r2"
    ],
    "why": "对象存储不是数据库，但当归档层最合适：10GB 且**出网免费**（回读不花钱）"
   },
   {
    "data": "大表 · 分析型读取",
    "write_to": "db-tidb",
    "read_from": [
     "db-tidb"
    ],
    "why": "行存 + 列存同时在，免费 25GiB ⇒ 扛大表与聚合"
   }
  ]
 },
 "conventions": {
  "env_var": "每库凭据一律走环境变量引用（apiKeyEnv 风格），**配置文件里绝不出现明文密钥**——与本仓 ~/.dsh 的凭据 seam 同一口径。",
  "sql": "🔴 所有 SQL 一律**参数绑定**（? / :name / 驱动占位符）；禁止拼接、format、f-string 组装 SQL。",
  "migration": "建表/改表脚本计划放 deploy/cloud-10/db-fleet.sql（**尚未创建**：没有凭据就先不写死 schema，避免「没开通先自造表结构」）。"
 },
 "sources": [
  {
   "id": "S1",
   "on": "db-d1",
   "name": "Cloudflare D1 限额官方文档",
   "url": "https://developers.cloudflare.com/d1/platform/limits/",
   "fetched": "2026-10-07",
   "quote": "Max database size: 500 MB (Free) · Total storage per account: 5 GB (Free) · Max databases per account: 10 (Free)"
  },
  {
   "id": "S2",
   "on": "db-turso",
   "name": "Turso 定价页",
   "url": "https://turso.tech/pricing",
   "fetched": "2026-10-07",
   "quote": "Free: Total storage 5GB · Databases 100 · Rows read per month 500 Million"
  },
  {
   "id": "S3",
   "on": "db-neon-pg",
   "name": "Neon 定价页",
   "url": "https://neon.com/pricing",
   "fetched": "2026-10-07",
   "quote": "Free: Postgres storage 1 GB/project, 20 GB account total · Compute 100 CU-hours/project · Projects 100 · Branches per project 10 · History window 6 hours (1 GB limit) · Scale to zero suspends after 5 min"
  },
  {
   "id": "S4",
   "on": "db-supabase",
   "name": "Supabase 定价页",
   "url": "https://supabase.com/pricing",
   "fetched": "2026-10-07",
   "quote": "Free: 500 MB database size per project · 1 GB file storage · 5 GB egress · Limit of 2 active projects · projects pause after 1 week of inactivity"
  },
  {
   "id": "S5",
   "on": "db-upstash",
   "name": "Upstash 定价页",
   "url": "https://upstash.com/pricing",
   "fetched": "2026-10-07",
   "quote": "Free: Max storage 256 MB · 500K commands per month · Bandwidth 10 GB · up to 10 databases"
  },
  {
   "id": "S6",
   "on": "db-tidb",
   "name": "TiDB Cloud Serverless 产品页",
   "url": "https://www.pingcap.com/tidb-cloud-serverless/",
   "fetched": "2026-10-07",
   "quote": "Free for 25GiB storage and 250 million reads（该页为产品页，未分列行存/列存/请求单元/集群数——这些字段本文件写 null）"
  },
  {
   "id": "S7",
   "on": "obj-r2",
   "name": "Cloudflare R2 定价页",
   "url": "https://developers.cloudflare.com/r2/pricing/",
   "fetched": "2026-10-07",
   "quote": "Free tier: 10 GB-month storage · 1 million Class A requests/month · 10 million Class B requests/month · Egress free"
  }
 ],
 "fleet": [
  {
   "id": "db-neon-pg",
   "provider": "Neon",
   "engine": "Postgres",
   "role": "主库（写主）",
   "rank": "主",
   "endpoint": "（占位 · 未开通：形如 postgresql://<user>:<pw>@<host>/<db>?sslmode=require）",
   "apiKeyEnv": "GBT_DB_NEON_URL",
   "quota": {
    "account_storage": "20 GB",
    "per_project_storage": "1 GB",
    "projects": 100,
    "compute": "100 CU-hours/项目",
    "branches_per_project": 10
   },
   "quota_source": "S3",
   "stability": {
    "why": "① 免费档带**分支 + 6 小时历史窗口**（回滚面真实存在）② 计费到上限只挂起计算、不删数据 ③ 每次改动态数据前可先开分支 ⇒ 这是全编队里唯一能「改坏了退回去」的关系库",
    "来源": "S3",
    "caveat": "scale-to-zero：闲置 5 分钟后挂起，下一次连接有冷启动（官网未给具体秒数，故本文件不写数）"
   },
   "points_at": [
    "审计账本 · 记录本索引"
   ],
   "stores": "**存**：审计账本、记录本索引、跨实体关系表、需要「改前先分支」的关键表。**不存**：原始大对象（走 obj-r2）、可丢缓存（走 db-upstash）。**生命周期**：长期，编队里的事实主库。",
   "binds": [
    "db-tidb",
    "db-turso",
    "obj-r2"
   ],
   "needs": {
    "缺什么": "Neon 账号 + 一个 project + 连接串",
    "谁有权给": "主人（注册/授权）",
    "开通后要做什么": "把连接串放进环境变量 GBT_DB_NEON_URL（**不写进任何仓内文件**）"
   },
   "status": "未开通"
  },
  {
   "id": "db-tidb",
   "provider": "TiDB Cloud",
   "engine": "MySQL 兼容（Serverless）",
   "role": "备主库 · 大表/分析",
   "rank": "主",
   "endpoint": "（占位 · 未开通）",
   "apiKeyEnv": "GBT_DB_TIDB_URL",
   "quota": {
    "storage": "25 GiB（官网用语：Free for 25GiB storage）",
    "reads": "250 million reads",
    "row_storage": null,
    "columnar_storage": null,
    "request_units": null,
    "clusters": null
   },
   "quota_source": "S6",
   "stability": {
    "why": "额度是这批里**最大**的（25GiB）；MySQL 兼容 ⇒ 迁移面窄、工具多；行存 + 列存同时在，聚合查询不必另建数仓。",
    "来源": "S6",
    "caveat": "该页是产品页，未列行/列存分项、请求单元与集群上限（相应字段写 null，**不补数**）；免费档实际条款以控制台为准，**未取证**。"
   },
   "points_at": [
    "大表 · 分析型读取",
    "审计账本（只读副本）"
   ],
   "stores": "**存**：大表与分析型数据、审计账本的只读副本（供聚合查询，避免压主库）。**不存**：写主职责（写主是 db-neon-pg——单一写入口）。**生命周期**：长期；换主时它可顶上。",
   "binds": [
    "db-neon-pg",
    "obj-r2"
   ],
   "needs": {
    "缺什么": "TiDB Cloud 账号 + 一个 Serverless 集群 + 连接串",
    "谁有权给": "主人",
    "开通后要做什么": "连接串进 GBT_DB_TIDB_URL；再建一条从主库到它的**单向**同步"
   },
   "status": "未开通"
  },
  {
   "id": "db-turso",
   "provider": "Turso",
   "engine": "libSQL（SQLite）",
   "role": "记忆分片编队（百库）",
   "rank": "主",
   "endpoint": "（占位 · 未开通：形如 libsql://<db>-<org>.turso.io）",
   "apiKeyEnv": "GBT_DB_TURSO_TOKEN",
   "quota": {
    "total_storage": "5 GB",
    "databases": 100,
    "rows_read_per_month": "500 million"
   },
   "quota_source": "S2",
   "stability": {
    "why": "**100 个库**是它的核心价值：每个实体/触手一个小库，坏一个不牵连全体；SQLite 语义简单、没有连接池地狱；带边缘复制。",
    "来源": "S2",
    "caveat": "定价页未给**单库**容量上限——以控制台为准（本文件不猜）。"
   },
   "points_at": [
    "记忆分片（每实体一个小库）"
   ],
   "stores": "**存**：每个实体/触手的**自有记忆分片**（一实体一库，互不越界）。**不存**：全局唯一的账本事实（那是主库的事）、大对象。**生命周期**：与实体同生命周期；实体注销则整库归档到 obj-r2 后再删。",
   "binds": [
    "db-neon-pg",
    "db-d1"
   ],
   "needs": {
    "缺什么": "Turso 账号 + 组织 + API token（一 token 可管多库）",
    "谁有权给": "主人",
    "开通后要做什么": "token 进 GBT_DB_TURSO_TOKEN；先只开 3~5 个库验通，再放量到 100"
   },
   "status": "未开通"
  },
  {
   "id": "db-d1",
   "provider": "Cloudflare",
   "engine": "D1（SQLite）",
   "role": "边缘热表 · 配置 · 路由",
   "rank": "备",
   "endpoint": "（占位 · 未开通：与现役 Worker 同账号，走 binding 而不是公网地址）",
   "apiKeyEnv": "CLOUDFLARE_API_TOKEN",
   "quota": {
    "per_database": "500 MB",
    "account_storage": "5 GB",
    "databases": 10
   },
   "quota_source": "S1",
   "stability": {
    "why": "与现役 Worker（gbt-potato-cloud-10）**同一个账号同一张网**，边缘读延迟最低、不跨网出口；维度小、重建容易。",
    "来源": "S1",
    "caveat": "**只放能重建的数据**：配置/路由/映射表。唯一副本不许放这里（免费档无 SLA）。"
   },
   "points_at": [
    "边缘热表 · 配置 · 路由表"
   ],
   "stores": "**存**：云插件路由表、开关配置、需要边缘低延迟读的映射表（**全部可从主库重建**）。**不存**：唯一事实、审计账本原档。**生命周期**：可随时整库重建——丢了不算事故。",
   "binds": [
    "db-neon-pg",
    "db-turso",
    "db-upstash"
   ],
   "needs": {
    "缺什么": "Cloudflare API token（现役 Worker 已在该账号下）+ 建 1~10 个 D1 库",
    "谁有权给": "主人（token 权限里要有 D1 编辑权）",
    "开通后要做什么": "先建 1 个库放路由表，验通再复制到其余"
   },
   "status": "未开通"
  },
  {
   "id": "db-upstash",
   "provider": "Upstash",
   "engine": "Redis（Serverless）",
   "role": "缓存 · 限流 · 队列",
   "rank": "备",
   "endpoint": "（占位 · 未开通：形如 https://<db>.upstash.io）",
   "apiKeyEnv": "GBT_DB_UPSTASH_TOKEN",
   "quota": {
    "storage": "256 MB",
    "commands_per_month": "500K",
    "bandwidth": "10 GB",
    "databases": 10
   },
   "quota_source": "S5",
   "stability": {
    "why": "真正按量的无服务器 Redis：TTL / 原子计数 / 队列这些**本来就不该落关系库**的东西交给它，主库因此能瘦下来。",
    "来源": "S5",
    "caveat": "256MB 很小，且**只放可丢的数据**：缓存冷暖不影响任何事实。"
   },
   "points_at": [
    "缓存 · 限流计数 · 任务队列"
   ],
   "stores": "**存**：热缓存、限流计数、待办队列（**全是可丢的**）。**不存**：任何唯一事实。**生命周期**：随时可清空——清了只影响速度，不影响正确性。",
   "binds": [
    "db-d1",
    "db-neon-pg"
   ],
   "needs": {
    "缺什么": "Upstash 账号 + 一个 Redis 库（REST token）",
    "谁有权给": "主人",
    "开通后要做什么": "token 进 GBT_DB_UPSTASH_TOKEN"
   },
   "status": "未开通"
  },
  {
   "id": "db-supabase",
   "provider": "Supabase",
   "engine": "Postgres + pgvector（含对象存储）",
   "role": "向量层（降为备）",
   "rank": "备",
   "endpoint": "（占位 · 未开通：形如 https://<ref>.supabase.co）",
   "apiKeyEnv": "GBT_DB_SUPABASE_KEY",
   "quota": {
    "database": "500 MB",
    "file_storage": "1 GB",
    "egress": "5 GB",
    "projects": 2
   },
   "quota_source": "S4",
   "stability": {
    "why": "**唯一优势**：pgvector 与 Postgres 同库，做语义检索不必另搭一套。",
    "来源": "S4",
    "caveat": "🔴 **最不稳的一条**：官网写明免费项目**闲置 1 周会被暂停**，且只给 2 个活跃项目 ⇒ **绝不能当主库**，只能当向量层；它若被暂停，检索要降级成「无结果」而不是报错（调用方必须能接受）。"
   },
   "points_at": [
    "向量（语义检索）"
   ],
   "stores": "**存**：文本/图像的向量与索引（**可由原文重建**——丢了能重算）。**不存**：原文（原文在主库与 obj-r2）。**生命周期**：随时可重建；被暂停只影响检索，不影响事实。",
   "binds": [
    "db-neon-pg",
    "obj-r2"
   ],
   "needs": {
    "缺什么": "Supabase 账号 + 1 个 project + 开 vector 扩展",
    "谁有权给": "主人",
    "开通后要做什么": "先跑一次「重建索引」的小批验证，确认免费档 pgvector 真能用（**这一点本文件未取证**）"
   },
   "status": "未开通"
  },
  {
   "id": "obj-r2",
   "provider": "Cloudflare",
   "engine": "R2（对象存储，不是数据库）",
   "role": "归档层（工件/帧/模型/备份）",
   "rank": "备",
   "endpoint": "（占位 · 未开通）",
   "apiKeyEnv": "CLOUDFLARE_API_TOKEN",
   "quota": {
    "storage": "10 GB-month",
    "class_a_ops": "100 万/月",
    "class_b_ops": "1000 万/月",
    "egress": "免费"
   },
   "quota_source": "S7",
   "stability": {
    "why": "**出网免费**是关键：归档层最怕「存得起、取不起」，R2 把回读成本清零 ⇒ 适合当冷归档与备份落点。",
    "来源": "S7",
    "caveat": "只覆盖 Standard 存储档；请求数超了要计费（写密集的大型导入要注意）。"
   },
   "points_at": [
    "工件 · 帧 · 模型 · 冷归档"
   ],
   "stores": "**存**：工件、触手帧、模型文件、数据库冷备份（含被归档的实体分片）。**不存**：需要事务/查询的东西（它是对象存储）。**生命周期**：最冷一层，保留策略由主人定。",
   "binds": [
    "db-neon-pg",
    "db-turso",
    "db-tidb"
   ],
   "needs": {
    "缺什么": "Cloudflare 账号开启 R2（现役 Worker 同账号）+ 一个 bucket",
    "谁有权给": "主人",
    "开通后要做什么": "先建 bucket 与一条「最小权限」的 token，专用于归档"
   },
   "status": "未开通"
  }
 ],
 "totals": {
  "库": 7,
  "主": 3,
  "备": 4,
  "指向": 7,
  "未开通": 7
 }
};
