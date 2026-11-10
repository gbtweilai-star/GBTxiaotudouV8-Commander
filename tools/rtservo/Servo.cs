using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Threading;

// Servo —— 原生眼手伺服（必须在 Medium 完整性进程内调用）
//
// 为什么必须在这层做（2026-11-07 实测）：
//   pyembed / 托管 exe 子进程 = Low(0x1000) -> SetCursorPos 被静默拒绝
//   powershell.exe            = Medium(0x2000) -> 正常
//   => 采集可以到处做，输入只能在同一 Medium 进程内 P/Invoke
public class Servo
{
    // ---------------- P/Invoke ----------------
    [DllImport("user32.dll", SetLastError = true)] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern bool GetCursorPos(out POINT p);
    [DllImport("user32.dll")] static extern void mouse_event(uint f, int dx, int dy, uint d, IntPtr e);
    [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr v);
    [DllImport("user32.dll")] static extern int GetSystemMetrics(int i);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowTextW(IntPtr h, System.Text.StringBuilder s, int n);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint SendInput(uint n, INPUTK[] inputs, int size);

    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    public delegate bool EnumProc(IntPtr h, IntPtr l);

    [StructLayout(LayoutKind.Sequential)]
    struct MOUSEINPUT { public int dx; public int dy; public uint mouseData; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }

    [StructLayout(LayoutKind.Sequential)]
    struct KEYBDINPUT { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }

    [StructLayout(LayoutKind.Explicit)]
    struct INPUTUNION { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }

    [StructLayout(LayoutKind.Sequential)]
    struct INPUTK { public uint type; public INPUTUNION u; }

    const uint INPUT_MOUSE = 0;
    const uint INPUT_KEYBOARD = 1;
    const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    const uint MOUSEEVENTF_LEFTUP = 0x0004;
    const uint KEYEVENTF_KEYUP = 0x0002;

    static Servo()
    {
        try { SetProcessDpiAwarenessContext(new IntPtr(-4)); } catch { }
    }

    static string B(bool v) { return v ? "true" : "false"; }

    static string J(string s)
    {
        if (s == null) return "";
        return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", " ").Replace("\n", " ");
    }

    // ---------------- 完整性自述 ----------------
    [DllImport("advapi32.dll", SetLastError = true)] static extern bool OpenProcessToken(IntPtr h, uint a, out IntPtr t);
    [DllImport("advapi32.dll", SetLastError = true)] static extern bool GetTokenInformation(IntPtr t, int c, IntPtr b, uint l, out uint r);
    [DllImport("advapi32.dll")] static extern IntPtr GetSidSubAuthority(IntPtr s, uint i);
    [DllImport("advapi32.dll")] static extern IntPtr GetSidSubAuthorityCount(IntPtr s);
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();

    public static uint IntegrityRid()
    {
        IntPtr tok;
        if (!OpenProcessToken(GetCurrentProcess(), 8, out tok)) return 0xFFFF;
        uint len;
        GetTokenInformation(tok, 25, IntPtr.Zero, 0, out len);
        IntPtr buf = Marshal.AllocHGlobal((int)len);
        uint rid = 0xFFFE;
        if (GetTokenInformation(tok, 25, buf, len, out len))
        {
            IntPtr sid = Marshal.ReadIntPtr(buf);
            byte cnt = Marshal.ReadByte(GetSidSubAuthorityCount(sid));
            rid = (uint)Marshal.ReadInt32(GetSidSubAuthority(sid, (uint)(cnt - 1)));
        }
        Marshal.FreeHGlobal(buf);
        return rid;
    }

    // ---------------- 基础采集 ----------------
    static byte[] GrabRegion(int left, int top, int w, int h, out int stride)
    {
        using (Bitmap b2 = new Bitmap(w, h, PixelFormat.Format32bppArgb))
        {
            using (Graphics g2 = Graphics.FromImage(b2))
                g2.CopyFromScreen(left, top, 0, 0, new Size(w, h), CopyPixelOperation.SourceCopy);
            BitmapData bd = b2.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            stride = bd.Stride;
            byte[] buf = new byte[bd.Stride * h];
            Marshal.Copy(bd.Scan0, buf, 0, buf.Length);
            b2.UnlockBits(bd);
            return buf;
        }
    }

