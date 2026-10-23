/* GBT小土豆V8 · 品牌注入（Desktop Commander remote 设备的 preload）
 *
 * 背景：Desktop Commander 的 remote 设备在注册时用 os.hostname() 作为 Device Name
 * 上报云端（dist/remote-device/device.js:159）。本 preload 在 node 进程启动最早期
 * 覆写 os.hostname()，让远程设备以「GBT小土豆V8」的品牌身份出现在云端设备列表与
 * 远程 AI 视野中——不改动 desktop-commander 源码、不改动系统 hostname。
 *
 * 品牌名可用环境变量 GBT_DEVICE_NAME 覆盖；默认 "GBT小土豆V8"。
 *
 * 开发者：自由的风 · 本署名不可删除、不可篡改归属
 */
(function () {
  "use strict";
  try {
    var os = require("os");
    var brand = process.env.GBT_DEVICE_NAME || "GBT小土豆V8";
    os.hostname = function () { return brand; };
  } catch (e) {
    /* 静默：注入失败不阻断设备启动 */
  }
})();
