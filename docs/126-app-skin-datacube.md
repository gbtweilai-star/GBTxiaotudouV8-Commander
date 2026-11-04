# 126 · APP 皮肤：Claude 2026 新版（中性无衬线）

日期：2026-11-02 · 应用：`/console/index.html` · 截图：`claude2026-chat.png`、`claude2026-caps.png`、`claude2026-dash.png`

## 依据
2026-10 新版 Claude 桌面界面（Claude Code desktop / Artifacts 一起改版）：**去掉衬线字体和暖色背景**，改中性冷白、信息密度更高、侧栏动作列表、胶囊输入卡、页签下划线；Artifacts 卡片用浅色底 + 类型图标 + 名称/更新时间在下。
参考：[IT之家报道](https://m.ithome.com/html/1017710.htm)、[TechCrunch：chat 与 cowork 合并](https://techcrunch.com/2026/09/16/anthropic-merges-claude-chat-and-cowork-in-one-interface/)、[改版前后对照](https://www.aiposthub.com/ai-creative-claude-redesign-guide/)。

## 本项目的落地
| 元素 | 新版做法 |
|---|---|
| 字体 | 全站无衬线（Söhne/Inter/system-ui 兜底），标题 600 字重、字号收紧 |
| 底色 | 中性冷白 `#f7f8f9`，卡片纯白，不再有暖纸色 |
| 边框 | 1px `#e6e7ea` 细线，圆角 10–12px，阴影几乎为零 |
| 侧栏 | 动作列表风格：紧凑条目、hover 浅灰、底部小按钮组 |
| 页签 | 纯文字 + 选中黑色下划线（不再用彩色药丸） |
| 输入卡 | 大圆角胶囊 24px、白底细边、模型选择在卡内、深色圆形发送键 |
| 对话 | bot 纯文字、user 浅灰气泡、内容栏 720px、行高 1.72 |
| 仪表盘 | 白卡片，陶土色数据条（修复了原来 span 不显示的问题） |
| 3D 沉浸视图 | 保留自身深色画布，外壳仍是中性白 |

## 通电
不做闪烁：进入页面/切视图时三栏轻微上浮淡入（0.4–0.45s）；`prefers-reduced-motion` 关闭。

## 文件
| 文件 | 作用 |
|---|---|
| `holo_pet_w3/console/skin-cube.css` | 新版主题（令牌 + 侧栏/页签/胶囊输入卡/表格/仪表盘） |
| `holo_pet_w3/console/skin-cube.js` | 进入动效与切视图轻过渡，不注入覆盖层 |
| `holo_pet_w3/console/index.html` | 引入上述两个文件 |

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