    // ---------------- 颜色检测 ----------------
    static bool FindColor(byte[] buf, int stride, int w, int h,
                          int tr, int tg, int tb, int tol, int step,
                          out int cx, out int cy, out int n)
    {
        long sx = 0, sy = 0; n = 0;
        for (int y = 0; y < h; y += step)
        {
            int row = y * stride;
            for (int x = 0; x < w; x += step)
            {
                int i = row + x * 4;
                if (i + 2 >= buf.Length) continue;
                if (Math.Abs(buf[i + 2] - tr) <= tol && Math.Abs(buf[i + 1] - tg) <= tol && Math.Abs(buf[i] - tb) <= tol)
                { sx += x; sy += y; n++; }
            }
        }
        cx = n > 0 ? (int)(sx / n) : 0;
        cy = n > 0 ? (int)(sy / n) : 0;
        return n >= 4;
    }

    // ---------------- 窗口 ----------------
    public static RECT RectOfPid(int pid)
    {
        RECT best = new RECT(); int bestArea = 0;
        EnumWindows((h, l) =>
        {
            uint p; GetWindowThreadProcessId(h, out p);
            if (p == pid && IsWindowVisible(h))
            {
                RECT r;
                if (GetWindowRect(h, out r))
                {
                    int a = (r.Right - r.Left) * (r.Bottom - r.Top);
                    if (a > bestArea) { bestArea = a; best = r; }
                }
            }
            return true;
        }, IntPtr.Zero);
        return best;
    }

    public static string RectOfPidJson(int pid)
    {
        RECT r = RectOfPid(pid);
        return "{\"left\":" + r.Left + ",\"top\":" + r.Top + ",\"w\":" + (r.Right - r.Left) + ",\"h\":" + (r.Bottom - r.Top) + "}";
    }

    public static string Foreground()
    {
        IntPtr h = GetForegroundWindow();
        uint pid; GetWindowThreadProcessId(h, out pid);
        System.Text.StringBuilder sb = new System.Text.StringBuilder(256);
        GetWindowTextW(h, sb, 256);
        string t = sb.ToString();
        if (t.Length > 70) t = t.Substring(0, 70);
        return "{\"pid\":" + pid + ",\"title\":\"" + J(t) + "\"}";
    }

    // ---------------- 基本动作 ----------------
    public static string Ping()
    {
        POINT p; GetCursorPos(out p);
        return "{\"screen\":[" + GetSystemMetrics(0) + "," + GetSystemMetrics(1)
             + "],\"cursor\":[" + p.X + "," + p.Y + "]"
             + ",\"il\":\"0x" + IntegrityRid().ToString("x") + "\""
             + ",\"session\":" + Process.GetCurrentProcess().SessionId
             + ",\"fg\":" + Foreground()
             + ",\"grab_fps\":" + Grabber.FpsOfCurrent() + "}";
    }

    public static string Move(int x, int y)
    {
        bool ok = SetCursorPos(x, y);
        POINT p; GetCursorPos(out p);
        bool landed = Math.Abs(p.X - x) <= 3 && Math.Abs(p.Y - y) <= 3;
        return "{\"ok\":" + B(ok && landed) + ",\"want\":[" + x + "," + y + "],\"got\":[" + p.X + "," + p.Y + "]}";
    }

