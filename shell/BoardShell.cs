// BoardShell.cs — 看板桌面壳（WebView2 + WinForms，单 exe，非 Electron）
//
// 为什么是它：
//   · 浏览器标签页「有点 low」：没有自己的图标、没有自己的窗口、地址栏喧宾夺主
//   · Electron 太重（自带一份 Chromium，一百多 MB）
//   · 本机已装 WebView2 Evergreen 运行时（Win11 自带），复用系统 Edge 内核 ⇒ exe 只有几十 KB
//   · 编译链和托盘完全一致（csc.exe + 系统 .NET Framework）⇒ 不引入 Node / Rust / MSBuild
//
// 它只做壳：
//   · 起后端（没有就起）→ 开窗口 → WebView2 加载 127.0.0.1:8777
//   · 最小化/关闭 → 收进托盘；托盘双击 → 回来
//   · 终端已经融进页面里（tools/term.py + 界面的底部抽屉），这里不再开黑窗口
//   · 业务逻辑一律在 Python 后端，⛔ 这里不重复实现
//
// 自检（⛔ 不弹任何可见物）：
//   boardshell.exe --selftest          真起 WebView2、加载页面、回读 DOM，打印 PASS/FAIL
//   boardshell.exe --shot out.png      0 透明度窗口截图（证明真的渲染出来了，不是白屏）
//   boardshell.exe --shot out.png --visible   真开一次窗口、截带标题栏的整窗图（需要人同意）
//
// ⚠️ C# 5（csc 4.0.30319）：⛔ 不要用插值字符串 / nameof / 表达式体成员。

