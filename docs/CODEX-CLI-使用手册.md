# Codex CLI 使用手册（跨平台）

> **更新与验证：** 2026-10-11，Windows 原生 CLI 0.162.1。文中标注“本机实测”或“历史记录”的内容只代表注明的版本、时间和平台；macOS、Linux、WSL2 的命令仍应以对应版本的 `codex --help` 为准。

## 目录

- [1. 安装、登录与升级](#1-安装登录与升级)
- [2. Windows 本机实测：多份 CLI 的现状](#2-windows-本机实测多份-cli-的现状)
- [3. 配置目录](#3-配置目录)
- [4. 接入多个中转（核心）](#4-接入多个中转核心)
- [5. 模型与推理档位](#5-模型与推理档位)
- [6. 日常命令](#6-日常命令)
- [7. 会话管理](#7-会话管理)
- [8. 非交互与脚本化](#8-非交互与脚本化)
- [9. 沙箱与审批](#9-沙箱与审批)
- [10. MCP 服务器](#10-mcp-服务器)
- [11. 诊断与维护](#11-诊断与维护)
- [12. 已知坑（本机实测）](#12-已知坑本机实测)
- [13. 一页速查](#13-一页速查)
- [14. 官方文档与核验顺序](#14-官方文档与核验顺序)

### 快速开始

```bash
codex --version
codex login
codex -C /path/to/project
codex
```

Windows PowerShell 可将 `codex` 换成 `codex.cmd`，`-C` 也可以省略，省略时使用当前目录。

本手册覆盖 Windows、macOS、Linux 和 WSL2。通用命令统一写成 `codex`；Windows 如果 PATH 中只有 npm 生成的批处理入口，请将它替换为 `codex.cmd`。参数是否可用应以当前安装版本的 `codex --help`（Windows 可用 `codex.cmd --help`）为准。标 ⚠️ 的内容是实测风险或易错点。

平台差异先看这张表：

| 平台 | 常用命令 | 默认配置目录 | 沙箱实现（通常） |
|---|---|---|---|
| Windows PowerShell/CMD | `codex`、`codex.cmd` | `%USERPROFILE%\.codex` | Windows 原生沙箱 |
| macOS | `codex` | `~/.codex` | Seatbelt |
| Linux | `codex` | `~/.codex` | bubblewrap（`bwrap`） |
| WSL2 | `codex` | Linux 环境的 `~/.codex` | Linux 沙箱 |

WSL2 是独立的 Linux 用户空间，不会自动读取 Windows 的 `%USERPROFILE%\.codex`。建议 Windows 原生和 WSL2 分别登录、分别维护配置；只有在明确需要共享时才设置同一个 `CODEX_HOME`。

VS Code 扩展和桌面应用可能自带另一份 CLI，不一定使用 PATH 中的 npm 版本。先用 `command -v codex`（Unix）或 `Get-Command codex -All`（Windows）确认终端版本；多份 CLI 是否冲突，主要取决于它们是否共用同一个 `CODEX_HOME`。

---

## 1. 安装、登录与升级

### 1.1 前置条件

- **Node.js 和 npm**：npm 安装方式需要 Node.js 和 npm。可从 [nodejs.org](https://nodejs.org/) 安装，或使用各平台版本管理器（`nvm`、`fnm`、`volta`）。以当前 `@openai/codex` 版本声明的 Node.js 要求为准。
- **Git**：Codex 的代码审查、worktree 和许多项目操作都依赖 Git。
- **终端**：macOS/Linux 使用 Terminal，Windows 使用 PowerShell 或 CMD，WSL2 使用 Linux shell。

检查 Node.js、npm 和 Git：

```bash
node --version
npm --version
git --version
```

### 1.2 安装 CLI

官方安装脚本：

```bash
# macOS / Linux / WSL2
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

```powershell
# Windows PowerShell
powershell -ExecutionPolicy Bypass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
```

在 CI 或无交互终端中，可以显式关闭安装器提问：

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 sh
```

```powershell
$env:CODEX_NON_INTERACTIVE = "1"; irm https://chatgpt.com/codex/install.ps1 | iex
```

也可以使用 npm（所有平台通用）：

```bash
npm install --global @openai/codex
```

macOS 也可以使用 Homebrew：

```bash
brew install --cask codex
```

安装后重新打开终端，让 PATH 生效。Windows 若 PowerShell 阻止 `codex.ps1`，使用 `codex.cmd`；macOS/Linux/WSL2 一般使用 `codex`。

如果提示找不到 `codex`，先确认 npm 的全局前缀并把对应的可执行目录加入 PATH：

```bash
npm prefix --global
```

macOS/Linux/WSL2 通常是 `<prefix>/bin`，Windows 通常是 `<prefix>`。修改 PATH 后必须重新打开终端，再运行 `codex --version`（Windows 可用 `codex.cmd --version`）。

### 1.3 验证安装与登录

```bash
codex --version
codex doctor --summary
codex login
codex login status
```

无浏览器或远程服务器环境可使用设备登录：

```bash
codex login --device-auth
```

使用 API key 登录时，先在当前 shell 设置 `OPENAI_API_KEY`，再通过 stdin 传给 Codex：

```bash
# macOS / Linux / WSL2
printf '%s' "$OPENAI_API_KEY" | codex login --with-api-key
```

```powershell
# Windows PowerShell
$env:OPENAI_API_KEY | codex.cmd login --with-api-key
```

登出：

```bash
codex logout
```

### 1.4 升级与卸载

官方安装脚本安装的版本可重新运行安装脚本更新，也可以使用当前 CLI 提供的更新命令：

```bash
codex update
```

npm 安装的版本建议使用与官方文档一致的安装命令覆盖更新：

```bash
npm install --global @openai/codex
```

确认实际调用的是哪一份 CLI：

```bash
# macOS / Linux / WSL2
command -v codex
codex --version
```

```powershell
# Windows PowerShell
Get-Command codex, codex.cmd -All
codex.cmd --version
```

卸载 npm 版本：

```bash
npm uninstall --global @openai/codex
```

安装脚本版本按安装器输出的路径移除，并先确认 `command -v codex` 或 `Get-Command codex` 指向的确实是该版本。

### 1.5 Shell 语法约定

后文的 `bash` 代码块默认使用 POSIX shell 语法（macOS/Linux/WSL2）；标记为 `powershell` 的代码块适用于 Windows PowerShell。CMD 不支持单引号包裹参数，涉及 `-c` 的命令请使用第 4.2 节的 CMD 写法。全文 `<...>` 均为占位符，执行前应替换为实际值并去掉尖括号。在 Windows 上也可以使用 Git Bash，但它读取的是 Windows 环境变量和 Windows 的 `CODEX_HOME`。

官方参考：

- [CLI 概览](https://learn.chatgpt.com/docs/codex/cli)
- [CLI 命令](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
- [配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)
- [高级配置（provider 与 profile）](https://learn.chatgpt.com/docs/config-file/config-advanced)
- [MCP 配置](https://learn.chatgpt.com/docs/extend/mcp)
- [权限与沙箱](https://learn.chatgpt.com/docs/agent-approvals-security#common-sandbox-and-approval-combinations)

---

## 2. Windows 本机实测：多份 CLI 的现状

这台机器上有多份 Codex CLI。下表在 **2026-10-11** 复核：npm 与桌面版本已实际运行 `--version`；VS Code 扩展路径本次未找到，保留旧记录只用于说明可能存在第三份 CLI。路径中的通配符表示安装目录可能随升级变化。它们是不同的可执行文件，但通常共用同一个 `CODEX_HOME`：

| 来源 | 路径 | 本机版本 |
|---|---|---|
| npm 全局安装 | `%USERPROFILE%\Tools\node\node-v23.9.0-win-x64\codex.cmd` | 0.162.1 |
| VS Code 扩展 `openai.chatgpt` 内置 | `%USERPROFILE%\.vscode\extensions\openai.chatgpt-*\bin\windows-x86_64\codex.exe` | 本次未找到；旧稿曾记录 0.160.0 |
| 桌面 Codex 应用内置 | `%LOCALAPPDATA%\OpenAI\Codex\bin\<版本>\codex.exe` | 0.154.0-alpha.6.2 |

```powershell
Get-Command codex.cmd       # PowerShell 中查看实际命令路径
codex.cmd --version         # 当前终端：codex-cli 0.162.1
where.exe codex.cmd         # 也可以用 Windows 的 where.exe
```

`codex.cmd` 是 npm 在 Windows 上生成的命令入口；如果 PowerShell 因执行策略拒绝 `codex.ps1`，直接使用 `codex.cmd`。这些命令在 PowerShell/CMD 中执行，不是在 Codex 对话输入框中执行。

VS Code 扩展通常调用它自己目录里的 `codex.exe`，不会自动改用 PATH 中的 npm 版本。两者一般共用 `%USERPROFILE%\.codex\`，因此可能读写同一份配置和会话数据；同时运行不同版本时不要让它们并行修改同一会话。

> ⚠️ **改配置前先退出所有 Codex**（终端 + VSCode 扩展）。Codex 运行时会回写 config.toml，实测发生过把 `model_reasoning_effort` 从 `xhigh` 改回 `high` 的情况。

### 2.1 多份 CLI 会冲突吗？

可执行文件本身通常不会冲突：PowerShell 通过 PATH 选择 npm 版本，VS Code 和桌面应用则直接调用各自目录里的 `codex.exe`。真正可能冲突的是它们共用的 `CODEX_HOME`，其中包含 `config.toml`、登录凭据和会话索引。

```powershell
Get-Command codex, codex.cmd -All  # 查看 PATH 中实际会调用哪些入口
codex.cmd --version               # 确认当前终端使用的版本
Get-ChildItem "$env:USERPROFILE\.vscode\extensions\openai.chatgpt-*\bin\windows-x86_64\codex.exe"
Get-ChildItem "$env:LOCALAPPDATA\OpenAI\Codex\bin\*\codex.exe"
```

如果要让某一套 CLI 使用独立配置，先创建目录，再只对当前 PowerShell 窗口设置：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex-npm"
$env:CODEX_HOME = "$env:USERPROFILE\.codex-npm"
codex.cmd login
codex.cmd --version
```

关闭该窗口后这个临时设置就失效。需要永久设置时使用 `setx CODEX_HOME "$env:USERPROFILE\.codex-npm"`；它会影响之后启动的进程，独立目录需要重新登录，也不会自动看到原目录中的会话。

---

## 3. 配置目录

```
~/.codex/                         # macOS / Linux / WSL2
%USERPROFILE%\.codex/             # Windows
├── config.toml          主配置（模型、provider、MCP、项目信任）
├── auth.json            OAuth / API key 凭据（用 codex login 生成）
├── sessions/            会话记录（版本相关的 rollout 文件）
├── archived_sessions/   已归档会话（若当前版本创建）
├── state_5.sqlite       会话索引（内部文件名和结构可能变化）
├── thread_history_1.sqlite  部分版本使用的对话存储
└── <名字>.config.toml   profile 文件（-p 使用）
```

`CODEX_HOME` 默认是 `~/.codex`。Windows 原生 PowerShell 展开为 `$env:USERPROFILE\.codex`；WSL2 使用 Linux 用户的 `~/.codex`，即使 Windows 主机也设置过 `%USERPROFILE%\.codex`，两者仍是不同目录。

Codex 还会在受信任项目中读取项目级 `.codex/config.toml`。项目配置适合保存模型、沙箱等项目默认值，但不能覆盖会重定向凭据或主机行为的字段，例如 `model_provider`、`model_providers`、`openai_base_url`、`profile`、`notify` 和 `otel`。这些字段应放在用户级 `$CODEX_HOME/config.toml`；profile 则通过 `--profile` / `-p` 选择。

需要临时使用其他配置目录时，目录必须先存在：

```bash
mkdir -p "$HOME/.codex-work"
CODEX_HOME="$HOME/.codex-work" codex login
```

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex-work"
$env:CODEX_HOME = "$env:USERPROFILE\.codex-work"
codex.cmd login
```

如果要允许 `workspace-write` 沙箱内的命令访问网络，在 `config.toml` 中配置：

```toml
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true
```

`[windows] sandbox = "mxc" | "elevated" | "unelevated"` 只选择 Windows 原生沙箱实现，与上面的 Codex 沙箱策略不是同一个字段。macOS/Linux/WSL2 不应照抄 `[windows]` 配置。`mxc` 不可用时，显式选择它会失败；具体兼容性以当前官方 Windows 沙箱文档和 `codex doctor` 为准。

TOML 的根级默认项（例如 `model`、`model_provider`、`approval_policy`）应放在第一个 `[table]` 之前；进入 `[model_providers.*]`、`[mcp_servers.*]` 等表后，后续同名键属于该表，不会回到根级。维护多个 provider 时建议先写根级默认项，再按 provider 分块并用空行分隔，最后写 MCP、`[tui]`、`[projects.*]` 等其他区块。

会话索引通常包含 `model_provider`、`model`、`cwd`、`title` 等元数据；文件名、表结构和正文存储方式属于内部实现，可能随版本变化。备份或迁移时复制整个 `CODEX_HOME`，不要只复制某一个 SQLite 文件，也不要把 `auth.json` 当作唯一可能的凭据存储（某些登录方式会使用系统密钥环）。

---

## 4. 接入多个中转（核心）

Codex **支持在一份 config.toml 里定义多个 provider**，方便按项目或按调用临时切换。

### 4.1 写法

```toml
model_provider = "hangzhale"      # 默认用哪个
model = "gpt-6.1-sol"
model_reasoning_effort = "xhigh"

# 根级默认项放在所有 [table] 之前；不同 provider 之间留空行便于维护

[model_providers.hangzhale]
name = "hangzhale"
base_url = "https://api.hangzhale.com"
wire_api = "responses"
env_key = "HANGZHALE_KEY"

[model_providers.modelflare]
name = "modelflare"
base_url = "https://modelflare.dev/v1"
wire_api = "responses"
env_key = "MODELFLARE_KEY"
```

**关键点：**

- 每个 provider 一个 `[model_providers.<名字>]` 区块，**名字随意取**，并列写就行
- provider 名字可按 URL 或用途自定义。TOML 的裸键只能包含英文字母、数字、下划线和连字符；在此范围内 `[model_providers.foo]` 与 `[model_providers."foo"]` 等价。名称含空格、点号、中文、`/`、`@` 等字符时必须加引号
- 纯数字 ID 也可以作为裸键，例如 `[model_providers.790053500]`，但为提高辨识度可以写成 `[model_providers."790053500"]`。点号尤其要注意：`[model_providers.openai.cn]` 是多层表，而 `[model_providers."openai.cn"]` 才表示 ID 为 `openai.cn` 的单个 provider
- `wire_api` **只支持 `"responses"`**。中转必须提供 Responses API 端点，只有 Chat Completions 的接不上
- `base_url` **按中转要求填写**：有的要带 `/v1`（如 `https://modelflare.dev/v1`），有的不带（如 `https://hubway.cc`）。Codex 会在末尾拼 `/responses`。填错会报 404 或一直重连
- `wire_api = "responses"` 和 `requires_openai_auth = false` 都是对应情形下的默认值，可以省略；写出 `wire_api` 有助于读者看懂协议。`experimental_bearer_token` 虽仍受支持，但官方不建议把 token 直接写进配置，应优先使用 `env_key`
- 内置 provider ID `openai`、`ollama`、`lmstudio` 是保留名称，不能用自定义表覆盖。若只想让内置 `openai` 走代理或数据驻留地址，使用根级 `openai_base_url = "..."`

`model_provider` 右侧是字符串值，所以配置文件中必须写引号：

```toml
model_provider = "modelflare"
```

表头里的 provider ID 是 TOML 键，引号是否必需取决于 ID 本身；不要把这两个位置混为一谈。

### 4.2 三种切换方式

```bash
codex                                    # 用 config.toml 里的默认 provider
codex -c 'model_provider="modelflare"'   # 单次覆盖
codex -p <名字>                          # 用 profile 文件
codex resume --last -c 'model_provider="modelflare"'
codex resume --all --include-non-interactive
codex resume <session-id> --no-daemon -c 'model_provider="modelflare"'
```

Windows PowerShell 如果只能找到 `codex.cmd`，将上面命令中的 `codex` 替换为 `codex.cmd`。`-c` 的引号在 Bash、PowerShell 中可用；CMD 不把单引号当作引号。对 provider 等字符串配置，CLI 在值无法解析为 TOML 时会采用原始字符串，因此 CMD 可直接使用：

```cmd
codex.cmd -c model_provider=modelflare
codex.cmd resume <session-id> --no-daemon -c model_provider=modelflare
```

PowerShell 中 `codex -c model_provider=modelflare` 目前也能工作，因为无法解析为 TOML 的值会回退为普通字符串。不过推荐统一写成 `codex -c 'model_provider="modelflare"'`：外层单引号保护整个 PowerShell 参数，内层双引号明确表示 TOML 字符串，也不会在 provider ID 恰好是 `true`、`123` 等值时被解析成布尔值或数字。执行前请把尖括号中的占位符替换为实际值。

### 4.3 用命名配置叠加

`-p <名字>` 会**叠加** `$CODEX_HOME/<名字>.config.toml` 到主配置之上：

```toml
# macOS / Linux / WSL2: ~/.codex/work.config.toml
# Windows: %USERPROFILE%/.codex/work.config.toml
model_provider = "modelflare"
model = "gpt-6.1-sol"
```

```bash
codex -p work
```

profile **只叠加不替换**——provider 定义仍然集中在主 config.toml；profile 可以覆盖模型、provider，也可以放置其他受支持的配置项。它不会创建独立的会话、登录凭据或 `CODEX_HOME`。

### 4.4 用环境变量存密钥（推荐）

明文 token 写在配置里有泄漏风险。改成指向环境变量：

```toml
[model_providers.modelflare]
name = "modelflare"
base_url = "https://modelflare.dev/v1"
wire_api = "responses"
requires_openai_auth = false
env_key = "MODELFLARE_KEY"     # 在原有 provider 区块中替代 experimental_bearer_token
```

```bash
export MODELFLARE_KEY="YOUR_TOKEN"   # 仅对当前 shell 及其子进程生效
```

```powershell
$env:MODELFLARE_KEY = "YOUR_TOKEN"    # 仅对当前 PowerShell 窗口生效
# setx MODELFLARE_KEY "YOUR_TOKEN"    # 写入用户环境变量；新终端才会读取
```

`env_key` 是官方支持字段；缺少对应环境变量时，Codex 会报告变量不存在。不要在同一个 config.toml 中重复声明同名 `[model_providers.modelflare]` 表；把字段合并到已有区块，并移除明文 token。

---

## 5. 模型与推理档位

### 5.1 切换模型

```bash
codex -m gpt-6-astra
codex -c 'model="gpt-6.1-sol"'
```

也可以在 config.toml 里改 `model = "..."` 设默认。

本手册的模型 ID 来自当前配置示例；具体名称和可用性由 provider 决定，不能据此推断 OpenAI 官方账户也提供这些模型。

### 5.2 本机可用模型（Windows 实测）

下表保留原稿中的历史测试记录，**原始测试日期和 CLI 版本未记录，本次修订没有重新发起模型推理请求**。结果只适用于当时使用的凭据，不是 provider 的永久能力保证。余额、权限或网关路由变化会造成 403；遇到失败先看完整错误和额度，再判断模型是否真的不支持。

| 中转 | `gpt-6.1-sol` | `gpt-6-astra` |
|---|---|---|
| `modelflare` | ✅ | ✅ |
| `portdan` | ✅ | ✅ |
| `hubway` | ✅ | ✅ |
| `hangzhale` | ❌ 403 余额不足 | ❌ 余额不足 |

> ⚠️ **版本号里的点和横杠含义不同**：`gpt-6.1-sol`（6.1）和 `gpt-6-astra`（6）是两个不同模型。

### 5.3 推理档位

`model_reasoning_effort` 是字符串配置，具体可选值取决于当前模型和 CLI 版本。常见值包括 `minimal`、`low`、`medium`、`high`、`xhigh`、`max`、`ultra`；不要把这份示例当成所有模型都支持的固定枚举。

```bash
codex -c 'model_reasoning_effort="xhigh"'
```

可用档位会受当前模型限制。交互界面通常可用 `Shift+Tab` 切换模式，`Alt+,` 降低推理档位，`Alt+.` 提高推理档位，`/model` 打开模型和推理选择器；快捷键和斜杠命令会随版本变化，请以当前界面的 `?`、`/` 和 `/keymap` 为准。⚠️ 见第 12 节：配置可能被 Codex 回写覆盖。

---

## 6. 日常命令

| 命令 | 作用 |
|---|---|
| `codex` | 启动交互式 TUI |
| `codex "你的任务"` | 带初始 prompt 启动 |
| `codex exec "任务"` | 非交互跑一次（简写 `codex e`） |
| `codex resume` | 恢复会话并打开选择器 |
| `codex resume --last` | 直接继续最近一次 |
| `codex fork` | 从历史会话分叉 |
| `codex review` | 代码审查（非交互） |
| `codex apply <TASK_ID>` | 把云端任务的 diff 应用到本地 |
| `codex doctor` | 诊断安装/配置/网络健康 |
| `codex update` | 升级 Codex |
| `codex login` / `codex logout` | 管理登录 |
| `codex mcp` | 管理 MCP 服务器 |
| `codex plugin` | 管理插件与插件市场 |
| `codex completion <shell>` | 生成 Bash、PowerShell、Zsh 等补全脚本 |
| `codex sandbox` | 在沙箱里跑命令 |
| `codex features` | 查看/开关实验特性 |

Windows PowerShell 若 `codex` 被执行策略拦截，使用同样参数的 `codex.cmd`，例如 `codex.cmd resume --last`。命令始终在外部终端执行，不是在 Codex 的 prompt 输入框中执行。

### 6.1 启动时的常用开关

```text
-C, --cd <DIR>                指定工作根目录
--add-dir <DIR>               额外可写目录
-s, --sandbox <MODE>          read-only | workspace-write | danger-full-access
-a, --ask-for-approval <POL>  on-request | never
-m, --model <MODEL>           指定模型
-i, --image <FILE>            附加图片到初始 prompt
--search                      启用联网搜索
--worktree                    在新建的 git worktree 里跑
--no-alt-screen               不用备用屏幕，保留滚动历史
--no-daemon                   本次不用共享后台服务
--strict-config               遇到未知配置字段立即报错
```

> 上述参数可与 `codex` 或 Windows 的 `codex.cmd` 组合使用。完整选项以当前版本的 `codex --help` 为准。

`-C, --cd <DIR>` 指定本次启动的工作目录；可以完全省略，省略时使用启动命令所在的当前目录。它不会切换 `CODEX_HOME`。小写 `-c, --config key=value` 则临时覆盖配置，可以重复使用并通过点号设置嵌套项，例如 `-c 'model_provider="modelflare"'`；它不是指定配置文件路径。

恢复会话时，如果当前目录与会话记录的目录不同，CLI 可能询问使用哪个目录。可以在配置中设置默认选择：

```toml
[tui]
resume_cwd = "current"  # 也可以是 "session"
```

显式传入 `-C` 时，以命令行目录为准。

某些版本在使用 `-c`、`-p`、`--enable`、`--disable` 或 `--search` 等启动覆盖项时，可能显示“Running without shared background server...”并使用本次启动内嵌的服务；`--no-daemon` 会明确选择这种模式。它不会 fork，也不会改变 session ID。`codex agents` 浏览的是共享后台服务中的会话；独立内嵌的 TUI 会话不保证能被其他进程排队访问。

---

## 7. 会话管理

### 7.1 恢复

```bash
codex resume                               # 弹出选择器
codex resume --last                        # 最近的，不弹窗
codex resume --all                         # 取消 cwd 过滤
codex resume --all --include-non-interactive # 加入 exec 等非交互会话
codex resume <UUID|会话名>                  # 按 ID 或名称恢复
```

在已经打开的交互界面中输入 `/resume` 也可以打开选择器。`--all` 的确定含义是取消当前工作目录过滤，不保证忽略 provider、列出已归档会话或跨所有历史来源；`--include-non-interactive` 才是加入 `exec` 等非交互会话。`--last` 选择符合筛选条件的最新会话，多个 provider 共用目录时可能不是你想要的那一个。Windows 把命令名替换成 `codex.cmd` 即可。

需要稳定恢复某个会话时，优先使用完整 UUID。交互界面可输入 `/status` 查看当前会话信息，`/rename` 设置易记名称；`/statusline` 可以把状态信息放进底部状态栏（具体显示项随版本变化）。在选择器中按 `Ctrl+C` 返回终端。

### 7.2 分支与分叉

```bash
codex fork                     # 分叉一个历史会话
codex fork --last
```

分叉让你**不改动原会话**地试另一个方案——对比不同模型对同一题的表现时很有用。

### 7.3 跨 provider 恢复（实测行为）

显式指定 session UUID 时，可以在当前配置下用另一个 provider 继续同一会话，不需要 fork：

```bash
codex resume <session-id>                   # 用 config.toml 的默认 provider
codex resume <session-id> --no-daemon -c 'model_provider="hubway"'
```

实测会看到 `This session was recorded with model X but is resuming with Y` 一类提示。会话记录包含原始 provider/model 元数据，恢复时的实际请求使用当前配置；是否更新历史标签、能否在删除旧 provider 后继续，属于版本实现细节，不应当作为备份或迁移保证。正文可能存放在 JSONL 或版本迁移后的分页数据库中，不能保证全部位于某一个 SQLite 文件。

### 7.4 排队与清理

```bash
codex queue --thread <UUID|名字> --message "继续做 X"   # 给正在跑的会话排队消息
codex archive <id>          # 归档
codex unarchive <id>        # 取消归档
codex delete <id|名字>      # 永久删除（会提示确认）
codex delete --force <UUID> # UUID 明确时跳过确认
```

删除是永久操作；`archive` 只是隐藏/归档，之后仍可用 `unarchive` 恢复。命令行操作应在 PowerShell/CMD 中执行，不是在 Codex 输入框中执行。

---

## 8. 非交互与脚本化

`codex exec` 适合自动化评测和脚本化调用。

```bash
codex exec "解释这个仓库"                    # 一次性
git diff | codex exec "审查这个改动"          # 管道喂入
codex exec --json "..." > events.jsonl      # 输出 JSONL 事件
codex exec -o result.txt "..."              # 把最终回答写文件
```

### 8.1 关键开关

```text
--skip-git-repo-check          允许在非 Git 目录运行
--ephemeral                    不落盘会话文件
--json                         stdout 输出 JSONL 事件
-o, --output-last-message <FILE>  最终消息写入文件
--output-schema <FILE>         JSON Schema 约束最终回答结构
--ignore-user-config          不读 config.toml（auth 仍用 CODEX_HOME）
--ignore-rules                 不读 execpolicy .rules
--color always|never|auto
```

### 8.2 评测示例

```bash
cat prompt.txt |
  codex exec --skip-git-repo-check -c 'model_provider="modelflare"' --json -o answer.txt -
```

```powershell
Get-Content -Raw -Encoding utf8 prompt.txt |
  codex.cmd exec --skip-git-repo-check -c 'model_provider="modelflare"' --json -o answer.txt -
```

`--json` 会把事件流输出为 JSONL；`-o/--output-last-message` 只保存最终消息，未配合 `--output-schema` 时不保证它本身是 JSON，因此示例使用 `answer.txt`。需要结构化 JSON 时另行提供 JSON Schema，例如 `--output-schema schema.json -o answer.json`。`codex exec` 还有子命令：`resume`、`fork`、`review`；`--ephemeral` 可执行而不持久化本次 session。Windows PowerShell 版本使用 `codex.cmd exec`。

`--skip-git-repo-check` 只是在非 Git 目录运行时跳过检查，并非所有评测都必需。`--ignore-user-config` 会跳过 `config.toml`，因此自定义 provider 也不会加载；不要和依赖命名 provider 的示例盲目组合。`--help` 或 TOML 解析成功只能说明参数/语法可读，不代表 provider 能完成网络推理；真正的 smoke test 仍需一次 `exec` 请求并检查退出码和输出。

> ⚠️ **Windows CMD 下复杂引号可能被重新解析**。如果出现 `unexpected argument`，CMD 可用 `codex.cmd exec < prompt.txt` 从 stdin 输入；PowerShell 请用 `Get-Content -Raw -Encoding utf8 prompt.txt | codex.cmd exec -`。PowerShell 的反引号 \` 是续行符，CMD 下请把命令写成一行。

---

## 9. 沙箱与审批

Codex 有内置沙箱；macOS 使用 Seatbelt，Linux/WSL2 使用 bubblewrap 与 seccomp（兼容路径可能使用 Landlock），Windows 可使用 MXC 或旧版受限沙箱实现。具体能力取决于操作系统和主机支持，以官方平台文档、`codex doctor` 和当前安装结果为准。

### 9.1 沙箱模式

| 模式 | 效果 |
|---|---|
| `read-only` | 受沙箱约束的命令不能写入工作区 |
| `workspace-write` | 工作区及 `--add-dir` 目录可写（常见默认预设） |
| `danger-full-access` | 移除文件系统和网络边界（危险） |

```bash
codex -s workspace-write
codex --dangerously-bypass-approvals-and-sandbox   # 完全放开，仅限外部已隔离的环境
```

Windows PowerShell 将 `codex` 替换为 `codex.cmd`。缺少平台所需能力时，先运行 `codex doctor` 查看诊断。`codex sandbox` 是平台相关的调试入口，参数形式会随操作系统和版本变化，使用前先运行 `codex sandbox --help`。

### 9.2 审批策略

```
on-request   模型自己决定何时问你要批准
never        从不询问，失败直接返回给模型
```

### 9.3 Full access（完全访问）

CLI 交互界面里输入 `/permissions`，可以打开权限选择器。桌面版的 **Full access** 在 CLI 中对应“关闭沙箱 + 不再询问审批”：

```bash
codex -s danger-full-access -a never
```

也可以在 `~/.codex/config.toml`（Windows 为 `%USERPROFILE%\.codex\config.toml`）中设为默认：

```toml
sandbox_mode = "danger-full-access"
approval_policy = "never"
```

仅设置 `-s danger-full-access` 会移除沙箱限制，但审批策略仍由 `approval_policy` 决定。下面这个快捷开关会同时跳过所有确认并取消沙箱，等价于同时选择完全访问和 `never` 审批：

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

`approval_policy = "never"` 只是不再询问审批，并不会自动关闭沙箱。`danger-full-access` 才会移除文件系统和网络边界；两者组合后的权限接近桌面版的 Full access。此时 Codex 仍以当前操作系统用户身份运行，不会自动获得管理员/root 权限。仅在你信任当前项目和任务时使用；组织策略也可能禁用该模式。参见[官方权限与沙箱说明](https://learn.chatgpt.com/docs/agent-approvals-security#common-sandbox-and-approval-combinations)。

### 9.4 在沙箱里跑任意命令

```bash
codex sandbox -- sh -c 'whoami'      # macOS / Linux / WSL2；先用 --help 确认当前版本语法
```

```powershell
codex.cmd sandbox -- cmd.exe /c whoami  # Windows；0.160.1 本机实测
```

```text
-P, --permission-profile <NAME>   套用命名权限配置
--sandbox-state-disable-network   关掉网络
```

Windows 上可额外配置 `[windows] sandbox = "mxc" | "elevated" | "unelevated"`；其他平台不要添加该平台专属字段。

---

## 10. MCP 服务器

MCP 是可选扩展。普通聊天、代码编辑、终端命令和 Git 操作不依赖 MCP；浏览器或外部连接器等能力可能需要额外 MCP 服务器。`config.toml` 中的 HTTP 示例：

```toml
# OpenAI 官方文档 MCP
[mcp_servers.openai_docs]
url = "https://developers.openai.com/mcp"
```

stdio 服务器需要真正实现 MCP 的 JSON-RPC 握手；`echo hi`、`cmd.exe /c echo hi` 等会立即退出或只输出普通文本，不能作为 MCP 服务器。需要停用某个配置项时可在该区块设置 `enabled = false`，或用 `codex mcp remove <name>` 删除。

用 CLI 管理更省事：

```bash
codex mcp list
codex mcp get <name>
codex mcp get <name> --json
codex mcp add <name> -- <命令> [参数...]     # stdio 服务器
codex mcp add <name> --url <URL>             # HTTP 服务器
codex mcp add <name> --url <URL> --bearer-token-env-var <ENV_VAR>
codex mcp remove <name>
codex mcp login <name>                 # 适用于支持 OAuth 的 HTTP 服务器
codex mcp login <name> --no-browser    # 远程或无浏览器终端
codex mcp logout <name>
```

Windows PowerShell 将命令名换成 `codex.cmd`。MCP 的 `command` 必须是目标平台实际存在的可执行文件，不能把 `cmd.exe` 配置复制到 macOS/Linux。

> ⚠️ 当前 CLI 通过是否配置 `command` 来识别 stdio 服务器；旧配置中的 `mcp_servers.<名字>.type` 可能被忽略并产生 warning，应以 `codex mcp get <name> --json` 和当前配置参考为准。`codex mcp login/logout` 主要用于支持 OAuth 的 HTTP 服务器，不是所有 stdio 服务器都适用。

如果出现 `MCP client ... failed to start` / `MCP startup incomplete`，先检查可执行文件路径、依赖、服务器是否真的支持 MCP 握手以及启动超时。桌面应用生成的 `node_repl` 路径可能随更新变化；已经不需要它时，可在已有区块设置 `enabled = false`，或执行 `codex mcp remove node_repl`。修改配置后需重新启动 CLI，旧启动提示不会从当前界面自动消失。

---

## 11. 诊断与维护

### 11.1 doctor

```bash
codex doctor                # 完整诊断
codex doctor --summary      # 只看汇总
codex doctor --json         # 机器可读（已脱敏）
```

检查项覆盖配置、auth、MCP、沙箱、更新、网络和后端服务；汇总会随环境变化，原稿中的 `18 ok · 3 notes · 3 warn · 0 fail` 只是一次历史结果。分享诊断输出前仍应检查路径和账户信息。

### 11.2 配置严格校验

```bash
codex --strict-config --no-daemon  # 加载配置并进入 TUI，未提交任务时不会发起模型推理
```

**配置里有本版本不认识的字段就直接报错**。管理多个中转时可用它检查未知字段；也可以在实际 `codex exec` 命令上添加 `--strict-config`。单独运行 `--help` 会提前显示帮助，不能代替配置校验。TOML 语法有效、字段受支持与 API 请求成功是三个不同的检查。

旧版实测曾用这种方式发现 `disable_response_storage` 不受支持：

```
unknown configuration field `disable_response_storage`
```

### 11.3 特性开关

```bash
codex features list
codex features enable <name>
codex features disable <name>
```

`features enable/disable` 会写入 `config.toml`，属于持久化修改。单次运行请用 `--enable <name>`、`--disable <name>` 或 `-c 'features.<name>=true/false'`；这些覆盖只对本次调用生效。`--strict-config` 是顶层或 `exec`/`resume` 等支持该选项的命令参数，不适用于 `codex features`。

---

## 12. 已知坑（本机实测）

**⚠️ 坑 1：Codex 会回写 config.toml**

运行时它会写 `[tui]` 状态、`model_availability_nux` 记录，并可能归一化 `reasoning_effort`。**改配置前退出所有 Codex 实例**（含 VSCode 扩展）。

**⚠️ 坑 2：当前版本忽略 `disable_response_storage`**

0.160.1 不认识这个字段，启动时会警告 `is ignored`；当前官方配置参考也没有列出它。从根级配置中删掉即可。这个键的名字涉及 API 响应存储，不能把它当作“是否保存本地 session”的开关。

**⚠️ 坑 3：cmd.exe 引号丢失**

见 8.2 节。用 stdin 传 prompt。

**⚠️ 坑 4：VSCode 扩展和 CLI 抢配置**

两者共用对应平台的 `CODEX_HOME`。Windows 原生和 WSL2 默认目录不同；同一目录被多个版本同时写入时仍可能互相覆盖。

**⚠️ 坑 5：只支持 Responses 协议**

`wire_api` 只能写 `"responses"`。中转必须在实际填写的 `base_url` 下提供 Responses API；只有 Chat Completions 或 Anthropic 协议的某个入口，并不能证明这个 URL 可用。不要仅凭域名把某个网关列为“不兼容”，应以实际端点和完整错误为准。

**⚠️ 坑 6：覆盖项会切换后台服务模式**

使用 `-c`、`-p`、`--enable`、`--disable`、`--search` 等覆盖项时，部分版本的 CLI 可能启动内嵌服务并显示 “Running without shared background server...”。`--no-daemon` 可明确选择内嵌模式；它不创建新会话，也不改变 session ID。相关限制见第 6.1 节。

**⚠️ 坑 7：验证 provider 别只看关键词**

prompt 里如果含 `PONG`，回显的 prompt 也会含 `PONG`，文本搜索会误判成功。应检查退出码、最终消息和完整错误；`-o answer.txt` 可单独保存模型最终回答，`--json` 的事件流可帮助定位失败阶段。不能仅凭 prompt 回显或 token 统计判断成功。

**⚠️ 坑 8：历史快照不是额度承诺**

模型/余额表保留的是未记录测试日期的旧结果，本机多版本表则标明了检查日期。余额变化、403、路由策略或本地登录状态都可能改变结果；重测时记录日期、CLI 版本、provider、模型和退出码，不要把诊断 endpoint 可访问当作推理成功。

---

## 13. 一页速查

```bash
# 启动
codex                                      # 交互式
codex exec "任务"                           # 非交互

# 切换中转
codex -c 'model_provider="modelflare"'
codex -p <profile>
codex -m gpt-6-astra

# 会话
codex resume --last                          # 接着上次
codex resume <session-id> --no-daemon -c 'model_provider="X"' # 指定会话并切换中转
codex fork --last                            # 分叉
codex resume --all --include-non-interactive  # 打开包含非交互会话的跨目录选择器

# 脚本化
cat prompt.txt | codex exec --skip-git-repo-check -c 'model_provider="X"' --json -o out.txt -

# 沙箱
codex -s workspace-write
codex -s read-only -a never

# 诊断
codex doctor --summary
codex --strict-config --no-daemon             # 加载配置，未知字段直接报错
codex mcp list
codex update
```

Windows PowerShell 速查：把上面每行开头的 `codex` 换成 `codex.cmd`；脚本化命令改用 `Get-Content -Raw -Encoding utf8 prompt.txt | codex.cmd exec ...`。

**配置**：macOS/Linux/WSL2 为 `~/.codex/config.toml`，Windows 为 `%USERPROFILE%\.codex\config.toml`
**会话**：对应 `CODEX_HOME` 下的版本相关索引、JSONL 或数据库文件；备份整个 `CODEX_HOME`
**profile**：对应 `CODEX_HOME` 下的 `<名字>.config.toml`

**推理档位**：常见 `minimal low medium high xhigh max ultra`，以当前模型和 CLI 为准
**沙箱**：`read-only workspace-write danger-full-access`
**审批**：`on-request never`
**协议**：`wire_api = "responses"`（唯一支持）

---

## 14. 官方文档与核验顺序

Codex 更新较快，遇到本文与实际行为不一致时，按下面顺序核验：

1. 运行 `codex --version`，确认实际调用的是哪一份 CLI。
2. 运行目标命令的 `--help`，例如 `codex resume --help` 或 `codex mcp add --help`。
3. 使用 `codex --strict-config --no-daemon` 检查配置字段；该命令只验证本机版本是否识别配置，不能证明 provider 的网络端点可用。
4. 查阅官方 OpenAI 文档；自定义 provider 最后仍需运行一次最小 `codex exec` 请求验证端点、凭据和 Responses 协议。

常用官方入口：

- [Codex CLI](https://developers.openai.com/codex/cli)
- [高级配置](https://developers.openai.com/codex/config-advanced)
- [配置参考](https://developers.openai.com/codex/config-reference)
- [沙箱与审批](https://developers.openai.com/codex/agent-approvals-security)
- [MCP](https://developers.openai.com/codex/mcp)
