# hypit-ai/hypit 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T09:19:50 | 来源: https://github.com/hypit-ai/hypit
> Stars: 27145 | 语言: TypeScript | 许可: NOASSERTION

## 项目概览
- 描述: Clone any viral video with AI agents. Not just a script, the whole workflow: swap the face, the words, the B-roll, ship 100 variants in one command, and get your 100M views.
- 主题: agentic-ai, ai, ai-agents, ai-video, compiler, dsl, ffmpeg, generative-ai, llm, markup-language
- 分支: main | 最近推送: 2026-10-31

## README 摘要
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/public/hypit-logo-light.svg">
    <img alt="Hypit" src="./docs/public/hypit-logo-dark.svg" width="400" height="122">
  </picture>
</p>

<h3 align="center">Clone any viral video with AI agents</h3>
<p align="center">1 command, 100 variants, 100M views.</p>

<p align="center">
  <a href="https://hypit.ai"><strong>Demo</strong></a>
  &nbsp;&bull;&nbsp;
  <a href="https://hypit.ai/quickstart/"><strong>Quickstart</strong></a>
  &nbsp;&bull;&nbsp;
  <a href="https://hypit.ai/guide/develop/"><strong>Develop</strong></a>
  &nbsp;&bull;&nbsp;
  <a href="./README.zh-CN.md"><strong>简体中文</strong></a>
</p>

<p align="center">
  <a href="https://trendshift.io/repositories/229030"><img alt="Trendshift #1 Repository of the Day" src="https://trendshift.io/api/badge/trendshift/repositories/229030/daily"></a>
</p>

<p align="center">
  <a href="https://trendshift.io/repositories/229030"><img alt="Trendshift #1 TypeScript Repository of the Day" src="https://trendshift.io/api/badge/trendshift/repositories/229030/daily?language=TypeScript"></a>
  <a href="https://trendshift.io/repositories/229030?utm_source=trendshift-badge&amp;utm_medium=badge&amp;utm_campaign=badge-trendshift-229030" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/trendshift/repositories/229030/weekly?language=TypeScript" alt="hypit-ai/hypit | Trendshift TypeScript Weekly" width="250" height="55"></a>
</p>

<p align="center">
  <img alt="Stars" src="https://img.shields.io/github/stars/hypit-ai/hypit?style=flat-square&color=FFD700&logo=github&logoColor=white&label=Stars">
  <a href="./package.json"><img alt="Node 22.15+" src="https://img.shields.io/badge/Node.js-22.15%2B-5FA04E?style=flat-square&logo=nodedotjs&logoColor=white"></a>
  <a href="./package.json"><img alt="pnpm 10.33" src="https://img.shields.io/badge/pnpm-10.33-F69220?style=flat-square&logo=pnpm&logoColor=white"></a>
  <a href="./package.json"><img alt="TypeScript 5.9" src="https://img.shields.io/badge/TypeScript-5.9-3178C6?style=flat-square&logo=typescript&logoColor=white"></a>
  <a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/License-Apache--2.0%20with%20conditions-E3B341?style=flat-square"></a>
</p>

<p align="center">
  <a href="https://hypit.ai"><img alt="Visit our website" src="https://img.shields.io/badge/Visit%20our%20website-DF3C68?style=for-the-badge&logo=hypit&logoColor=white"></a>
  <a href="https://discord.gg/85hnyQnxpn"><img alt="Join our Discord" src="https://img.shields.io/badge/Join%20our%20Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white"></a>
  <a href="https://t.me/hypitai"><img alt="Join our Telegram" src="https://img.shields.io/badge/Join%20our%20Telegram-26A5E4?style=for-the-badge&logo=telegram&logoColor=white"></a>
  <a href="https://x.com/hypitai"><img alt="Follow @hypitai on X" src="https://img.shields.io/badge/Follow%20%40hypitai-000000?style=for-the-badge&logo=x&logoColor=white"></a>
</p>

<p align="center">
  ⭐ <em>Help more people find Hypit and grow the community. Star this repo!</em>
</p>

## Hypit

Hypit gives AI agents (Claude Code, Codex...) a language and system to create video. Drop in a video, and your agent clones it as a complete workflow: footage, captions, B-roll and effects, all anchored to words instead of seconds.

**To be clear:** cloning a video is the fastest way in, not the only one. You can start from our templates, or just describe the video you want and your agent writes the workflow from scratch. Generation models are optional too: a workflow can compile captions, motion graphics and code-rendered visuals into a finished video without calling a generation model or incurring its service charges.

![SVML source and live video preview](https://github.com/user-attachments/assets/981c28e8-ddab-4164-85bc-03b5d71275dc)

<p align="center"><em>SVML source on the left, with the corresponding video rendered live on the right.</em></p>

## Install once

```bash
npx skills add hypit-ai/hypit -g
```

This installs the Skill. On first use, your agent checks for the Hypit executable and helps prepare
it if needed. Your video project can live anywhere.

Hypit is free to use; your Coding Agent and model services have their own accounts and charges.
HypiHub is our recommended hosted model service. You can also use your own API or local models;
tell your agent the service name and API documentation so it can set up the appropriate connection.

[Agent environments and entry partners](./docs/guide/agents.md) ·
[Model and deployment services](./docs/guide/service-partners.md)

## Examples

### UGC

[Generation source](examples/ranking-football/reference.svml) · [Run and production notes](examples/ranking-football/README.md)

<table>
  <tr>
    <th width="16%">Reference</th>
    <td width="28%"></td>
    <td width="28%"><video src="https://github.com/user-attachments/assets/f573bdac-62da-4b5d-825d-54d5880a7026" controls muted></video></td>
    <td width="28%"></td>
  </tr>
  <tr>
    <th width="16%">Clones</th>
    <td width="28%"><video src="https://github.com/user-attachments/assets/3ffd9951-e423-4a48-ad8f-5c596627be69" controls muted></video></td>
    <td width="28%"><video src="https://github.com/user-attachments/assets/eb62372d-2464-4a4b-83ee-41e227f99a8e" controls muted></video></td>
    <td width="28%"><video src="https://github.com/user-attachments/assets/9ba050f6-355d-460c-b684-7344cf49c051" controls muted></video></td>
  </tr>
  <tr>
    <td colspan="4"><p><b>"GOAT DEBATE"</b> — a 20-second football tier list that puts Ronaldo in D and Messi in S. Two Seedance 2 Mini 720p trolling A-rolls, a 2K goth girl portrait and ten 1K brain-rot B-rolls by GPT Image 2, WhisperX word alignment, a sound-synced ranking board, color-box karaoke captions, buttery-smooth animation and catchy background music, concurrently rendered in 64 headless Chromium processes.</p><p>Three clones includ

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识