    public static string Click(int x, int y)
    {
        SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, IntPtr.Zero);
        Thread.Sleep(25);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, IntPtr.Zero);
        return "{\"ok\":true,\"at\":[" + x + "," + y + "]}";
    }

    public static string Drag(int x1, int y1, int x2, int y2, int steps, int holdMs)
    {
        if (steps < 4) steps = 18;
        if (steps > 120) steps = 120;
        if (holdMs < 30) holdMs = 80;
        SetCursorPos(x1, y1);
        Thread.Sleep(holdMs);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, IntPtr.Zero);
        Thread.Sleep(30);
        for (int i = 1; i <= steps; i++)
        {
            int x = x1 + (int)((x2 - x1) * (double)i / steps);
            int y = y1 + (int)((y2 - y1) * (double)i / steps);
            SetCursorPos(x, y);
            Thread.Sleep(8);
        }
        Thread.Sleep(40);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, IntPtr.Zero);
        POINT p; GetCursorPos(out p);
        return "{\"ok\":true,\"from\":[" + x1 + "," + y1 + "],\"to\":[" + x2 + "," + y2
             + "],\"steps\":" + steps + ",\"cursor\":[" + p.X + "," + p.Y + "]}";
    }

    // ---------------- 键盘 ----------------
    static ushort Vk(string name)
    {
        string s = name.ToUpperInvariant();
        switch (s)
        {
            case "ENTER": case "RETURN": return 0x0D;
            case "TAB": return 0x09;
            case "ESC": case "ESCAPE": return 0x1B;
            case "SPACE": return 0x20;
            case "BACKSPACE": case "BS": return 0x08;
            case "DELETE": case "DEL": return 0x2E;
            case "UP": return 0x26;
            case "DOWN": return 0x28;
            case "LEFT": return 0x25;
            case "RIGHT": return 0x27;
            case "HOME": return 0x24;
            case "END": return 0x23;
            case "PGUP": return 0x21;
            case "PGDN": return 0x22;
            case "CTRL": case "CONTROL": return 0x11;
            case "ALT": return 0x12;
            case "SHIFT": return 0x10;
            case "WIN": case "LWIN": return 0x5B;
            case "F1": return 0x70; case "F2": return 0x71; case "F3": return 0x72; case "F4": return 0x73;
            case "F5": return 0x74; case "F6": return 0x75; case "F7": return 0x76; case "F8": return 0x77;
            case "F9": return 0x78; case "F10": return 0x79; case "F11": return 0x7A; case "F12": return 0x7B;
        }
        if (s.Length == 1)
        {
            char c = s[0];
            if (c >= 'A' && c <= 'Z') return (ushort)c;
            if (c >= '0' && c <= '9') return (ushort)c;
        }
        return 0;
    }

    static void KeyEvent(ushort vk, bool up)
    {
        INPUTK[] arr = new INPUTK[1];
        arr[0].type = INPUT_KEYBOARD;
        arr[0].u.ki.wVk = vk;
        arr[0].u.ki.wScan = 0;
        arr[0].u.ki.dwFlags = up ? KEYEVENTF_KEYUP : 0;
        arr[0].u.ki.time = 0;
        arr[0].u.ki.dwExtraInfo = IntPtr.Zero;
        SendInput(1, arr, Marshal.SizeOf(typeof(INPUTK)));
    }

    // combo 形如 "CTRL+S" / "ENTER" / "ALT+F4"
    public static string Key(string combo)
    {
        if (combo == null) combo = "";
        string[] parts = combo.Split('+');
        List<ushort> vks = new List<ushort>();
        foreach (string raw in parts)
        {
            ushort vk = Vk(raw.Trim());
            if (vk == 0) return "{\"ok\":false,\"error\":\"unknown key: " + J(raw.Trim()) + "\"}";
            vks.Add(vk);
        }
        for (int i = 0; i < vks.Count; i++) { KeyEvent(vks[i], false); Thread.Sleep(15); }
        for (int i = vks.Count - 1; i >= 0; i--) { KeyEvent(vks[i], true); Thread.Sleep(15); }
        return "{\"ok\":true,\"keys\":\"" + J(combo) + "\"}";
    }

    // ---------------- 等目标出现 ----------------
    public static string WaitFor(int tr, int tg, int tb, int tol, int step, int timeoutMs, int pid)
    {
        int L = 0, T = 0, W = GetSystemMetrics(0), H = GetSystemMetrics(1);
        if (pid > 0)
        {
            RECT r = RectOfPid(pid);
            if (r.Right - r.Left > 50) { L = r.Left; T = r.Top; W = r.Right - r.Left; H = r.Bottom - r.Top; }
        }
        Stopwatch sw = Stopwatch.StartNew();
        while (sw.ElapsedMilliseconds < timeoutMs)
        {
            int stride;
            byte[] buf = GrabRegion(L, T, W, H, out stride);
            int cx, cy, n;
            if (FindColor(buf, stride, W, H, tr, tg, tb, tol, step, out cx, out cy, out n))
            {
                return "{\"ok\":true,\"found\":true,\"ms\":" + sw.ElapsedMilliseconds
                     + ",\"x\":" + (L + cx) + ",\"y\":" + (T + cy) + ",\"count\":" + n + "}";
            }
            Thread.Sleep(30);
        }
        return "{\"ok\":true,\"found\":false,\"ms\":" + sw.ElapsedMilliseconds + "}";
    }

    public static string FindColorJson(int tr, int tg, int tb, int tol, int step, int pid)
    {
        int L = 0, T = 0, W = GetSystemMetrics(0), H = GetSystemMetrics(1);
        if (pid > 0)
        {
            RECT r = RectOfPid(pid);
            if (r.Right - r.Left > 50) { L = r.Left; T = r.Top; W = r.Right - r.Left; H = r.Bottom - r.Top; }
        }
        int stride;
        byte[] buf = GrabRegion(L, T, W, H, out stride);
        int cx, cy, n;
        if (!FindColor(buf, stride, W, H, tr, tg, tb, tol, step, out cx, out cy, out n))
            return "{\"found\":false}";
        return "{\"found\":true,\"x\":" + (L + cx) + ",\"y\":" + (T + cy) + ",\"count\":" + n + "}";
    }

    // ================================================================
    //                   双线程抓帧（采集与控制解耦）
    // ================================================================

    public class Grabber
    {
        Thread th;
        volatile bool running;
        readonly object lk = new object();
        byte[] frame;
        int stride, w, h;
        long seq;
        int left, top;
        bool regionDirty;
        int targetL, targetT, targetW, targetH;
        double fps;
        static Grabber current;

        public static double FpsOfCurrent() { return current == null ? 0 : Math.Round(current.fps, 1); }

        public static Grabber Get(int l, int t, int ww, int hh)
        {
            Grabber g = current;
            if (g == null)
            {
                g = new Grabber();
                current = g;
                g.SetRegion(l, t, ww, hh);
                g.Start();
            }
            else if (g.left != l || g.top != t || g.w != ww || g.h != hh)
            {
                g.SetRegion(l, t, ww, hh);
            }
            return g;
        }

        void SetRegion(int l, int t, int ww, int hh)
        {
            lock (lk) { targetL = l; targetT = t; targetW = ww; targetH = hh; regionDirty = true; }
        }

        void Start()
        {
            running = true;
            th = new Thread(Loop);
            th.IsBackground = true;
            th.Start();
        }

        public void Stop() { running = false; }

        void Loop()
        {
            Bitmap bmp = null;
            Graphics g = null;
            int cw = 0, ch = 0;
            long n = 0;
            Stopwatch fpsWatch = Stopwatch.StartNew();

            while (running)
            {
                if (regionDirty)
                {
                    lock (lk)
                    {
                        left = targetL; top = targetT; w = targetW; h = targetH;
                        regionDirty = false;
                    }
                    if (bmp == null || cw != w || ch != h)
                    {
                        if (g != null) g.Dispose();
                        if (bmp != null) bmp.Dispose();
                        bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
                        g = Graphics.FromImage(bmp);
                        cw = w; ch = h;
                    }
                }
                if (bmp == null) { Thread.Sleep(5); continue; }

                try
                {
                    g.CopyFromScreen(left, top, 0, 0, new Size(w, h), CopyPixelOperation.SourceCopy);
                    BitmapData bd = bmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                    int st = bd.Stride;
                    byte[] buf = new byte[st * h];
                    Marshal.Copy(bd.Scan0, buf, 0, buf.Length);
                    bmp.UnlockBits(bd);
                    lock (lk)
                    {
                        frame = buf; stride = st; seq++;
                    }
                    n++;
                    if (fpsWatch.ElapsedMilliseconds >= 1000)
                    {
                        fps = n * 1000.0 / fpsWatch.ElapsedMilliseconds;
                        n = 0; fpsWatch.Restart();
                    }
                }
                catch { Thread.Sleep(10); }
                Thread.Sleep(1);
            }

            if (g != null) g.Dispose();
            if (bmp != null) bmp.Dispose();
        }

        public bool Latest(out byte[] buf, out int st, out int ww, out int hh, out long s)
        {
            lock (lk)
            {
                buf = frame; st = stride; ww = w; hh = h; s = seq;
                return frame != null;
            }
        }

        public int Left { get { return left; } }
        public int Top { get { return top; } }
        public int W { get { return w; } }
        public int H { get { return h; } }
    }

    // ================================================================
    //                   模板匹配（金字塔 + 归一化互相关）
    // ================================================================

    static byte[] tpl;          // 灰度模板
    static int tplW, tplH, tplStride;
    static string tplPath = "";

    static byte[] ToGray(byte[] bgra, int stride, int w, int h)
    {
        byte[] gray = new byte[w * h];
        for (int y = 0; y < h; y++)
        {
            int row = y * stride;
            int grow = y * w;
            for (int x = 0; x < w; x++)
            {
                int i = row + x * 4;
                gray[grow + x] = (byte)((bgra[i + 2] * 299 + bgra[i + 1] * 587 + bgra[i] * 114) / 1000);
            }
        }
        return gray;
    }

    static float[] Downsample(byte[] gray, int w, int h, int ds, out int ow, out int oh)
    {
        ow = Math.Max(1, w / ds);
        oh = Math.Max(1, h / ds);
        float[] o = new float[ow * oh];
        for (int y = 0; y < oh; y++)
        {
            int sy = y * ds, srow = sy * w;
            int orow = y * ow;
            for (int x = 0; x < ow; x++)
            {
                int sx = x * ds;
                float sum = 0; int cnt = 0;
                for (int yy = 0; yy < ds && sy + yy < h; yy++)
                {
                    int r = srow + yy * w;
                    for (int xx = 0; xx < ds && sx + xx < w; xx++)
                    { sum += gray[r + sx + xx]; cnt++; }
                }
                o[orow + x] = cnt > 0 ? sum / cnt : 0;
            }
        }
        return o;
    }

    // 归一化互相关（零均值），返回 -1..1
    static double Ncc(float[] hay, int hw, int hh, float[] t, int tw, int th, int ox, int oy)
    {
        int n = tw * th;
        double sumH = 0, sumT = 0, sumHT = 0, sumHH = 0, sumTT = 0;
        for (int y = 0; y < th; y++)
        {
            int hrow = (oy + y) * hw + ox;
            int trow = y * tw;
            for (int x = 0; x < tw; x++)
            {
                double hv = hay[hrow + x], tv = t[trow + x];
                sumH += hv; sumT += tv;
                sumHT += hv * tv; sumHH += hv * hv; sumTT += tv * tv;
            }
        }
        double num = sumHT - sumH * sumT / n;
        double d1 = sumHH - sumH * sumH / n;
        double d2 = sumTT - sumT * sumT / n;
        double den = Math.Sqrt(Math.Max(d1, 1e-9) * Math.Max(d2, 1e-9));
        return num / den;
    }

    public static string TplLoad(string path)
    {
        try
        {
            using (Bitmap src = new Bitmap(path))
            {
                tplW = src.Width; tplH = src.Height;
                BitmapData bd = src.LockBits(new Rectangle(0, 0, tplW, tplH), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                tplStride = bd.Stride;
                byte[] raw = new byte[bd.Stride * tplH];
                Marshal.Copy(bd.Scan0, raw, 0, raw.Length);
                src.UnlockBits(bd);
                tpl = ToGray(raw, tplStride, tplW, tplH);
                tplStride = tplW;
                tplPath = path;
            }
            return "{\"ok\":true,\"w\":" + tplW + ",\"h\":" + tplH + ",\"path\":\"" + J(path) + "\"}";
        }
        catch (Exception ex)
        {
            return "{\"ok\":false,\"error\":\"" + J(ex.Message) + "\"}";
        }
    }

    // 在灰度帧里找模板；返回帧内坐标
    static bool MatchTpl(byte[] gray, int w, int h, double minScore, int ds,
                         out int bx, out int by, out double score)
    {
        bx = by = 0; score = -1;
        if (tpl == null) return false;
        if (tplW >= w || tplH >= h) return false;

        int hw, hh, tw, th;
        float[] hay = Downsample(gray, w, h, ds, out hw, out hh);
        float[] t = Downsample(tpl, tplW, tplH, ds, out tw, out th);
        if (tw < 2 || th < 2 || tw >= hw || th >= hh) return false;

        double best = -2;
        int bestX = 0, bestY = 0;
        for (int y = 0; y + th <= hh; y += 2)
        {
            for (int x = 0; x + tw <= hw; x += 2)
            {
                double s = Ncc(hay, hw, hh, t, tw, th, x, y);
                if (s > best) { best = s; bestX = x; bestY = y; }
            }
        }
        if (best < minScore) return false;

        // 粗定位 -> 全分辨率精修
        int cx0 = bestX * ds, cy0 = bestY * ds;
        int pad = ds * 3;
        double fineBest = -2;
        int fx = cx0, fy = cy0;
        for (int y = Math.Max(0, cy0 - pad); y <= Math.Min(h - tplH, cy0 + pad); y++)
        {
            for (int x = Math.Max(0, cx0 - pad); x <= Math.Min(w - tplW, cx0 + pad); x++)
            {
                double s = NccGray(gray, w, tpl, tplW, tplH, x, y);
                if (s > fineBest) { fineBest = s; fx = x; fy = y; }
            }
        }
        bx = fx + tplW / 2;
        by = fy + tplH / 2;
        score = fineBest;
        return fineBest >= minScore;
    }

    static double NccGray(byte[] hay, int hw, byte[] t, int tw, int th, int ox, int oy)
    {
        int n = tw * th;
        double sumH = 0, sumT = 0, sumHT = 0, sumHH = 0, sumTT = 0;
        for (int y = 0; y < th; y++)
        {
            int hrow = (oy + y) * hw + ox;
            int trow = y * tw;
            for (int x = 0; x < tw; x++)
            {
                double hv = hay[hrow + x], tv = t[trow + x];
                sumH += hv; sumT += tv;
                sumHT += hv * tv; sumHH += hv * hv; sumTT += tv * tv;
            }
        }
        double num = sumHT - sumH * sumT / n;
        double d1 = sumHH - sumH * sumH / n;
        double d2 = sumTT - sumT * sumT / n;
        double den = Math.Sqrt(Math.Max(d1, 1e-9) * Math.Max(d2, 1e-9));
        return num / den;
    }

    public static string TplFind(double minScore, int pid)
    {
        if (tpl == null) return "{\"ok\":false,\"error\":\"no template loaded\"}";
        int L = 0, T = 0, W = GetSystemMetrics(0), H = GetSystemMetrics(1);
        if (pid > 0)
        {
            RECT r = RectOfPid(pid);
            if (r.Right - r.Left > 50) { L = r.Left; T = r.Top; W = r.Right - r.Left; H = r.Bottom - r.Top; }
        }
        int stride;
        byte[] buf = GrabRegion(L, T, W, H, out stride);
        byte[] gray = ToGray(buf, stride, W, H);
        int bx, by; double sc;
        if (!MatchTpl(gray, W, H, minScore, 4, out bx, out by, out sc))
            return "{\"ok\":true,\"found\":false,\"score\":" + Math.Round(sc, 3) + "}";
        return "{\"ok\":true,\"found\":true,\"x\":" + (L + bx) + ",\"y\":" + (T + by)
             + ",\"score\":" + Math.Round(sc, 3) + ",\"w\":" + tplW + ",\"h\":" + tplH + "}";
    }

    // ================================================================
    //                  TRACK —— 单线程（保留兼容）
    // ================================================================

    public static string Track(int tr, int tg, int tb, int tol, int step,
                               double secs, double gain, int dead, int pid)
    {
        int L = 0, T = 0, W = GetSystemMetrics(0), H = GetSystemMetrics(1);
        if (pid > 0)
        {
            RECT r = RectOfPid(pid);
            if (r.Right - r.Left > 50) { L = r.Left; T = r.Top; W = r.Right - r.Left; H = r.Bottom - r.Top; }
        }

        List<double> loops = new List<double>();
        int cycles = 0, hits = 0, misses = 0;
        double errSum = 0, firstHit = -1;
        Stopwatch total = Stopwatch.StartNew();
        Stopwatch sw = new Stopwatch();
        POINT p;

        while (total.Elapsed.TotalSeconds < secs)
        {
            sw.Restart();
            int stride;
            byte[] buf = GrabRegion(L, T, W, H, out stride);
            int cx, cy, n;
            if (!FindColor(buf, stride, W, H, tr, tg, tb, tol, step, out cx, out cy, out n)) { misses++; continue; }

            int tx = L + cx, ty = T + cy;
            GetCursorPos(out p);
            double ex = tx - p.X, ey = ty - p.Y;
            double err = Math.Sqrt(ex * ex + ey * ey);
            errSum += err;
            if (err <= dead) { hits++; if (firstHit < 0) firstHit = total.Elapsed.TotalMilliseconds; }
            else SetCursorPos((int)(p.X + ex * gain), (int)(p.Y + ey * gain));
            cycles++;
            loops.Add(sw.Elapsed.TotalMilliseconds);
        }

        return Summary(cycles, hits, misses, errSum, firstHit, loops, L, T, W, H);
    }

    // ================================================================
    //             TRACK2 —— 双线程（采集线程 + 控制环）
    // ================================================================

    public static string Track2(int tr, int tg, int tb, int tol, int step,
                                double secs, double gain, int dead, int pid)
    {
        int L = 0, T = 0, W = GetSystemMetrics(0), H = GetSystemMetrics(1);
        if (pid > 0)
        {
            RECT r = RectOfPid(pid);
            if (r.Right - r.Left > 50) { L = r.Left; T = r.Top; W = r.Right - r.Left; H = r.Bottom - r.Top; }
        }

        Grabber gb = Grabber.Get(L, T, W, H);
        // 等采集线程出第一帧
        long waitUntil = Environment.TickCount + 3000;
        byte[] buf; int stride, gw, gh; long sq;
        while (Environment.TickCount < waitUntil)
        {
            if (gb.Latest(out buf, out stride, out gw, out gh, out sq) && sq > 0) break;
            Thread.Sleep(5);
        }
        if (!gb.Latest(out buf, out stride, out gw, out gh, out sq))
            return "{\"ok\":false,\"error\":\"capture thread gave no frame\"}";

        List<double> loops = new List<double>();
        int cycles = 0, hits = 0, misses = 0;
        double errSum = 0, firstHit = -1;
        long lastSeq = -1;
        Stopwatch total = Stopwatch.StartNew();
        Stopwatch sw = new Stopwatch();
        POINT p;

        while (total.Elapsed.TotalSeconds < secs)
        {
            sw.Restart();
            if (!gb.Latest(out buf, out stride, out gw, out gh, out sq)) { Thread.Sleep(1); continue; }
            if (sq == lastSeq) { Thread.Sleep(1); continue; }   // 没新帧就不重复决策
            lastSeq = sq;

            int cx, cy, n;
            if (!FindColor(buf, stride, gw, gh, tr, tg, tb, tol, step, out cx, out cy, out n)) { misses++; continue; }

            int tx = gb.Left + cx, ty = gb.Top + cy;
            GetCursorPos(out p);
            double ex = tx - p.X, ey = ty - p.Y;
            double err = Math.Sqrt(ex * ex + ey * ey);
            errSum += err;
            if (err <= dead) { hits++; if (firstHit < 0) firstHit = total.Elapsed.TotalMilliseconds; }
            else SetCursorPos((int)(p.X + ex * gain), (int)(p.Y + ey * gain));
            cycles++;
            loops.Add(sw.Elapsed.TotalMilliseconds);
        }

        string s = Summary(cycles, hits, misses, errSum, firstHit, loops, gb.Left, gb.Top, gb.W, gb.H);
        return s.Substring(0, s.Length - 1) + ",\"grab_fps\":" + Math.Round(Grabber.FpsOfCurrent(), 1) + ",\"mode\":\"dual-thread\"}";
    }

    // ================================================================
    //            TPLTRACK —— 模板闭环（追任意图像目标）
    // ================================================================

    public static string TplTrack(double secs, double minScore, int dead, int pid)
    {
        if (tpl == null) return "{\"ok\":false,\"error\":\"no template loaded\"}";

        int L = 0, T = 0, W = GetSystemMetrics(0), H = GetSystemMetrics(1);
        if (pid > 0)
        {
            RECT r = RectOfPid(pid);
            if (r.Right - r.Left > 50) { L = r.Left; T = r.Top; W = r.Right - r.Left; H = r.Bottom - r.Top; }
        }

        Grabber gb = Grabber.Get(L, T, W, H);
        long waitUntil = Environment.TickCount + 3000;
        byte[] buf; int stride, gw, gh; long sq;
        while (Environment.TickCount < waitUntil)
        {
            if (gb.Latest(out buf, out stride, out gw, out gh, out sq) && sq > 0) break;
            Thread.Sleep(5);
        }

        List<double> loops = new List<double>();
        int cycles = 0, hits = 0, misses = 0;
        double errSum = 0, scoreSum = 0, firstHit = -1;
        long lastSeq = -1;
        Stopwatch total = Stopwatch.StartNew();
        Stopwatch sw = new Stopwatch();
        POINT p;

        while (total.Elapsed.TotalSeconds < secs)
        {
            sw.Restart();
            if (!gb.Latest(out buf, out stride, out gw, out gh, out sq)) { Thread.Sleep(1); continue; }
            if (sq == lastSeq) { Thread.Sleep(1); continue; }
            lastSeq = sq;

            byte[] gray = ToGray(buf, stride, gw, gh);
            int bx, by; double sc;
            if (!MatchTpl(gray, gw, gh, minScore, 4, out bx, out by, out sc)) { misses++; continue; }
            scoreSum += sc;

            int tx = gb.Left + bx, ty = gb.Top + by;
            GetCursorPos(out p);
            double ex = tx - p.X, ey = ty - p.Y;
            double err = Math.Sqrt(ex * ex + ey * ey);
            errSum += err;
            if (err <= dead) { hits++; if (firstHit < 0) firstHit = total.Elapsed.TotalMilliseconds; }
            else SetCursorPos(tx, ty);
            cycles++;
            loops.Add(sw.Elapsed.TotalMilliseconds);
        }

        string s = Summary(cycles, hits, misses, errSum, firstHit, loops, gb.Left, gb.Top, gb.W, gb.H);
        double avgScore = cycles > 0 ? scoreSum / cycles : 0;
        return s.Substring(0, s.Length - 1)
             + ",\"avg_score\":" + Math.Round(avgScore, 3)
             + ",\"grab_fps\":" + Math.Round(Grabber.FpsOfCurrent(), 1)
             + ",\"mode\":\"template\"}";
    }

    // ---------------- 输出 ----------------
    static string Summary(int cycles, int hits, int misses, double errSum, double firstHit,
                          List<double> loops, int L, int T, int W, int H)
    {
        loops.Sort();
        double avg = 0, p95 = 0;
        if (loops.Count > 0)
        {
            double s = 0; foreach (double d in loops) s += d;
            avg = s / loops.Count;
            p95 = loops[(int)Math.Min(loops.Count - 1, loops.Count * 0.95)];
        }
        return "{\"cycles\":" + cycles
             + ",\"hz\":" + (avg > 0 ? Math.Round(1000.0 / avg, 1) : 0)
             + ",\"loop_avg_ms\":" + Math.Round(avg, 2)
             + ",\"loop_p95_ms\":" + Math.Round(p95, 2)
             + ",\"err_avg_px\":" + Math.Round(cycles > 0 ? errSum / cycles : 0, 1)
             + ",\"on_target_pct\":" + (cycles > 0 ? Math.Round(100.0 * hits / cycles, 1) : 0)
             + ",\"misses\":" + misses
             + ",\"converge_ms\":" + Math.Round(firstHit, 0)
             + ",\"region\":[" + L + "," + T + "," + W + "," + H + "]}";
    }
}