using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace BoardShell
{
    static class Program
    {
        // ---------- Win32 ----------
        [DllImport("dwmapi.dll")]
        static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int val, int size);
        [DllImport("user32.dll")]
        static extern bool SetForegroundWindow(IntPtr hWnd);
        [DllImport("user32.dll")]
        static extern bool SetProcessDPIAware();
        [DllImport("user32.dll")]
        static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);
        [DllImport("user32.dll")]
        static extern IntPtr GetForegroundWindow();
        [DllImport("kernel32.dll")]
        static extern bool AttachConsole(int dwProcessId);

        static void Say(string line)
        {
            // winexe 没有自己的控制台：挂到父控制台上，同时留一份进日志（
            // ⛔ 不能只靠 Console：从资源管理器双击时压根没有父亲控制台）
            try { Console.WriteLine(line); Console.Out.Flush(); } catch { }
            try
            {
                File.AppendAllText(Path.Combine(ProjectDir ?? AppDir, "board", "shell-selftest.log"),
                    DateTime.Now.ToString("HH:mm:ss") + "  " + line + Environment.NewLine,
                    Encoding.UTF8);
            }
            catch { }
        }

        // ---------- 状态 ----------
        static string AppDir;
        static string ProjectDir;
        static string LogFile;
        static string Url;
        static int Port = 8777;
        static Process Server;
        static bool StartedServer;
        static HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(3) };
        static NotifyIcon Tray;
        static Form Win;
        static WebView2 View;
        static Mutex Instance;
        static EventWaitHandle WakeSignal;
        static bool DevTools;
        static bool TrayHintShown;
        static string ShotPath;
        static bool ShotVisible;
        // WebView2 初始化是异步的：⛔ 绝不能在 UI 线程上 .Result/.Wait —— 那会把消息循环
        // 卡住，而初始化回调恰恰要靠消息循环才能回来 ⇒ 死锁／超时（2026-10-20 实测：双击卡死）
        static bool _initDone;
        static string _initError = "";
        static bool _navDone;

        const string MUTEX_NAME = "allworktogether-board-shell";
        const string WAKE_NAME = "allworktogether-board-shell-wake";

        [STAThread]
        static int Main(string[] args)
        {
            try { SetProcessDPIAware(); } catch { }

            AppDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
            ProjectDir = Path.GetFullPath(Path.Combine(AppDir, ".."));
            LogFile = Path.Combine(ProjectDir, "board", "shell.log");
            Url = null;

            string mode = "";
            foreach (var a in args)
            {
                if (a.StartsWith("--port=")) int.TryParse(a.Substring(7), out Port);
                else if (a.StartsWith("--project=")) ProjectDir = a.Substring(10);
                else if (a.StartsWith("--url=")) Url = a.Substring(6);
                else if (a == "--devtools") DevTools = true;
                else if (a == "--selftest") mode = "selftest";
                else if (a == "--visible") ShotVisible = true;
                else if (a.StartsWith("--shot=")) { ShotPath = a.Substring(7); }
            }
            if (Url == null) Url = "http://127.0.0.1:" + Port + "/";
            try { Directory.CreateDirectory(Path.GetDirectoryName(LogFile)); } catch { }

            if (mode == "selftest" || ShotPath != null) AttachConsole(-1);   // 挂到父控制台，自检输出能看见
            try { Console.OutputEncoding = Encoding.UTF8; } catch { }

            if (mode == "selftest") return SelfTest();
            if (ShotPath != null) return TakeShot();

            // ---------- 单实例：第二次启动只把已有的窗口叫回来 ----------
            bool created;
            Instance = new Mutex(true, MUTEX_NAME, out created);
            if (!created)
            {
                try
                {
                    using (var ev = EventWaitHandle.OpenExisting(WAKE_NAME)) ev.Set();
                }
                catch { }
                return 0;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.AddMessageFilter(new KeyFilter());

            if (!EnsureServer(false)) return 3;

            BuildWindow();
            BuildTray();
            WatchWake();
            CheckBackendFreshness();

            Application.Run(Win);

            StopServerIfOwned();
            return 0;
        }

        // ---------- 窗口 ----------

        static void BuildWindow(bool hidden = false)
        {
            Win = new Form();
            Win.Text = "看板";
            Win.BackColor = Color.FromArgb(14, 16, 20);
            Win.MinimumSize = new Size(760, 480);
            Win.StartPosition = FormStartPosition.Manual;
            Win.Icon = LoadIcon();
            if (hidden)
            {
                // 自检/截图用：真窗口、真渲染，但人看不见
                Win.FormBorderStyle = ShotVisible ? FormBorderStyle.Sizable : FormBorderStyle.None;
                Win.ShowInTaskbar = ShotVisible;
                Win.Opacity = ShotVisible ? 1.0 : 0.0;
                Win.Bounds = new Rectangle(0, 0, 1360, 860);
            }
            else
            {
                ApplyPlacement(Win);
            }

            View = new WebView2();
            View.Dock = DockStyle.Fill;
            View.DefaultBackgroundColor = Color.FromArgb(14, 16, 20);
            Win.Controls.Add(View);

            if (!hidden)
            {
                Win.Resize += delegate
                {
                    // 最小化＝收进托盘（用户要求「做好最小化到托盘」）
                    if (Win.WindowState == FormWindowState.Minimized)
                    {
                        Win.Hide();
                        Win.WindowState = FormWindowState.Normal;
                        if (!TrayHintShown) { Balloon("还在跑", "双击托盘图标回到看板"); TrayHintShown = true; }
                    }
                };
                Win.FormClosing += delegate(object s, FormClosingEventArgs e)
                {
                    if (e.CloseReason == CloseReason.UserClosing && Tray != null)
                    {
                        // 关闭先收进托盘；真要退出走托盘菜单
                        e.Cancel = true;
                        Win.Hide();
                        if (!TrayHintShown) { Balloon("已收进托盘", "看板还在后台；退出请右键托盘图标"); TrayHintShown = true; }
                    }
                };
                Win.FormClosed += delegate { SavePlacement(); };
            }

            Win.Shown += delegate
            {
                DarkTitleBar(Win.Handle);
                InitView();                 // async void：立刻返回，不占 UI 线程
            };
        }

        static void DarkTitleBar(IntPtr hwnd)
        {
            // Win11 原生暗色标题栏 + 与页面同色的标题栏/描边（不自己画，避免自绘边框的手感问题）
            try
            {
                int on = 1;
                DwmSetWindowAttribute(hwnd, 20, ref on, sizeof(int));   // 沉浸式暗色
                DwmSetWindowAttribute(hwnd, 19, ref on, sizeof(int));   // 老版本号，失败无妨
                int caption = 0x001E1815;                               // #15181e (COLORREF = BGR)
                DwmSetWindowAttribute(hwnd, 35, ref caption, sizeof(int));
                int text = 0x00EDEAE8;                                  // #e8eaed
                DwmSetWindowAttribute(hwnd, 36, ref text, sizeof(int));
                int border = 0x003A302A;                                // #2a303a
                DwmSetWindowAttribute(hwnd, 34, ref border, sizeof(int));
                int round = 2;
                DwmSetWindowAttribute(hwnd, 33, ref round, sizeof(int));
            }
            catch { }
        }

        static async void InitView()
        {
            try
            {
                var udf = UserDataDir();
                var env = await CoreWebView2Environment.CreateAsync(null, udf, null);
                await View.EnsureCoreWebView2Async(env);

                var core = View.CoreWebView2;
                if (core == null) throw new Exception("内核起来了，但 CoreWebView2 是空的");

                core.Settings.AreDevToolsEnabled = DevTools;
                core.Settings.IsStatusBarEnabled = false;
                core.Settings.AreBrowserAcceleratorKeysEnabled = false;
                core.Settings.IsZoomControlEnabled = true;
                core.Settings.IsPasswordAutosaveEnabled = false;
                core.Settings.IsGeneralAutofillEnabled = false;

                core.NewWindowRequested += delegate(object s, CoreWebView2NewWindowRequestedEventArgs e)
                {
                    e.Handled = true;
                    try { Process.Start(new ProcessStartInfo(e.Uri) { UseShellExecute = true }); }
                    catch { }
                };
                core.ProcessFailed += delegate(object s, CoreWebView2ProcessFailedEventArgs e)
                {
                    ShowErrorPanel("渲染进程挂了：" + e.ProcessFailedKind
                                   + "\n按 F5 或关掉重开一次看板。");
                };
                core.NavigationCompleted += delegate { _navDone = true; };

                _initError = "";
                _initDone = true;
                View.Source = new Uri(Url);
            }
            catch (Exception ex)
            {
                _initError = ex.GetType().Name + "：" + ex.Message;
                if (ex.InnerException != null) _initError += " ／ " + ex.InnerException.Message;
                _initDone = true;
                Log("init failed: " + _initError);
                ShowErrorPanel(
                    "WebView2 没起来。\n\n" + _initError +
                    "\n\n常见原因：\n" +
                    "1) 已经有一个看板窗口没关（用户数据目录被占用）\n" +
                    "2) WebView2 运行时缺失（Win11 自带；Win10 装 Evergreen Runtime）\n\n" +
                    "日志：" + LogFile);
            }
        }

        // WinForms 版 WebView2 控件不暴露 CoreWebView2Controller（也就没有 AcceleratorKeyPressed），
        // 所以快捷键在**消息循环**这层拦：页面拿不到这几个键，其余全给页面。
        class KeyFilter : IMessageFilter
        {
            public bool PreFilterMessage(ref Message m)
            {
                if (m.Msg != 0x100 && m.Msg != 0x104) return false;   // WM_KEYDOWN / WM_SYSKEYDOWN
                int k = (int)m.WParam;
                bool ctrl = (Control.ModifierKeys & Keys.Control) == Keys.Control;
                if (k == 0x74 || (ctrl && k == 0x52)) { Reload(); return true; }
                if (ctrl && (k == 0xBB || k == 0x6B)) { Zoom(0.1); return true; }
                if (ctrl && (k == 0xBD || k == 0x6D)) { Zoom(-0.1); return true; }
                if (ctrl && k == 0x30) { SetZoom(1.0); return true; }
                if (k == 0x7A) { ToggleMax(); return true; }
                if (k == 0x7B && DevTools) { OpenDevTools(); return true; }
                return false;
            }
        }

        static void Reload()
        {
            try { if (View != null && View.CoreWebView2 != null) View.Reload(); }
            catch { }
        }

        static void Zoom(double delta)
        {
            try { SetZoom(View.ZoomFactor + delta); } catch { }
        }

        static void SetZoom(double z)
        {
            try
            {
                if (z < 0.4) z = 0.4;
                if (z > 3.0) z = 3.0;
                View.ZoomFactor = z;
            }
            catch { }
        }

        static void OpenDevTools()
        {
            try { View.CoreWebView2.OpenDevToolsWindow(); } catch { }
        }

        static void ToggleMax()
        {
            Win.WindowState = Win.WindowState == FormWindowState.Maximized
                ? FormWindowState.Normal : FormWindowState.Maximized;
        }

        // 出错不弹模态框（弹框会把窗口挡死，用户只会觉得「卡死」）：
        // 直接把原因写进窗口里，窗口还能动、还能复制文字。
        static void ShowErrorPanel(string why)
        {
            Log(why);
            try
            {
                var core = View != null ? View.CoreWebView2 : null;
                if (core != null)
                {
                    var html = "<html><body style='background:#0e1014;color:#e8eaed;"
                             + "font:14px/1.7 \"Segoe UI\",\"Microsoft YaHei\",sans-serif;padding:40px'>"
                             + "<h2 style='color:#f85149;margin:0 0 12px'>界面没起来</h2>"
                             + "<pre style='white-space:pre-wrap;color:#c8d0da;background:#11141a;"
                             + "border:1px solid #2a303a;border-radius:10px;padding:14px'>"
                             + System.Security.SecurityElement.Escape(why) + "</pre>"
                             + "<p style='color:#8b94a1'>关掉这个窗口再开一次；还是不行看 <code>board\\shell.log</code>。</p>"
                             + "</body></html>";
                    core.NavigateToString(html);
                    return;
                }
            }
            catch { }
            try
            {
                if (View != null) View.Visible = false;
                var lab = new Label();
                lab.Dock = DockStyle.Fill;
                lab.ForeColor = Color.FromArgb(232, 234, 237);
                lab.BackColor = Color.FromArgb(14, 16, 20);
                lab.Padding = new Padding(32);
                lab.Font = new Font("Microsoft YaHei UI", 10f);
                lab.Text = "界面没起来\n\n" + why + "\n\n关掉这个窗口再开一次；还是不行看 board\\shell.log。";
                Win.Controls.Add(lab);
                lab.BringToFront();
            }
            catch { }
        }

        // ---------- 窗口位置 ----------

        static string PlacementFile { get { return Path.Combine(ProjectDir, "board", "shell.txt"); } }

        static void ApplyPlacement(Form f)
        {
            try
            {
                if (File.Exists(PlacementFile))
                {
                    var txt = File.ReadAllText(PlacementFile);
                    var kv = txt.Split(';');
                    int x = 0, y = 0, w = 0, h = 0;
                    foreach (var p in kv)
                    {
                        var t = p.Split('=');
                        if (t.Length != 2) continue;
                        int v; int.TryParse(t[1], out v);
                        if (t[0] == "x") x = v;
                        else if (t[0] == "y") y = v;
                        else if (t[0] == "w") w = v;
                        else if (t[0] == "h") h = v;
                    }
                    if (w > 400 && h > 300)
                    {
                        var r = new Rectangle(x, y, w, h);
                        bool onScreen = false;
                        foreach (var sc in Screen.AllScreens)
                            if (sc.WorkingArea.IntersectsWith(r)) onScreen = true;
                        if (onScreen) { f.StartPosition = FormStartPosition.Manual; f.Bounds = r; return; }
                    }
                }
            }
            catch { }
            var wa = Screen.PrimaryScreen.WorkingArea;
            int vw = Math.Max(1000, Math.Min(1680, (int)(wa.Width * 0.82)));
            int vh = Math.Max(700, Math.Min(1040, (int)(wa.Height * 0.86)));
            f.Size = new Size(vw, vh);
            f.StartPosition = FormStartPosition.CenterScreen;
        }

        static void SavePlacement()
        {
            try
            {
                var r = Win.WindowState == FormWindowState.Normal ? Win.Bounds : Win.RestoreBounds;
                File.WriteAllText(PlacementFile,
                    "x=" + r.X + ";y=" + r.Y + ";w=" + r.Width + ";h=" + r.Height);
            }
            catch { }
        }

        // ---------- 托盘 ----------

        static void BuildTray()
        {
            Tray = new NotifyIcon();
            Tray.Icon = LoadIcon();
            Tray.Text = "看板";
            Tray.Visible = true;
            Tray.DoubleClick += delegate { Restore(); };

            var menu = new ContextMenuStrip();
            menu.Items.Add("打开看板", null, delegate { Restore(); });
            menu.Items.Add("跑一张", null, delegate { RunOne(); });
            menu.Items.Add("自检", null, delegate { RunCheck(); });
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add("退出", null, delegate { Quit(); });
            Tray.ContextMenuStrip = menu;
        }

        static Icon LoadIcon()
        {
            try
            {
                var p = Path.Combine(ProjectDir, "assets", "board.ico");
                if (File.Exists(p)) return new Icon(p, new Size(32, 32));
            }
            catch { }
            return SystemIcons.Application;
        }

        static void Balloon(string title, string text)
        {
            try
            {
                Tray.BalloonTipTitle = title;
                Tray.BalloonTipText = text;
                Tray.ShowBalloonTip(2500);
            }
            catch { }
        }

        static void Restore()
        {
            if (Win == null) return;
            Win.Show();
            Win.WindowState = FormWindowState.Normal;
            Win.Activate();
            SetForegroundWindow(Win.Handle);
        }

        static void Quit()
        {
            try { if (Tray != null) { Tray.Visible = false; Tray.Dispose(); } } catch { }
            StopServerIfOwned();
            Application.Exit();
        }

        static void WatchWake()
        {
            // 第二次双击快捷方式：把已经开着的窗口叫回来（不再开第二个）
            try
            {
                WakeSignal = new EventWaitHandle(false, EventResetMode.AutoReset, WAKE_NAME);
                var t = new Thread(delegate()
                {
                    while (true)
                    {
                        WakeSignal.WaitOne();
                        try { Win.BeginInvoke((MethodInvoker)delegate { Restore(); }); } catch { }
                    }
                });
                t.IsBackground = true;
                t.Start();
            }
            catch { }
        }

        static void RunOne()
        {
            StartPython("tools/orchestrator.py", "-C \"" + ProjectDir + "\" run --max 1", true);
            Balloon("开始跑一张", "需要你拍板的会停下等你");
        }

        static void RunCheck()
        {
            StartPython("tools/check.py", "--quick", false);
            Balloon("自检开始", "结果看看板里的终端");
        }

        static Process StartPython(string script, string args, bool quiet)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = "python",
                    Arguments = "\"" + Path.Combine(ProjectDir, script) + "\" " + args,
                    WorkingDirectory = ProjectDir,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                return Process.Start(psi);
            }
            catch (Exception ex)
            {
                Log("start python " + script + ": " + ex.Message);
                return null;
            }
        }

        // ---------- 后端 ----------

        static bool ServerAlive()
        {
            try
            {
                var r = Http.GetAsync("http://127.0.0.1:" + Port + "/api/state").Result;
                return r.IsSuccessStatusCode;
            }
            catch { return false; }
        }

        static bool EnsureServer(bool quiet)
        {
            if (ServerAlive()) return true;
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = "python",
                    Arguments = "\"" + Path.Combine(ProjectDir, "tools", "server.py") + "\" --port " + Port,
                    WorkingDirectory = ProjectDir,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };
                Server = Process.Start(psi);
                StartedServer = true;
                var logPath = Path.Combine(ProjectDir, "board", "ui-server.log");
                Hook(Server.StandardOutput, logPath);
                Hook(Server.StandardError, logPath);
                for (int i = 0; i < 20; i++)
                {
                    Thread.Sleep(400);
                    if (ServerAlive()) return true;
                }
                Log("server did not come alive in 8s");
                if (!quiet) MessageBox.Show("后端没起来。\n跑 board.cmd 看报错，日志：" + LogFile,
                                            "看板壳", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return false;
            }
            catch (Exception ex)
            {
                Log("ensure server: " + ex.Message);
                if (!quiet) MessageBox.Show("起不了 python：" + ex.Message, "看板壳",
                                            MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return false;
            }
        }

        static void Hook(StreamReader r, string path)
        {
            var t = new Thread(delegate()
            {
                try
                {
                    using (var w = new StreamWriter(path, true, Encoding.UTF8))
                    {
                        string line;
                        while ((line = r.ReadLine()) != null)
                        {
                            w.WriteLine(line);
                            w.Flush();
                        }
                    }
                }
                catch { }
            });
            t.IsBackground = true;
            t.Start();
        }

        static void StopServerIfOwned()
        {
            if (!StartedServer) return;
            try
            {
                if (Server != null && !Server.HasExited) { Server.Kill(); Server.WaitForExit(3000); }
            }
            catch { }
        }

        // ---------- 无界面自检 / 截图 ----------

        static string UserDataDir()
        {
            // ⛔ 必须显式给目录：传 null 会在 exe 旁边建 `boardshell.exe.WebView2\`
            //    （两百多个运行时文件，会被误当源码提交——2026-10-20 真踩过）
            var d = Path.Combine(ProjectDir, "board", "webview2");
            Directory.CreateDirectory(d);
            return d;
        }

        static Form MakeHiddenForm(bool visible)
        {
            var f = new Form();
            f.Text = "看板";
            f.FormBorderStyle = visible ? FormBorderStyle.Sizable : FormBorderStyle.None;
            f.ShowInTaskbar = visible;
            f.StartPosition = FormStartPosition.Manual;
            f.Bounds = new Rectangle(0, 0, 1360, 860);
            if (!visible) f.Opacity = 0.0;                 // 真窗口、真渲染，但人看不见
            f.BackColor = Color.FromArgb(14, 16, 20);
            f.Icon = LoadIcon();
            return f;
        }

        static bool Pump(Func<bool> done, int ms)
        {
            var until = DateTime.Now.AddMilliseconds(ms);
            while (DateTime.Now < until)
            {
                if (done()) return true;
                Application.DoEvents();          // 让 async 的续体有机会跑（这里就是消息循环）
                Thread.Sleep(40);
            }
            return done();
        }

        // 自检/截图走的是**和真实窗口完全同一条路径**（BuildWindow + InitView）。
        // ⛔ 以前自检自己另写一套初始化，结果「自检全绿、双击卡死」——这就是为什么必须同一条路。
        static bool BootHidden(out string why)
        {
            why = "";
            BuildWindow(true);
            Win.Show();
            if (ShotVisible)
            {
                Win.TopMost = true;              // SetForegroundWindow 常被拒，TopMost 才真的在最上面
                Win.Activate();
                SetForegroundWindow(Win.Handle);
            }
            if (!Pump(delegate { return _initDone; }, 30000))
            {
                why = "初始化 30 秒没回来";
                return false;
            }
            if (_initError != "")
            {
                why = _initError;
                return false;
            }
            return true;
        }

        static int SelfTest()
        {
            try
            {
                if (!EnsureServer(true)) { Say("SELFTEST FAIL: server"); return 2; }
                string why;
                if (!BootHidden(out why))
                {
                    Say("SELFTEST FAIL: " + why);
                    return 2;
                }
                Say("init   = ok");
                bool nav = Pump(delegate { return _navDone; }, 30000);
                Say("nav    = " + nav);

                string js = "JSON.stringify({title:document.title,"
                          + "h1:(document.querySelector('h1')||{}).textContent||'',"
                          + "cols:document.querySelectorAll('.col').length,"
                          + "term:!!document.getElementById('term'),"
                          + "msg:!!document.getElementById('btn-msg')})";
                var t = View.CoreWebView2.ExecuteScriptAsync(js);
                Pump(delegate { return t.IsCompleted; }, 10000);
                // ExecuteScriptAsync 回的是 JSON 字符串字面量：里面的引号是 \" 转义的，
                // 先还原成正常文本再判定（否则会一直判「没有这个字段」）
                string raw = t.IsCompleted ? (t.Result ?? "") : "";
                string norm = raw.Replace("\\\"", "\"").Replace("\\\\", "\\");
                Say("dom    = " + norm);

                bool okTitle = norm.Contains("看板");
                bool okTerm = norm.Contains("\"term\":true");
                bool okMsg = norm.Contains("\"msg\":true");
                bool okCols = false;
                var i = norm.IndexOf("\"cols\":");
                if (i > 0)
                {
                    int n = 0;
                    var digits = "";
                    for (int j = i + 7; j < norm.Length && char.IsDigit(norm[j]); j++) digits += norm[j];
                    if (int.TryParse(digits, out n) && n >= 3) okCols = true;
                }
                Say("cols ok= " + okCols + "  title ok= " + okTitle
                                  + "  term ok= " + okTerm + "  msg ok= " + okMsg);
                bool pass = nav && okTitle && okCols && okTerm && okMsg;
                Say(pass ? "SELFTEST PASS" : "SELFTEST FAIL");
                return pass ? 0 : 2;
            }
            catch (Exception ex)
            {
                Say("SELFTEST FAIL: " + ex.GetType().Name + ": " + ex.Message);
                if (ex.InnerException != null) Say("  inner: " + ex.InnerException.Message);
                return 2;
            }
            finally
            {
                try { if (Win != null) Win.Close(); } catch { }
                StopServerIfOwned();      // 自检自己起的后端不留垃圾进程
            }
        }

        static int TakeShot()
        {
            try
            {
                if (!EnsureServer(true)) { Say("SHOT FAIL: server"); return 2; }
                string why;
                if (!BootHidden(out why)) { Say("SHOT FAIL: " + why); return 2; }
                Pump(delegate { return _navDone; }, 30000);
                Thread.Sleep(1500);                       // 等卡片画出来
                Pump(delegate { return false; }, 600);

                var dir = Path.GetDirectoryName(Path.GetFullPath(ShotPath));
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

                if (ShotVisible)
                {
                    var r = Win.Bounds;
                    using (var bmp = new Bitmap(r.Width, r.Height))
                    using (var g = Graphics.FromImage(bmp))
                    {
                        g.CopyFromScreen(r.Location, Point.Empty, r.Size);
                        bmp.Save(ShotPath, ImageFormat.Png);
                    }
                }
                else
                {
                    using (var fs = File.Create(ShotPath))
                    {
                        var t = View.CoreWebView2.CapturePreviewAsync(
                            CoreWebView2CapturePreviewImageFormat.Png, fs);
                        Pump(delegate { return t.IsCompleted; }, 15000);
                    }
                }
                long size = new FileInfo(ShotPath).Length;
                Say("SHOT OK: " + ShotPath + " (" + size + " bytes)");
                return size > 3000 ? 0 : 4;               // 太小＝大概率白屏
            }
            catch (Exception ex)
            {
                Say("SHOT FAIL: " + ex.GetType().Name + ": " + ex.Message);
                return 2;
            }
            finally
            {
                try { if (Win != null) Win.Close(); } catch { }
                StopServerIfOwned();      // 自检自己起的后端不留垃圾进程
            }
        }

        // 后端是不是「老代码」：改了 server.py 但旧的 server 进程还在 8777（E-31）
        // 旧进程配新页面 ⇒ 新接口 404，而且看起来像「路由写错了」。
        static void CheckBackendFreshness()
        {
            try
            {
                var s = Http.GetStringAsync("http://127.0.0.1:" + Port + "/api/state").Result;
                var f = Path.Combine(ProjectDir, "tools", "server.py");
                if (!File.Exists(f)) return;
                long disk = (long)(File.GetLastWriteTimeUtc(f)
                                   - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
                int i = s.IndexOf("\"code_mtime\":");
                if (i < 0)
                {
                    Log("backend has no code_mtime ⇒ 旧版本进程");
                    Balloon("后端是旧版", "关掉看板再开一次就会用新代码；否则新接口会报 not found");
                    return;
                }
                var digits = "";
                for (int j = i + 13; j < s.Length && char.IsDigit(s[j]); j++) digits += s[j];
                long running;
                if (!long.TryParse(digits, out running)) return;
                if (running < disk - 1)
                {
                    Log("backend stale: running=" + running + " disk=" + disk);
                    Balloon("后端是旧版", "它比 tools\\server.py 旧；关掉看板再开一次");
                }
            }
            catch { }
        }

        // ---------- 日志 ----------

        static void Log(string msg)
        {
            try
            {
                File.AppendAllText(LogFile,
                    DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + msg
                    + Environment.NewLine, Encoding.UTF8);
            }
            catch { }
        }
    }
}
