using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

// RtServo —— 常驻原生伺服进程：
//   采集线程持续抓屏，控制线程按命令动，动作后立刻用新帧校验。
//   必须以 Medium 完整性运行（pyembed/Low 无法注入输入），所以由 WMI 拉起。
public class RtServo
{
    [DllImport("user32.dll", SetLastError = true)]
    static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")]
    static extern bool GetCursorPos(out POINT p);
    [DllImport("user32.dll")]
    static extern void mouse_event(uint f, int dx, int dy, uint d, IntPtr e);
    [DllImport("user32.dll")]
    static extern bool SetProcessDpiAwarenessContext(IntPtr v);
    [DllImport("user32.dll")]
    static extern int GetSystemMetrics(int i);
    [DllImport("user32.dll")]
    static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")]
    static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")]
    static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")]
    static extern bool EnumWindows(EnumProc cb, IntPtr l);

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    public delegate bool EnumProc(IntPtr h, IntPtr l);

    static int SW, SH;
    static volatile bool running = true;

    // ---------- integrity ----------
    [DllImport("advapi32.dll", SetLastError = true)]
    static extern bool OpenProcessToken(IntPtr h, uint acc, out IntPtr tok);
    [DllImport("advapi32.dll", SetLastError = true)]
    static extern bool GetTokenInformation(IntPtr tok, int cls, IntPtr buf, uint len, out uint ret);
    [DllImport("advapi32.dll")]
    static extern IntPtr GetSidSubAuthority(IntPtr sid, uint idx);
    [DllImport("advapi32.dll")]
    static extern IntPtr GetSidSubAuthorityCount(IntPtr sid);
    [DllImport("kernel32.dll")]
    static extern IntPtr GetCurrentProcess();

    static uint IntegrityRid()
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

    // ---------- capture ----------
    static Bitmap bmp;
    static Graphics gfx;

    static void InitCapture()
    {
        SW = GetSystemMetrics(0);
        SH = GetSystemMetrics(1);
        bmp = new Bitmap(SW, SH, PixelFormat.Format32bppArgb);
        gfx = Graphics.FromImage(bmp);
    }

