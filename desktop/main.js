const { app, BrowserWindow, Menu, shell, dialog, screen, globalShortcut,
  Notification, session } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

const PORT = 8766;
let serverProc = null;
let win = null;

function payloadDir() {
  const beside = path.join(path.dirname(process.execPath), "payload");
  if (fs.existsSync(beside)) return beside;
  return path.resolve(__dirname, ".."); // dev: workspace root
}

function pyExe(dir) {
  return path.join(dir, "pyembed", process.platform === "win32" ? "python.exe" : "python");
}

function ping() {
  return new Promise((resolve) => {
    const req = http.get({ host: "127.0.0.1", port: PORT, path: "/api/ping", timeout: 900 },
      (r) => { resolve(r.statusCode === 200); r.resume(); });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

async function ensureServer(dir) {
  if (await ping()) return true;
  const args = ["-X", "utf8", path.join(dir, "tools", "console-server.py"),
    "--port", String(PORT)];
  try {
    serverProc = spawn(pyExe(dir), args, { cwd: dir, windowsHide: true, stdio: "ignore" });
  } catch (e) { return false; }
  for (let i = 0; i < 100; i++) {
    if (await ping()) return true;
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

function saveShot() {
  if (!win) return;
  win.webContents.capturePage().then(function (img) {
    try {
      const dir = path.join(app.getPath("pictures"), "GBT小土豆V8");
      fs.mkdirSync(dir, { recursive: true });
      const f = path.join(dir, "screenshot-" +
        new Date().toISOString().replace(/[:.]/g, "-") + ".png");
      fs.writeFileSync(f, img.toPNG());
      try { new Notification({ title: "截图已保存", body: f }).show(); } catch (e) {}
    } catch (e) { /* ignore */ }
  }).catch(function () {});
}

function createWindow() {
  const icon = path.join(payloadDir(), "icons", "avatar.png");
  const wa = screen.getPrimaryDisplay().workAreaSize;
  const w = Math.max(1024, Math.min(1440, wa.width - 24));
  const h = Math.max(640, Math.min(900, wa.height - 24));
  win = new BrowserWindow({
    width: w, height: h, minWidth: 1024, minHeight: 640,
    center: true,
    title: "GBT小土豆V8",
    backgroundColor: "#111315",
    autoHideMenuBar: true,
    titleBarStyle: "hidden",
    titleBarOverlay: { color: "#111315", symbolColor: "#e6e6e3", height: 30 },
    show: false,
    icon: fs.existsSync(icon) ? icon : undefined,
    webPreferences: { contextIsolation: true, spellcheck: false }
  });
  win.setMenuBarVisibility(false);
  win.maximize();
  const wa2 = screen.getPrimaryDisplay().workAreaSize;
  const zf = Math.max(0.6, Math.min(1, wa2.width / 1280));
  win.webContents.setZoomFactor(zf);
  win.webContents.on("did-finish-load", () => { win.webContents.setZoomFactor(zf); });
  win.once("ready-to-show", () => { win.show(); });
  win.loadURL("http://127.0.0.1:" + PORT + "/console/index.html");
  win.webContents.on("did-finish-load", function () {
    win.webContents.executeJavaScript(
      "document.body.classList.add('electron-app');"
    ).catch(function () {});
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  win.on("closed", () => { win = null; });
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) { if (win.isMinimized()) win.restore(); win.focus(); }
  });
  app.whenReady().then(async () => {
    const dir = payloadDir();
    const ok = await ensureServer(dir);
    if (!ok) {
      dialog.showErrorBox("启动失败",
        "无法启动本地服务（127.0.0.1:8766）。请确认 payload 目录完整，或先运行 停止.bat 清理旧进程。");
      app.quit();
      return;
    }
    try {
      session.defaultSession.setPermissionRequestHandler(function (wc, perm, cb) {
        cb(perm === "media");
      });
      session.defaultSession.setPermissionCheckHandler(function (wc, perm) {
        return perm === "media";
      });
    } catch (e) {}
    Menu.setApplicationMenu(null);
    createWindow();
    try {
      globalShortcut.register("CommandOrControl+Shift+S", saveShot);
    } catch (e) {}
    app.on("will-quit", function () { globalShortcut.unregisterAll(); });
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });
  app.on("window-all-closed", () => { app.quit(); });
  app.on("before-quit", () => {
    if (serverProc && !serverProc.killed) {
      try { serverProc.kill(); } catch (e) {}
    }
  });
}
