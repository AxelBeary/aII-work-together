// BoardTray.cs — 看板托盘（原生 Win32/WinForms，无 Electron）
//
// 职责：托盘常驻 → 起停 Python 后端 → 提供「打开看板 / 跑一轮 / 状态 / 退出」
// 为什么用 C#：单 exe、启动快、内存小（约 20MB），WinForms 是系统自带组件
// ⚠️ 只做壳：所有业务逻辑在 Python 后端，这里不重复实现

using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

namespace BoardTray
{
    static class Program
    {
        static Mutex _mutex;
        static NotifyIcon _tray;
        static Process _server;
        static string _appDir;
        static string _projectDir;
        static int _port = 8777;
        static HttpClient _http = new HttpClient { Timeout = TimeSpan.FromSeconds(3) };
        static string _logFile;

        [STAThread]
        static void Main(string[] args)
        {
            bool created;
            _mutex = new Mutex(true, "allworktogether-board-tray", out created);
            if (!created) { return; }   // 已经在跑了

            _appDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
            // tray/ 的上一级就是项目根
            _projectDir = Path.GetFullPath(Path.Combine(_appDir, ".."));
            _logFile = Path.Combine(_projectDir, "board", "tray.log");
            Directory.CreateDirectory(Path.GetDirectoryName(_logFile));

            foreach (var a in args)
            {
                if (a.StartsWith("--port=")) int.TryParse(a.Substring(7), out _port);
                if (a.StartsWith("--project=")) _projectDir = a.Substring(10);
            }

            // 无界面自检：起来、探活、退出（⛔ 不创建托盘、不弹任何东西）
            bool selftest = Array.IndexOf(args, "--selftest") >= 0;
            if (selftest)
            {
                Console.WriteLine("project = " + _projectDir);
                Console.WriteLine("alive(before) = " + ServerAlive());
                EnsureServerQuiet();
                bool ok = ServerAlive();
                Console.WriteLine("alive(after) = " + ok);
                Console.WriteLine(ok ? "SELFTEST PASS" : "SELFTEST FAIL");
                if (_server != null && !_server.HasExited)
                {
                    try { _server.Kill(); _server.WaitForExit(3000); } catch { }
                }
                Environment.Exit(ok ? 0 : 1);
                return;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            BuildTray();
            EnsureServer();

            Application.Run();
        }

        // ---------- 托盘 ----------

        static void BuildTray()
        {
            _tray = new NotifyIcon();
            _tray.Icon = MakeIcon();
            _tray.Text = "看板";
            _tray.Visible = true;
            _tray.DoubleClick += (s, e) => OpenBoard();

            var menu = new ContextMenuStrip();
            menu.Items.Add("打开看板", null, (s, e) => OpenBoard());
            menu.Items.Add("跑一轮", null, (s, e) => RunRound());
            menu.Items.Add("看看状态", null, (s, e) => ShowStatus());
            menu.Items.Add(new ToolStripSeparator());
            var auto = new ToolStripMenuItem("开机自动启动");
            auto.Checked = IsAutoStart();
            auto.Click += (s, e) => ToggleAutoStart();
            menu.Items.Add(auto);
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add("退出", null, (s, e) => Shutdown());

            _tray.ContextMenuStrip = menu;
            _tray.BalloonTipTitle = "看板已就绪";
            _tray.BalloonTipText = "双击托盘图标打开看板";
            _tray.ShowBalloonTip(2000);
        }

        static Icon MakeIcon()
        {
            // 优先用 assets/board.ico（和桌面快捷方式是同一张图，视觉一致）
            try
            {
                var p = Path.Combine(_projectDir, "assets", "board.ico");
                if (File.Exists(p)) return new Icon(p, new Size(32, 32));
            }
            catch { }

            // 退路：运行时画一个图标（不依赖外部文件）
            int s = 32;
            using (var bmp = new Bitmap(s, s))
            using (var g = Graphics.FromImage(bmp))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.Clear(Color.Transparent);
                using (var bg = new SolidBrush(Color.FromArgb(90, 169, 255)))
                using (var path = RoundRect(new Rectangle(1, 1, s - 2, s - 2), 7))
                    g.FillPath(bg, path);
                using (var fg = new SolidBrush(Color.FromArgb(6, 18, 31)))
                using (var f = new Font("Segoe UI", 15, FontStyle.Bold, GraphicsUnit.Pixel))
                {
                    var sf = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center };
                    g.DrawString("板", f, fg, new RectangleF(1, 1, s - 2, s - 2), sf);
                }
                return Icon.FromHandle(bmp.GetHicon());
            }
        }

        static GraphicsPath RoundRect(Rectangle r, int radius)
        {
            int d = radius * 2;
            var p = new GraphicsPath();
            p.AddArc(r.X, r.Y, d, d, 180, 90);
            p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            p.CloseFigure();
            return p;
        }

        // ---------- 后端 ----------

        static string BaseUrl { get { return "http://127.0.0.1:" + _port + "/"; } }

        static bool ServerAlive()
        {
            try
            {
                var r = _http.GetAsync(BaseUrl + "api/state").Result;
                return r.IsSuccessStatusCode;
            }
            catch { return false; }
        }

        static void EnsureServer()
        {
            if (ServerAlive()) return;
            if (StartServerQuiet()) return;
            Balloon("后端没起来", "看看 board\\tray.log，或手动跑 board.cmd");
        }