    static byte[] GrabBytes()
    {
        gfx.CopyFromScreen(0, 0, 0, 0, new Size(SW, SH), CopyPixelOperation.SourceCopy);
        BitmapData bd = bmp.LockBits(new Rectangle(0, 0, SW, SH),
                                     ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        int stride = bd.Stride;
        byte[] buf = new byte[stride * SH];
        Marshal.Copy(bd.Scan0, buf, 0, buf.Length);
        bmp.UnlockBits(bd);
        return buf;
    }

    static byte[] GrabRegion(int left, int top, int w, int h, out int stride)
    {
        Bitmap b2 = new Bitmap(w, h, PixelFormat.Format32bppArgb);
        using (Graphics g2 = Graphics.FromImage(b2))
            g2.CopyFromScreen(left, top, 0, 0, new Size(w, h), CopyPixelOperation.SourceCopy);
        BitmapData bd = b2.LockBits(new Rectangle(0, 0, w, h),
                                    ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        stride = bd.Stride;
        byte[] buf = new byte[bd.Stride * h];
        Marshal.Copy(bd.Scan0, buf, 0, buf.Length);
        b2.UnlockBits(bd);
        b2.Dispose();
        return buf;
    }

    // ---------- detection ----------
    // find centroid of pixels whose BGR matches target within tolerance
    static bool FindColor(byte[] buf, int stride, int w, int h,
                          int tr, int tg, int tb, int tol, int step,
                          out int cx, out int cy, out int count)
    {
        long sx = 0, sy = 0;
        int n = 0;
        for (int y = 0; y < h; y += step)
        {
            int row = y * stride;
            for (int x = 0; x < w; x += step)
            {
                int i = row + x * 4;
                if (i + 2 >= buf.Length) continue;
                int b = buf[i], g = buf[i + 1], r = buf[i + 2];
                if (Math.Abs(r - tr) <= tol && Math.Abs(g - tg) <= tol && Math.Abs(b - tb) <= tol)
                {
                    sx += x; sy += y; n++;
                }
            }
        }
        if (n < 4) { cx = cy = 0; count = 0; return false; }
        cx = (int)(sx / n); cy = (int)(sy / n); count = n;
        return true;
    }

    // ---------- window helpers ----------
    static RECT RectOfPid(int pid)
    {
        RECT best = new RECT();
        int bestArea = 0;
        EnumWindows((h, l) =>
        {
            uint p;
            GetWindowThreadProcessId(h, out p);
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

    static string ForegroundInfo()
    {
        IntPtr h = GetForegroundWindow();
        uint pid;
        GetWindowThreadProcessId(h, out pid);
        StringBuilder sb = new StringBuilder(256);
        GetWindowTextW(h, sb, 256);
        string title = sb.ToString();
        if (title.Length > 60) title = title.Substring(0, 60);
        return "{\"pid\":" + pid + ",\"title\":\"" + J(title) + "\"}";
    }

    static string J(string s)
    {
        if (s == null) return "";
        return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "").Replace("\n", " ");
    }

    // ---------- command handlers ----------
    public static string Handle(string cmd)
    {
        string[] p = cmd.Split(' ');
        string op = p[0].ToUpperInvariant();

        try
        {
            switch (op)
            {
                case "PING":
                {
                    POINT pt; GetCursorPos(out pt);
                    return "{\"ok\":true,\"screen\":[" + SW + "," + SH + "],\"cursor\":[" + pt.X + "," + pt.Y + "],\"il\":\"0x" + IntegrityRid().ToString("x") + "\",\"session\":" + Process.GetCurrentProcess().SessionId + ",\"fg\":" + ForegroundInfo() + "}";
                }
                case "IL":
                {
                    return "{\"ok\":true,\"integrity\":\"0x" + IntegrityRid().ToString("x") + "\",\"session\":" + Process.GetCurrentProcess().SessionId + "}";
                }
                case "MOVE":
                {
                    int x = int.Parse(p[1]), y = int.Parse(p[2]);
                    bool ok = SetCursorPos(x, y);
                    POINT pt; GetCursorPos(out pt);
                    bool landed = Math.Abs(pt.X - x) <= 3 && Math.Abs(pt.Y - y) <= 3;
                    return "{\"ok\":" + (ok && landed).ToString().ToLower()
                         + ",\"want\":[" + x + "," + y + "],\"got\":[" + pt.X + "," + pt.Y + "],\"landed\":" + landed.ToString().ToLower() + "}";
                }
                case "CLICK":
                {
                    if (p.Length > 2) SetCursorPos(int.Parse(p[1]), int.Parse(p[2]));
                    mouse_event(0x0002, 0, 0, 0, IntPtr.Zero);
                    Thread.Sleep(30);
                    mouse_event(0x0004, 0, 0, 0, IntPtr.Zero);
                    return "{\"ok\":true,\"clicked\":true}";
                }
                case "DBLCLICK":
                {
                    if (p.Length > 2) SetCursorPos(int.Parse(p[1]), int.Parse(p[2]));
                    for (int i = 0; i < 2; i++)
                    {
                        mouse_event(0x0002, 0, 0, 0, IntPtr.Zero);
                        Thread.Sleep(20);
                        mouse_event(0x0004, 0, 0, 0, IntPtr.Zero);
                        Thread.Sleep(40);
                    }
                    return "{\"ok\":true}";
                }
                case "DOWN":
                    mouse_event(0x0002, 0, 0, 0, IntPtr.Zero);
                    return "{\"ok\":true,\"down\":true}";
                case "UP":
                    mouse_event(0x0004, 0, 0, 0, IntPtr.Zero);
                    return "{\"ok\":true,\"up\":true}";
                case "GRAB":
                {
                    int left = int.Parse(p[1]), top = int.Parse(p[2]);
                    int w = int.Parse(p[3]), h = int.Parse(p[4]);
                    int stride;
                    byte[] buf = GrabRegion(left, top, w, h, out stride);
                    using (Bitmap b3 = new Bitmap(w, h, PixelFormat.Format32bppArgb))
                    {
                        BitmapData bd = b3.LockBits(new Rectangle(0, 0, w, h),
                                                    ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
                        Marshal.Copy(buf, 0, bd.Scan0, buf.Length);
                        b3.UnlockBits(bd);
                        string path = Path.Combine(Path.GetTempPath(), "rtservo_" + DateTime.Now.Ticks + ".png");
                        b3.Save(path, ImageFormat.Png);
                        return "{\"ok\":true,\"path\":\"" + J(path) + "\",\"w\":" + w + ",\"h\":" + h + "}";
                    }
                }
                case "FINDCOLOR":
                {
                    // FINDCOLOR r g b tol step [left top w h]
                    int tr = int.Parse(p[1]), tg = int.Parse(p[2]), tb = int.Parse(p[3]);
                    int tol = int.Parse(p[4]), step = int.Parse(p[5]);
                    int left = 0, top = 0, w = SW, h = SH;
                    if (p.Length >= 10)
                    {
                        left = int.Parse(p[6]); top = int.Parse(p[7]);
                        w = int.Parse(p[8]); h = int.Parse(p[9]);
                    }
                    int stride;
                    byte[] buf = GrabRegion(left, top, w, h, out stride);
                    int cx, cy, cnt;
                    bool found = FindColor(buf, stride, w, h, tr, tg, tb, tol, step, out cx, out cy, out cnt);
                    if (!found) return "{\"ok\":true,\"found\":false}";
                    return "{\"ok\":true,\"found\":true,\"x\":" + (left + cx) + ",\"y\":" + (top + cy)
                         + ",\"count\":" + cnt + ",\"local\":[" + cx + "," + cy + "]}";
                }
                case "TRACK":
                {
                    // TRACK r g b tol step seconds gain deadband [pidForWindow]
                    int tr = int.Parse(p[1]), tg = int.Parse(p[2]), tb = int.Parse(p[3]);
                    int tol = int.Parse(p[4]), step = int.Parse(p[5]);
                    double secs = double.Parse(p[6], System.Globalization.CultureInfo.InvariantCulture);
                    double gain = double.Parse(p[7], System.Globalization.CultureInfo.InvariantCulture);
                    int dead = int.Parse(p[8]);
                    int left = 0, top = 0, w = SW, h = SH;
                    if (p.Length >= 10)
                    {
                        RECT r = RectOfPid(int.Parse(p[9]));
                        if (r.Right - r.Left > 50)
                        { left = r.Left; top = r.Top; w = r.Right - r.Left; h = r.Bottom - r.Top; }
                    }
                    return Track(tr, tg, tb, tol, step, secs, gain, dead, left, top, w, h);
                }
                case "QUIT":
                    running = false;
                    return "{\"ok\":true,\"bye\":true}";
                default:
                    return "{\"ok\":false,\"error\":\"unknown op\"}";
            }
        }
        catch (Exception ex)
        {
            return "{\"ok\":false,\"error\":\"" + J(ex.Message) + "\"}";
        }
    }

    // closed-loop servo: capture -> detect -> move -> verify (same thread, no spawn)
    static string Track(int tr, int tg, int tb, int tol, int step, double secs,
                        double gain, int dead, int left, int top, int w, int h)
    {
        List<double> loops = new List<double>();
        int cycles = 0, hits = 0, misses = 0;
        double errSum = 0;
        double firstHitMs = -1;
        Stopwatch total = Stopwatch.StartNew();
        Stopwatch sw = new Stopwatch();
        POINT pt;

        while (total.Elapsed.TotalSeconds < secs)
        {
            sw.Restart();
            int stride;
            byte[] buf = GrabRegion(left, top, w, h, out stride);
            int cx, cy, cnt;
            if (!FindColor(buf, stride, w, h, tr, tg, tb, tol, step, out cx, out cy, out cnt))
            { misses++; continue; }

            int tx = left + cx, ty = top + cy;
            GetCursorPos(out pt);
            double ex = tx - pt.X, ey = ty - pt.Y;
            double err = Math.Sqrt(ex * ex + ey * ey);
            errSum += err;
            if (err <= dead)
            {
                hits++;
                if (firstHitMs < 0) firstHitMs = total.Elapsed.TotalMilliseconds;
            }
            else
            {
                SetCursorPos((int)(pt.X + ex * gain), (int)(pt.Y + ey * gain));
            }
            cycles++;
            loops.Add(sw.Elapsed.TotalMilliseconds);
        }

        loops.Sort();
        double avg = 0, p95 = 0;
        if (loops.Count > 0)
        {
            double s = 0; foreach (double d in loops) s += d;
            avg = s / loops.Count;
            p95 = loops[(int)Math.Min(loops.Count - 1, loops.Count * 0.95)];
        }
        double errAvg = cycles > 0 ? errSum / cycles : 0;

        return "{\"ok\":true,\"cycles\":" + cycles
             + ",\"hz\":" + (avg > 0 ? Math.Round(1000.0 / avg, 1) : 0)
             + ",\"loop_avg_ms\":" + Math.Round(avg, 2)
             + ",\"loop_p95_ms\":" + Math.Round(p95, 2)
             + ",\"err_avg_px\":" + Math.Round(errAvg, 1)
             + ",\"on_target_pct\":" + (cycles > 0 ? Math.Round(100.0 * hits / cycles, 1) : 0)
             + ",\"misses\":" + misses
             + ",\"converge_ms\":" + Math.Round(firstHitMs, 0)
             + ",\"region\":[" + left + "," + top + "," + w + "," + h + "]}";
    }

    // ---------- main ----------
    public static int Main(string[] args)
    {
        int port = 7791;
        foreach (string a in args)
        {
            if (a.StartsWith("--port=", StringComparison.OrdinalIgnoreCase))
                port = int.Parse(a.Substring(7));
        }

        string home = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
        string logPath = Path.Combine(home, "rtservo.log");
        Action<string> log = (msg) =>
        {
            try { File.AppendAllText(logPath, DateTime.Now.ToString("HH:mm:ss.fff") + " " + msg + "\r\n"); } catch { }
        };

        try
        {
            log("starting port=" + port);
            SetProcessDpiAwarenessContext(new IntPtr(-4));
            InitCapture();
            log("capture ready " + SW + "x" + SH);

            TcpListener srv = new TcpListener(IPAddress.Loopback, port);
            srv.Start();
            log("listening " + port);
            File.WriteAllText(Path.Combine(home, "rtservo.pid"), Process.GetCurrentProcess().Id.ToString());

            while (running)
            {
                try
                {
                    using (TcpClient c = srv.AcceptTcpClient())
                    using (NetworkStream ns = c.GetStream())
                    using (StreamReader rd = new StreamReader(ns, Encoding.UTF8))
                    using (StreamWriter wr = new StreamWriter(ns, new UTF8Encoding(false)) { AutoFlush = true })
                    {
                        string line;
                        while ((line = rd.ReadLine()) != null)
                        {
                            line = line.Trim();
                            if (line.Length == 0) continue;
                            string resp = Handle(line);
                            wr.WriteLine(resp);
                            if (!running) break;
                        }
                    }
                }
                catch (Exception ex)
                {
                    log("conn error: " + ex.GetType().Name + " " + ex.Message);
                    if (!running) break;
                    Thread.Sleep(50);
                }
            }

            srv.Stop();
            log("stopped");
            return 0;
        }
        catch (Exception ex)
        {
            log("FATAL " + ex.GetType().Name + ": " + ex.Message);
            try { log(ex.StackTrace ?? ""); } catch { }
            return 1;
        }
    }
}
