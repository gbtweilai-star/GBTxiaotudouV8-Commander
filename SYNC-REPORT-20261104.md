# 主仓 ↔ payload 同步报告（2026-11-04）

> 由 `tools/codex-scripts/atomic-sync.py` 驱动（原子替换：tmp + os.replace + sha256 双校验 + 备份 + 回执）。


## 一、本次已同步

| 类型 | 数量 | 方式 |
|---|---|---|
| 新增代码模块（主仓缺） | 28 | 原子 `put` |
| 路径修复文件（差异仅路径行） | 102 | 原子 `put` |
| 权重文件（主仓缺） | 10（645.0 MB） | 原子 `put` |
| 定点改动 | 2 | 原子 `patch`（hand_vision makedirs / caps_registry see_camera） |
| 文档 | 2 | AGENTS.md / PROJECT_BLUEPRINT.md |
| 工具 | 1 | tools/codex-scripts/atomic-sync.py |

复核：代码不一致 **0**，权重不一致 **0**。


## 二、尚未处理：实质分叉 137 个（需人工判断，未擅自改）

这些文件两边内容不同，且差异**不只是路径**。整文件覆盖会丢东西，所以一律没动。

| 文件 | payload 行 | 主仓行 | 判断 |
|---|---|---|---|
| `gbt_allinone\api.py` | 3681 | 3451 | payload行数多 |
| `gbt_allinone\brain_exec.py` | 908 | 865 | payload行数多 |
| `gbt_allinone\browser_cap.py` | 191 | 190 | payload行数多 |
| `gbt_allinone\cap_taxonomy.py` | 287 | 287 | payload行数多 |
| `gbt_allinone\caps_registry.py` | 4044 | 3788 | payload行数多 |
| `gbt_allinone\coding_discipline.py` | 279 | 296 | 主仓行数多 |
| `gbt_allinone\cross_scan.py` | 636 | 608 | payload行数多 |
| `gbt_allinone\digital_human.py` | 500 | 499 | payload行数多 |
| `gbt_allinone\heartbeat_tentacle.py` | 1009 | 957 | payload行数多 |
| `gbt_allinone\image_scout.py` | 278 | 277 | payload行数多 |
| `gbt_allinone\install_selfcheck.py` | 231 | 230 | payload行数多 |
| `gbt_allinone\llm\cloud_llm.py` | 1514 | 1547 | 主仓行数多 |
| `gbt_allinone\mirror_space.py` | 359 | 400 | 主仓行数多 |
| `gbt_allinone\omni_plug.py` | 1301 | 1572 | 主仓行数多 |
| `gbt_allinone\security\policy.py` | 1264 | 1326 | 主仓行数多 |
| `gbt_allinone\security\redteam.py` | 1246 | 1245 | payload行数多 |
| `gbt_allinone\tentacle\hand_bridge.py` | 425 | 425 | payload行数多 |
| `gbt_allinone\tentacle\hand_onnx.py` | 122 | 121 | payload行数多 |
| `gbt_allinone\tentacle\hand_onnx_chunked_chain.py` | 194 | 194 | payload行数多 |
| `gbt_allinone\tentacle\hand_pipeline.py` | 166 | 166 | payload行数多 |
| `gbt_allinone\tentacle\hand_realtime.py` | 356 | 355 | payload行数多 |
| `gbt_allinone\tentacle\hand_retarget.py` | 352 | 352 | payload行数多 |
| `gbt_allinone\tentacle\hand_video.py` | 146 | 146 | payload行数多 |
| `gbt_allinone\tentacle\hand_vision.py` | 165 | 164 | payload行数多 |
| `gbt_allinone\tentacle\mirror_stage.py` | 277 | 315 | 主仓行数多 |
| `gbt_allinone\tentacle\pulse_core.py` | 538 | 543 | 主仓行数多 |
| `gbt_allinone\tentacle\trunk_cover.py` | 327 | 329 | 主仓行数多 |
| `gbt_allinone\tests\test_api_probe.py` | 542 | 528 | payload行数多 |
| `gbt_allinone\tests\test_omni_plug.py` | 168 | 172 | 主仓行数多 |
| `gbt_allinone\tests\test_vision_loop.py` | 117 | 74 | payload行数多 |
| `gbt_allinone\thebrain_bridge.py` | 847 | 846 | payload行数多 |
| `gbt_allinone\tools\action_gate.py` | 277 | 276 | payload行数多 |
| `gbt_allinone\tools\actioncam_cap.py` | 164 | 163 | payload行数多 |
| `gbt_allinone\tools\agent_console.py` | 299 | 298 | payload行数多 |
| `gbt_allinone\tools\agent_control.py` | 151 | 150 | payload行数多 |
| `gbt_allinone\tools\agent_council.py` | 294 | 293 | payload行数多 |
| `gbt_allinone\tools\agent_rig.py` | 303 | 302 | payload行数多 |
| `gbt_allinone\tools\anatomy_cap.py` | 271 | 270 | payload行数多 |
| `gbt_allinone\tools\answer_shaper.py` | 135 | 134 | payload行数多 |
| `gbt_allinone\tools\art_brief.py` | 238 | 237 | payload行数多 |
| `gbt_allinone\tools\art_chain.py` | 178 | 177 | payload行数多 |
| `gbt_allinone\tools\automation_keys.py` | 693 | 692 | payload行数多 |
| `gbt_allinone\tools\belief_forge.py` | 230 | 229 | payload行数多 |
| `gbt_allinone\tools\bi_distill.py` | 113 | 112 | payload行数多 |
| `gbt_allinone\tools\bits_kit.py` | 393 | 392 | payload行数多 |
| `gbt_allinone\tools\blender_cap.py` | 118 | 117 | payload行数多 |
| `gbt_allinone\tools\blender_surface.py` | 319 | 318 | payload行数多 |
| `gbt_allinone\tools\cad_distill.py` | 109 | 108 | payload行数多 |
| `gbt_allinone\tools\cadgen_cap.py` | 181 | 180 | payload行数多 |
| `gbt_allinone\tools\cap_tags.py` | 327 | 326 | payload行数多 |
| `gbt_allinone\tools\case_mine.py` | 283 | 282 | payload行数多 |
| `gbt_allinone\tools\code_audit.py` | 418 | 778 | 主仓行数多 |
| `gbt_allinone\tools\code_patch.py` | 313 | 500 | 主仓行数多 |
| `gbt_allinone\tools\comfy_nodes_extra.py` | 2229 | 2276 | 主仓行数多 |
| `gbt_allinone\tools\comfyui_surface.py` | 364 | 408 | 主仓行数多 |
| `gbt_allinone\tools\command_chain.py` | 628 | 627 | payload行数多 |
| `gbt_allinone\tools\console_hub.py` | 347 | 346 | payload行数多 |
| `gbt_allinone\tools\console_pages.py` | 1253 | 1252 | payload行数多 |
| `gbt_allinone\tools\creation_camp.py` | 181 | 180 | payload行数多 |
| `gbt_allinone\tools\db_probe.py` | 266 | 265 | payload行数多 |
| `gbt_allinone\tools\design_atlas.py` | 260 | 259 | payload行数多 |
| `gbt_allinone\tools\desktop_distill.py` | 181 | 180 | payload行数多 |
| `gbt_allinone\tools\devour_fusion.py` | 265 | 264 | payload行数多 |
| `gbt_allinone\tools\dh_brain.py` | 209 | 208 | payload行数多 |
| `gbt_allinone\tools\dh_pose.py` | 328 | 327 | payload行数多 |
| `gbt_allinone\tools\diagram_distill.py` | 151 | 150 | payload行数多 |
| `gbt_allinone\tools\director_mood.py` | 248 | 247 | payload行数多 |
| `gbt_allinone\tools\eigenflux.py` | 550 | 549 | payload行数多 |
| `gbt_allinone\tools\energy_scheduler.py` | 235 | 234 | payload行数多 |
| `gbt_allinone\tools\event_ledger.py` | 191 | 190 | payload行数多 |
| `gbt_allinone\tools\flow_canvas.py` | 200 | 199 | payload行数多 |
| `gbt_allinone\tools\freebuff_term.py` | 342 | 341 | payload行数多 |
| `gbt_allinone\tools\genoffice_cap.py` | 221 | 220 | payload行数多 |
| `gbt_allinone\tools\gods_eye.py` | 1208 | 1207 | payload行数多 |
| `gbt_allinone\tools\growth_hooks.py` | 342 | 341 | payload行数多 |
| `gbt_allinone\tools\gs_h3_cap.py` | 372 | 371 | payload行数多 |
| `gbt_allinone\tools\handoff.py` | 175 | 174 | payload行数多 |
| `gbt_allinone\tools\hf_voice.py` | 391 | 390 | payload行数多 |
| `gbt_allinone\tools\impact_check.py` | 409 | 327 | payload行数多 |
| `gbt_allinone\tools\intake_kit.py` | 539 | 538 | payload行数多 |
| `gbt_allinone\tools\llm_redteam.py` | 259 | 258 | payload行数多 |
| `gbt_allinone\tools\lobehub.py` | 609 | 608 | payload行数多 |
| `gbt_allinone\tools\long_run_supervisor.py` | 316 | 315 | payload行数多 |
| `gbt_allinone\tools\look_grade_cap.py` | 85 | 91 | 主仓行数多 |
| `gbt_allinone\tools\machine_cap.py` | 363 | 362 | payload行数多 |
| `gbt_allinone\tools\machine_distill.py` | 156 | 155 | payload行数多 |
| `gbt_allinone\tools\memory_bank.py` | 311 | 310 | payload行数多 |
| `gbt_allinone\tools\memory_manager.py` | 271 | 270 | payload行数多 |
| `gbt_allinone\tools\motion_kit.py` | 446 | 445 | payload行数多 |
| `gbt_allinone\tools\n8n_wf_cap.py` | 145 | 144 | payload行数多 |
| `gbt_allinone\tools\obsidian_vault.py` | 425 | 424 | payload行数多 |
| `gbt_allinone\tools\offload_distill.py` | 219 | 218 | payload行数多 |
| `gbt_allinone\tools\omni_arm.py` | 159 | 158 | payload行数多 |
| `gbt_allinone\tools\one_shot.py` | 243 | 242 | payload行数多 |
| `gbt_allinone\tools\pentest_distill.py` | 148 | 147 | payload行数多 |
| `gbt_allinone\tools\pod_link.py` | 648 | 649 | 主仓行数多 |
| `gbt_allinone\tools\policy_delta.py` | 147 | 146 | payload行数多 |
| `gbt_allinone\tools\rea_reverse.py` | 246 | 245 | payload行数多 |
| `gbt_allinone\tools\recon_distill.py` | 258 | 257 | payload行数多 |
| `gbt_allinone\tools\scan_scope.py` | 301 | 286 | payload行数多 |
| `gbt_allinone\tools\scrapling_cap.py` | 131 | 130 | payload行数多 |
| `gbt_allinone\tools\sec_sweeper.py` | 456 | 455 | payload行数多 |
| `gbt_allinone\tools\slim_profile.py` | 286 | 285 | payload行数多 |
| `gbt_allinone\tools\spend_guard.py` | 185 | 184 | payload行数多 |
| `gbt_allinone\tools\surface_bind.py` | 370 | 369 | payload行数多 |
| `gbt_allinone\tools\task_manager.py` | 221 | 220 | payload行数多 |
| `gbt_allinone\tools\tentacle_arm.py` | 331 | 330 | payload行数多 |
| `gbt_allinone\tools\train_recipe.py` | 159 | 158 | payload行数多 |
| `gbt_allinone\tools\transformer_cap.py` | 592 | 591 | payload行数多 |
| `gbt_allinone\tools\ui_kit.py` | 284 | 283 | payload行数多 |
| `gbt_allinone\tools\ui_render.py` | 193 | 192 | payload行数多 |
| `gbt_allinone\tools\update_chain.py` | 286 | 317 | 主仓行数多 |
| `gbt_allinone\tools\vision_print.py` | 996 | 995 | payload行数多 |
| `gbt_allinone\tools\zimage_rewash_cap.py` | 253 | 252 | payload行数多 |
| `gbt_allinone\vision_ocr.py` | 247 | 68 | payload行数多 |
| `gbt_allinone\voice_studio.py` | 776 | 775 | payload行数多 |
| `tools\blueprint-land.py` | 68 | 70 | 主仓行数多 |
| `tools\codex-scripts\cf-oauth-check.py` | 95 | 95 | payload行数多 |
| `tools\codex-scripts\dsh-bus.py` | 117 | 117 | payload行数多 |
| `tools\codex-scripts\lark_delete_caches.py` | 138 | 138 | payload行数多 |
| `tools\codex-scripts\lark_inventory.py` | 174 | 174 | payload行数多 |
| `tools\codex-scripts\local-comfy-image.py` | 217 | 195 | payload行数多 |
| `tools\codex-scripts\local-image-endpoint.py` | 230 | 229 | payload行数多 |
| `tools\codex-scripts\project-bind.py` | 216 | 219 | 主仓行数多 |
| `tools\codex-scripts\quick_scan.py` | 2146 | 2147 | 主仓行数多 |
| `tools\codex-scripts\welcome-page.py` | 127 | 139 | 主仓行数多 |
| `tools\console-server.py` | 2859 | 2715 | payload行数多 |
| `tools\context_guard.py` | 374 | 376 | 主仓行数多 |
| `tools\digihuman\dh-live.py` | 378 | 378 | payload行数多 |
| `tools\digihuman\dh-puppet.py` | 266 | 266 | payload行数多 |
| `tools\digihuman\gpu-avatar.py` | 204 | 204 | payload行数多 |
| `tools\digihuman\motion-publish.py` | 323 | 323 | payload行数多 |
| `tools\i2v_agnes.py` | 219 | 218 | payload行数多 |
| `tools\model-bridge\body.py` | 257 | 190 | payload行数多 |
| `tools\model-bridge\hand_onnx_chunk_worker.py` | 63 | 63 | payload行数多 |
| `tools\omni_adapter.py` | 291 | 303 | 主仓行数多 |
| `tools\page_lazy.py` | 235 | 237 | 主仓行数多 |

**其中主仓明显更新的（优先参考主仓，别用 payload 覆盖）：**

- `gbt_allinone\tools\code_audit.py`：payload 418 行 / 主仓 778 行（主仓行数多）
- `gbt_allinone\omni_plug.py`：payload 1301 行 / 主仓 1572 行（主仓行数多）
- `gbt_allinone\tools\code_patch.py`：payload 313 行 / 主仓 500 行（主仓行数多）
- `gbt_allinone\security\policy.py`：payload 1264 行 / 主仓 1326 行（主仓行数多）

## 三、主仓独有（payload 没有）

共 375 个，含 `gbt_commander/`、`runtime/`、`tests/` 等整块目录。
打包时若只拷 payload，这些不会进产品 —— 需确认它们是否该随包发布。


## 四、已知非产品残渣（语法校验收到的 14 个 FAIL 全是它）

`state/mirror/stage/cp-*/.scratch/t_cp_sample.py` 与 `t_cp_new_bad.py` ——
是 `code_patch` 自测「验证不过就拒」时故意造的坏样本，2026-11-03 遗留。
**不是产品代码，也不是本次改动引入。** 未删，待确认是否清理。