        static void EnsureServerQuiet()
        {
            if (ServerAlive()) return;
            StartServerQuiet();
        }

        static bool StartServerQuiet()
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = "python",
                    Arguments = "\"" + Path.Combine(_projectDir, "tools", "server.py") + "\" --port " + _port,
                    WorkingDirectory = _projectDir,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                };
                _server = Process.Start(psi);
                for (int i = 0; i < 16; i++)
                {
                    Thread.Sleep(500);
                    if (ServerAlive()) return true;
                }
                Log("server did not become alive in 8s");
                return false;
            }
            catch (Exception ex)
            {
                Log("start server: " + ex.Message);
                return false;
            }
        }

        static void OpenBoard()
        {
            EnsureServer();
            try { Process.Start(new ProcessStartInfo(BaseUrl) { UseShellExecute = true }); }
            catch (Exception ex) { Balloon("打不开浏览器", ex.Message); }
        }

        static void RunRound()
        {
            EnsureServer();
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = "python",
                    Arguments = "\"" + Path.Combine(_projectDir, "tools", "orchestrator.py") + "\" " +
                                "-C \"" + _projectDir + "\" run --max 3",
                    WorkingDirectory = _projectDir,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                };
                var p = Process.Start(psi);
                Balloon("开始跑一轮", "完成后会提示；需要你拍板的会停下");
                p.EnableRaisingEvents = true;
                p.Exited += (s, e) =>
                {
                    try
                    {
                        var cnt = CountPending();
                        if (cnt > 0) Balloon("跑完了", "有 " + cnt + " 张等你拍板");
                        else Balloon("跑完了", "没有待拍板的");
                    }
                    catch { }
                };
            }
            catch (Exception ex) { Balloon("跑不起来", ex.Message); }
        }

        static int CountPending()
        {
            var s = _http.GetStringAsync(BaseUrl + "api/cards").Result;
            // 极简统计：数 "拍板中" 出现次数（够用，且不引 JSON 依赖）
            int n = 0, i = 0;
            while ((i = s.IndexOf("\"state\":\"拍板中\"", i, StringComparison.Ordinal)) >= 0)
            { n++; i += 10; }
            return n;
        }

        static void ShowStatus()
        {
            EnsureServer();
            try
            {
                // ⚠️ 必须读 api/cards：api/state 只给项目列表和当前项目，里面没有卡片，
                // 以前在这儿数字段导致「永远是 0 张」。
                var s = _http.GetStringAsync(BaseUrl + "api/cards").Result;
                int total = Count(s, "\"id\":\"");
                int done = Count(s, "\"state\":\"完成\"");
                int pending = Count(s, "\"state\":\"拍板中\"");
                int running = Count(s, "\"state\":\"进行中\"");
                string msg = "共 " + total + " 张卡：完成 " + done +
                             "，进行中 " + running;
                if (pending > 0) msg += "，等你拍板 " + pending;
                Balloon("现在的状态", msg);
            }
            catch (Exception ex) { Balloon("读不到状态", ex.Message); }
        }

        static int Count(string s, string needle)
        {
            int n = 0, i = 0;
            while ((i = s.IndexOf(needle, i, StringComparison.Ordinal)) >= 0)
            { n++; i += needle.Length; }
            return n;
        }

        static void Balloon(string title, string text)
        {
            try
            {
                _tray.BalloonTipTitle = title;
                _tray.BalloonTipText = text;
                _tray.ShowBalloonTip(3000);
            }
            catch { }
        }

        // ---------- 开机自启（用户点了才写注册表，不默认开）----------

        const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
        const string RunName = "BoardTray";

        static bool IsAutoStart()
        {
            try
            {
                using (var k = Registry.CurrentUser.OpenSubKey(RunKey, false))
                    return k != null && k.GetValue(RunName) != null;
            }
            catch { return false; }
        }

        static void ToggleAutoStart()
        {
            try
            {
                using (var k = Registry.CurrentUser.OpenSubKey(RunKey, true))
                {
                    if (IsAutoStart())
                    {
                        k.DeleteValue(RunName, false);
                        Balloon("已关闭", "下次开机不再自动启动");
                    }
                    else
                    {
                        k.SetValue(RunName, "\"" + Application.ExecutablePath + "\"");
                        Balloon("已开启", "下次开机会自动启动");
                    }
                }
                BuildTrayMenuRefresh();
            }
            catch (Exception ex) { Balloon("改不了自启", ex.Message); }
        }

        static void BuildTrayMenuRefresh()
        {
            if (_tray != null && _tray.ContextMenuStrip != null)
            {
                foreach (ToolStripItem it in _tray.ContextMenuStrip.Items)
                {
                    var m = it as ToolStripMenuItem;
                    if (m != null && m.Text == "开机自动启动") m.Checked = IsAutoStart();
                }
            }
        }

        // ---------- 退出 ----------

        static void Shutdown()
        {
            try
            {
                if (_server != null && !_server.HasExited)
                {
                    _server.Kill();
                    _server.WaitForExit(3000);
                }
            }
            catch { }
            try { if (_tray != null) { _tray.Visible = false; _tray.Dispose(); } } catch { }
            Application.Exit();
        }

        static void Log(string msg)
        {
            try
            {
                File.AppendAllText(_logFile,
                    DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + msg + Environment.NewLine,
                    Encoding.UTF8);
            }
            catch { }
        }
    }
}
