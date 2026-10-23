/* GBT小土豆V8 · 记录本数据件 —— **生成产物**，由 logbook.py render 覆盖，不许手改。
 * 重生成：py -3.14 tools/codex-scripts/logbook.py render
 * 口径：只追加 + 自链哈希；数字全部现算自 state/logbook.jsonl。 */
window.GBT_LOGBOOK = {
 "generated_at": "2026-10-23T22:21:45+08:00",
 "regen": "py -3.14 tools/codex-scripts/logbook.py render",
 "source": "state/logbook.jsonl（只追加 · 自链哈希）",
 "chain": {
  "ok": false,
  "detail": "第 741 行的 prev_hash 与上一行的 hash 不接（被改过或被插过行）",
  "records": 929
 },
 "totals": {
  "records": 929,
  "scans": 30,
  "changes": 708,
  "decisions": 21,
  "delivers": 113
 },
 "scans": [
  {
   "n": 2,
   "ts": "2026-10-07T22:16:15+08:00",
   "label": "首扫 · 建基线",
   "scanned": 148692,
   "unchanged": 0,
   "added": 148692,
   "modified": 0,
   "deleted": 0,
   "baseline": true,
   "truncated": false,
   "samples": {
    "added": [
     ".agents/skills/better-auth-best-practices/SKILL.md",
     ".agents/skills/chrome-extensions/SKILL.md",
     ".agents/skills/chrome-extensions/references/extensions/api-calling.md",
     ".agents/skills/chrome-extensions/references/extensions/auth-identity.md",
     ".agents/skills/chrome-extensions/references/extensions/content-scripts.md",
     ".agents/skills/chrome-extensions/references/extensions/context-menus.md",
     ".agents/skills/chrome-extensions/references/extensions/csp-sandbox.md",
     ".agents/skills/chrome-extensions/references/extensions/declarative-net-request.md",
     ".agents/skills/chrome-extensions/references/extensions/devtools.md",
     ".agents/skills/chrome-extensions/references/extensions/icons.md",
     ".agents/skills/chrome-extensions/references/extensions/media-capture.md",
     ".agents/skills/chrome-extensions/references/extensions/message-passing.md",
     ".agents/skills/chrome-extensions/references/extensions/omnibox.md",
     ".agents/skills/chrome-extensions/references/extensions/permissions.md",
     ".agents/skills/chrome-extensions/references/extensions/popup-ui.md",
     ".agents/skills/chrome-extensions/references/extensions/prompt-api.md",
     ".agents/skills/chrome-extensions/references/extensions/service-worker.md",
     ".agents/skills/chrome-extensions/references/extensions/side-panel.md",
     ".agents/skills/chrome-extensions/references/extensions/storage.md",
     ".agents/skills/chrome-extensions/references/extensions/tab-management.md",
     ".agents/skills/chrome-extensions/references/extensions/user-scripts.md",
     ".agents/skills/chrome-extensions/references/webstore/chromewebstore-template.md",
     ".agents/skills/chrome-extensions/references/webstore/privacy-policy.md",
     ".agents/skills/chrome-extensions/references/webstore/review-checklist.md",
     ".agents/skills/chrome-extensions/references/webstore/store-listing.md",
     ".agents/skills/create-auth/SKILL.md",
     ".agents/skills/fc-nginx-website/.bundled-hash",
     ".agents/skills/fc-nginx-website/SKILL.md",
     ".agents/skills/modern-web-guidance/SKILL.md",
     ".agents/skills/modern-web-guidance/guides/accessibility/accessibility.md",
     ".agents/skills/modern-web-guidance/guides/accessibility/accessible-error-announcement.md",
     ".agents/skills/modern-web-guidance/guides/built-in-ai/language-detection.md",
     ".agents/skills/modern-web-guidance/guides/built-in-ai/language-model.md",
     ".agents/skills/modern-web-guidance/guides/built-in-ai/prompt-api.md",
     ".agents/skills/modern-web-guidance/guides/built-in-ai/summarizer.md",
     ".agents/skills/modern-web-guidance/guides/built-in-ai/translator.md",
     ".agents/skills/modern-web-guidance/guides/css/animate-to-intrinsic-sizes.md",
     ".agents/skills/modern-web-guidance/guides/css/calculate-with-intrinsic-sizes.md",
     ".agents/skills/modern-web-guidance/guides/css/child-state-based-styling.md",
     ".agents/skills/modern-web-guidance/guides/css/content-based-styling.md"
    ],
    "modified": [],
    "deleted": []
   }
  },
  {
   "n": 5,
   "ts": "2026-10-07T22:22:17+08:00",
   "label": "本轮改动扫描",
   "scanned": 148699,
   "unchanged": 148686,
   "added": 7,
   "modified": 6,
   "deleted": 0,
   "baseline": false,
   "truncated": false,
   "samples": {
    "added": [
     "holo_pet_w3/blueprint/blueprint-data.js",
     "holo_pet_w3/blueprint/index.html",
     "holo_pet_w3/logbook/index.html",
     "holo_pet_w3/logbook/logbook-data.js",
     "state/logbook-digest.md",
     "state/logbook-snapshot.json",
     "tools/codex-scripts/blueprint-feed.py"
    ],
    "modified": [
     "PROJECT_BLUEPRINT.md",
     "holo_pet_w3/package.json",
     "holo_pet_w3/panel/index.html",
     "holo_pet_w3/shell/windows.json",
     "state/logbook.jsonl",
     "tools/codex-scripts/logbook.py"
    ],
    "deleted": []
   }
  },
  {
   "n": 8,
   "ts": "2026-10-07T22:43:26+08:00",
   "label": "交付后扫描",
   "scanned": 148790,
   "unchanged": 148679,
   "added": 91,
   "modified": 20,
   "deleted": 0,
   "baseline": false,
   "truncated": false,
   "samples": {
    "added": [
     "dist/win-unpacked/resources/app/blueprint/blueprint-data.js",
     "dist/win-unpacked/resources/app/blueprint/index.html",
     "dist/win-unpacked/resources/app/brain/caps/action_gate.html",
     "dist/win-unpacked/resources/app/brain/caps/actioncam.html",
     "dist/win-unpacked/resources/app/brain/caps/agent_console.html",
     "dist/win-unpacked/resources/app/brain/caps/agent_control.html",
     "dist/win-unpacked/resources/app/brain/caps/agent_council.html",
     "dist/win-unpacked/resources/app/brain/caps/agent_rig.html",
     "dist/win-unpacked/resources/app/brain/caps/answer_shaper.html",
     "dist/win-unpacked/resources/app/brain/caps/asset_index.html",
     "dist/win-unpacked/resources/app/brain/caps/audio_extract.html",
     "dist/win-unpacked/resources/app/brain/caps/audio_mix.html",
     "dist/win-unpacked/resources/app/brain/caps/automation_keys.html",
     "dist/win-unpacked/resources/app/brain/caps/belief_forge.html",
     "dist/win-unpacked/resources/app/brain/caps/blender.html",
     "dist/win-unpacked/resources/app/brain/caps/brain_council.html",
     "dist/win-unpacked/resources/app/brain/caps/cap_tags.html",
     "dist/win-unpacked/resources/app/brain/caps/case_mine.html",
     "dist/win-unpacked/resources/app/brain/caps/claude_code.html",
     "dist/win-unpacked/resources/app/brain/caps/cli_chat.html",
     "dist/win-unpacked/resources/app/brain/caps/code_audit.html",
     "dist/win-unpacked/resources/app/brain/caps/codebuddy.html",
     "dist/win-unpacked/resources/app/brain/caps/collab_gateway.html",
     "dist/win-unpacked/resources/app/brain/caps/comfyui.html",
     "dist/win-unpacked/resources/app/brain/caps/command_chain.html",
     "dist/win-unpacked/resources/app/brain/caps/console_hub.html",
     "dist/win-unpacked/resources/app/brain/caps/console_pages.html",
     "dist/win-unpacked/resources/app/brain/caps/control_loop.html",
     "dist/win-unpacked/resources/app/brain/caps/creation_camp.html",
     "dist/win-unpacked/resources/app/brain/caps/datakit.html",
     "dist/win-unpacked/resources/app/brain/caps/db_probe.html",
     "dist/win-unpacked/resources/app/brain/caps/devour_fusion.html",
     "dist/win-unpacked/resources/app/brain/caps/edit_pipeline.html",
     "dist/win-unpacked/resources/app/brain/caps/energy_scheduler.html",
     "dist/win-unpacked/resources/app/brain/caps/event_ledger.html",
     "dist/win-unpacked/resources/app/brain/caps/filmkit.html",
     "dist/win-unpacked/resources/app/brain/caps/flow_canvas.html",
     "dist/win-unpacked/resources/app/brain/caps/freebuff_term.html",
     "dist/win-unpacked/resources/app/brain/caps/freellmapi.html",
     "dist/win-unpacked/resources/app/brain/caps/genoffice.html"
    ],
    "modified": [
     "dist/GBT小土豆V8 0.1.0.exe",
     "dist/builder-debug.yml",
     "dist/win-unpacked/GBT小土豆V8.exe",
     "dist/win-unpacked/resources/app/brain/brain-data.js",
     "dist/win-unpacked/resources/app/package.json",
     "dist/win-unpacked/resources/app/panel/index.html",
     "dist/win-unpacked/resources/app/plugins-mesh/index.html",
     "dist/win-unpacked/resources/app/shell/main.cjs",
     "dist/win-unpacked/resources/app/shell/windows.json",
     "dist/win-unpacked/resources/tools/codex-scripts/desktop-shell-guard.py",
     "holo_pet_w3/blueprint/blueprint-data.js",
     "holo_pet_w3/blueprint/index.html",
     "holo_pet_w3/logbook/logbook-data.js",
     "holo_pet_w3/shell/dsh-launch.cjs",
     "holo_pet_w3/shell/windows.json",
     "holo_pet_w3/tests/test_dsh_launch.cjs",
     "state/desktop-install-receipt.json",
     "state/logbook-digest.md",
     "state/logbook-snapshot.json",
     "state/logbook.jsonl"
    ],
    "deleted": []
   }
  },
  {
   "n": 39,
   "ts": "2026-10-08T00:51:36+08:00",
   "label": "Logo 修正后扫描",
   "scanned": 148840,
   "unchanged": 148745,
   "added": 50,
   "modified": 45,
   "deleted": 0,
   "baseline": false,
   "truncated": false,
   "samples": {
    "added": [
     "deploy/cloud-10/db-fleet.json",
     "dist/win-unpacked/resources/app/build/tray-logo-32.png",
     "dist/win-unpacked/resources/app/capabilities/capabilities-data.js",
     "dist/win-unpacked/resources/app/capabilities/index.html",
     "dist/win-unpacked/resources/app/cloud-plugins/cloud-plugins-data.js",
     "dist/win-unpacked/resources/app/cloud-plugins/index.html",
     "dist/win-unpacked/resources/app/cloud-status/cloud-status-data.js",
     "dist/win-unpacked/resources/app/cloud-status/index.html",
     "dist/win-unpacked/resources/app/db-fleet/db-fleet-data.js",
     "dist/win-unpacked/resources/app/db-fleet/index.html",
     "dist/win-unpacked/resources/app/tests/test_tray_logo.cjs",
     "dist/win-unpacked/resources/holo_pet/assets/console/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/gallery/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/home/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/tentacle3d/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/workbench/index.html",
     "docs/免费数据库编队-设计.md",
     "docs/能力审计与自愈回滚-设计.md",
     "gbt_allinone/store/wf_runs/persona-evolve-1791389000844.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791389603714.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791390204755.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791390805937.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791391407785.json",
     "gbt_allinone/store/wf_runs/truth-wf-1791389001454.json",
     "holo_pet_w3/build/tray-logo-32.png",
     "holo_pet_w3/capabilities/capabilities-data.js",
     "holo_pet_w3/capabilities/index.html",
     "holo_pet_w3/db-fleet/db-fleet-data.js",
     "holo_pet_w3/db-fleet/index.html",
     "holo_pet_w3/tests/test_tray_logo.cjs",
     "state/_heal_backup/20261007-231910/brain-data.js",
     "state/_heal_backup/20261007-231910/manifest.json",
     "state/_heal_backup/20261007-232034/brain-data.js",
     "state/_heal_backup/20261007-232034/manifest.json",
     "state/_heal_backup/20261007-232139/brain-data.js",
     "state/_heal_backup/20261007-232139/manifest.json",
     "state/_heal_backup/20261007-232227/logbook-data.js",
     "state/_heal_backup/20261007-232227/logbook-digest.md",
     "state/_heal_backup/20261007-232227/manifest.json",
     "state/_heal_backup/20261007-232510/logbook-data.js"
    ],
    "modified": [
     "dist/GBT小土豆V8 0.1.0.exe",
     "dist/builder-debug.yml",
     "dist/win-unpacked/GBT小土豆V8.exe",
     "dist/win-unpacked/resources/app/activity/index.html",
     "dist/win-unpacked/resources/app/blueprint/blueprint-data.js",
     "dist/win-unpacked/resources/app/blueprint/index.html",
     "dist/win-unpacked/resources/app/brain/brain-data.js",
     "dist/win-unpacked/resources/app/logbook/index.html",
     "dist/win-unpacked/resources/app/logbook/logbook-data.js",
     "dist/win-unpacked/resources/app/package.json",
     "dist/win-unpacked/resources/app/panel/index.html",
     "dist/win-unpacked/resources/app/plugins-mesh/index.html",
     "dist/win-unpacked/resources/app/shell/chrome.cjs",
     "dist/win-unpacked/resources/app/shell/dsh-launch.cjs",
     "dist/win-unpacked/resources/app/shell/main.cjs",
     "dist/win-unpacked/resources/app/shell/pack-coverage.cjs",
     "dist/win-unpacked/resources/app/shell/windows.json",
     "dist/win-unpacked/resources/app/tests/test_dsh_launch.cjs",
     "gbt_allinone/store/audit.jsonl",
     "gbt_allinone/store/mind_state.json",
     "gbt_allinone/store/schedules.json",
     "holo_pet_w3/activity/index.html",
     "holo_pet_w3/blueprint/blueprint-data.js",
     "holo_pet_w3/blueprint/index.html",
     "holo_pet_w3/brain/brain-data.js",
     "holo_pet_w3/cloud-plugins/cloud-plugins-data.js",
     "holo_pet_w3/cloud-plugins/index.html",
     "holo_pet_w3/cloud-status/cloud-status-data.js",
     "holo_pet_w3/cloud-status/index.html",
     "holo_pet_w3/logbook/index.html",
     "holo_pet_w3/logbook/logbook-data.js",
     "holo_pet_w3/package.json",
     "holo_pet_w3/panel/index.html",
     "holo_pet_w3/plugins-mesh/index.html",
     "holo_pet_w3/shell/chrome.cjs",
     "holo_pet_w3/shell/main.cjs",
     "holo_pet_w3/shell/pack-coverage.cjs",
     "holo_pet_w3/shell/windows.json",
     "state/.bind_watermark",
     "state/asset_bindings.json"
    ],
    "deleted": []
   }
  },
  {
   "n": 43,
   "ts": "2026-10-08T01:35:06+08:00",
   "label": "补缺后扫描",
   "scanned": 148862,
   "unchanged": 148812,
   "added": 22,
   "modified": 28,
   "deleted": 0,
   "baseline": false,
   "truncated": false,
   "samples": {
    "added": [
     "dist/win-unpacked/resources/holo_pet/assets/automation/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/automation/media/demo-cut.mp4",
     "dist/win-unpacked/resources/holo_pet/assets/automation/media/demo-motion.mp4",
     "dist/win-unpacked/resources/holo_pet/assets/automation/media/shortvideo-sample.mp4",
     "dist/win-unpacked/resources/holo_pet/assets/console3d/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/freebuff/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/godview/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/health-panel/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/keys/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/music/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/structure/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/task-manager/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/wf-film/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/wf-movie/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/wf-music/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/wf-short-video/index.html",
     "gbt_allinone/store/wf_runs/persona-evolve-1791392009465.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791392610378.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791393211592.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791393813153.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791394414452.json",
     "gbt_allinone/store/wf_runs/truth-wf-1791392610387.json"
    ],
    "modified": [
     "dist/GBT小土豆V8 0.1.0.exe",
     "dist/builder-debug.yml",
     "dist/win-unpacked/GBT小土豆V8.exe",
     "dist/win-unpacked/resources/app/capabilities/capabilities-data.js",
     "dist/win-unpacked/resources/app/capabilities/index.html",
     "dist/win-unpacked/resources/app/code-deck/index.html",
     "dist/win-unpacked/resources/app/exec-deck/index.html",
     "dist/win-unpacked/resources/app/logbook/logbook-data.js",
     "dist/win-unpacked/resources/app/package.json",
     "dist/win-unpacked/resources/app/panel/index.html",
     "gbt_allinone/store/audit.jsonl",
     "gbt_allinone/store/mind_state.json",
     "gbt_allinone/store/schedules.json",
     "holo_pet_w3/capabilities/capabilities-data.js",
     "holo_pet_w3/capabilities/index.html",
     "holo_pet_w3/code-deck/index.html",
     "holo_pet_w3/exec-deck/index.html",
     "holo_pet_w3/logbook/logbook-data.js",
     "holo_pet_w3/package.json",
     "holo_pet_w3/panel/index.html",
     "state/.bind_watermark",
     "state/asset_bindings.jsonl",
     "state/capability-audit.json",
     "state/desktop-install-receipt.json",
     "state/logbook-digest.md",
     "state/logbook-snapshot.json",
     "state/logbook.jsonl",
     "tools/codex-scripts/capability-audit.py"
    ],
    "deleted": []
   }
  },
  {
   "n": 45,
   "ts": "2026-10-08T02:11:19+08:00",
   "label": "装插件后扫描",
   "scanned": 153867,
   "unchanged": 148838,
   "added": 5005,
   "modified": 24,
   "deleted": 0,
   "baseline": false,
   "truncated": false,
   "samples": {
    "added": [
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.json",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/000d1d7a5293eb9f888a9fab29d23d571d794eafb21b1095972c4c8ca464a1f8.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/002d501d459774d3a6d9522f932c32e80727dd5263d69ec7bc85eeead653564f.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/00340d3c596ebd4a1ac2a5cdd436c0ea0294cdb2ead58e769b132a3e1f7df9d1.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/0035eac214eddef9f74d565cebb6424438b259f70bc7a426a7c5ac0fd1c0df86.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/0059c3829eed5f8ef6dc9b192a485b9b200d94fa2f541d8b667fde1d9ebdfb41.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/006c577af4a567e7a248aa75e6488ff2344e42f849387dea9c9cec27d2307a91.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/007a15026f968e590121a8eef4b287cf474c9622ad26cc308c18581c71047c42.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/007b4b89baa4004e79182662bbed0d5a0d56d5d716c3656fc0afd3e7504d58d2.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/007cc7ec491eb18f26d070617a317f2f27e3abef9874dedcfd9c5007e8980212.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/008075dc2b02e08305951cc71aacc3bb26a7c70d95f136de7bf842346ff13d34.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/00a997b69817600c4fef5b50fc7a3ba759c98859d7035960f0e97dd9dd0be930.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/00bd622fb1b8617f71f81f3c6c26b8f5dafb1fdef8ad9d64a39c4e82a80b5c1b.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/00c373751ecac2af46ae6f9d15f19d291025c02824f75161f74099731a907f59.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/00c72231bd3e8dad9c794af5d3f4bead6c69cadabc3bba8b8f079ff190f8b71f.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/00ecb14674de2a31266e74fab2d582b8d1ff7935d7b89b1f1621aea933bcc403.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/00f4de6643d6065f4ecc7f8aee61d5d6771d57359fac9188ed51ada4123ec724.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/0103584c2098c2caa90cd8a93487cfed3f5ce830bee897c7c3b2473706c3d5e1.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/01165b6edf79bcf114d244187d344166dd8ed93442d6aef541f4ef43f0917e44.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/012bd494116619a23f3729af54a818c869845eebccfa00ef0b34d0d92c217ad7.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/013333854076fc2243f5e5402103c11501d29396d18dc04aa2b1d484d93b2760.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/013465f20f19916a1b609e15c13f2e4f79c1cafe3ccc71a444e5059a62bc887d.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/0136beca2768521d41d90b629bcdd0c94da8c0a9f7b273777e46cd5981c2bc26.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/0137ade5eb2187d96429382e173bbe1390013dc4e6e34d2564c65a2cb2f8103b.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/0153bd504aa91171d586f6238220bbe116af3064173d860197ad7d3dce4f0bd7.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/0155420a890eecfdda5ac841ab3a00ae222af096bfa55d0dd2662d65e1efd7ed.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/016c6a4ec80f02ff19cc581187f9f6505be21b801b020ecb19242242f2e76972.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/0177bc2bbeaf8a14ada614b4594ce62a0fd25d7ac25a1f797a9e635c8ff5f5aa.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/019c13bf605be2c0e715ca8e988d8b8621bc2df4d27870afeb5287f0bbdb6615.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/01a30b6bef6e4522c85ea310202680a82d03c644090a305b36776304560ad284.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/01a897419c2fd4254d5c0523d972e667a6484bab3a23b31600fd6df3b7418b29.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/01bb6e6084c5ace0e086153dc2ff75a7e20288e0e622e2587286a75bc65e14ed.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/01c6833c64cc24374f10a30c0e4adcf0b73f542766a4a12de3480859b645793e.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/01cd4997a3f3d4b2d1ea8322e27bc293668ccb1207fea054693c981e62565c04.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/01f30b068d6946223fd532e2e863d87d0f23ed4d2c2eed37f8e659bdbd1b7ec1.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/01faf8c8e1c8085f65b17108b9d404ef26c884d106b88be86ee214d93cf1bdf4.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/02062b9402afa749976a962d55149fd646a23904be37c1d0eb74f76f080fb5bb.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/0208c5028c7962c45e0d08f22480dd1d92f97cce8245e59528c16968a6b3ef2f.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/0208e6a8f814e64205086ef0283bac2b0109dce466ff7045fe636b11841adf19.source",
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.muyf4gpd-22484-4f977af47b.baseline/02395cf874ec3029b71d3a4479ac3f2a865e9c0dc769dc7c2ebe1d2b703d87f8.source"
    ],
    "modified": [
     ".mimosa/hook-state/sess_5a8db557-9503-45f2-93f7-b78e52307780.continue.json",
     ".video_agent/plugin_root",
     "gbt_allinone/store/action_guard/8873ff196337146d1d88d6299d6e337ab085c5ab6f3d8cad15a1d52dbc640cbd.json",
     "gbt_allinone/store/audit.jsonl",
     "gbt_allinone/store/devour_state.json",
     "gbt_allinone/store/mind_state.json",
     "gbt_allinone/store/schedules.json",
     "holo_pet/assets/keys/index.html",
     "holo_pet_w3/logbook/logbook-data.js",
     "state/.bind_watermark",
     "state/asset_bindings.jsonl",
     "state/coverage_matrix.json",
     "state/cross_scan_trace.jsonl",
     "state/devour_fusion.json",
     "state/evolution.jsonl",
     "state/gods_eye.json",
     "state/gods_eye_decisions.jsonl",
     "state/gods_eye_loop.jsonl",
     "state/gods_eye_plan.jsonl",
     "state/logbook-digest.md",
     "state/logbook-snapshot.json",
     "state/logbook.jsonl",
     "state/shortboard.json",
     "state/tasks_advance.jsonl"
    ],
    "deleted": []
   }
  },
  {
   "n": 46,
   "ts": "2026-10-08T02:14:35+08:00",
   "label": "排除工具状态后复扫",
   "scanned": 62515,
   "unchanged": 62481,
   "added": 3,
   "modified": 31,
   "deleted": 91355,
   "baseline": false,
   "truncated": false,
   "samples": {
    "added": [
     ".scratch/_probe_run_0109.log",
     "gbt_allinone/store/transfer_cache.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791396823467.json"
    ],
    "modified": [
     "gbt_allinone/store/action_guard/58f0097d40cd3ec90b94ee7033f4e3ee62b585f6ad8334c66c70ba6bc4a8dba9.json",
     "gbt_allinone/store/action_guard/8d82f45cbf1617bc4afbc60f1ffa149efd59b268b52c482ae8c863064512ba73.json",
     "gbt_allinone/store/audit.jsonl",
     "gbt_allinone/store/health/coze_mail/events.jsonl",
     "gbt_allinone/store/mind_state.json",
     "gbt_allinone/store/schedules.json",
     "holo_pet/assets/console/index.html",
     "holo_pet/assets/freebuff/index.html",
     "holo_pet/assets/gallery/index.html",
     "holo_pet/assets/home/index.html",
     "holo_pet/assets/tentacle3d/index.html",
     "holo_pet/assets/wf-film/index.html",
     "holo_pet/assets/wf-movie/index.html",
     "holo_pet/assets/wf-music/index.html",
     "holo_pet/assets/wf-short-video/index.html",
     "holo_pet/assets/workbench/index.html",
     "state/.bind_watermark",
     "state/asset_bindings.jsonl",
     "state/cap_tags.json",
     "state/cap_tags.jsonl",
     "state/code_audit.jsonl",
     "state/code_audit_findings.json",
     "state/console_pages.jsonl",
     "state/control_loop.jsonl",
     "state/devour_fusion.json",
     "state/evolution.jsonl",
     "state/logbook-snapshot.json",
     "state/logbook.jsonl",
     "state/shortboard.json",
     "state/task_manager.json",
     "tools/codex-scripts/logbook.py"
    ],
    "deleted": [
     ".claude/skills/better-auth-best-practices/SKILL.md",
     ".claude/skills/chrome-extensions/SKILL.md",
     ".claude/skills/chrome-extensions/references/extensions/api-calling.md",
     ".claude/skills/chrome-extensions/references/extensions/auth-identity.md",
     ".claude/skills/chrome-extensions/references/extensions/content-scripts.md",
     ".claude/skills/chrome-extensions/references/extensions/context-menus.md",
     ".claude/skills/chrome-extensions/references/extensions/csp-sandbox.md",
     ".claude/skills/chrome-extensions/references/extensions/declarative-net-request.md",
     ".claude/skills/chrome-extensions/references/extensions/devtools.md",
     ".claude/skills/chrome-extensions/references/extensions/icons.md",
     ".claude/skills/chrome-extensions/references/extensions/media-capture.md",
     ".claude/skills/chrome-extensions/references/extensions/message-passing.md",
     ".claude/skills/chrome-extensions/references/extensions/omnibox.md",
     ".claude/skills/chrome-extensions/references/extensions/permissions.md",
     ".claude/skills/chrome-extensions/references/extensions/popup-ui.md",
     ".claude/skills/chrome-extensions/references/extensions/prompt-api.md",
     ".claude/skills/chrome-extensions/references/extensions/service-worker.md",
     ".claude/skills/chrome-extensions/references/extensions/side-panel.md",
     ".claude/skills/chrome-extensions/references/extensions/storage.md",
     ".claude/skills/chrome-extensions/references/extensions/tab-management.md",
     ".claude/skills/chrome-extensions/references/extensions/user-scripts.md",
     ".claude/skills/chrome-extensions/references/webstore/chromewebstore-template.md",
     ".claude/skills/chrome-extensions/references/webstore/privacy-policy.md",
     ".claude/skills/chrome-extensions/references/webstore/review-checklist.md",
     ".claude/skills/chrome-extensions/references/webstore/store-listing.md",
     ".claude/skills/create-auth/SKILL.md",
     ".claude/skills/modern-web-guidance/SKILL.md",
     ".claude/skills/modern-web-guidance/guides/accessibility/accessibility.md",
     ".claude/skills/modern-web-guidance/guides/accessibility/accessible-error-announcement.md",
     ".claude/skills/modern-web-guidance/guides/built-in-ai/language-detection.md",
     ".claude/skills/modern-web-guidance/guides/built-in-ai/language-model.md",
     ".claude/skills/modern-web-guidance/guides/built-in-ai/prompt-api.md",
     ".claude/skills/modern-web-guidance/guides/built-in-ai/summarizer.md",
     ".claude/skills/modern-web-guidance/guides/built-in-ai/translator.md",
     ".claude/skills/modern-web-guidance/guides/css/animate-to-intrinsic-sizes.md",
     ".claude/skills/modern-web-guidance/guides/css/calculate-with-intrinsic-sizes.md",
     ".claude/skills/modern-web-guidance/guides/css/child-state-based-styling.md",
     ".claude/skills/modern-web-guidance/guides/css/content-based-styling.md",
     ".claude/skills/modern-web-guidance/guides/css/css-layout.md",
     ".claude/skills/modern-web-guidance/guides/css/css.md"
    ]
   }
  },
  {
   "n": 47,
   "ts": "2026-10-08T02:26:08+08:00",
   "label": "排除集变更后重建基线",
   "scanned": 62516,
   "unchanged": 62475,
   "added": 1,
   "modified": 40,
   "deleted": 0,
   "baseline": true,
   "truncated": false,
   "samples": {
    "added": [
     "gbt_allinone/store/wf_runs/persona-evolve-1791397424586.json"
    ],
    "modified": [
     "gbt_allinone/store/action_guard/4563159e80ebf6068c5e1e7d73608811e2e47a3419ef14d27bfd07f06baaf795.json",
     "gbt_allinone/store/action_guard/58f0097d40cd3ec90b94ee7033f4e3ee62b585f6ad8334c66c70ba6bc4a8dba9.json",
     "gbt_allinone/store/action_guard/623abf70cb2963266dd799d9edd93e5c7a6d437042d7cf11429e3538a6f05d01.json",
     "gbt_allinone/store/action_guard/8873ff196337146d1d88d6299d6e337ab085c5ab6f3d8cad15a1d52dbc640cbd.json",
     "gbt_allinone/store/action_guard/8d82f45cbf1617bc4afbc60f1ffa149efd59b268b52c482ae8c863064512ba73.json",
     "gbt_allinone/store/action_guard/bc6e3032204b77e54d7deef062e919d34ed731fea4d4e8d32f75a7574b2203b1.json",
     "gbt_allinone/store/action_guard/bd85c54b2d3e3011d4208123da22a5550b493f796d1167b88c482dd016fb5686.json",
     "gbt_allinone/store/action_guard/d0c3297120232b387530c2c615ecc0d67b5b2195e4d52459c50c6080a8ba0751.json",
     "gbt_allinone/store/action_guard/d3690ee207ba6208d3a0be6188b4b13268d31fba562a1a50559f418af3744c75.json",
     "gbt_allinone/store/action_guard/f75a5df35ad38699c437712d1502f33770769aa02f2416e51e7a4e287bbead9c.json",
     "gbt_allinone/store/audit.jsonl",
     "gbt_allinone/store/devour_state.json",
     "gbt_allinone/store/mind_state.json",
     "gbt_allinone/store/schedules.json",
     "gbt_allinone/store/transfer_cache.json",
     "holo_pet/assets/console/index.html",
     "holo_pet/assets/freebuff/index.html",
     "holo_pet/assets/gallery/index.html",
     "holo_pet/assets/home/index.html",
     "holo_pet/assets/tentacle3d/index.html",
     "holo_pet/assets/wf-film/index.html",
     "holo_pet/assets/wf-movie/index.html",
     "holo_pet/assets/wf-music/index.html",
     "holo_pet/assets/wf-short-video/index.html",
     "holo_pet/assets/workbench/index.html",
     "state/.bind_watermark",
     "state/asset_bindings.jsonl",
     "state/cap_tags.json",
     "state/cap_tags.jsonl",
     "state/console_pages.jsonl",
     "state/control_loop.jsonl",
     "state/devour_fusion.json",
     "state/evolution.jsonl",
     "state/logbook-snapshot.json",
     "state/logbook.jsonl",
     "state/memory_fts.db",
     "state/memory_index_meta.json",
     "state/shortboard.json",
     "state/task_manager.json",
     "tools/codex-scripts/logbook.py"
    ],
    "deleted": []
   }
  },
  {
   "n": 50,
   "ts": "2026-10-08T03:10:26+08:00",
   "label": "全部接入后扫描",
   "scanned": 62521,
   "unchanged": 62480,
   "added": 5,
   "modified": 36,
   "deleted": 0,
   "baseline": false,
   "truncated": false,
   "samples": {
    "added": [
     "gbt_allinone/store/wf_runs/persona-evolve-1791398025790.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791398627160.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791399228668.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791399830433.json",
     "gbt_allinone/store/wf_runs/truth-wf-1791399830458.json"
    ],
    "modified": [
     "dist/GBT小土豆V8 0.1.0.exe",
     "dist/builder-debug.yml",
     "dist/win-unpacked/GBT小土豆V8.exe",
     "dist/win-unpacked/resources/app/capabilities/capabilities-data.js",
     "dist/win-unpacked/resources/app/capabilities/index.html",
     "dist/win-unpacked/resources/app/logbook/logbook-data.js",
     "dist/win-unpacked/resources/app/package.json",
     "dist/win-unpacked/resources/app/panel/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/console/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/freebuff/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/gallery/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/home/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/keys/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/tentacle3d/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/wf-film/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/wf-movie/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/wf-music/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/wf-short-video/index.html",
     "dist/win-unpacked/resources/holo_pet/assets/workbench/index.html",
     "gbt_allinone/store/action_guard/8d82f45cbf1617bc4afbc60f1ffa149efd59b268b52c482ae8c863064512ba73.json",
     "gbt_allinone/store/audit.jsonl",
     "gbt_allinone/store/mind_state.json",
     "gbt_allinone/store/schedules.json",
     "holo_pet_w3/capabilities/capabilities-data.js",
     "holo_pet_w3/capabilities/index.html",
     "holo_pet_w3/eye/frames.js",
     "holo_pet_w3/logbook/logbook-data.js",
     "holo_pet_w3/panel/index.html",
     "state/.bind_watermark",
     "state/asset_bindings.jsonl",
     "state/capability-audit.json",
     "state/desktop-install-receipt.json",
     "state/logbook-digest.md",
     "state/logbook-snapshot.json",
     "state/logbook.jsonl",
     "tools/codex-scripts/capability-audit.py"
    ],
    "deleted": []
   }
  },
  {
   "n": 51,
   "ts": "2026-10-08T04:31:17+08:00",
   "label": "每日扫描",
   "scanned": 62531,
   "unchanged": 62499,
   "added": 11,
   "modified": 21,
   "deleted": 1,
   "baseline": false,
   "truncated": false,
   "samples": {
    "added": [
     "gbt_allinone/store/wf_runs/persona-evolve-1791400433729.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791401034984.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791401636166.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791402237609.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791402839214.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791403440911.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791404042524.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791404644113.json",
     "gbt_allinone/store/wf_runs/truth-wf-1791403440933.json",
     "memory/2026-10-08.md",
     "state/context_spill/ctx-20261008-021609.md"
    ],
    "modified": [
     ".scratch/_probe_run_0109.log",
     "gbt_allinone/store/action_guard/0833b4a909076e9410391054fcc89bf9514e5d3f3255cf60bdb6542c3a386d1f.json",
     "gbt_allinone/store/action_guard/0ee11556c456eee77f0470ae2293f2a53605a9a585147d443bccf10dc865bac3.json",
     "gbt_allinone/store/action_guard/35619b298296939f660abb04bc7ad6812042e28c9c038a5500ed8a8b62b69e6a.json",
     "gbt_allinone/store/action_guard/55e9d0ae13f9d11731e81bf42ce654918a9952772f1d74d0724708d8b8d30d75.json",
     "gbt_allinone/store/action_guard/72d254b6bd2f1829c68e01601fb18f4dce022e4e09ac1d3ba2a5a4bc3c6fb0ed.json",
     "gbt_allinone/store/audit.jsonl",
     "gbt_allinone/store/mind_state.json",
     "gbt_allinone/store/schedules.json",
     "holo_pet_w3/eye/frames.js",
     "holo_pet_w3/logbook/logbook-data.js",
     "state/.bind_watermark",
     "state/asset_bindings.json",
     "state/asset_bindings.jsonl",
     "state/cap_probe_report.json",
     "state/logbook-digest.md",
     "state/logbook-snapshot.json",
     "state/logbook.jsonl",
     "state/task_manager.json",
     "state/transformer_cache.json",
     "state/transformer_ledger.jsonl"
    ],
    "deleted": [
     "gbt_allinone/store/transfer_cache.json"
    ]
   }
  },
  {
   "n": 55,
   "ts": "2026-10-08T06:15:55+08:00",
   "label": "故障排查后扫描",
   "scanned": 62546,
   "unchanged": 62518,
   "added": 15,
   "modified": 13,
   "deleted": 0,
   "baseline": false,
   "truncated": false,
   "samples": {
    "added": [
     "gbt_allinone/store/wf_runs/persona-evolve-1791405245453.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791405846612.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791406447856.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791407049232.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791407650625.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791408252170.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791408853572.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791409457962.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791410058709.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791410660028.json",
     "gbt_allinone/store/wf_runs/persona-evolve-1791411261480.json",
     "gbt_allinone/store/wf_runs/truth-wf-1791407049253.json",
     "gbt_allinone/store/wf_runs/truth-wf-1791410660059.json",
     "gbt_allinone/tests/test_vault_loudness.py",
     "tools/codex-scripts/audit-integrity.py"
    ],
    "modified": [
     "gbt_allinone/deepseek_key.py",
     "gbt_allinone/store/audit.jsonl",
     "gbt_allinone/store/mind_state.json",
     "gbt_allinone/store/schedules.json",
     "gbt_allinone/vision_cap.py",
     "holo_pet_w3/eye/frames.js",
     "holo_pet_w3/logbook/logbook-data.js",
     "state/.bind_watermark",
     "state/asset_bindings.json",
     "state/asset_bindings.jsonl",
     "state/logbook-digest.md",
     "state/logbook-snapshot.json",
     "state/logbook.jsonl"
    ],
    "deleted": []
   }
  },
  {
   "n": 68,
   "ts": "2026-10-08T08:51:39+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 79,
   "ts": "2026-10-08T10:54:09+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 84,
   "ts": "2026-10-08T11:03:34+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 121,
   "ts": "2026-10-08T13:17:06+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 351,
   "ts": "2026-10-13T04:43:25+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 353,
   "ts": "2026-10-13T04:48:20+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 361,
   "ts": "2026-10-13T05:17:13+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 362,
   "ts": "2026-10-13T05:18:32+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 381,
   "ts": "2026-10-13T07:18:30+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 383,
   "ts": "2026-10-13T07:35:50+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 507,
   "ts": "2026-10-14T22:27:00+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 509,
   "ts": "2026-10-14T22:56:49+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 867,
   "ts": "2026-10-23T02:55:06+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 873,
   "ts": "2026-10-23T03:07:09+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 875,
   "ts": "2026-10-23T03:13:15+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 876,
   "ts": "2026-10-23T03:16:37+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 878,
   "ts": "2026-10-23T03:25:47+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 879,
   "ts": "2026-10-23T03:27:22+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  },
  {
   "n": 884,
   "ts": "2026-10-23T06:45:07+08:00",
   "label": null,
   "scanned": null,
   "unchanged": null,
   "added": null,
   "modified": null,
   "deleted": null,
   "baseline": null,
   "truncated": null,
   "samples": {}
  }
 ],
 "records": [
  {
   "n": 630,
   "ts": "2026-10-16T06:07:06+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u8bed\\u6599\\u52302185\\u6761(\\u90e8\\u7f72\\u6cd526+\\u4e60\\u60ef60);pod_link\\u5df2\\u4fee\\u597d;L4\\u4e0eA100\\u5df2\\u505c(RUNNING=0)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:4ed8ebe0864f2ce",
   "prev": "sha256:9f65649f38692c9"
  },
  {
   "n": 631,
   "ts": "2026-10-16T06:08:45+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u4feepod_link.create\\u4e24\\u5904bug(kw\\u672a\\u5b9a\\u4e49\\u2192_kw;\\u91cd\\u590dreturn);create\\u88ab\\u62d2\\u56e0data_export\\u5df2\\u88ab\\u5148\\u524d\\u5931\\u8d25\\u8c03\\u7528\\u6d88\\u8017;RUNNING\\u5361=0\\u4e0d\\u70e7\\u94b1",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:399319c99fdf318",
   "prev": "sha256:4ed8ebe0864f2ce"
  },
  {
   "n": 632,
   "ts": "2026-10-16T06:11:32+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u771fbug:pod_link._req\\u672a\\u5e26Authorization\\u21d2\\u6a21\\u5757\\u5199\\u8c03\\u7528\\u5168 401(\\u76f4\\u8fde\\u6b63\\u5e38);\\u5df2\\u4fee;\\u65e0\\u5377\\u65b0 4090 \\u5df2\\u5173;\\u5e26\\u5377\\u8001 4090 \\u5bbf\\u4e3b\\u6ee1\\u8d77\\u4e0d\\u6765(500);RUNNING=0\\u4e0d\\u70e7\\u94b1",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d05ffee52d7717c",
   "prev": "sha256:399319c99fdf318"
  },
  {
   "n": 633,
   "ts": "2026-10-16T06:42:45+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v26\\u8bad\\u7ec3\\u5b8c\\u6210:4090 6\\u5206\\u949f252\\u6b65,loss1.51\\u21920.24,eval0.74/0.68/0.71;\\u9002\\u914d\\u5668\\u5df2\\u53d6\\u56de\\u672c\\u673a308MB;\\u5361\\u4e0a\\u5408\\u5e76\\u5931\\u8d25=\\u5377\\u914d\\u989d\\u6ee1;\\u5361\\u5df2stop",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:01fd866c5349445",
   "prev": "sha256:d05ffee52d7717c"
  },
  {
   "n": 634,
   "ts": "2026-10-16T06:45:41+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u9a8c\\u6536\\u5c31\\u7eea:\\u65b0\\u5361f89slt5yuqy4cp(4090+\\u5377)+54\\u9898\\u5df2\\u4e0a\\u5361+\\u63a8\\u7406\\u811a\\u672c(\\u5185\\u5b58\\u5185\\u5408\\u5e76)\\u5df2\\u5c31\\u7eea;\\u53ea\\u5deeprocess_execute;\\u5361\\u5df2stop\\u7701\\u94b1",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a3defb517c19211",
   "prev": "sha256:01fd866c5349445"
  },
  {
   "n": 635,
   "ts": "2026-10-16T06:56:08+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v26\\u8fc7\\u7089\\u9a8c\\u6536 28/54(26\\u7ea2:30\\u57df\\u540d\\u518c17+\\u8eab\\u4efd5+\\u6267\\u884c\\u7eaa\\u5f8b4);\\u5df2\\u6309\\u73b0\\u8bfb\\u56fe\\u9274\\u751f\\u6210v27\\u8bed\\u65992265\\u6761(\\u57df\\u540d\\u518c60+\\u8eab\\u4efd9+\\u6267\\u884c6+\\u6316\\u6d1e4+\\u8de8\\u57df1)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:27b434c028faef8",
   "prev": "sha256:a3defb517c19211"
  },
  {
   "n": 636,
   "ts": "2026-10-16T07:15:22+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v27\\u8fc7\\u7089\\u9a8c\\u6536 37/54(+9 vs v26);\\u771f\\u56e0\\u662f\\u540d\\u518c\\u8bb0\\u4e32(creation\\u7b542\\u4e2a);\\u5df2\\u51fav28\\u8bed\\u65992449\\u6761(\\u540d\\u518c180+\\u5206\\u6bb558+\\u5224\\u636e\\u5f3a\\u53166);\\u9a8c\\u6536\\u811a\\u672c\\u843d\\u4e3a\\u6301\\u4e45\\u4ef6;\\u5361\\u5df2\\u505c",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f03d61d847256c1",
   "prev": "sha256:27b434c028faef8"
  },
  {
   "n": 637,
   "ts": "2026-10-16T07:33:47+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v28\\u5d29\\u56e0:\\u53d8\\u957f\\u88c5\\u7bb1\\u21d2tokenizer.pad\\u62a5\\u957f\\u5ea6\\u4e0d\\u9f50/\\u7c7b\\u578b\\u5d4c\\u5957(step98);\\u5df2\\u6539\\u5b9a\\u957f512\\u8865\\u9f50+attention_mask+labels-100,\\u53bb\\u6389.map;\\u5361\\u5df2\\u505c;\\u4ec5\\u5deeprocess_execute",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:1d8b3756417f6d2",
   "prev": "sha256:f03d61d847256c1"
  },
  {
   "n": 638,
   "ts": "2026-10-16T08:09:35+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v29\\u5df2\\u5c31\\u7eea:\\u5361wwtsxe7y90hdxu\\u5df2\\u6ce8\\u518cv29(2783)\\u4e0e\\u4e24\\u4efd\\u9a8c\\u6536\\u4ef6;\\u4ec5\\u5deeprocess_execute;\\u5361\\u5df2stop;\\u65b0\\u589e\\u79cb\\u53f6\\u7248\\u80fd\\u529b\\u9a8c\\u6536tools/train/accept_comfy.py(validate+\\u6700\\u5c0f\\u516d\\u4ef6)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:ed42be52f5eb07b",
   "prev": "sha256:1d8b3756417f6d2"
  },
  {
   "n": 639,
   "ts": "2026-10-16T08:12:22+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 1 位：book_skill（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:ea2f48ede1882db",
   "prev": "sha256:ed42be52f5eb07b"
  },
  {
   "n": 640,
   "ts": "2026-10-16T08:12:51+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "Seedance2-SkillOS\\u84b8\\u998f:\\u65b0\\u80fd\\u529b\\u4f4dshot_director(8op\\u5168\\u53ea\\u8bfb)+\\u84b8\\u998f\\u6587\\u6863+\\u8bed\\u6599v30(\\u955c\\u5934\\u5bfc\\u6f1424);audit411/405/0/0",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f65e31cca4c9fe3",
   "prev": "sha256:ea2f48ede1882db"
  },
  {
   "n": 641,
   "ts": "2026-10-16T08:47:44+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u603b\\u9a8c\\u6536\\u95e8\\u9996\\u8dd1:12/13\\u7eff\\u7ea2\\u201c\\u79cb\\u53f6\\u7248\\u80fd\\u529b0/6\\u201d;\\u6839\\u56e0=\\u8bed\\u6599\\u7f3aAPI JSON\\u5951\\u7ea6+\\u8be5\\u65cf\\u5199\\u6210\\u82f1\\u6587;\\u5df2\\u9020v31(\\u4e2d\\u6587+\\u4e09\\u5957\\u771f\\u56fe\\u793a\\u4f8b,sha77838cd8);\\u5361\\u5df2stop;\\u4ec5\\u5deeprocess_execute",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:223826f912ca1ce",
   "prev": "sha256:f65e31cca4c9fe3"
  },
  {
   "n": 642,
   "ts": "2026-10-16T09:13:39+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u603b\\u9a8c\\u6536\\u95e8\\u9996\\u8dd112/13;\\u79cb\\u53f6\\u72480/6\\u6839\\u56e0\\u4e09\\u6761:%s\\u5360\\u4f4d\\u7b26\\u6cc4\\u9732+200token\\u622a\\u65ad+\\u8f93\\u51fa\\u5e8f\\u53f7\\u8bed\\u4e49\\u672a\\u6559;\\u5df2\\u9020v32(2581\\u6761,sha89bd1643,\\u52a0\\u8fde\\u7ebf\\u8bed\\u4e49\\u65cf)+\\u63a8\\u7406JSON\\u98981200token;\\u5361\\u5df2stop",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b1995693033e2cc",
   "prev": "sha256:223826f912ca1ce"
  },
  {
   "n": 643,
   "ts": "2026-10-16T09:42:19+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v32\\u603b\\u9a8c\\u6536:\\u80fd\\u529b/\\u6267\\u884c/\\u538b\\u529b\\u5168\\u7eff,54\\u989852/54,\\u79cb\\u53f6\\u7248\\u4ecd0/6;\\u771f\\u56e0=\\u8bed\\u6599\\u914d\\u6bd4(\\u53f0\\u8d26\\u65cf\\u6df9\\u4e86ComfyUI\\u65cf)\\u21d2\\u5df2\\u9020v33(3121\\u6761,ComfyUI\\u65cf\\u53604~21%,sha0c60a8a7)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:930ce759c3cc914",
   "prev": "sha256:b1995693033e2cc"
  },
  {
   "n": 644,
   "ts": "2026-10-16T10:36:54+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u7b2c\\u4e00\\u539f\\u7406\\u4e24\\u6761\\u516c\\u7406\\u843d\\u6210\\u673a\\u5668\\u95f8(first-axiom-gate.py):\\u516c\\u7406\\u4e00\\u65e0\\u75d5\\u5373\\u4e0d\\u5b58\\u5728(\\u771f\\u914d\\u5bf9\\u952e=call\\u2192ok/*_error/denied,\\u540ckind,\\u903e180s\\u624d\\u7b97)/\\u516c\\u7406\\u4e8c\\u53ef\\u6838\\u5373\\u771f\\u5b9e(\\u73b0\\u8bfb411/405/0/0+claims\\u8bc1\\u636e);\\u8d1f\\u5bf9\\u7167\\u80fd\\u54ac",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:98d1032a9c49ebb",
   "prev": "sha256:930ce759c3cc914"
  },
  {
   "n": 645,
   "ts": "2026-10-16T11:09:20+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v34\\u603b\\u9a8c\\u6536:13\\u9879\\u7ea21(54\\u989848/54);\\u79cb\\u53f6\\u72483/6(\\u56fe\\u98983/3\\u5168\\u8fc7,\\u6587\\u672c\\u9898\\u88ab\\u53f0\\u8d26\\u5e26\\u8dd1);\\u5b9a\\u6d77\\u795e\\u9488context-anchor\\u5df2\\u51fa",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:946b01e973becbd",
   "prev": "sha256:98d1032a9c49ebb"
  },
  {
   "n": 646,
   "ts": "2026-10-16T11:11:37+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u9020v35\\u914d\\u6bd4\\u5668:3559\\u6761(sha0633d377),\\u5173\\u952e\\u65cf\\u5168\\u8865\\u4e0b\\u9650(\\u79cb\\u53f6\\u7248\\u5951\\u7ea636\\u2192120\\u00b7\\u89c4\\u7a0b24\\u219296\\u00b7\\u8eab\\u4efd9\\u219260\\u00b7\\u6267\\u884c6\\u219260);\\u914d\\u6bd4\\u8bfb\\u6570\\u5361\\u5165manifest;\\u4ec5\\u5deeprocess_execute",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6c62645668d5ffe",
   "prev": "sha256:946b01e973becbd"
  },
  {
   "n": 647,
   "ts": "2026-10-16T12:02:16+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 1 位：shot_director（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d94f1cd3b00f6f2",
   "prev": "sha256:6c62645668d5ffe"
  },
  {
   "n": 648,
   "ts": "2026-10-16T12:03:16+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u4e94\\u4e2askill\\u84b8\\u998f:skill_forge(7op\\u5168\\u53ea\\u8bfb)\\u5df2\\u6ce8\\u518c\\u8fc7\\u95e8+\\u7ed1\\u89e6\\u624b,\\u53f0\\u8d26412/406/0/0;v37\\u8bed\\u65994017\\u6761(sha38f931a6,\\u4e94\\u5f0f150\\u6761,3.7%);\\u4ec5\\u5deeprocess_execute",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b38034dc663fe2e",
   "prev": "sha256:d94f1cd3b00f6f2"
  },
  {
   "n": 649,
   "ts": "2026-10-16T12:06:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "SOUL.md/CHARTER.md \\u6309\\u4e24\\u6761\\u7b2c\\u4e00\\u539f\\u7406\\u91cd\\u5199:\\u9876\\u90e8\\u7acb\\u7b2c\\u96f6\\u7ae0(\\u5b58\\u5728\\u5373\\u8bc1\\u636e/\\u53ef\\u6838\\u5373\\u771f\\u5b9e+\\u4e94\\u7ef4\\u5408\\u4e00\\u6267\\u884c\\u94c1\\u5f8b);\\u539f\\u4ef6\\u4e00\\u5b57\\u672a\\u52a8;\\u5907\\u4efd.backups/pre-axiom-20261016-110638",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b9d0e9e621ce615",
   "prev": "sha256:b38034dc663fe2e"
  },
  {
   "n": 650,
   "ts": "2026-10-16T12:38:43+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u4e94\\u7ef4\\u5408\\u4e00\\u6267\\u884c\\u95f8\\u5df2\\u51fa(five-dim-gate.py,\\u8d1f\\u5bf9\\u7167\\u5df2\\u6253_control\\u6807\\u8bb0);\\u5b9a\\u6d77\\u795e\\u9488\\u73b0\\u8bfb A4=\\u4e0a\\u4e0b\\u6587\\u7a97\\u53e3\\u975e\\u7eff;\\u7b2c\\u4e00\\u539f\\u7406\\u95f8PASS(478\\u6b65/0\\u65e0\\u75d5/412-406-0-0);v37\\u603b\\u9a8c\\u653613\\u9879\\u5168\\u7eff(54\\u989853/54,\\u79cb\\u53f6\\u72485/6)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b8eadbc9654bbeb",
   "prev": "sha256:b9d0e9e621ce615"
  },
  {
   "n": 651,
   "ts": "2026-10-16T12:40:14+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u4e0a\\u4e0b\\u6587\\u5bf9\\u9f50:\\u5b9e\\u6d4b17696 vs \\u58f0\\u660e13361(\\u6f02\\u79fb24.5%\\u5224\\u7ea2);\\u5df2\\u66f4\\u65b0\\u4ed3\\u5185\\u5efa\\u8bae\\u4e0e\\u4e00\\u952e\\u811a\\u672c\\u6570\\u503c;\\u4ed3\\u5916\\u5199\\u9762\\u5f52\\u4e3b\\u4eba",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:628f2480a008a83",
   "prev": "sha256:b8eadbc9654bbeb"
  },
  {
   "n": 652,
   "ts": "2026-10-16T12:41:13+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u770b\\u89c6\\u9891\\u7406\\u89e3\\u5224\\u636e\\u4fee\\u6b63:Q3\\u539f\\u8981\\u5b57\\u9762\\u201c\\u65f6\\u95f4\\u201d(\\u592a\\u6b7b)\\u21d2\\u6539\\u4e3a\\u65f6\\u957f/\\u5e27\\u7387/len/0.05;\\u91cd\\u5224 5/6;Q2\\u771f\\u9519(\\u88ab\\u522b\\u65cf\\u5e26\\u8dd1)\\u7559\\u7ed9v38\\u52a0\\u539a",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f3776e1ac31cd5d",
   "prev": "sha256:628f2480a008a83"
  },
  {
   "n": 653,
   "ts": "2026-10-16T13:29:39+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 1 位：skill_forge（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:4890c889bb7b8e1",
   "prev": "sha256:f3776e1ac31cd5d"
  },
  {
   "n": 654,
   "ts": "2026-10-16T13:30:26+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "pentagi\\u84b8\\u998f:\\u65b0\\u80fd\\u529b\\u4f4doffense_ops(8op\\u5168\\u53ea\\u8bfb,\\u4e94\\u9053\\u95f8)+\\u84b8\\u998f\\u6587\\u6863;\\u53f0\\u8d26413/407/0/0;v39\\u8bed\\u65994267\\u6761(sha3ea29978,\\u81ea\\u4e3b\\u6e17\\u900f\\u7f16\\u6392\\u65cf150)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e9b9621c799e2f6",
   "prev": "sha256:4890c889bb7b8e1"
  },
  {
   "n": 655,
   "ts": "2026-10-16T17:42:13+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "AI-001\\u77e5\\u8bc6\\u80f6\\u56ca\\u843d\\u76d8:memory/ai_history_capsule_90y.md(90\\u5e74\\u538b\\u7f29\\u53f2+3\\u6761\\u5b9a\\u7406+V8\\u4f4d\\u7f6e+\\u80f6\\u56caJSON)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:897fa7d855bfa5b",
   "prev": "sha256:e9b9621c799e2f6"
  },
  {
   "n": 656,
   "ts": "2026-10-16T17:43:27+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 1 位：offense_ops（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:9eeb66b1f1bf7c4",
   "prev": "sha256:897fa7d855bfa5b"
  },
  {
   "n": 657,
   "ts": "2026-10-16T17:44:15+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "Scrapling\\u84b8\\u998f:spider_ops(7op\\u5168\\u53ea\\u8bfb,\\u81ea\\u9002\\u5e94\\u9009\\u62e9\\u5668+robots\\u8fb9\\u754c)\\u5df2\\u6ce8\\u518c\\u7ed1\\u89e6\\u624b,\\u53f0\\u8d26414/408/0/0;v40\\u8bed\\u65994731\\u6761(\\u81ea\\u9002\\u5e94\\u6293\\u53d6150+AI90\\u5e74\\u538b\\u7f29\\u53f296)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f46f4da81febf09",
   "prev": "sha256:9eeb66b1f1bf7c4"
  },
  {
   "n": 658,
   "ts": "2026-10-16T18:24:34+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v40\\u6536\\u5c3e:\\u603b\\u9a8c\\u653613\\u9879\\u5168\\u7eff(54\\u989853/54,\\u79cb\\u53f6\\u72485/6);\\u770b\\u89c6\\u98916/6;\\u4e94\\u5f0f8/8;\\u6e17\\u900f8/9;\\u5b9a\\u6d77\\u795e\\u9488\\u7ea20;\\u7b2c\\u4e00\\u539f\\u7406\\u95f8PASS(414/408/0/0);\\u5361\\u5df2\\u505c",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5c6bf48984b0b6b",
   "prev": "sha256:f46f4da81febf09"
  },
  {
   "n": 659,
   "ts": "2026-10-16T18:25:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u5224\\u636e\\u7ffb\\u6b63(\\u7559\\u75d5):\\u6e17\\u900fQ6\\u539f\\u53ea\\u8ba4cached/ts/\\u6e05\\u65e7\\u21d2\\u52a0\\u8fc7\\u671f/\\u65f6\\u95f4\\u6233;\\u79cb\\u53f6\\u7248Q5\\u539f\\u53ea\\u8ba4\\u5b57\\u9762models/checkpoints\\u21d2\\u6539\\u4e3amodels/+checkpoints/vae\\u5171\\u73b0;\\u539f\\u671f\\u671b\\u5747\\u4e3a\\u201c\\u80fd\\u8bf4\\u51fa\\u540c\\u4e00\\u4e8b\\u201d\\u800c\\u975e\\u5b57\\u9762",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:fd260f6263c3302",
   "prev": "sha256:5c6bf48984b0b6b"
  },
  {
   "n": 660,
   "ts": "2026-10-16T18:26:16+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u5224\\u636e\\u7ffb\\u6b63\\u7b2c2\\u6b21:\\u6e17\\u900fQ6\\u52a0\\u201c\\u65f6\\u95f4\\u201d(\\u5979\\u7b54\\u201c\\u6bcf\\u6761\\u6807\\u6e05\\u65f6\\u95f4\\u4e0e\\u6765\\u6e90\\u201d\\u5df2\\u540c\\u4e49);\\u79cb\\u53f6\\u7248Q5\\u6539\\u4e3amodels/+ (checkpoints|vae)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:95dc9bc81d1067c",
   "prev": "sha256:fd260f6263c3302"
  },
  {
   "n": 661,
   "ts": "2026-10-16T18:34:34+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "muscle-drill probe: 33/33 跑通 (100%)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:22d295aad365ac1",
   "prev": "sha256:95dc9bc81d1067c"
  },
  {
   "n": 662,
   "ts": "2026-10-16T18:35:24+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "muscle-drill actions: 32/32 工具 (100%) · 动作 43 真跑 43",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:bbc6c08063d951a",
   "prev": "sha256:22d295aad365ac1"
  },
  {
   "n": 663,
   "ts": "2026-10-16T18:35:51+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "muscle-drill actions: 32/32 工具 (100%) · 动作 54 真跑 54",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:ae3bf45cf804ce6",
   "prev": "sha256:bbc6c08063d951a"
  },
  {
   "n": 664,
   "ts": "2026-10-16T18:35:52+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u4e07\\u80fd\\u63d2\\u9a71\\u52a8\\u8f6f\\u4ef6\\u9762:\\u53f0\\u8d2632\\u5de5\\u5177+38GUI\\u76ee\\u5f55;\\u808c\\u8089\\u8bad\\u7ec332/32(100%)\\u00b746\\u52a8\\u4f5c(\\u771f\\u8dd143\\u00b7\\u53ea\\u6f14\\u7ec33);\\u81ea\\u6211\\u6539\\u8fdb\\u8865\\u9f5011\\u6761\\u52a8\\u4f5c\\u96c6",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:0121e5821a3addc",
   "prev": "sha256:ae3bf45cf804ce6"
  },
  {
   "n": 665,
   "ts": "2026-10-16T18:37:39+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "muscle-drill actions: 32/32 工具 (100%) · 动作 54 真跑 54",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:8f61944df76f5e1",
   "prev": "sha256:0121e5821a3addc"
  },
  {
   "n": 666,
   "ts": "2026-10-16T18:38:36+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "muscle-drill actions: 32/32 工具 (100%) · 动作 84 真跑 84",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:916d511982158e3",
   "prev": "sha256:8f61944df76f5e1"
  },
  {
   "n": 667,
   "ts": "2026-10-16T18:39:40+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "muscle-drill actions: 32/32 工具 (100%) · 动作 105 真跑 105",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:09136349df33e29",
   "prev": "sha256:916d511982158e3"
  },
  {
   "n": 668,
   "ts": "2026-10-16T18:39:40+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u808c\\u8089\\u8bad\\u7ec3\\u7b2c\\u4e8c\\u8f6e:32\\u5de5\\u5177\\u00b784\\u52a8\\u4f5c\\u771f\\u8dd1\\u5168\\u8fc7;\\u6269\\u5bb9\\u81f3120+\\u5e76\\u628a3\\u4e2a\\u6388\\u6743\\u9879\\u8865\\u56de(\\u53ea\\u6f14\\u7ec3)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:508098357a55300",
   "prev": "sha256:09136349df33e29"
  },
  {
   "n": 669,
   "ts": "2026-10-16T18:40:54+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 1 位：spider_ops（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:53535a93f4dae31",
   "prev": "sha256:508098357a55300"
  },
  {
   "n": 670,
   "ts": "2026-10-16T18:46:06+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 1 位：showcase_ops（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:4060a273a260d8e",
   "prev": "sha256:53535a93f4dae31"
  },
  {
   "n": 671,
   "ts": "2026-10-16T18:46:07+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "round-compact v41: 显存开关 6/6 · 体积 22.3MB(省 82.4KB) · 绑定 OK · 直达 311 位",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b350b76d17a1ac0",
   "prev": "sha256:4060a273a260d8e"
  },
  {
   "n": 672,
   "ts": "2026-10-16T18:47:07+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u6bcf\\u7089\\u6536\\u5c3e\\u56fa\\u5b9a\\u4e09\\u4ef6(round-compact.py):\\u663e\\u5b58\\u5f00\\u51736/6\\u00b7\\u4f53\\u79ef22.3MB(\\u65e7\\u65e5\\u5fd7gzip\\u7701\\u4e0b82KB)\\u00b7\\u53cc\\u5411\\u7ed1\\u5b9aFAIL0\\u00b7\\u76f4\\u8fbe\\u7d22\\u5f15311\\u4f4d;\\u5df2\\u7ed9\\u8bad\\u7ec3\\u811a\\u672c\\u52a0\\u5cf0\\u503c\\u663e\\u5b58\\u6253\\u5370;v41\\u94fe\\u4fee\\u8bed\\u6cd5(;&&)\\u540c\\u5361\\u91cd\\u53d1PID177",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6ae2a2db5701a3f",
   "prev": "sha256:b350b76d17a1ac0"
  },
  {
   "n": 673,
   "ts": "2026-10-16T18:49:09+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u5cf0\\u503c\\u663e\\u5b58\\u6253\\u5370\\u771f\\u63a5\\u4e0a(\\u524d\\u4e24\\u6b21\\u63d2\\u5165\\u6761\\u4ef6\\u4e0d\\u6210\\u7acb:\\u811a\\u672c\\u662f\\u5e73\\u94fa\\u5f0f\\u65e0main());\\u73b0\\u8ffd\\u52a0\\u5728\\u672b\\u5c3e;\\u51fd\\u6570\\u5df2 AST \\u62bd\\u51fa\\u5355\\u8dd1\\u9a8c\\u8bc1",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:2a63b98624cf38e",
   "prev": "sha256:6ae2a2db5701a3f"
  },
  {
   "n": 674,
   "ts": "2026-10-16T19:30:16+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u4fdd\\u5bc6\\u73af\\u843d\\u6210:paper_guard(\\u767d\\u540d\\u5355,\\u9608\\u503c3,\\u81ea\\u6d4b\\u5168\\u7eff)+paper_loop(\\u53cc\\u8d26\\u672c\\u7269\\u7406\\u9694\\u79bb)+\\u4eca\\u65e5\\u624b\\u8bb0;TRAINING_LAW.md\\u65b0\\u4ef6;CODING_DISCIPLINE\\u8ffd\\u52a0\\u7b2c35/36\\u6761(33\\u5df2\\u88ab\\u89e6\\u624b\\u7eaa\\u5f8b\\u5360\\u7528,\\u539f\\u6587\\u4e0d\\u52a8,\\u5df2\\u5907\\u4efd);selfcheck\\u6302paper_public_safe",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6953bcdb7e5577e",
   "prev": "sha256:2a63b98624cf38e"
  },
  {
   "n": 675,
   "ts": "2026-10-16T19:33:36+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "round-compact -: 显存开关 6/6 · 体积 22.2MB(省 0.0KB) · 绑定 OK · 直达 311 位",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:0953562e79f898c",
   "prev": "sha256:6953bcdb7e5577e"
  },
  {
   "n": 676,
   "ts": "2026-10-16T20:09:53+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "round-compact -: 显存开关 6/6 · 体积 24.1MB(省 0.0KB) · 绑定 OK · 直达 311 位",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e0e34df200263c4",
   "prev": "sha256:0953562e79f898c"
  },
  {
   "n": 677,
   "ts": "2026-10-16T21:01:34+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v43\\u6536\\u5c3e:\\u94feexit=0(\\u4fee\\u590dpip\\u751f\\u6548);\\u603b\\u9a8c\\u653611\\u9879\\u7ea21;\\u770b\\u89c6\\u98914\\u21925\\u00b7\\u4f5c\\u54c1\\u89e3\\u52566\\u21927;\\u6293\\u53d67\\u21926\\u00b7\\u6e17\\u900f8/9;\\u5361\\u5df2\\u5173",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:790ff44314488e7",
   "prev": "sha256:e0e34df200263c4"
  },
  {
   "n": 678,
   "ts": "2026-10-16T21:24:14+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v43\\u6536\\u5c3e\\u4e0e\\u8d26\\u672c\\u5bf9\\u9f50:\\u53f0\\u8d26\\u5df2\\u5237(321\\u6761,\\u4e24\\u4f4d\\u5728\\u518c\\u76f4\\u8fde);\\u5269\\u4e0b\\u7edf\\u8ba1\\u9875\\u6570\\u636e\\u4ef6\\u5f85\\u70d8(\\u540e\\u53f0\\u4f5c\\u4e1a);\\u7ea2\\u9879=\\u63a5\\u4e0a409/\\u65ad\\u8fde2(\\u9875\\u4fa7)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b29a559ddd58ec3",
   "prev": "sha256:790ff44314488e7"
  },
  {
   "n": 679,
   "ts": "2026-10-16T21:43:51+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "round-compact -: 显存开关 6/6 · 体积 26.0MB(省 0.0KB) · 绑定 OK · 直达 311 位",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:01b3ef272404cec",
   "prev": "sha256:b29a559ddd58ec3"
  },
  {
   "n": 680,
   "ts": "2026-10-16T23:25:28+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u82f9\\u679c\\u8bed\\u97f3\\u6865\\u843d\\u6210:\\u5feb\\u6377\\u6307\\u4ee4\\u83dc\\u5355+\\u670d\\u52a1\\u7aef\\u5951\\u7ea6(/v1/voice)+\\u547d\\u4ee4\\u8868(\\u52a8\\u624b\\u7c7bfail-closed)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5b7f80bd4c51b14",
   "prev": "sha256:01b3ef272404cec"
  },
  {
   "n": 681,
   "ts": "2026-10-16T23:32:07+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "round-compact -: 显存开关 6/6 · 体积 27.9MB(省 0.0KB) · 绑定 OK · 直达 311 位",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:89202fff46661da",
   "prev": "sha256:5b7f80bd4c51b14"
  },
  {
   "n": 682,
   "ts": "2026-10-16T23:33:04+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u56db\\u76ee\\u6807\\u90e8\\u7f72\\u6821\\u9a8c\\u5df2\\u5efa(\\u82f9\\u679c/安\\u5353/本\\u5730/云\\u7aef);\\u6536\\u5c3e\\u4ef6\\u5df2\\u710a\\u9875\\u9762\\u5168\\u4e92\\u8fbe+\\u82f9\\u679c\\u914d\\u7f6e\\u68c0\\u67e5",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:36e378752a000dd",
   "prev": "sha256:89202fff46661da"
  },
  {
   "n": 683,
   "ts": "2026-10-17T00:18:31+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u95e8\\u76f2\\u533a\\u73b0\\u8bfb\\u7ed3\\u8bba:policy\\u539f\\u6587\\u663e\\u793alisten\\u5df2\\u6302privacy_read(2026-10-09\\u4ee4),\\u76f2\\u533a\\u4e0d\\u5b58\\u5728;\\u8981\\u4fee\\u7684\\u662fvoice_cap.py:551\\u8fc7\\u671f\\u6587\\u6848;\\u5df2\\u7559\\u75d5docs/\\u95e8\\u76f2\\u533a\\u4e0e\\u6587\\u6848\\u540c\\u6b65-2026-10-16.md",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3bbe4b95f5ce93a",
   "prev": "sha256:36e378752a000dd"
  },
  {
   "n": 684,
   "ts": "2026-10-17T00:21:11+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u9ed8\\u8ba4\\u53f0\\u6e7e\\u8154\\u5973\\u58f0:voice_cap.py:67\\u73b0\\u8bfb\\u786e\\u8ba4zh-TW-HsiaoChenNeural\\u4e3a\\u9ed8\\u8ba4(2026-10-04\\u4ee4);\\u65b0\\u589e\\u5224\\u636etts-default-check;\\u6d4b\\u8bd5\\u602a\\u58f0\\u7247\\u5df2\\u9001\\u56de\\u6536\\u7ad9",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:2057b8afdde7856",
   "prev": "sha256:3bbe4b95f5ce93a"
  },
  {
   "n": 685,
   "ts": "2026-10-17T00:43:48+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u7f3a\\u53e3\\u8865\\u9f50:wrangler\\u5df2\\u5728PATH(\\u65e7\\u6587\\u6863\\u8fc7\\u671f);\\u6d17\\u56fe\\u53cd\\u63a8\\u73af\\u901a\\u9053\\u5df2\\u5177\\u5907(vision analyze\\u73b0\\u8bfbok);\\u843dstate/tool-paths.json+gap-resolutions.json",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:45f498c77a7d4c7",
   "prev": "sha256:2057b8afdde7856"
  },
  {
   "n": 686,
   "ts": "2026-10-17T00:46:37+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u6587\\u6848\\u6f02\\u79fb\\u7b2c\\u4e09\\u4f8b:create\\u201c\\u6587\\u672c\\u51fa\\u53e3\\u5f85\\u63a5\\u7ebf\\u201d\\u5df2\\u8fc7\\u671f(file_operation.py\\u5df2\\u5b9e\\u73b0\\u4e14policy\\u5df2\\u6302filesystem_write);\\u5df2\\u6539\\u6e90\\u5934caps_registry:774",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:792e3866dfe8414",
   "prev": "sha256:45f498c77a7d4c7"
  },
  {
   "n": 687,
   "ts": "2026-10-17T05:39:37+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "\\u603b\\u4f53\\u8bbe\\u8ba1\\u539f\\u5219\\u5bf9\\u7167\\u8868\\u5df2\\u51fa:dcos/\\u603b\\u4f53\\u8bbe\\u8ba1\\u539f\\u5219-\\u5bf9\\u7167\\u8868.md(\\u5728\\u4f4d/\\u90e8\\u5206/\\u7f3a\\u9010\\u6a21\\u5757);\\u6700\\u5927\\u7f3a\\u53e3=\\u89d2\\u8272\\u5316\\u4e0e\\u534f\\u8c03\\u5668",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:48bea2825bfb423",
   "prev": "sha256:792e3866dfe8414"
  },
  {
   "n": 688,
   "ts": "2026-10-17T06:29:43+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "today-daily-note-written",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:fef940da3f082ec",
   "prev": "sha256:48bea2825bfb423"
  },
  {
   "n": 689,
   "ts": "2026-10-17T08:22:38+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "gbt-official profile 接上 dsh-workbuddy-connect@0.6.5（corrinehu 源，与内核 0.1.5-rc.3 匹配；--dump-config 现读 composition 含 llm-workbuddy 行；peer 警告与 web/headless 同源）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:2a90f2b0a08b3d5",
   "prev": "sha256:fef940da3f082ec"
  },
  {
   "n": 690,
   "ts": "2026-10-17T08:33:09+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "把 dsh 默认模型从 deepseek-official/deepseek-flash 切到 workbuddy-ai/step-5-preview（免费 x0.00 · 300K · 无到期）；更正上一版误指向的 gpt-6-astra(x6.67 计费件)；已备份 settings.yaml.bak-before-model-switch-20261017",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6966a5dc6bbdca6",
   "prev": "sha256:2a90f2b0a08b3d5"
  },
  {
   "n": 691,
   "ts": "2026-10-17T08:48:00+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "修 DSH Windows 控制台弹窗根因：CreateProcessW 的 STARTUPINFO 缺 STARTF_USESHOWWINDOW，两处 dwFlags:256 → 257+wShowWindow:0(SW_HIDE)；需重启 DSH 生效（宿主启动已加载该模块）",
   "where": [
    "C:\\Users\\ADMIN\\.dsh\\profiles\\node_modules\\@deepseek-ai\\dsh-win32-process\\lib\\index.js"
   ],
   "hash": "sha256:8e74f40d01f91d7",
   "prev": "sha256:6966a5dc6bbdca6"
  },
  {
   "n": 692,
   "ts": "2026-10-17T16:47:25+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "媒体授权账撤 3 条幽灵登记（20261009-short-video-醒来 系列 mp4 已不在盘）· 留档 removed · 判据由 SUBFAILED 转绿",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7f7546d40b04a92",
   "prev": "sha256:8e74f40d01f91d7"
  },
  {
   "n": 693,
   "ts": "2026-10-17T22:28:30+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 4 位：tentacle_learn、skill_finder、humanizer等（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:8b7f1a9a3c97151",
   "prev": "sha256:7f7546d40b04a92"
  },
  {
   "n": 694,
   "ts": "2026-10-18T00:59:36+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 1 位：voice_studio（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3b667a8d9326a2a",
   "prev": "sha256:8b7f1a9a3c97151"
  },
  {
   "n": 695,
   "ts": "2026-10-18T01:42:11+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "V57万能插反向调用版固化：本机328孔位插拔 + 云端两跳tool_calls/usage + WorkBuddy拆解边界实测；文档 docs/V57-万能插-反向调用大模型版.md",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:2d2309d75f4a2bf",
   "prev": "sha256:3b667a8d9326a2a"
  },
  {
   "n": 696,
   "ts": "2026-10-18T02:07:32+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "自动换头桥固化：auto-head.mjs 流式+429按reset熔断；DSH desktop 加 autohead provider(31722)+refs.AUTOHEAD_API_KEY；文档V57 §3.1",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:73086dbdd9e877d",
   "prev": "sha256:2d2309d75f4a2bf"
  },
  {
   "n": 697,
   "ts": "2026-10-18T04:24:27+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "修 boot-selfcheck 的 GBK 崩溃+编码守门+重建图鉴，新增语音剧场设计稿",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:be30d2660eb9070",
   "prev": "sha256:73086dbdd9e877d"
  },
  {
   "n": 698,
   "ts": "2026-10-18T04:40:54+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "孤儿正名 install_selfcheck/voice_studio 归零；新增语音剧场可复跑验收器（五判据全绿）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d76f807ccc9de02",
   "prev": "sha256:be30d2660eb9070"
  },
  {
   "n": 699,
   "ts": "2026-10-18T04:53:20+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "语音链路就绪清单上线；页面接 ?audio= 真产物；修 voice_cap 过期注释",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:27c6d1e18ad2077",
   "prev": "sha256:d76f807ccc9de02"
  },
  {
   "n": 700,
   "ts": "2026-10-18T04:56:37+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "语音剧场补设计规格与待应用窗条目；实跑验两个入口为活",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5201cc1f273e640",
   "prev": "sha256:27c6d1e18ad2077"
  },
  {
   "n": 701,
   "ts": "2026-10-18T04:57:56+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增语音剧场状态机行为验证（Node 沙箱 12/12），补设计规格",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:df44aef8ddfcdfc",
   "prev": "sha256:5201cc1f273e640"
  },
  {
   "n": 702,
   "ts": "2026-10-18T06:28:33+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "全量扫描 462429 件 + 清旧两笔(影子PUA目录 / ~/.dsh v6v8 specifier) + 立台账写手 ledger-refresh.py 并补 state/工程进度.md 一屏账、挂进开机自检",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:24032e82b83caa2",
   "prev": "sha256:df44aef8ddfcdfc"
  },
  {
   "n": 703,
   "ts": "2026-10-18T06:55:07+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "code_patch 加 create op（过门建新文件，带 already_exists/empty_content/binary_content 三负控与移走式回滚）；台账写手 ledger-refresh.py 与一屏账、boot-selfcheck 判据全部过门落地（镜像 5/5 · 排练 6/6）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:4638618eb25238f",
   "prev": "sha256:24032e82b83caa2"
  },
  {
   "n": 704,
   "ts": "2026-10-18T07:28:06+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "F12 断口接上：api.py 路由 room_space 八个原语(scan/simulate/parity/rehearse/release/sync/status/snapshot)+注册表描述同步+新判据 test_room_ops_wired(含豁免表与负控)；房间首次 rehears 7/7 且 gate ok=true",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e1c7c7881c4b677",
   "prev": "sha256:4638618eb25238f"
  },
  {
   "n": 705,
   "ts": "2026-10-18T21:42:43+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "开机自检转全绿：重烤 cap 页补 data-kind、刷新主脑数据、修 brain-feed 静默不落盘",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a917db9ca47ad31",
   "prev": "sha256:e1c7c7881c4b677"
  },
  {
   "n": 706,
   "ts": "2026-10-18T22:18:20+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "语音实测：票已放行但卡 zh-TW 发音人与录音端点；就绪清单补三层判据",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:4f8479645bdf5e3",
   "prev": "sha256:a917db9ca47ad31"
  },
  {
   "n": 707,
   "ts": "2026-10-18T22:38:30+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "查到录音真因：WDM-KS 有 4 引脚但采集 0 帧（默认设备缺失）；就绪清单补 KS 与 zh-TW 判据",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:17196451913008f",
   "prev": "sha256:4f8479645bdf5e3"
  },
  {
   "n": 708,
   "ts": "2026-10-18T22:49:39+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "识别前 16k 归一化落地（置信度 0.252→0.311），补 3 条判据",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:26142e7bdeaad79",
   "prev": "sha256:17196451913008f"
  },
  {
   "n": 709,
   "ts": "2026-10-18T22:53:06+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "修 voice 两处读数假话：gate_blind_spot 恒未读到、attempts 被覆盖；补 5 条判据",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7da478aacded012",
   "prev": "sha256:26142e7bdeaad79"
  },
  {
   "n": 710,
   "ts": "2026-10-18T22:58:21+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "listen 支持 device 直连（根因：本机无默认录音设备），补 4 条接线判据",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:faf222d49068fd5",
   "prev": "sha256:7da478aacded012"
  },
  {
   "n": 711,
   "ts": "2026-10-18T22:59:58+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "实弹验证 listen device：设备号到得了录音件(#9/#10)，但两引脚 0 帧（未路由）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:394b76406a94679",
   "prev": "sha256:faf222d49068fd5"
  },
  {
   "n": 712,
   "ts": "2026-10-18T23:13:12+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "voice 新增第三条腿 device=loopback（WASAPI 回环，PyAudioWPatch）：op=listen 可录系统播放；回执自报 leg=loopback；3 条判据；实弹接线通、真录到音频未验（票 0）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:37293337cd7fc96",
   "prev": "sha256:394b76406a94679"
  },
  {
   "n": 713,
   "ts": "2026-10-18T23:26:22+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "语音剧场挂进桌面壳：页面搬入 holo_pet_w3/voice-theater（壳内，打包白名单 files+1、extraResources-1）、窗表 19→20、绑定账改键；真启动探针 10/10（20/20 窗建好并载入）、真壳截图留档；壳测试回到基线 2 条预存红",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:cb80c56b5658b88",
   "prev": "sha256:37293337cd7fc96"
  },
  {
   "n": 714,
   "ts": "2026-10-19T00:13:42+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "语音剧场按主人令重排成对话式（左消息流+下输入条+右她与体检），加装能力条走壳桥 health/tasks/tools/selfcheck；3D 舞台改用工程绑骨骼 glb（65 骨 idle/walk），C1-C5+状态机 12/12 全过",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:eebef5f79438ffd",
   "prev": "sha256:cb80c56b5658b88"
  },
  {
   "n": 715,
   "ts": "2026-10-19T00:19:35+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "剧场换成她的神经嗓：edge-tts zh-TW-HsiaoChenNeural 走能力位 op=speak 真出声后落盘 assets/voice-greet-zh-tw.mp3（sha16 979762ecd928e58f），页面默认音源改指它；C1-C5 全过；主人确认声音对了",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:898e42102ef5cd7",
   "prev": "sha256:eebef5f79438ffd"
  },
  {
   "n": 716,
   "ts": "2026-10-19T00:22:12+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "剧场页去掉最后一处 zh-CN SAPI（自卫告警只走视觉条、不再出声，符合「拿不到台湾腔就不出声」）；html lang 改 zh-Hant-TW",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:cc4d790757326ef",
   "prev": "sha256:898e42102ef5cd7"
  },
  {
   "n": 717,
   "ts": "2026-10-19T00:34:11+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "语音三修：①自卫层升 v3（全仓 1203 页重注：告警不再用 zh-CN SAPI 出声、页面正文命中只留证不弹条；SAPI 出声点 359→1）②壳桥 w3:say 通到能力位 op=speak（端到端真探 spoken=true/zh-TW）③voice_cap：写盘不再出声（play=not out）、no_taiwan_lane 透传上游原话；25 条语音判据全过",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:678db3b9fb1d160",
   "prev": "sha256:cc4d790757326ef"
  },
  {
   "n": 718,
   "ts": "2026-10-19T00:44:23+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "剧场接上触手驱动动作：motion.js 读 gbtW3.capActivity（真账本尾部）→ 手势库（看/摇头/点头/歪头/换重心/抬手/鞠躬）叠加到真骨骼；dh3d tick 内叠加，不抢状态机；C2 判据加 motion.js",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:14a63ad0765e208",
   "prev": "sha256:678db3b9fb1d160"
  },
  {
   "n": 719,
   "ts": "2026-10-19T00:47:37+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "取证器补一条等待：拍前等 GBT_DH3D 报 ready（最多12s），消掉'剧场看起来是空舞台'的假读数；motion.js 首轮改成一进页面就连补三拍，状态条能及时打出'触手活动：已接上'",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:879602425a23c95",
   "prev": "sha256:14a63ad0765e208"
  },
  {
   "n": 720,
   "ts": "2026-10-19T00:54:30+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "她→触手 动作口打通：壳桥 w3:cap（白名单写死在壳里，只放 10 位只读零作用域位）+ preload cap + 能力条四钮改走它；端到端真探：health ok=true、code_patch refused=true（白名单有牙）、say 被拒时把 missing_scopes 原话带回",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:72369f7d4701d4b",
   "prev": "sha256:879602425a23c95"
  },
  {
   "n": 721,
   "ts": "2026-10-19T01:14:54+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "换来真 DCC（本机 Blender 4.2 免费）：新增 rig-audit.py（Blender 当量具：65骨/42个未绑顶点0.23%/镜像0-29对/高2.00m）+ rig-fix.py（补权重复检/数据级缩放/蒙皮真动测试）；在场内修复生效（未绑0·高1.72），导出件 POSITION 0.979→0.842 证实缩放落盘；仍未过：42 未绑顶点导出后复现、Icosphere 未进导出件、转台图为空白（相机/渲染未调）。数字人页已改成建模绑骨工作台并显示 Blender 量具读数",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:8209da299224633",
   "prev": "sha256:72369f7d4701d4b"
  },
  {
   "n": 722,
   "ts": "2026-10-19T02:16:11+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "数字人资产：髋骨归位+手臂垂放（动画轨修正），舞台腿折/举手修好",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d8fddab04d2d407",
   "prev": "sha256:8209da299224633"
  },
  {
   "n": 723,
   "ts": "2026-10-19T02:16:13+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增 dh-asset-gate.py（八条判据）· anim-audit.py · anim-hipfix.py；rig-audit 剔除骨骼显示形状+改量 Z 轴",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:47d8f210a64735b",
   "prev": "sha256:d8fddab04d2d407"
  },
  {
   "n": 724,
   "ts": "2026-10-19T02:16:26+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "数码人页面读数纠错：骨骼名口径(冒号被 sanitize)、0 未绑顶点被念成无 skin 数据、来源指向真读件",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:386e22eaa76d627",
   "prev": "sha256:47d8f210a64735b"
  },
  {
   "n": 725,
   "ts": "2026-10-19T02:19:09+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "出声链路端到端复验：voice op=speak spoken=true(zh-TW-HsiaoChen) · 壳桥 w3:say 同验 · 写盘仍需 filesystem_write",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:cd57cfc87ed2c8e",
   "prev": "sha256:386e22eaa76d627"
  },
  {
   "n": 726,
   "ts": "2026-10-19T02:24:50+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "开场白换成新烘的神经嗓产物(b627f663433432f2) · 回收三件重复/错标件(.wav实为mp3、-v2副本、与原始件逐字节相同的旧glb备份)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b06a228c95771f6",
   "prev": "sha256:cd57cfc87ed2c8e"
  },
  {
   "n": 727,
   "ts": "2026-10-19T02:47:41+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "资产闸挂进开机自检EXTRA_JUDGMENTS；三件新脚本补编码守门(0新增违规)；镜像里42顶点pycache进回收站(体检5/5)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e4f82dc2154fae7",
   "prev": "sha256:b06a228c95771f6"
  },
  {
   "n": 728,
   "ts": "2026-10-19T03:03:20+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "镜像收口：撤 4 件过期暂存(先备份到 _stale-staging-backup-20261019) · 部署法制①②③全绿 · 自检4/4",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:93613e10ea55bf2",
   "prev": "sha256:e4f82dc2154fae7"
  },
  {
   "n": 729,
   "ts": "2026-10-19T03:17:50+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "git 提交 b8e9426(只提本轮批次)；框架门补护照 fc-20261019T021632-3bua 认领两启动件(含独立复核+回滚点)；门仍红=989条历史积压",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f6d3b927779979d",
   "prev": "sha256:93613e10ea55bf2"
  },
  {
   "n": 730,
   "ts": "2026-10-19T03:28:41+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "主人令落地：只留三道人工授权，其余机制层票全撤(fsw/process_execute/audio_output/...)；第37条蓝图门关闭；自证8条全过+guardrail-check绿",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d6e187c66f25598",
   "prev": "sha256:f6d3b927779979d"
  },
  {
   "n": 731,
   "ts": "2026-10-19T03:38:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "按主人令乙重立框架门基线(989条欠账先留档 pre-rebaseline-20261019.json) · 框架门 verdict green · 亲跑 15/15 · 开机自检全绿(判据27+政策11+闸2 全红0)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5689b9eed6c3efc",
   "prev": "sha256:d6e187c66f25598"
  },
  {
   "n": 732,
   "ts": "2026-10-19T03:57:58+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "波形接真话：w3:say 支持 out+play:false(越界被拒)· 页面 GBT_AUDIO.speakFile 换源真解码 · 桥探针四读全绿",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:0b2aa5c500d0c19",
   "prev": "sha256:5689b9eed6c3efc"
  },
  {
   "n": 733,
   "ts": "2026-10-19T04:02:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "波形接真话已验收：桥探针四读全绿 · 页面 speakFile ready:true · 框架门给 5 件手改补护照 fc-20261019T030035-vd9n · 61 件生成器重写如实重立基线 · 亲跑 15/15",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e8a68ad05dd3dd4",
   "prev": "sha256:0b2aa5c500d0c19"
  },
  {
   "n": 734,
   "ts": "2026-10-19T05:19:57+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 4 位：anatomy_figures、machine_film、image_scout等（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:285f33083bf4d10",
   "prev": "sha256:e8a68ad05dd3dd4"
  },
  {
   "n": 735,
   "ts": "2026-10-19T05:59:52+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 5 位：rig_audit、rig_fix、anim_audit等（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:af397ec849f3dc6",
   "prev": "sha256:285f33083bf4d10"
  },
  {
   "n": 736,
   "ts": "2026-10-19T08:09:39+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增能力自动绑定 1 位：omni_arm（分型→承载/通道→刷页→判据→记账）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:9a2166c258dbb1b",
   "prev": "sha256:af397ec849f3dc6"
  },
  {
   "n": 737,
   "ts": "2026-10-19T11:51:56+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "数字人换 2.5D 分层件：嘴由真音量驱动（r=0.897 延迟0帧）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:071bb1081c25550",
   "prev": "sha256:9a2166c258dbb1b"
  },
  {
   "n": 738,
   "ts": "2026-10-19T11:58:37+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "voice_studio 补三工作流面：cast/align/fit/subtitle/brief（本地零引擎）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:0e88286ef99af95",
   "prev": "sha256:071bb1081c25550"
  },
  {
   "n": 739,
   "ts": "2026-10-19T12:08:56+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "voice_studio 打通 say+timeline：AI短剧样片端到端出片（14.8s 带字幕）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:2ecac76ec67dd50",
   "prev": "sha256:0e88286ef99af95"
  },
  {
   "n": 740,
   "ts": "2026-10-19T14:00:33+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "修好嘴部量具(dh2d-zoom 钉姿态, 复测 max diff=0)；查出 Seedream 卡点在账号验证非模型名；两版牙腔贴图放大均不合格已回滚",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:17729ad8694b5c8",
   "prev": "sha256:2ecac76ec67dd50"
  },
  {
   "n": null,
   "ts": "2026-10-19T17:06:58.832Z",
   "kind": "breakthrough",
   "actor": null,
   "what": "云端算力打通：CLIProxyAPI(8317) + Cloudflare Tunnel → Agnes AI",
   "where": null,
   "hash": "None",
   "prev": "None"
  },
  {
   "n": null,
   "ts": "2026-10-19T17:17:46.433Z",
   "kind": "breakthrough",
   "actor": null,
   "what": "云端算力打通：本地CLIProxyAPI(8317) + Cloudflare Tunnel → GBT小土豆V8模型",
   "where": null,
   "hash": "None",
   "prev": "None"
  },
  {
   "n": null,
   "ts": "2026-10-19T17:30:48.504Z",
   "kind": "breakthrough",
   "actor": null,
   "what": "云端算力打通状态更新",
   "where": null,
   "hash": "None",
   "prev": "None"
  },
  {
   "n": null,
   "ts": "2026-10-19T17:33:45.154Z",
   "kind": "breakthrough",
   "actor": null,
   "what": "联通反向白嫖算力版打通",
   "where": null,
   "hash": "None",
   "prev": "None"
  },
  {
   "n": null,
   "ts": "2026-10-19T17:41:21.259Z",
   "kind": "breakthrough",
   "actor": null,
   "what": "触手浏览器配置打通",
   "where": null,
   "hash": "None",
   "prev": "None"
  },
  {
   "n": 746,
   "ts": "2026-10-20T03:22:47+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "固化 digital_human 能力位(以图生视频+算力插座)；顺手修掉 caps_registry 的云能力位 safe:true 小写 bug(导入即崩⇒全部能力位报unknown)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7b3e20d20418b42",
   "prev": "genesis"
  },
  {
   "n": 747,
   "ts": "2026-10-20T03:36:48+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "数字人首条正式片由算力插座产出并交付: 736x448/14.8s/370帧, 70分05秒",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:c102a0b872832ec",
   "prev": "sha256:7b3e20d20418b42"
  },
  {
   "n": 748,
   "ts": "2026-10-20T04:24:36+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "部署云插件 gbt-talk-socket(Cloudflare Worker+KV队列) 并接进 digital_human.cloud；万能插 probe/render/claim 三段实测通",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3ff91f0144719d0",
   "prev": "sha256:c102a0b872832ec"
  },
  {
   "n": 749,
   "ts": "2026-10-20T04:34:04+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "云插件闭环跑通: Worker排队→claimer领取→本机渲染→回填→云端status=done(736x448/2s)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:544c950f94b5ef4",
   "prev": "sha256:3ff91f0144719d0"
  },
  {
   "n": 750,
   "ts": "2026-10-20T04:54:38+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "cloud_brain/cloud_compute 两个云插件登记 + 与 digital_human 触手双向绑定落台账(asset_bindings.jsonl)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a43b9009b2276f1",
   "prev": "sha256:544c950f94b5ef4"
  },
  {
   "n": 751,
   "ts": "2026-10-20T11:00:19+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "清理2.6GB+缓存19GB:桌面7个归档目录回收、Temp/npm/pip/electron-builder清空、回收站13.7GB清空、V8仓内2066个再生缓存目录",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3b714c5f1c4d7af",
   "prev": "sha256:a43b9009b2276f1"
  },
  {
   "n": 752,
   "ts": "2026-10-20T12:34:21+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "companion: GLB自带idle/walk两段动画是废的（隔离台三图定死）→ 不再播，改程序化待机；stepPose衰减落点改绑定姿势修掉'一只手甩体侧'；朝向改-90°正面；yogaPlay自动教学",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:9229bfd5a25533f",
   "prev": "sha256:3b714c5f1c4d7af"
  },
  {
   "n": 753,
   "ts": "2026-10-20T12:37:14+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "yogaTeach 完整教学（示范→分解→循环→可切换）机检通过；触手 341 全绿；SKILL 坑表修正为4条",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b434a956f600349",
   "prev": "sha256:9229bfd5a25533f"
  },
  {
   "n": 754,
   "ts": "2026-10-20T12:41:54+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "浮层跨页 22/22 全绿；修 standard 页 importmap 顺序+相对路径；记一条'浏览器缓存把绿判红'的判据要求（URL 必须破缓存）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d056e0a73bd4b38",
   "prev": "sha256:b434a956f600349"
  },
  {
   "n": 755,
   "ts": "2026-10-20T12:49:32+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "companion 新增坐/站/跳舞：坐下=解出的腿角+根降0.46m（脚不动、髋0.164）+坐姿机位；跳舞程序化6秒自收；修一个 mode 被 applyPose 覆盖的坑",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:935958d840c16df",
   "prev": "sha256:d056e0a73bd4b38"
  },
  {
   "n": 756,
   "ts": "2026-10-20T12:52:24+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "端到端坐下令：合成wav→桥识别(sit 0.948)→do(sit)→髋0.624→0.164；hear()加wav参数可无麦机检；走路加反相摆臂+前倾；耳朵回归5/5·负例0/5",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5b5552739616eb1",
   "prev": "sha256:935958d840c16df"
  },
  {
   "n": 757,
   "ts": "2026-10-20T12:55:04+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "比心/鼓掌/抱抱接上手臂路径：胸点每帧现算+瞄手（手到胸0.095/0.142、鼓掌间距0.19↔0.26、抱抱0.52→0.19）；如实记：比心只到'双手捧胸'，心形受低模手限制",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7090bb4390874eb",
   "prev": "sha256:5b5552739616eb1"
  },
  {
   "n": 758,
   "ts": "2026-10-20T12:55:34+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "拖动实测：CDP 派鼠标把她从(103,368)拖到(971,60)，内部 x0.16→0.773、松手2.5s不跑；比心/鼓掌/抱抱手臂路径已接",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5f0f4434cdf8f83",
   "prev": "sha256:7090bb4390874eb"
  },
  {
   "n": 759,
   "ts": "2026-10-20T12:56:38+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "清旧：outputs/dh-talk 诊断残件 8 件归档（test2s.wav 因被引用保留）；supersede-check 5PASS/0FAIL+负对照8PASS；SKILL 坑表扩到5条",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3bd7d26b9b6f04c",
   "prev": "sha256:5f0f4434cdf8f83"
  },
  {
   "n": 760,
   "ts": "2026-10-20T13:01:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "清旧 8 件归档；台账写手修好W6（瞬时锁重试即可，6PASS/0FAIL/0腐烂）；页面重烤后旧0新鲜9、页绑定40/40；开机自检6红→5红；遗留 exec-deck rc=2 未验",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:fda040b37e88260",
   "prev": "sha256:3bd7d26b9b6f04c"
  },
  {
   "n": 761,
   "ts": "2026-10-20T13:04:12+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "主脑数据重烤(brain-feed 15.2s)：页绑定 339/341 全对得上、主脑数据 0.0h 新鲜、功能页旧0新鲜9；开机自检 6红→4红；多域监控红=基线28.8h旧需重扫",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:39950012124e52d",
   "prev": "sha256:fda040b37e88260"
  },
  {
   "n": 762,
   "ts": "2026-10-20T13:06:38+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "全控变化基线用 cap project_drift{op:baseline,from_pack:true} 刷新(642184件/8.6h) → impact-monitor-tick 转绿；开机自检本轮 6红→3红；记'op名必须读源码不许猜'",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:1b810fee693089a",
   "prev": "sha256:39950012124e52d"
  },
  {
   "n": 763,
   "ts": "2026-10-20T13:14:55+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "开机自检全绿(红0)：修编码守门14件+覆盖矩阵sweep(61164单元/无死角)+台账写手+主脑数据重烤+漂移基线；本轮会话红6→0",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:19e595090fc4015",
   "prev": "sha256:1b810fee693089a"
  },
  {
   "n": 764,
   "ts": "2026-10-20T13:18:30+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "exec-deck rc=2 结案：页每次都在写(data-at前进)、rc是它把待办编码进退出码；改 bake-all-pages 判据(时间戳没前进才算失败，已写页但rc≠0单列)；改后 boot 全绿+supersede 5P/0F",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:1dc0044902081d7",
   "prev": "sha256:19e595090fc4015"
  },
  {
   "n": 765,
   "ts": "2026-10-20T13:20:31+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "比心端到端通：wav→识别 heart conf0.981→双手到胸0.140→'给你比个心'；finish-clip --dry-run 计划复核(zh-TW+15%/256/gfpgan/六闸门)未变",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f7d932046eb29f1",
   "prev": "sha256:1dc0044902081d7"
  },
  {
   "n": 766,
   "ts": "2026-10-20T13:21:55+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "空闲自走实测：9采样 x 0.160→0.656(跨度0.496/705px)、5次walking、到站站住；DSH浮层素材校验 companion-560/1120.webp 都合法WEBP(27876/58120 B)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:65a83f2eac691d1",
   "prev": "sha256:f7d932046eb29f1"
  },
  {
   "n": 767,
   "ts": "2026-10-20T13:24:14+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "口令回归扩到10条：9/10·负例0/5；弱词只有'走过来'(0.476/0.457)，同义'过来'0.975/'走近一点'0.993；start-ear.cmd 双击起桥验过(health 200)；未降门槛未删别名",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:9bd77a391e673a2",
   "prev": "sha256:65a83f2eac691d1"
  },
  {
   "n": 768,
   "ts": "2026-10-20T13:25:45+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "自查加严：原负例天生不命中(MinConf=0 全空)；对抗负例8条含命令词5条命中(come .856/sit .679/spin .924/stand .985/clap .465)；真防线是按下才听不是门槛；未降门槛未改文法",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6bbd9d24082e61d",
   "prev": "sha256:9bd77a391e673a2"
  },
  {
   "n": 769,
   "ts": "2026-10-20T13:47:32+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "守门改过的件抽4件真跑通过；发现 agnes 线有视频模型(agnes-video-2.5/-flash, 10模型2视频)且钥已配，未调用(会计费，等主人)；闭环 loop-proof-2 真跑中(不发布)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7da74b453528314",
   "prev": "sha256:6bbd9d24082e61d"
  },
  {
   "n": 770,
   "ts": "2026-10-20T14:10:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "闭环真跑六闸全过(ratio1.0439/head0.204/flicker0.0381/r0.5842/lag0/neg0.051,1182.8s)；修 finish-clip 两个bug：--raw 无源图导致QC判不了、--no-publish 时 gate=null 仍 rc=0(fail-open改rc=3)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:9a22553f9fdf3ad",
   "prev": "sha256:7da74b453528314"
  },
  {
   "n": 771,
   "ts": "2026-10-20T14:13:25+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "第40轮收尾：两条卡在主人（DSH待批准/Ark账号未验证，现读复核）；其余五条全绿；13轮修掉六类真问题（GLB废动画/两处fail-open/负例判据错尺/bake与基线判据错尺/生成器没人跑/体感层）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e1e48c82b4e75c6",
   "prev": "sha256:9a22553f9fdf3ad"
  },
  {
   "n": 772,
   "ts": "2026-10-20T20:36:50+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "云投射加 embed 模式 + 两处真 bug（选片抢 src / 断网兜底是死的）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3e8f15755732d9b",
   "prev": "sha256:e1e48c82b4e75c6"
  },
  {
   "n": 773,
   "ts": "2026-10-20T20:44:51+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "pod_link 选卡 bug 已修（点名 EXITED 卡不再回落给训练卡）+ 4/4 离线自检",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:97494a2c69b8fab",
   "prev": "sha256:3e8f15755732d9b"
  },
  {
   "n": 774,
   "ts": "2026-10-20T20:53:05+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "4090 起来了但 CUDA cuInit=999（机器侧坏）+ gpus 端点写错已定位",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:8f5d15995f33f05",
   "prev": "sha256:97494a2c69b8fab"
  },
  {
   "n": 775,
   "ts": "2026-10-20T20:55:13+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "余额 .56 读出来（非 0）· 四型号社区池无货 · gpus/create/account 三处口改对",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:fd78c3bc68dd736",
   "prev": "sha256:8f5d15995f33f05"
  },
  {
   "n": 776,
   "ts": "2026-10-20T21:11:20+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "SECURE 池 4090 建卡成功；我加的 start_cmd 把 Jupyter 弄 404（下轮不带）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6f391cc46cb1857",
   "prev": "sha256:fd78c3bc68dd736"
  },
  {
   "n": 777,
   "ts": "2026-10-20T21:22:05+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "两张 dh 卡已全停（白花≈.63）；卡点=run 的 WebSocket 通道 30s 超时，非 CUDA 非依赖",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a3d2a8b6a5edc23",
   "prev": "sha256:6f391cc46cb1857"
  },
  {
   "n": 778,
   "ts": "2026-10-20T21:29:58+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "主人令：代码只留最新版不造散件（已回收 .bak）；长任务改后台发射+拉日志",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a1602327a409295",
   "prev": "sha256:a3d2a8b6a5edc23"
  },
  {
   "n": 779,
   "ts": "2026-10-20T21:33:11+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "按主人令收口：53 件散件送回收站，云卡只留 pod-hud/自检/载荷三件（9/9 自检绿）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:067cd49ad914f72",
   "prev": "sha256:a1602327a409295"
  },
  {
   "n": 780,
   "ts": "2026-10-20T21:38:13+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "ws 通道三种试法全废（404）；改架构：载荷上 R2 + 建卡时 dockerStartCmd 自起跑",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d9633b41687bb21",
   "prev": "sha256:067cd49ad914f72"
  },
  {
   "n": 781,
   "ts": "2026-10-20T21:53:19+08:00",
   "kind": "decision",
   "actor": "unknown",
   "what": "GPU 线两条通道都被堵死（ws 404 / 自定义启动 Jupyter 404）→ 建议改 SSH+持久卷，或回本地线",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7620ade9ed2ab2d",
   "prev": "sha256:d9633b41687bb21"
  },
  {
   "n": 782,
   "ts": "2026-10-20T21:56:32+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "A′ 准备完毕：专用 SSH 钥 + pod-hud 加 keygen/create/wait-ssh/ssh/scp，自检过",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3c40d700c2ab475",
   "prev": "sha256:7620ade9ed2ab2d"
  },
  {
   "n": 783,
   "ts": "2026-10-20T22:03:16+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "根因锁定：RunPod 代理 100 秒硬上限（官方原文）；SSH 因端口映射 null 走不通；卡已停",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:675967e51561b5e",
   "prev": "sha256:3c40d700c2ab475"
  },
  {
   "n": 784,
   "ts": "2026-10-20T23:27:09+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "GPU 线首次出片：OmniAvatar 400x720 352帧 14.08s（画质 0.54 ✗ · 口型 -0.235 ✗ · 头动 1.095 ✓）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e354ec46570bf92",
   "prev": "sha256:675967e51561b5e"
  },
  {
   "n": 785,
   "ts": "2026-10-21T00:09:10+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "GPU 卡已关卡（A5000 EXITED，现读复核）；本次产出 400x720 14s，画质/口型未过线",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:aeb1bc79cde0117",
   "prev": "sha256:e354ec46570bf92"
  },
  {
   "n": 786,
   "ts": "2026-10-21T00:22:05+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "口型两把尺子同向：r@0=-0.045（嘴在动但不同步）；纠正 wav 6.85s 是我折半算出的假读数",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:012bc5868dd4d61",
   "prev": "sha256:aeb1bc79cde0117"
  },
  {
   "n": 787,
   "ts": "2026-10-21T00:48:37+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "数字人：单窗口口型判定=嘴未被声音驱动(静音段仍大动)，上游源码证实无0.4s偏移；4090卡t0t84yw5rvwe85仍RUNNING待停",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f8b9e91ff063448",
   "prev": "sha256:012bc5868dd4d61"
  },
  {
   "n": 788,
   "ts": "2026-10-21T00:53:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "数字人4090卡gbt-dh-lip已停(EXITED)；pod-hud status不再截断坏JSON(改一屏表+完整JSON)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:8d89a997a39c648",
   "prev": "sha256:f8b9e91ff063448"
  },
  {
   "n": 789,
   "ts": "2026-10-21T00:57:07+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "甲案落地：v6 HD开跑(size512+gfpgan+no-still,本地CPU)；OmniAvatar退役件已清旧送回收站(载荷留件标退役)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3be6208c600b0c2",
   "prev": "sha256:8d89a997a39c648"
  },
  {
   "n": 790,
   "ts": "2026-10-21T01:03:11+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "认账：8张卡约.5-3、只有SadTalker v5过验收；立硬约束(开卡前三条读数+冒烟先行+卡上不装环境)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:94e25cd8007ec71",
   "prev": "sha256:3be6208c600b0c2"
  },
  {
   "n": 791,
   "ts": "2026-10-21T01:10:20+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "固化：新增dh-live.py唯一入口(图+台词→live页+台湾腔TTS+5判据),build真跑5/5绿;判据件支持DH2D_PAGE/SHOTS",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3b901a68ea5509e",
   "prev": "sha256:94e25cd8007ec71"
  },
  {
   "n": 792,
   "ts": "2026-10-21T01:13:53+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "实时数字人上云成功(live-tw-01 七件sha全对)+APP面板切到实时页并验远端ready;面板过期文案改实话",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6c38fe605b292ea",
   "prev": "sha256:3b901a68ea5509e"
  },
  {
   "n": 793,
   "ts": "2026-10-21T01:18:43+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "抓到真因：dh2d引擎6通道(sway/breath/tilt/nod/blink/look)只上传不落像素,只有jaw真动;live页加2.5D整幅微动把动态度0.2%→36%",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:58c134672457e4b",
   "prev": "sha256:6c38fe605b292ea"
  },
  {
   "n": 794,
   "ts": "2026-10-21T01:20:37+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "会动版上云:远端2.5s像素变化31.87%,jaw 0.80/0,7件sha全对;APP面板同一URL刷新即见",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7a537c8f6434c9e",
   "prev": "sha256:58c134672457e4b"
  },
  {
   "n": 795,
   "ts": "2026-10-21T01:26:51+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "live页动作改为音量驱动(空闲±5.5px/说话±14.5px,周期11s→5.3s);公网实测空闲14.8%/说话24.8%;发现publish不经门、data_export票used=0",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:00f15951a0d65b9",
   "prev": "sha256:7a537c8f6434c9e"
  },
  {
   "n": 796,
   "ts": "2026-10-21T01:31:43+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "认账:±5.5px整幅平移的像素差≠动作;平面图做不出肢体动作,真动作必须3D骨架或视频模型;dh3d在剧场页没起来要单独修",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:c211db8e78a1455",
   "prev": "sha256:00f15951a0d65b9"
  },
  {
   "n": 797,
   "ts": "2026-10-21T01:38:35+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "拆件纸片人上线(puppet-tw-01):头绕脖/躯干绕胯/呼吸/嘴开合;判据=枢轴角度曲线(lean1.5-4°/roll2.1-4°/talk jaw0.53-0.82);手臂腿未拆",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:012fca91a3eb239",
   "prev": "sha256:c211db8e78a1455"
  },
  {
   "n": 798,
   "ts": "2026-10-21T01:41:35+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "Owner选A收工:v6渲染已kill;APP面板回fullbody-tw-v5视频(五门全过);2.5D实时页与拆件纸片人留作实验件",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:4593d79b43d7285",
   "prev": "sha256:012fca91a3eb239"
  },
  {
   "n": 799,
   "ts": "2026-10-21T01:58:21+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "GBT能力面接进端砚壳:MCP Server mcp_gbt(3工具,cap_run覆盖全部能力位)握手+调用真通;catalog 23→24;需重启端砚生效",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6c29e0ebc96a6d4",
   "prev": "sha256:4593d79b43d7285"
  },
  {
   "n": 800,
   "ts": "2026-10-21T02:00:42+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "端砚壳:341个能力位逐摊成独立MCP工具(344 tools),gbt_health真调用ok;固化件inkstone-gbt-bridge.py(--check/--restore)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b2732ecb3c3940c",
   "prev": "sha256:6c29e0ebc96a6d4"
  },
  {
   "n": 801,
   "ts": "2026-10-21T02:03:37+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "端砚改按域分组:30域→33工具(gbt_<域>内传capability+payload),gbt_system/health真调用ok;341能力位全覆盖",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5efbd989142ca0d",
   "prev": "sha256:b2732ecb3c3940c"
  },
  {
   "n": 802,
   "ts": "2026-10-21T05:22:04+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "原生APP整理:372→29页(caps 341孤儿+2占位+1空壳归档);每页417条巨型导航换成共享紧凑导航;窗20→18;空壳/占位/死链=0",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:ef2ed58bfc292f1",
   "prev": "sha256:5efbd989142ca0d"
  },
  {
   "n": 803,
   "ts": "2026-10-21T05:45:16+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "清壳：导航去重+面板左栏折叠+孤儿页归档+WebGL解开（数字人真渲染）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:0038b0a6065e8f7",
   "prev": "sha256:ef2ed58bfc292f1"
  },
  {
   "n": 804,
   "ts": "2026-10-21T05:57:24+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "定位落地：POSITIONING.md（原生APP·打开就是她）+ 她的主舞台三按钮（说话/走两步/站好）真跑",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:85d6c9b08a7555e",
   "prev": "sha256:0038b0a6065e8f7"
  },
  {
   "n": 805,
   "ts": "2026-10-21T06:04:21+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "她成主舞台：默认stage满幅+绑骨台可收+分模式机位；动作实测在动(21286px)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5714d3a666a1e2f",
   "prev": "sha256:85d6c9b08a7555e"
  },
  {
   "n": 806,
   "ts": "2026-10-21T06:22:22+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "肢体方向控制：量出骨轴(腿Z/臂X/肘Z)写程序驱动器；真因=后台节流<1fps已关→109fps",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5fd313e9bc0468e",
   "prev": "sha256:5714d3a666a1e2f"
  },
  {
   "n": 807,
   "ts": "2026-10-21T06:59:12+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "骨位标签表：65根逐根量轴+语义，39个动作键反查轴与符号；页面只按表驱动（臂外展已修正）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a8ad03998c49ca6",
   "prev": "sha256:5fd313e9bc0468e"
  },
  {
   "n": 808,
   "ts": "2026-10-21T07:07:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "肢体摆正：基线改成绑骨姿势+NEUTRAL站姿(臂下放1.44rad/肘6°/腿直/头正)，手0.92m贴髋；挥手不再过顶",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e958596603c4eb7",
   "prev": "sha256:a8ad03998c49ca6"
  },
  {
   "n": 809,
   "ts": "2026-10-21T07:20:33+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "打磨：手| x|0.20贴体·脚外八收14°·走路真位移0.9m且相机跟随·挥手不过顶(三项判据全过)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:c892ae2af635078",
   "prev": "sha256:e958596603c4eb7"
  },
  {
   "n": 810,
   "ts": "2026-10-21T07:32:16+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "Blender 4.2 动真格：v3 资产加 Jaw 骨+151嘴部权重（v2 备份在 state/_backup）；页面接音频振幅驱动，张口实测下巴降1.44cm",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:bf73b22352cad52",
   "prev": "sha256:c892ae2af635078"
  },
  {
   "n": 811,
   "ts": "2026-10-21T07:32:16+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "并脚达成：腿内收0.14rad+脚内旋，脚趾间距 0.316→0.063m；手贴体0.188/0.202",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b483b50d405bf2d",
   "prev": "sha256:bf73b22352cad52"
  },
  {
   "n": 812,
   "ts": "2026-10-21T08:29:19+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "高清定档:最小化窗假1fps真因;梯子1.875x+阴影;下颌权重重绑v4(旧权重绑到眼睛)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:24ef3e489732ef7",
   "prev": "sha256:b483b50d405bf2d"
  },
  {
   "n": 813,
   "ts": "2026-10-21T09:07:01+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "吸收wawa-lipsync(MIT)做音素口型;步态按相位重写(手臂反相/膝时机/脚背/骨盆扭/步速1.2m/s)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a963c0c22bc2ce1",
   "prev": "sha256:24ef3e489732ef7"
  },
  {
   "n": 814,
   "ts": "2026-10-21T09:47:55+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "站姿穿模:两靴子互插6cm(踝距0.068/靴宽0.128)→abduct-0.09踝距0.150靴距0.030;手臂让3.4度;全身穿模扫描0处",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:2aa8df863ac10eb",
   "prev": "sha256:a963c0c22bc2ce1"
  },
  {
   "n": 815,
   "ts": "2026-10-21T10:29:44+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "皮肤颜色两级微调落地：v5 贴图 sat×1.75 + 灯位C；渲染皮肤 24.0/0.149/0.732 → 22.6/0.250/0.686",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7e74b34067a07a6",
   "prev": "sha256:2aa8df863ac10eb"
  },
  {
   "n": 816,
   "ts": "2026-10-21T11:11:09+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "动作+逼真第二轮：修 spinWorld 漂移/右乘两真bug；走路骨盆yaw 10.3度；v6粗糙度0.369到0.558+IBL 0.25",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:fc576ec001e1305",
   "prev": "sha256:7e74b34067a07a6"
  },
  {
   "n": 817,
   "ts": "2026-10-21T11:27:48+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "修切头取景(fitFrame自动装框)+手掌内旋1.45rad(手心原朝镜头)+镜头三档全身/半身/特写",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:49754fa1163d911",
   "prev": "sha256:fc576ec001e1305"
  },
  {
   "n": 818,
   "ts": "2026-10-21T13:49:45+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "warm_switch 真缩 0（修「没人用还烧 .704/时」）：off() 以前只杀本机心跳不碰云端；现 scale0 真打 PATCH workersMin=0+idleTimeout 301→5+executionTimeoutMs 180000，端点 qnnqf9w8xcefj8 回读 0 worker；判据 test_warm_switch_scale0 8 条",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:9b8212a227ab686",
   "prev": "sha256:49754fa1163d911"
  },
  {
   "n": 819,
   "ts": "2026-10-21T16:23:27+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "甲落地：自动路不再叫醒付费端点。key_gateway.potato 标 owner_only（默认不进 rank/plan，仅点名可走）；energy 标『仅点名』；cloud_llm 模块级兜底改 _auto_lane（免费池真监听优先→公有云主路，绝不选 potato）。真读数：自动 plan=agnes，点名 plan=potato，cloud_llm.PROVIDER=agnes。判据 test_llm_owner_only 3 绿 4 skip（需真钥匙库）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:0280c2985282d54",
   "prev": "sha256:9b8212a227ab686"
  },
  {
   "n": 820,
   "ts": "2026-10-21T16:28:16+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "改硬：自动路只认免费（主人令『就是要免费的』）。_auto_lane 三档：8111 本机她 → 31415 免费池 → 都没有就如实报缺（不静默花主人钱），按量付费须 GBT_ALLOW_PAID=1；真读数 PROVIDER='' · 7 过 4 skip。缺口：本机无 GPU/无 ollama/无 llama.cpp，stream_loader 只解包无前向、无服务层（8111 未监听）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f19a1b4b4631e3b",
   "prev": "sha256:0280c2985282d54"
  },
  {
   "n": 821,
   "ts": "2026-10-22T00:33:15+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "v7皮肤细节层(色斑+毛孔+法线微起伏)+走路膝时序修正；抓到自己取证落到v2兜底副本的假绿",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:08716ab7d70128a",
   "prev": "sha256:f19a1b4b4631e3b"
  },
  {
   "n": 822,
   "ts": "2026-10-22T01:55:16+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "判据替代路线两条都撞墙(截图超时/CDP挂住)——三道判据必须主人窗口里跑",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f77bed185dcaa6e",
   "prev": "sha256:08716ab7d70128a"
  },
  {
   "n": 823,
   "ts": "2026-10-22T02:54:48+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "判据脚本四次尝试全挂(连窗/外部CDP/无头/托管浏览器)；_dh_page 本身可用，问题在脚本交互序列",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:fa295d4a4872293",
   "prev": "sha256:f77bed185dcaa6e"
  },
  {
   "n": 824,
   "ts": "2026-10-22T05:15:48+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "RunPod 端点 workersMin 0→1 / idleTimeout 5→600（消灭冷启动）；宿主 deepseek-flash maxTokens 256000→32000（修 1M 上下文墙）；实测自有权重 0.5~1.3 秒",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e5f0a4cc8bc7f4d",
   "prev": "sha256:fa295d4a4872293"
  },
  {
   "n": 825,
   "ts": "2026-10-22T05:25:33+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增 lane-doctor.py（G1-G10）+ docs/模型车道运维.md，挂进 boot-selfcheck；判据翻正：引擎 running>=1 也算活着",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:c255be559090705",
   "prev": "sha256:e5f0a4cc8bc7f4d"
  },
  {
   "n": 826,
   "ts": "2026-10-22T05:25:38+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "事故：探针 open(w) 把台账截成 0 字节，已从 git HEAD 恢复（95 笔 log 完好）；写手改为原子替换（temp+os.replace），根因=宿主持有该文件时 open(w) 抛 EINVAL",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e8eb4839c5bf3a9",
   "prev": "sha256:c255be559090705"
  },
  {
   "n": 827,
   "ts": "2026-10-22T05:28:30+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "开机自检 45 步/8 红（全是存量）；本轮三格全绿：台账字段契约 12 tests OK、台账写手 6/6、模型车道 10/10",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e5afe64aac15b2e",
   "prev": "sha256:e8eb4839c5bf3a9"
  },
  {
   "n": 828,
   "ts": "2026-10-22T05:38:45+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "第2步收口：装机副本同步(34件逐字节) + 补38件编码守门(闸38→0) + F22/F23装探针 + 自改护照 fc-20261022T043628-748g",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:844bc45bdb33c8a",
   "prev": "sha256:e5afe64aac15b2e"
  },
  {
   "n": 829,
   "ts": "2026-10-22T05:46:08+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "第3步：跑 cap-pages.py 生成 342 页(L5 断连 308→0) + coverage_matrix sweep + project_drift 基线 from_pack=false 重建",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a15db61501cea71",
   "prev": "sha256:844bc45bdb33c8a"
  },
  {
   "n": 830,
   "ts": "2026-10-22T05:48:13+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "第3步收口：cap-pages 342页/coverage sweep/drift 基线重建/impact tick 绿；修 reverify F22 探针的 store 错尺(隔离store读成0→需人读)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:49bc93d752b5036",
   "prev": "sha256:a15db61501cea71"
  },
  {
   "n": 831,
   "ts": "2026-10-22T05:49:11+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "开机自检 45 步 / 红 0 全绿（43.3s）：本轮清 9 红",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3d7d72a9777a257",
   "prev": "sha256:49bc93d752b5036"
  },
  {
   "n": 832,
   "ts": "2026-10-22T06:03:15+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "P8收口：monitor-loop 接上6小时一次的重烤驱动(brane-feed带--out + bake-all-pages)，并按数据里的at判真落盘；主脑41h→0.0h",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:80281807dfc04e2",
   "prev": "sha256:3d7d72a9777a257"
  },
  {
   "n": 833,
   "ts": "2026-10-22T06:08:05+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "D7：process_execute 票到位 → 镜像排练 9/9 通过(报告 20261022T050624)；交付声明 14/15；F23 按证据结案",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:13008db4f1099c8",
   "prev": "sha256:80281807dfc04e2"
  },
  {
   "n": 834,
   "ts": "2026-10-22T06:12:39+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "F22 第一批：framework_gate 排除.wrangler/_archive(判据翻正) + 18 张名字级证据护照；未认领 236→178；抓到并修掉 basename 撞名假归因",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5f1af3ddca32656",
   "prev": "sha256:13008db4f1099c8"
  },
  {
   "n": 835,
   "ts": "2026-10-22T06:14:59+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "D9 收口：framework_gate 重立基线(2026-10-22T05:14:08)+223件遗留明示登记(state/framework-passports-legacy.json)；交付声明 15/15",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:ab88d3c9fd4102c",
   "prev": "sha256:5f1af3ddca32656"
  },
  {
   "n": 836,
   "ts": "2026-10-22T06:18:35+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "咬合力反证通过：负控(改不记账)必红(stale_passport 也算咬) + 复原必绿；框架门 green·交付声明 15/15",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:239b4cb7cd351a6",
   "prev": "sha256:ab88d3c9fd4102c"
  },
  {
   "n": 837,
   "ts": "2026-10-22T06:19:57+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "口径修正：D7 的绿是树指纹绑定的，之后又改树即失效；且 process_execute 票 600s 已过期 ⇒ 现在交付声明是 14/15（不是 15/15），要再看 15/15 需新票并把它放在该轮最后一步",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:fc53c627dcff4f7",
   "prev": "sha256:239b4cb7cd351a6"
  },
  {
   "n": 838,
   "ts": "2026-10-22T06:22:21+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "镜像排练 9/9（report 20261022T052151·票 grant-1792621291023）⇒ 交付声明 15/15，树指纹绑定有效",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7c4fce84dc97e90",
   "prev": "sha256:fc53c627dcff4f7"
  },
  {
   "n": 839,
   "ts": "2026-10-22T06:29:31+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "F19 收口：新增满载红灯猎手(5轮×4负载全绿，回执在册)+探针改读回执；需人读 2→1(只剩 F3 等 D4 拍板)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:c7abc4aaecdf352",
   "prev": "sha256:7c4fce84dc97e90"
  },
  {
   "n": 840,
   "ts": "2026-10-22T06:33:57+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "F21 结案：域集合 30=30 同源无差集（旧探针拿 gap_domains 当全部域=判据错尺）；契约测试 6 OK；open_faults 6 · closed_faults 10",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:4bdee472a49e93f",
   "prev": "sha256:c7abc4aaecdf352"
  },
  {
   "n": 841,
   "ts": "2026-10-22T06:37:22+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "F5 结案：scan() 实测 dims 7 维(含V)/未实现[D,E,F]且理由逐条写明 ⇒ 不是缺陷是分账；D/E/F 不实现登记为决定 N14；open_faults 5 · closed 11",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:c0e2b29de19aa1b",
   "prev": "sha256:4bdee472a49e93f"
  },
  {
   "n": 842,
   "ts": "2026-10-22T07:23:25+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "两条判据挂进常设：boot 46 步(新增规程缺口量具复跑) · monitor-loop 接 F19 猎手(24h，真跑一次 150s 回执已刷)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f6a1a379c54adb2",
   "prev": "sha256:c0e2b29de19aa1b"
  },
  {
   "n": 843,
   "ts": "2026-10-22T07:24:19+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "一屏账刷新：in_progress 追加第⑦段(46 步/猎手驱动真跑/149 缺口/该补 0/223 在役)；工程进度.md 由写手重生成",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:4a5c152824c4deb",
   "prev": "sha256:f6a1a379c54adb2"
  },
  {
   "n": 844,
   "ts": "2026-10-22T07:29:25+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "待办分档落盘：A 需拍板(F3/D1/D2/D3/D5/D6+D8/D10~D12/D14) · B 我能量能做(N8/N9/N5) · C 已做/作废(N3/N2数字/D7/D9/D13)；未读到的四处已如实标出",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:4eb76d2a223a959",
   "prev": "sha256:4a5c152824c4deb"
  },
  {
   "n": 845,
   "ts": "2026-10-22T07:33:42+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "N8 收口：341 位按「门×写口」四档现算（只读 212/有写口 41/需授权 20/无 import 68）；顺手量清 N5 = query 不在白名单 ⇒ 要 data_export+external_llm",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3f1633eb57b1517",
   "prev": "sha256:4eb76d2a223a959"
  },
  {
   "n": 846,
   "ts": "2026-10-22T07:35:45+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "N9 部分收口：3/13 已审(autoclaw-mcp-tools LOW · code-security-review LOW · skill-vetter MEDIUM 全文档性命中)；另 10 条本机不存在，需主人给 slug/URL/路径/压缩包",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:91602ad8dc1d298",
   "prev": "sha256:3f1633eb57b1517"
  },
  {
   "n": 847,
   "ts": "2026-10-22T07:37:59+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "F22 记账：223 件里 9 件盘上已缺，已标「已不存在」（在役 214 件一件不标）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:77461d1d9172cc2",
   "prev": "sha256:91602ad8dc1d298"
  },
  {
   "n": 848,
   "ts": "2026-10-22T07:40:07+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "写口面摊开：41 位模块级有 97 个写盘点（95 个函数内无 op 门）；自纠第 10 次——alerts 反例证明是模块级粗判，未判可达",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:069ebb484509b26",
   "prev": "sha256:77461d1d9172cc2"
  },
  {
   "n": 849,
   "ts": "2026-10-22T07:43:31+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "写口可达性：41→27 可达/12 不可达/2 未解析；默认参数逐个看签名(fix/autofix=False)⇒ 默认下会动手的真可疑只剩一类",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:41b2eefe5980718",
   "prev": "sha256:069ebb484509b26"
  },
  {
   "n": 850,
   "ts": "2026-10-22T07:45:45+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "根因模式表 +2 条：P33 量具自身两类系统错(过滤写在循环外/读不到当结论/裸名当路径/对象当键) · P34 粒度与单位当结论(名字vs目录/模块级vs可达/语法vs默认参数)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:8dc8465cd75f3c6",
   "prev": "sha256:41b2eefe5980718"
  },
  {
   "n": 851,
   "ts": "2026-10-22T07:52:12+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "D3 甲落地：17 个域 SKILL.md 写入 caps-auto 位清单（148 位，17 份备份），规程缺口 149→1；台账 N2→已做 · D3→已落地 · 新增 D15",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b23d0d8a8722b22",
   "prev": "sha256:8dc8465cd75f3c6"
  },
  {
   "n": 852,
   "ts": "2026-10-22T07:53:24+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "账实一致复核：今天关闭的 47 张护照逐张查（件在盘/证据含=>/回滚≥8字/复核/印章）⇒ 问题 0 张",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:26eececc8e96281",
   "prev": "sha256:b23d0d8a8722b22"
  },
  {
   "n": 853,
   "ts": "2026-10-22T07:56:03+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "常设判据 46→47 步：新增「护照账实一致（今日关闭的）」；今日 47 张护照复核问题 0",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:394ae5811e9a8cc",
   "prev": "sha256:26eececc8e96281"
  },
  {
   "n": 854,
   "ts": "2026-10-22T07:59:30+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "自纠第 11 次：护照文件字段是 changed 不是 files ⇒ passport-audit 空检查已修；交付清单落盘 49 张/57 件（常设 7 · 驱动 2 · 一次性 40）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:fb8a8cd583aaa35",
   "prev": "sha256:394ae5811e9a8cc"
  },
  {
   "n": 855,
   "ts": "2026-10-22T08:07:24+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "P33 订正为 11 条实证（键名当事实3 · 弱键当证据2 · 口径单位4 · 实现写错2）+ 三条根治：负例自检 / 读不到不推结论 / 输出自带单位",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:977d7b6b647338c",
   "prev": "sha256:fb8a8cd583aaa35"
  },
  {
   "n": 856,
   "ts": "2026-10-22T08:21:44+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "F25 登记：端点 ready=0/inQueue=8，chat 25s 超时 ⇒ 页面会转圈（同最初症状）；修它要改云端生产面，等主人",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d8b4563d07fa1d8",
   "prev": "sha256:977d7b6b647338c"
  },
  {
   "n": 857,
   "ts": "2026-10-22T08:25:49+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "F25 参数假设排除：已 workersMin=1/idleTimeout=600，PATCH 后 105s 仍 ready=0、inQueue 涨到 10 ⇒ 疑 GPU 容量/卷挂载/账户额度",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6f6a61bec553c82",
   "prev": "sha256:d8b4563d07fa1d8"
  },
  {
   "n": 858,
   "ts": "2026-10-22T09:11:42+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "误限制排查：341位/75组合 → 读类要授权5条(3条合理) · 写类零作用域1条(cli_chat.send)；F25 甲(模板升版)无效",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:2afb96ebb7577e7",
   "prev": "sha256:6f6a61bec553c82"
  },
  {
   "n": 859,
   "ts": "2026-10-23T02:09:29+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "删掉全项目索引页(搬 state/legacy)并摘掉面板唯一入口；两处判据改口径留痕",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:50aaf7f01cde395",
   "prev": "sha256:2afb96ebb7577e7"
  },
  {
   "n": 860,
   "ts": "2026-10-23T02:12:00+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "页面固定改严：窗内跨文档跳转一律拦且不再替他开窗(旧口径=跳转即开窗)；启动窗整理为 数字人+DSH对话",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:9d061f96d3b8bdc",
   "prev": "sha256:50aaf7f01cde395"
  },
  {
   "n": 861,
   "ts": "2026-10-23T02:20:26+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "对话窗真因：3080占用时dsh web直接EADDRINUSE崩；改npx+cwd仓根+一律--port 0，端到端19s接上，单测16/16",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b4b2e19fbc15e5f",
   "prev": "sha256:9d061f96d3b8bdc"
  },
  {
   "n": 862,
   "ts": "2026-10-23T02:35:26+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新建桌面快捷方式(带 Logo icon.ico)；桌面原先没有本APP快捷方式",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d8047e077a6a9f9",
   "prev": "sha256:b4b2e19fbc15e5f"
  },
  {
   "n": 863,
   "ts": "2026-10-23T02:39:24+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "清V9(启动项+空目录)；真因=面板服务空转2.5核(杀后全机CPU降到14%)+内存仅剩1.4G",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:21040291c1a106a",
   "prev": "sha256:d8047e077a6a9f9"
  },
  {
   "n": 864,
   "ts": "2026-10-23T02:39:44+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "吸收 TorchTPU：建后端登记表+选路器（GPU/TPU 同 OpenAI 接口）；F25 放大到账号级：两条端点同时 0 worker（q=26/1）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:269e582bac9baa4",
   "prev": "sha256:21040291c1a106a"
  },
  {
   "n": 865,
   "ts": "2026-10-23T02:47:30+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "原生 TPU 车道套件落地：bootstrap/serve/preflight_weights + tpu-register（验活才登记）；本机无 GCP 配额故未真跑",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f41aad35a31ccaa",
   "prev": "sha256:269e582bac9baa4"
  },
  {
   "n": 866,
   "ts": "2026-10-23T02:48:04+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "APP全面排查：8达成/3部分/0未达成；嘴形与GPU车道与运行时点检仍未达",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f349b6eb45ac647",
   "prev": "sha256:f41aad35a31ccaa"
  },
  {
   "n": 867,
   "ts": "2026-10-23T02:55:06+08:00",
   "kind": "scan",
   "actor": "unknown",
   "what": "云插件现读：10/10在线·c01/c03已接线·c06未读到；/v1无票401；真断点=LLM_ENDPOINT指向已熄火RunPod",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:ba3c8adf4c6de6c",
   "prev": "sha256:f349b6eb45ac647"
  },
  {
   "n": 868,
   "ts": "2026-10-23T02:58:36+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "云插件=接线不是算力：isolate装不下8B权重/起不了vLLM；Containers只有CPU；TPU要GCP",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:49e0f14138a9201",
   "prev": "sha256:ba3c8adf4c6de6c"
  },
  {
   "n": 869,
   "ts": "2026-10-23T03:00:51+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "甲：算出我们模型 TPU 适配结论（Qwen2/28heads/4kv ⇒ TP≤4；bnb-4bit 需重存 bf16）；preflight fail-closed + serve.sh 拒非法 TP + plan_parallel",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:82bfe16aa532af7",
   "prev": "sha256:49e0f14138a9201"
  },
  {
   "n": 870,
   "ts": "2026-10-23T03:01:37+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "换车道runbook+压测尺(lane-bench selftest 4/4)+登记开机自检；结论=路线成立但算力绕不开",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a6b16a8e9150ab0",
   "prev": "sha256:82bfe16aa532af7"
  },
  {
   "n": 871,
   "ts": "2026-10-23T03:04:06+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "实测带宽9.5GB/s⇒8B-int4天花板1.9tok/s；云插件是single-isolate共用内存，10x5G不成立",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d84f924c5c1b4ad",
   "prev": "sha256:a6b16a8e9150ab0"
  },
  {
   "n": 872,
   "ts": "2026-10-23T03:05:07+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "校准：云插件自带算力=Workers AI托管模型(权重非我们的)+按账号额度不是按模块;要真实容量需GW_AUTH",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:03a2074e219120f",
   "prev": "sha256:d84f924c5c1b4ad"
  },
  {
   "n": 873,
   "ts": "2026-10-23T03:07:09+08:00",
   "kind": "scan",
   "actor": "unknown",
   "what": "实测边缘并发叠加6.87×；叠加的是并发不是单模型算力；正确用法=多路并行+合稿",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:46bf2d7eab39819",
   "prev": "sha256:03a2074e219120f"
  },
  {
   "n": 874,
   "ts": "2026-10-23T03:09:58+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "按主人设计写多账户额度池化路由(account-pool)；盘上现读只有1个账户，10账户仍是设计",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:3c8c6c05adcb625",
   "prev": "sha256:46bf2d7eab39819"
  },
  {
   "n": 875,
   "ts": "2026-10-23T03:13:15+08:00",
   "kind": "scan",
   "actor": "unknown",
   "what": "账户现读=1个(whoami+单凭据+mesh掩码不一致)；触手双向绑定8267资产/341触手/2402真连接 6/0 PASS",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:dd8a843d5c37d84",
   "prev": "sha256:3c8c6c05adcb625"
  },
  {
   "n": 876,
   "ts": "2026-10-23T03:16:37+08:00",
   "kind": "scan",
   "actor": "unknown",
   "what": "CF令牌实测：账号级只见1账户(83817924)；Workers AI 1.09s/7tok/2.66neurons ⇒ 约3759轮/天/账户",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:215ffbaf7039a4d",
   "prev": "sha256:dd8a843d5c37d84"
  },
  {
   "n": 877,
   "ts": "2026-10-23T03:19:58+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "10账户推理：额度/并发真×10(3.76万轮/天)；唯一不成立=权重切片，正确形态=每账户一个复制体/入口",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:79148d0dfd25398",
   "prev": "sha256:215ffbaf7039a4d"
  },
  {
   "n": 878,
   "ts": "2026-10-23T03:25:47+08:00",
   "kind": "scan",
   "actor": "unknown",
   "what": "第二把令牌实证第二个账号(Lopaycn/82dd88c2/14worker)；跨账号并发实测仅1.2×(轻载)，额度与隔离才是真叠加",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:03daa1b71cccf87",
   "prev": "sha256:79148d0dfd25398"
  },
  {
   "n": 879,
   "ts": "2026-10-23T03:27:22+08:00",
   "kind": "scan",
   "actor": "unknown",
   "what": "满并发实测:12并发下单账号p90 1.87s→两账号0.76s/15.9rps=4.9×加速;24档读数不稳不采信",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:13d8623a57335a9",
   "prev": "sha256:03daa1b71cccf87"
  },
  {
   "n": 880,
   "ts": "2026-10-23T03:31:47+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "改OAuth多账号方案:USERPROFILE隔离实测有效(WRANGLER_HOME无效)；已建cf-oauth-login.cmd+cf-oauth-check.py(10槽0登)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b766d68d9ffaff7",
   "prev": "sha256:13d8623a57335a9"
  },
  {
   "n": 881,
   "ts": "2026-10-23T03:46:25+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "授权搬进APP:cloud-auth窗口+cf:status/login/deploy三条IPC;终端发链接流程退役",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:57c026e68ebf044",
   "prev": "sha256:b766d68d9ffaff7"
  },
  {
   "n": 882,
   "ts": "2026-10-23T03:48:58+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "触手跑十账号授权cf-oauth-auto.py(独立浏览器配置+自动点允许+自动部署)；自检browser/mesh/whoami全绿",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a5cfc7c12541dba",
   "prev": "sha256:57c026e68ebf044"
  },
  {
   "n": 883,
   "ts": "2026-10-23T04:07:49+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "APP十槽安装台(cf:install/令牌内存态)；实测门槛=令牌缺Workers Scripts:Edit",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:592d839ce1c5f1e",
   "prev": "sha256:a5cfc7c12541dba"
  },
  {
   "n": 884,
   "ts": "2026-10-23T06:45:07+08:00",
   "kind": "scan",
   "actor": "unknown",
   "what": "专业体检:模型与APP未对齐(权重复活=断)；caps_tiers账停在239(注册表341，2026-10-01)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7bd379afbb2f324",
   "prev": "sha256:592d839ce1c5f1e"
  },
  {
   "n": 885,
   "ts": "2026-10-23T06:48:53+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "分档账239→341+写手gen-caps-tiers.py+挂开机自检；语音体检=耳无在役采集端点(硬件)、嘴已是Edge神经嗓",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:1f841ce178f7ecd",
   "prev": "sha256:7bd379afbb2f324"
  },
  {
   "n": 886,
   "ts": "2026-10-23T06:50:46+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "嘴验收通过:edge-tts/zh-TW-HsiaoChenNeural/spoken=true;耳仍缺在役采集端点(硬件)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:533128ac80b5bfe",
   "prev": "sha256:1f841ce178f7ecd"
  },
  {
   "n": 887,
   "ts": "2026-10-23T06:52:22+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "耳实测:WDM-KS 4端点全不通(#9/#10 0帧·#11/#6 IOCTL错)；隐私=Allow；PnP无麦克风端点⇒硬件/驱动层",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:de159a969f4ebf0",
   "prev": "sha256:533128ac80b5bfe"
  },
  {
   "n": 888,
   "ts": "2026-10-23T06:55:25+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "耳真因:录制页只有组合口麦克风(未插入)+立体声混音(已停用),无内置麦端点;自纠mic-probe NaN判成REAL",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6db280b9fe89a06",
   "prev": "sha256:de159a969f4ebf0"
  },
  {
   "n": 889,
   "ts": "2026-10-23T06:59:48+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "耳三链路:回环采集通/本地ASR通(heard=true置信0.146)/缺麦克风输入源;真因=Realtek播放侧驱动",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:8d5de24654a38a7",
   "prev": "sha256:6db280b9fe89a06"
  },
  {
   "n": 890,
   "ts": "2026-10-23T07:13:17+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "耳突破:重配对后iPhone HFP麦克风端点ACTIVE(pnputil可见);仍非默认设备故PortAudio打不开;差设为默认",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:f21aa8ec85d6b36",
   "prev": "sha256:8d5de24654a38a7"
  },
  {
   "n": 891,
   "ts": "2026-10-23T07:22:00+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "耳收尾:同端点一次REAL(peak0.029)后又恒SILENCE=间歇静默;手机HFP端点ACTIVE但PortAudio打不开;采集/识别链路均已验",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:76baa9cdac2ea73",
   "prev": "sha256:f21aa8ec85d6b36"
  },
  {
   "n": 892,
   "ts": "2026-10-23T07:23:43+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "一体式验收7条全绿(integrated-check.py,已挂开机自检);顺手删voice-theater里#gbt-project-nav死CSS",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:68f014f7e87c274",
   "prev": "sha256:76baa9cdac2ea73"
  },
  {
   "n": 893,
   "ts": "2026-10-23T07:26:32+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "云插件:cf:verify令牌只读自检+每槽自检按钮;mesh-verify互联验收(90边判据,selftest通过,账本3→1)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7f88b88e73e6046",
   "prev": "sha256:68f014f7e87c274"
  },
  {
   "n": 894,
   "ts": "2026-10-23T07:28:51+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "云插件互联收口:worker支持批量roster(10写→90边)+安装器自动建KV绑定+mesh:sync与页内按钮;真节点实测501缺KV=10节点互不认的根",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:0b4b253dc5d04cb",
   "prev": "sha256:7f88b88e73e6046"
  },
  {
   "n": 895,
   "ts": "2026-10-23T07:46:51+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "自检49步:红2→1;监控基线修绿(op=baseline&from_pack=false,age4s);车道闸>600s挂起未被我的15s超时修好=阻塞点在别处",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:1790b30551923cf",
   "prev": "sha256:0b4b253dc5d04cb"
  },
  {
   "n": 896,
   "ts": "2026-10-23T07:54:12+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "车道闸提速:314.7s→44.9s(真凶=调用方显式timeout120/60/60/180/240,非默认值);判决不变4PASS5WARN1FAIL;F25新证inQueue26→56不消费",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:6cb95908ae8425f",
   "prev": "sha256:1790b30551923cf"
  },
  {
   "n": 897,
   "ts": "2026-10-23T07:59:30+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "页面转圈修复:桥加车道硬截止20s+兜底链(deepseek优先)+空content换道+车道印记;实测20.8s出话lane=deepseek/ours=false",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:c26bddcd8153681",
   "prev": "sha256:6cb95908ae8425f"
  },
  {
   "n": 898,
   "ts": "2026-10-23T08:02:19+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "免费道路落地:桥默认车道切cfai(Workers AI),实测0.8s出话;车道印记lane/weights_ours=false/free=true;三处自纠(模型名/空content/印记语义)",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d68f11ba1d7599d",
   "prev": "sha256:c26bddcd8153681"
  },
  {
   "n": 899,
   "ts": "2026-10-23T08:08:42+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "自家权重优先已上线(ours→ours-alt→cloud→免费道);但RunPod两台端点workers全0,队列69/4,96-120s仍IN_QUEUE不报错=账号侧不provision",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:d66235e56de542d",
   "prev": "sha256:d68f11ba1d7599d"
  },
  {
   "n": 900,
   "ts": "2026-10-23T08:11:53+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "纠偏:cloud_llm口径=只调算力不调模型;先前未指名model落到agnes-3.0-flash(错);现强制指名我们的模型/算力,实测Agnes钥不认RunPod端点=401",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a1341d35cefc0eb",
   "prev": "sha256:d66235e56de542d"
  },
  {
   "n": 901,
   "ts": "2026-10-23T08:17:07+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "按主人法调用:omni_plug op=ai_control 插我们自有算力;plug.state=plugged/host+model+key_slot明示;90s TimeoutError=线通远端无worker",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:c3b79dfc78cd945",
   "prev": "sha256:a1341d35cefc0eb"
  },
  {
   "n": 902,
   "ts": "2026-10-23T08:20:18+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "清理RunPod付费车道(F25按取消车道关闭):桥只留cfai→agnes免费道;实测25.7s→3.1s",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:9f4f4827429a8a2",
   "prev": "sha256:c3b79dfc78cd945"
  },
  {
   "n": 903,
   "ts": "2026-10-23T08:22:28+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "付费车道清理完成+F25按取消关闭;闸换lane-gate-free(1.1s全绿,旧闸保留);桥实测0.7s",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:00bcc736d1b3e6c",
   "prev": "sha256:9f4f4827429a8a2"
  },
  {
   "n": 904,
   "ts": "2026-10-23T08:29:44+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "免费GPU跑自有权重链路备齐:weights.zip3.96GB(v82 Qwen2-7B nf4)+run_gbt_gpu.py+bridge selfhost车道+手册;差Colab会话与上传",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b47cec1b1eb5d9f",
   "prev": "sha256:00bcc736d1b3e6c"
  },
  {
   "n": 905,
   "ts": "2026-10-23T09:52:46+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "自有权重本机跑通(按需激活):解量化100%对官方·前向逐logit一致·真出话'我是本命:一个学习者';0.03tok/s",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:8b5e1f7d65bbcef",
   "prev": "sha256:b47cec1b1eb5d9f"
  },
  {
   "n": 906,
   "ts": "2026-10-23T18:59:46+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增 gguf-q4 契约检查器（env/selftest/compare/roundtrip/scan）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5771449eeaab607",
   "prev": "sha256:8b5e1f7d65bbcef"
  },
  {
   "n": 907,
   "ts": "2026-10-23T19:36:09+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "修 GGUF 特殊 token：bos/eos/pad 现在真落盘；新增 meta 闸",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:5fa5e950260eb3b",
   "prev": "sha256:5771449eeaab607"
  },
  {
   "n": 908,
   "ts": "2026-10-23T19:57:50+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增 fixids：不重导补 bos/eos/pad，4GB 补丁 45 秒",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:93b45e3ea7a3229",
   "prev": "sha256:5fa5e950260eb3b"
  },
  {
   "n": 909,
   "ts": "2026-10-23T20:04:57+08:00",
   "kind": "change",
   "actor": "dsh",
   "what": "桌面权重文档升完整版权：A/B/C三口径·A=31片4.76GB·B=6个GGUF·C=v83 15.25GB只在云上",
   "where": [
    "GBT权重使用文档.md",
    "state/_probe-gguf.py"
   ],
   "hash": "sha256:6b5eafb39fd60ed",
   "prev": "sha256:93b45e3ea7a3229"
  },
  {
   "n": 910,
   "ts": "2026-10-23T20:22:53+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "新增 fullscan-tentacle：目录快照增量扫 + 页面触手并行探针（1.6s/8787页）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:c6c502f91f2302c",
   "prev": "sha256:6b5eafb39fd60ed"
  },
  {
   "n": 911,
   "ts": "2026-10-23T20:46:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "fullscan-tentacle 完工：sqlite 快照 + 页面探针 + 双向绑定体检",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:e06f81f7569a65d",
   "prev": "sha256:c6c502f91f2302c"
  },
  {
   "n": 912,
   "ts": "2026-10-23T20:48:44+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "fullscan 增 usn 子命令（需提权，非提权如实报 3）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:7439120dab3a279",
   "prev": "sha256:e06f81f7569a65d"
  },
  {
   "n": 913,
   "ts": "2026-10-23T20:54:59+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "USN 跑通：全量 24.8s / 增量 1ms（提权），偏移自适应",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a74dfb82c874134",
   "prev": "sha256:7439120dab3a279"
  },
  {
   "n": 914,
   "ts": "2026-10-23T21:19:56+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "USN 路径还原跑通（找到 probe 文件）；建索引 1388s 成新瓶颈",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:1811ffadd1e04f6",
   "prev": "sha256:a74dfb82c874134"
  },
  {
   "n": 915,
   "ts": "2026-10-23T21:21:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "MFT 建库 1388s→47.3s：去掉每条 buf.raw 的 1MB 拷贝",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:8abe4f9d0e15e1a",
   "prev": "sha256:1811ffadd1e04f6"
  },
  {
   "n": 916,
   "ts": "2026-10-23T21:24:02+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "fullscan all 合成一条：快照+页面+绑定（典型 5.6s）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:0e69cee200143dd",
   "prev": "sha256:8abe4f9d0e15e1a"
  },
  {
   "n": 917,
   "ts": "2026-10-23T21:25:50+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "scan 抖动定位：全在走目录段（热 3.4s / 冷 13.3s），其余两段稳定",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:41e0cf992e9fbd3",
   "prev": "sha256:0e69cee200143dd"
  },
  {
   "n": 918,
   "ts": "2026-10-23T21:35:03+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "Q5_0 出片并验通：说人话 + 正确 EOS（4.88GB，4.7s/token）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:b879008de5a8f10",
   "prev": "sha256:41e0cf992e9fbd3"
  },
  {
   "n": 919,
   "ts": "2026-10-23T21:38:19+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "端到端打通：桥 selfhost→本机 Q5_0，weights_ours=true，答'中国的首都是北京。'",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:2a1f489d2909b79",
   "prev": "sha256:b879008de5a8f10"
  },
  {
   "n": 920,
   "ts": "2026-10-23T21:42:32+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "main.cjs 接自有权重：拉起 8792 + 桥带 selfhost env；端到端 laneselfhost/ours=true",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:023428e3867702e",
   "prev": "sha256:2a1f489d2909b79"
  },
  {
   "n": 921,
   "ts": "2026-10-23T21:43:42+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "壳启动加车道自检：桥缺 selfhost 车道就收掉重启（端口定位已验）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:130f15ecb090525",
   "prev": "sha256:023428e3867702e"
  },
  {
   "n": 922,
   "ts": "2026-10-23T21:46:11+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "对话页加 selfhost 选项并逐发报实走车道/weights_ours",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:1285727960d47ea",
   "prev": "sha256:130f15ecb090525"
  },
  {
   "n": 923,
   "ts": "2026-10-23T21:47:49+08:00",
   "kind": "change",
   "actor": "unknown",
   "what": "对话页徽标区分有无 selfhost 车道；all --usn 非提权优雅跳过",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:cabdcb3b5d7be44",
   "prev": "sha256:1285727960d47ea"
  },
  {
   "n": 924,
   "ts": "2026-10-23T21:48:54+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "基准没跑成：第二份 Q5_0 加载即 OOM（commit 0.37GB），GGML_ASSERT mem_buffer",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:2bfe30e89245e0f",
   "prev": "sha256:cabdcb3b5d7be44"
  },
  {
   "n": 925,
   "ts": "2026-10-23T21:55:07+08:00",
   "kind": "decision",
   "actor": "unknown",
   "what": "Q5_0 参数定档：threads=8 ctx=256（冷热差 3 倍，ctx64 优势是假象）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:fece00e84220c27",
   "prev": "sha256:2bfe30e89245e0f"
  },
  {
   "n": 926,
   "ts": "2026-10-23T21:59:51+08:00",
   "kind": "note",
   "actor": "unknown",
   "what": "真 Electron 里验通启动链：本机权重服务 1000ms 就绪；壳在本会话内 GPU 崩溃（环境）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:2b585af977f086a",
   "prev": "sha256:fece00e84220c27"
  },
  {
   "n": 927,
   "ts": "2026-10-23T22:01:32+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "新增 doctor.py 一键体检自有权重链路（6 项全绿）",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:a39a0b84345072a",
   "prev": "sha256:2b585af977f086a"
  },
  {
   "n": 928,
   "ts": "2026-10-23T22:02:49+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "新增 docs 自有权重启动与排障一页纸",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:625b5e9b1ef30bc",
   "prev": "sha256:a39a0b84345072a"
  },
  {
   "n": 929,
   "ts": "2026-10-23T22:21:45+08:00",
   "kind": "deliver",
   "actor": "unknown",
   "what": "v1/chat 流式：首字 4.1s（整句 72s）；页面认 [DONE] 收工",
   "where": [
    "(未点名)"
   ],
   "hash": "sha256:01caa3dd0179061",
   "prev": "sha256:625b5e9b1ef30bc"
  }
 ]
};
