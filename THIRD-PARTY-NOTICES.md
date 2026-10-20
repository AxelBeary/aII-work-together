# Third-Party Notices

本文件记录**随仓库分发**的第三方二进制及其许可证全文。项目自身的许可见 [LICENSE](LICENSE)；
「借鉴过哪些思路、参考过哪些项目」见 [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md)。

> 为什么这个文件是**必须**的：WebView2 SDK 的许可证第 2 条要求「二进制形式的再分发，
> 必须在随分发提供的文档和／或其他材料中复现版权声明、条件列表与免责声明」。
> 本仓库把三个 DLL 一起提交，所以这句话对我们生效。

---

## 1. Microsoft Edge WebView2 SDK 1.0.4258.31

| 项 | 值 |
|---|---|
| 随仓库的文件 | `shell/Microsoft.Web.WebView2.Core.dll`（698,208 B）<br>`shell/Microsoft.Web.WebView2.WinForms.dll`（38,752 B）<br>`shell/WebView2Loader.dll`（194,912 B，x64） |
| 来源 | NuGet 包 [`Microsoft.Web.WebView2` 1.0.4258.31](https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.4258.31)（`lib/net462/` ×2 ＋ `build/native/x64/` ×1） |
| 许可证 | **Microsoft WebView2 SDK License**（BSD-3-Clause 式三条款；无 SPDX 标识符；**不是 MIT**） |
| 许可证全文 | [`shell/Microsoft.Web.WebView2.LICENSE.txt`](shell/Microsoft.Web.WebView2.LICENSE.txt)（取自该 NuGet 包内 `LICENSE.txt`，1,487 字节，逐字节未改） |
| 再分发 | 允许：许可证第 1、2 条明确允许源码与二进制再分发；官方分发文档也把这 3 个文件列为「Files to ship with the app」 |
| 已履行的义务 | 版权声明＋条件＋免责声明已随仓库提供（本文件 §1.1 ＋ 上面那份 LICENSE.txt） |
| ⛔ 商标边界 | 本项目的名称、图标、域名不含 Edge／WebView2／Microsoft 品牌；描述里只作事实陈述（"uses the Microsoft Edge WebView2 control"），不暗示 Microsoft 背书 |

### 1.1 许可证全文（同上文件，此处再列一份便于分发时随包携带）

```
Copyright (C) Microsoft Corporation. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

   * Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
   * Redistributions in binary form must reproduce the above
copyright notice, this list of conditions and the following disclaimer
in the documentation and/or other materials provided with the
distribution.
   * The name of Microsoft Corporation, or the names of its contributors 
may not be used to endorse or promote products derived from this
software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

Microsoft、Microsoft Edge、WebView2 是 Microsoft 集团公司的商标。本项目与 Microsoft 无隶属、
背书或赞助关系。运行时依赖 **WebView2 Evergreen Runtime**（Win11 自带；Win10 由 Windows Update 安装），
该运行时**不随本仓库分发**。

---

## 2. 其它第三方件：无

- **Python 侧**：零第三方包，全部使用 Python 3.9+ 标准库（`sqlite3` / `http.server` / `subprocess` / `json` / `hashlib` …）。
- **前端**：`tools/ui.html` 是单文件手写 vanilla JS，**无框架、无 CDN 外链、无字体外链**。
- **桌面壳 / 托盘**：仅引用系统自带 .NET Framework 程序集（`System.Windows.Forms` / `System.Drawing` / `System.Net.Http`）与上面 §1 的三个 DLL。
- **图标**：`assets/board.ico` 由仓库内 `tools/make_icon.py` 用标准库现画，非第三方素材。

> 本节的依据是一次全仓溯源核验（30 个源文件＋4 个 `.cmd`＋`ui.html`）：无第三方版权头、无 SPDX 标识、
> 无可疑搬运片段、无 minified 代码、无 `sourceMappingURL`。若要复跑，可用
> `python tools/check.py --quick`（含语法与回归）加人工复核。
