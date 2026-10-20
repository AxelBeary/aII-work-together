# shell/ 里的三个二进制是 vendored 依赖（不是本项目的源码）

桌面壳需要 WebView2 的 .NET 封装。本项目**刻意不用 NuGet 还原／不用 MSBuild**：
`build.cmd` 直接 `csc.exe /r:…`，所以这三个文件必须躺在 `shell/` 里。

| 文件 | 大小 | 来源 |
|---|---|---|
| `Microsoft.Web.WebView2.Core.dll` | 682 KB | `Microsoft.Web.WebView2` **1.0.4258.31** → `lib/net462/` |
| `Microsoft.Web.WebView2.WinForms.dll` | 38 KB | 同上 → `lib/net462/` |
| `WebView2Loader.dll` | 190 KB | 同上 → `build/native/x64/`（x64 版） |

- 包来源：`https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.4258.31/microsoft.web.webview2.1.0.4258.31.nupkg`
- 许可：**Microsoft WebView2 SDK License**（BSD-3 式三条款；允许随应用分发；**不是** MIT）。
  - 全文逐字节存在 [`shell/Microsoft.Web.WebView2.LICENSE.txt`](Microsoft.Web.WebView2.LICENSE.txt)（取自该 nupkg 的 `LICENSE.txt`）。
  - **再分发义务**：许可证第 2 条要求「二进制再分发必须在随分发材料中复现版权声明＋条件＋免责声明」。
    本仓用根目录的 [`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md) 履行；**分发 exe 时请连这个文件一起给**。
  - ⛔ 商标：应用名／图标／域名不得含 Edge／WebView2／Microsoft；描述里只作事实陈述（"uses the Microsoft Edge WebView2 control"）。
- 运行时依赖：**WebView2 Evergreen Runtime**。Win11 自带；Win10 由 Windows Update 装。
  本机实测：注册表 `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` → `155.0.4283.45`。
- ⛔ 不要把这三个文件当成项目源码改；升级＝换包、重取这三个文件、更新本表，然后 `shell\build.cmd` 重编。

## 为什么不用 `dotnet` / 包引用

- 目标机器只要 .NET Framework（Windows 自带）＋ WebView2 运行时，`csc.exe` 一行编译完，**离线可重建**。
- 引 `PackageReference` 就要 NuGet 还原：断网编不了、还要在仓库里塞 `obj/`。
- ⚠️ `csc.exe`（4.0.30319）是 **C# 5**：⛔ 插值字符串、`nameof`、表达式体成员都用不了。
