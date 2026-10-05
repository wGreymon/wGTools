# Pi CLI 快速上手指南

> 面向第一次使用 Pi CLI 的用户，覆盖安装、配置、日常开发、会话管理、图片输入、故障排查和安全注意事项。
>
> 文档按 Pi 1.0.x 与 Node.js 22.19+ 编写。部分服务商、模型或终端快捷键可能略有差异，最终以 `pi --help` 和 Pi 内的 `/` 命令菜单为准。

**目录**

- [入门与日常使用](#1-pi-是什么)：Pi 简介、安装、工作流与常用命令（1–6）
- [会话与项目配置](#7-会话管理中断后如何继续)：会话、CLI、项目说明与提示模板（7–9）
- [模型接入](#10-接入第三方-api)：第三方 API 与 Provider Extension（10）
- [维护与排错](#11-删除会话与资源清理)：资源清理、常见问题与安全建议（11–13）
- [速查与扩展](#14-推荐日常模板)：提示模板、快捷参考、官方文档和插件选型（14–17）

## 1. Pi 是什么

Pi 是一个运行在终端里的 AI 编程助手。它可以在当前工作目录中：

- 阅读文件、搜索代码和分析项目结构
- 执行 Shell 命令
- 创建和修改文件
- 运行测试、构建项目和检查结果
- 保存对话，之后继续同一项工作
- 通过扩展、技能和提示模板定制工作流

Pi 不是隔离沙箱。它使用当前操作系统用户的权限运行，能做的事情取决于当前账号和启用的工具。

## 2. 首次安装

### 2.1 安装与验证

**检查 Node.js**

当前 Pi 要求 Node.js `22.19` 或更高版本：

```bash
node --version
npm --version
```

如果版本过低，先安装新版 Node.js，再重新打开终端检查版本。

**安装 Pi**

```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent
```

验证：

```bash
pi --version
pi --help
```

`--ignore-scripts` 是官方推荐的普通安装方式。Pi 正常运行不依赖 npm 生命周期脚本。

### 2.2 Shell 与命令环境

Pi 的 `bash` 工具和以 `!` 开头的命令使用配置的 Shell，默认通常是 Bash。启动 Pi 后，可以用下面的命令验证命令环境是否可用：

```text
!printf 'Shell is working\n'
```

如果需要使用其它 Shell，可以在用户配置文件 `~/.pi/agent/settings.json` 中设置 `shellPath`：

```json
{
  "shellPath": "/path/to/bash"
}
```

修改后重启 Pi。具体路径取决于本机的 Shell 安装位置；遇到命令执行问题时，先确认 `shellPath` 指向可执行文件，并在 Pi 中运行一个无副作用的命令测试。

## 3. 第一次启动和登录

进入需要处理的项目目录并启动 Pi（此处以 Bash 为例）：

```bash
cd /path/to/project
pi
```

工作目录很重要：Pi 会根据它读取项目文件、发现上下文配置，并按目录保存会话。

第一次使用时，在 Pi 中输入：

```text
/login
```

选择服务商并按提示登录或保存 API Key。然后选择模型：

```text
/model
```

也可以直接指定模型启动：

```bash
pi --model provider/model-id
```

查看当前可用模型：

```bash
pi --list-models
```

调整当前对话的思考强度：

```text
/thinking
```

常用级别包括 `off`、`minimal`、`low`、`medium`、`high`。复杂任务不一定需要最高级别，简单修改使用低级别通常更快、更省用量。

## 4. 第一个日常工作流

推荐每次任务按下面顺序开始：

**步骤 1：了解项目**

```text
先不要修改文件。请检查项目结构，说明使用的技术栈、启动命令、测试命令，以及你认为与当前任务相关的文件。
```

这样可以减少 Pi 在不了解项目约定时直接改错文件。

**步骤 2：明确任务、范围和验收标准**

```text
请在 src/auth 目录中修复登录超时问题。
要求：
1. 先定位原因，再修改代码。
2. 不要改动无关文件。
3. 修改后运行相关测试。
4. 最后告诉我改了哪些文件、测试结果和仍存在的风险。
```

好的任务描述通常包含：目标、范围、限制、验证方式和输出要求。

**步骤 3：检查改动**

Pi 会显示它执行的读取、搜索、命令和编辑操作。完成后，在 Pi 中运行：

```text
!git status --short
!git diff --stat
!git diff
```

不要只看 Pi 的文字总结，重要改动要检查实际 diff。

**步骤 4：运行验证**

```text
请运行项目已有的测试和构建检查。如果有失败，请区分是本次改动引入的，还是环境中原本就存在的。
```

也可以直接执行：

```text
!npm test
!npm run build
```

`!` 命令由 Pi 配置的 Shell 执行；默认通常是 Bash。如果命令行为异常，先检查 `shellPath` 和当前工作目录。

## 5. 日常输入方式

**输入多行内容**

- `Enter`：发送消息
- `Shift+Enter`：插入换行
- `Ctrl+G`：使用外部编辑器编辑长提示
- 输入 `@`：搜索并附加文件
- `Tab`：补全路径或选项

示例：

```text
请阅读 @src/api.ts 和 @test/api.test.ts，分析接口变更是否会破坏现有调用方。
```

文件路径按当前工作目录解析。图片也可以直接粘贴或拖入支持图片的终端，前提是当前模型支持图片输入。

**工作过程中追加指令**

- `Esc`：停止当前任务
- `Enter`：排队一条指导消息，当前操作完成后处理
- `Alt+Enter`：在终端支持该快捷键时排队后续消息
- `Alt+Up`：在终端支持该快捷键时恢复已排队消息
- 如果快捷键无效，使用 `/hotkeys` 查看当前绑定，或直接使用 Pi 内的消息队列功能
- `Ctrl+O`：展开或折叠工具输出
- `Ctrl+T`：显示或隐藏思考块

如果只是想纠正当前方向，可输入：

```text
先暂停。不要继续编辑，先解释你准备修改的文件和原因。
```

## 6. 必记的 Pi 命令

在 Pi 中输入 `/`，可以搜索当前可用命令。最常用的命令如下：

| 命令 | 用途 |
| --- | --- |
| `/help` | 查看帮助（若当前版本提供） |
| `/model` | 选择模型 |
| `/thinking` | 设置思考强度 |
| `/login` | 登录或配置服务商 |
| `/logout` | 移除服务商凭据 |
| `/settings` | 修改常用设置 |
| `/new` | 开始新会话 |
| `/resume` | 选择历史会话 |
| `/name 名称` | 给当前会话命名 |
| `/session` | 查看会话文件、ID、消息数和用量 |
| `/compact` | 压缩较长的上下文 |
| `/tree` | 浏览当前会话的分支树 |
| `/fork` | 从历史节点创建独立分支 |
| `/clone` | 复制当前会话 |
| `/copy` | 复制上一条助手回复 |
| `/export` | 导出会话为 HTML 或 JSONL |
| `/share` | 上传并分享会话，使用前先检查敏感信息 |
| `/reload` | 重新加载设置、技能、模板和扩展 |
| `/hotkeys` | 查看当前快捷键 |
| `/debug` | 写出终端和会话诊断日志 |
| `/bug` | 准备 Pi 问题报告 |
| `/quit` | 退出 Pi |

具体命令以当前会话的 `/` 菜单为准，因为扩展和技能可以增加命令。

## 7. 会话管理：中断后如何继续

### 7.1 恢复会话与管理分支

Pi 默认自动保存会话。退出后，在同一个项目目录运行：

```bash
pi --continue
```

选择其他历史会话：

```bash
pi --resume
```

在会话内：

```text
/resume
```

建议给重要任务命名：

```text
/name 修复支付回调
```

当一条会话里尝试了多个方案时，用 `/tree` 查看分支；想把某个方案独立出来，用 `/fork`。

### 7.2 上下文压缩与临时会话

**上下文太长**

当上下文接近模型上限时，Pi 通常会自动压缩旧消息。也可以手动执行：

```text
/compact
```

带上保留要求：

```text
/compact 保留已修改文件、失败测试、待处理问题和所有接口约束
```

压缩不会删除原始会话条目，只会改变后续请求发送给模型的历史内容。

**一次性任务，不保存会话**

```bash
pi --no-session --print "总结当前项目的启动方式"
```

这种模式退出后不能用 `--continue` 恢复。

## 8. 常用 CLI 模式

**交互模式**

```bash
pi
```

适合连续开发、反复查看结果和追加需求。

**一次性文本输出**

```bash
pi --print "总结当前仓库的结构和测试命令"
```

也可以把 Git diff 传给 Pi：

```bash
git diff | pi --print "审查这次改动，重点关注错误、回归和缺失测试"
```

**附加文件启动**

```bash
pi --print @README.md "总结这个项目并给出上手步骤"
```

**JSONL 事件输出**

```bash
pi --mode json "检查当前项目" > events.jsonl
```

适合脚本集成。JSON 模式的标准输出用于协议事件，不要把普通日志混到 stdout。

**限制工具**

只允许读取和搜索，不允许编辑或执行命令：

```bash
pi --tools read,grep,find,ls --print "审查当前项目，但不要修改任何文件"
```

注意：`--tools` 会替换整套工具，必须把需要的工具全部写出来。

## 9. 项目级说明文件与提示模板

### 9.1 项目约定

如果希望 Pi 每次进入项目都遵守固定约定，可以在项目根目录创建：

```text
AGENTS.md
```

示例：

```markdown
# 项目约定

- 使用 pnpm，不要使用 npm 安装依赖。
- 修改后运行 pnpm test 和 pnpm lint。
- API 错误统一使用 src/errors 中的类型。
- 不要修改 generated/ 目录中的文件。
- 提交总结时列出修改文件和验证命令。
```

Pi 也会发现 `CLAUDE.md` 等上下文文件。项目中的说明会影响模型行为，因此首次使用陌生仓库时要先检查其内容。

修改说明文件后，在当前 Pi 会话中运行：

```text
/reload
```

### 9.2 提示模板

提示模板是可重复使用的 `/` 命令，不会执行代码。创建用户级模板 `~/.pi/agent/prompts/review.md`：

内容示例：

```markdown
---
description: Review current git changes
argument-hint: "[focus]"
---
Review the current git diff. Focus on ${1:-correctness, security, performance, and missing tests}.
Return findings first with file and line references.
```

重新加载并使用：

```text
/reload
/review
/review API compatibility
```

模板适合固定提示；如果还需要配套资料和任务知识，考虑使用 Skill；如果需要执行自定义工具，则考虑 Extension。

### 9.3 配置目录与基础设置

默认用户配置目录：

```text
~/.pi/agent
```

常见文件：

| 文件 | 作用 |
| --- | --- |
| `settings.json` | 默认模型、工具、界面和网络重试设置 |
| `auth.json` | 登录凭据和 API Key，不要提交到 Git |
| `models.json` | 自定义服务商、模型和兼容端点 |
| `keybindings.json` | 自定义快捷键 |
| `AGENTS.md` | 所有项目通用的工作约定 |
| `sessions/` | 保存的会话 |
| `skills/` | 用户技能 |
| `prompts/` | 用户提示模板 |
| `extensions/` | 用户扩展 |

项目级配置位于：

```text
项目目录/.pi/
```

项目配置需要信任后才会加载。可以在 Pi 中执行：

```text
/trust
```

手动修改配置后执行：

```text
/reload
```

**一个稳妥的基础设置**

```json
{
  "defaultThinkingLevel": "medium",
  "tuiMode": "fullscreen",
  "retry": {
    "enabled": true,
    "maxRetries": 3,
    "baseDelayMs": 2000
  }
}
```

不建议一开始就改很多配置。先使用默认值，遇到具体需求再调整。

## 10. 接入第三方 API

Pi 接入第三方模型服务，先判断服务商支持哪一种协议：

| 服务商情况 | 推荐方式 |
| --- | --- |
| Pi 内置支持的服务商 | `/login` 登录，或设置官方环境变量 |
| OpenAI Chat Completions 兼容 | `models.json` + `openai-completions` |
| OpenAI Responses 兼容 | `models.json` + `openai-responses` |
| Anthropic Messages 兼容 | `models.json` + `anthropic-messages` |
| Ollama、LM Studio、vLLM 等兼容服务 | `models.json` |
| 自定义请求格式、认证流程或流式协议 | Provider Extension |

不要只因为服务商宣传“兼容 OpenAI”就直接假设它完全兼容。应确认它支持工具调用、流式输出、图片输入和具体请求路径。

### 10.1 凭据与请求头

**使用环境变量保存 API Key**

在启动 Pi 的终端中设置环境变量：

```bash
export MY_AI_API_KEY="你的密钥"
pi
```

该设置通常只对当前终端会话有效。若需持久保存，请使用当前系统的用户环境变量设置；修改后重新打开终端并启动 Pi。

在 `models.json` 中使用 `$MY_AI_API_KEY` 或 `${MY_AI_API_KEY}`，Pi 会在请求时解析它。不要把密钥放进 `index.html`、`AGENTS.md`、项目 `.pi` 目录或聊天提示中。

**使用固定 API Key 或自定义请求头**

可以直接写固定值，但不推荐：

```json
{
  "apiKey": "sk-example"
}
```

更推荐环境变量：

```json
{
  "apiKey": "$MY_AI_API_KEY"
}
```

如果服务商需要额外请求头，先确认当前 Pi 版本和该 API 实现支持的字段，再按服务商要求配置。不要通过把 Token 写进普通自定义 Header 的方式绕过 Pi 的认证机制，也不要把 `models.json` 提交到公开仓库。

部分服务商需要额外配置，例如组织 ID、区域或账户 ID。可把非敏感值放到 provider 配置中，把敏感值放到环境变量。服务商要求特殊认证流程时，优先使用 `/login` 或官方 provider；只有现有 API 实现无法满足时，才写扩展。

**凭据优先级**

Pi 解析 API Key 时，大致按以下优先级处理：

1. 当前命令的 `--api-key`
2. `auth.json` 中已保存的凭据
3. `models.json` 中的 `apiKey`
4. 服务商对应的环境变量

建议日常使用环境变量或 `/login`，避免将密钥硬编码在配置文件中。绝不要把 `auth.json` 提交到 Git。

### 10.2 OpenAI 兼容接口

**Chat Completions**

打开用户配置文件 `~/.pi/agent/models.json`，其中 `~` 表示当前用户的主目录。

示例：

```json
{
  "providers": {
    "my-openai-proxy": {
      "baseUrl": "https://api.example.com/v1",
      "api": "openai-completions",
      "apiKey": "$MY_AI_API_KEY",
      "models": [
        {
          "id": "my-model",
          "name": "My Model",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 128000,
          "maxTokens": 8192,
          "cost": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0
          }
        }
      ]
    }
  }
}
```

然后重新打开模型选择器：

```text
/model
```

选择 `my-openai-proxy/my-model`。也可以从命令行测试：

```bash
pi --model my-openai-proxy/my-model --print "用一句话介绍你自己"
```

`baseUrl` 要根据服务商文档填写。常见情况是填写到 `/v1`，但不要盲目追加 `/v1`；有些网关的接口根路径不同。

**Responses**

如果服务商明确实现的是 OpenAI Responses API，而不是旧的 Chat Completions API，使用：

```json
{
  "providers": {
    "my-responses-proxy": {
      "baseUrl": "https://api.example.com/v1",
      "api": "openai-responses",
      "apiKey": "$MY_AI_API_KEY",
      "models": [
        {
          "id": "my-responses-model",
          "name": "My Responses Model",
          "reasoning": true,
          "input": ["text"],
          "contextWindow": 128000,
          "maxTokens": 8192,
          "cost": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0
          }
        }
      ]
    }
  }
}
```

如果服务商只实现 `/v1/chat/completions`，不要使用 `openai-responses`。

### 10.3 Anthropic 兼容接口

服务商如果实现 Anthropic Messages 协议，可以配置：

```json
{
  "providers": {
    "my-anthropic-proxy": {
      "baseUrl": "https://api.example.com",
      "api": "anthropic-messages",
      "apiKey": "$MY_AI_API_KEY",
      "models": [
        {
          "id": "my-claude-model",
          "name": "My Claude Compatible Model",
          "reasoning": true,
          "input": ["text"],
          "contextWindow": 200000,
          "maxTokens": 8192,
          "cost": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0
          }
        }
      ]
    }
  }
}
```

`baseUrl` 仍然要以代理文档为准。确认服务商是否要求特殊版本请求头、额外组织 ID 或特定认证方式。

### 10.4 Ollama 本地模型

Ollama 通常不需要真实 API Key，可以把占位值写入配置：

```json
{
  "providers": {
    "ollama": {
      "baseUrl": "http://localhost:11434/v1",
      "api": "openai-completions",
      "apiKey": "ollama",
      "models": [
        {
          "id": "qwen2.5-coder:7b",
          "name": "Qwen 2.5 Coder 7B",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 32768,
          "maxTokens": 8192,
          "cost": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0
          }
        }
      ]
    }
  }
}
```

先确认 Ollama 正在运行并已下载模型：

```bash
ollama list
ollama pull qwen2.5-coder:7b
```

### 10.5 验证与故障排查

**验证顺序**

配置完成后，按以下顺序检查：

```bash
pi --list-models
pi auth check --provider my-openai-proxy --json
pi --model my-openai-proxy/my-model --print "回复 OK"
```

如果 `auth check` 不接受自定义 provider 名称，可以直接用最小的 `--print` 请求验证；不要使用真实业务数据。

第一次验证建议依次测试：

```text
回复 OK。
```

```text
请调用工具读取当前目录文件，并说明你读取了什么。
```

```text
请输出一段较长的中文文本，确认流式响应可以正常结束。
```

如果要在实际项目使用，再测试工具调用、上下文长度、图片输入和取消请求。

**常见故障**

**模型不出现在 `/model`**

检查：

1. `models.json` 是合法 JSON。
2. `providers`、provider 名称和 `models` 数组拼写正确。
3. `apiKey` 能被解析；环境变量必须在启动 Pi 的同一个终端进程中存在。
4. 模型对象包含 `id`、`name`、`input`、上下文窗口和输出限制等必要元数据。
5. 修改后重新打开 `/model` 或重启 Pi。

**401 / 403**

通常是密钥错误、环境变量没有传入、请求头格式不符，或服务商要求额外组织信息。不要先改模型协议，先用服务商提供的 curl 示例验证 URL 和凭据。

**404**

通常是 `baseUrl` 多了或少了路径，或者把 Responses、Chat Completions、Anthropic Messages 的协议弄混。确认完整请求路径和 `baseUrl` 的拼接规则。

**工具调用失败**

“能返回文本”不代表“完全兼容”。服务商可能不支持工具调用，或工具参数格式与 Pi 需要的格式不同。检查模型服务商对 tool calling、流式 tool call 和 JSON 参数的支持。

**`stream_read_error` 或没有 `finish_reason`**

这表示流式响应可能提前中断，或代理没有转发正常的结束事件。可能原因包括服务端超时、网关断连、协议转换问题或错误的 API 类型。降低任务长度只能作为临时排查手段；应同时检查服务端流式日志，并确认 `api` 配置与真实协议一致。

如果服务商的协议确实不同，`models.json` 不能修复它，需要自定义 provider extension。扩展需要正确处理请求、工具、取消、用量和终止事件，不能只把普通文本拼接回来。

### 10.6 自定义 Provider Extension

只有在以下情况才考虑扩展：

- 服务商不是 OpenAI、Anthropic 或其他 Pi 已支持的协议
- 需要自定义 OAuth、设备码或多步骤认证
- 需要动态发现模型
- 服务商的流式事件格式特殊
- 需要自定义请求转换、工具调用或错误处理

Provider Extension 会在 Pi 进程内运行，可以接触提示、工具定义、模型响应和凭据，因此只能加载自己审查过的代码。开发时可以通过 `--extension ./provider.ts` 临时加载，修改后在会话中运行 `/reload`。

## 11. 删除会话与资源清理

Pi 的会话、登录凭据、模型配置、扩展和项目配置是不同类型的资源。删除其中一种不会自动删除其他资源。清理前先确认自己要删除的是“历史对话”还是“工具和配置”。

### 11.1 会话清理

**删除单个会话**

在 Pi 中执行：

```text
/resume
```

在会话选择器中选中目标会话，然后按：

```text
Ctrl+D
```

确认删除。官方快捷键中：

- `Ctrl+D`：删除选中的会话
- `Ctrl+Backspace`：查询为空时执行非侵入式删除
- `Ctrl+P`：切换路径显示
- `Ctrl+S`：切换排序方式
- `Ctrl+N`：只显示已命名会话

不同终端可能拦截快捷键，遇到不一致时运行：

```text
/hotkeys
```

删除当前会话前，如果可能还需要继续使用它，先执行：

```text
/export backup-session.html
```

或：

```text
/export backup-session.jsonl
```

**开始新会话，而不是删除旧会话**

如果只是想清空当前上下文，不一定要删除历史记录：

```text
/new
```

这会创建新会话，旧会话仍然保留，可以之后通过 `/resume` 找回。

如果只是上下文太长，使用：

```text
/compact
```

`/compact` 只压缩后续请求使用的上下文，不会删除原始会话文件。

**查看会话文件位置**

在当前 Pi 会话中执行：

```text
/session
```

它会显示当前会话文件、会话 ID、消息数量和用量统计。

默认会话目录是 `~/.pi/agent/sessions/`，其中 `~` 表示当前用户的主目录。

会话通常按工作目录分组。也可以通过环境变量指定会话目录：

```bash
export PI_CODING_AGENT_SESSION_DIR="$HOME/PiSessions"
pi
```

或者直接通过 CLI 参数指定：

```bash
pi --session-dir "$HOME/PiSessions"
```

命令行参数的优先级高于环境变量和设置文件。

**批量清理旧会话：先预览，再删除**

不建议直接删除整个 `sessions` 目录，因为其中可能包含仍要恢复的项目会话。

先列出 30 天以前修改的 JSONL 会话（使用 Bash）：

```bash
sessionRoot="$HOME/.pi/agent/sessions"
find "$sessionRoot" -type f -name '*.jsonl' -mtime +30 -print
```

确认列表无误后，先移动到临时回收目录，而不是立即永久删除：

```bash
sessionRoot="$HOME/.pi/agent/sessions"
quarantine="${TMPDIR:-/tmp}/pi-old-sessions"
if [ -e "$quarantine" ]; then
  echo "Quarantine directory already exists; inspect it first: $quarantine"
  exit 1
fi
mkdir -p "$quarantine"
find "$sessionRoot" -type f -name '*.jsonl' -mtime +30 -print0 |
  while IFS= read -r -d '' file; do
    relative="${file#"$sessionRoot"/}"
    mkdir -p "$quarantine/$(dirname "$relative")"
    mv "$file" "$quarantine/$relative"
  done
echo "Moved old sessions to: $quarantine"
```

观察几天确认没有误删后，再清理临时目录。若使用其他路径，请把路径替换为上一步输出的实际回收目录：

```bash
rm -rf "${TMPDIR:-/tmp}/pi-old-sessions"
```

批量操作前必须退出所有 Pi 进程，避免 Pi 正在写入会话文件。

**删除全部本地会话**

只有确认不需要恢复任何历史对话时，才在 Bash 中执行：

```bash
rm -rf "$HOME/.pi/agent/sessions"
```

更稳妥的做法是先改名保留备份：

```bash
sessionRoot="$HOME/.pi/agent/sessions"
mv "$sessionRoot" "${sessionRoot}-backup-$(date +%Y%m%d-%H%M%S)"
```

Pi 下次启动时会创建新的会话目录。确认备份不需要后，再手动删除它。

### 11.2 登录凭据与 API Key

退出某个服务商：

```text
/logout
```

这会移除 Pi 保存的该服务商凭据，但不会自动：

- 删除环境变量中的 API Key
- 修改 `models.json` 中的 `apiKey`
- 撤销服务商后台的 API Key
- 删除已经导出的会话文件

如果 API Key 曾经泄露，应到服务商后台撤销并重新生成，而不是只运行 `/logout`。

凭据文件通常位于 `~/.pi/agent/auth.json`，其中 `~` 表示当前用户的主目录。

不要直接把 `auth.json` 发给别人，也不要提交到 Git。需要彻底重置所有本地登录凭据时，先退出 Pi，再备份并删除它（Bash）：

```bash
auth="$HOME/.pi/agent/auth.json"
if [ -f "$auth" ]; then
  cp -p "$auth" "$auth.backup"
  rm -f "$auth"
fi
```

### 11.3 扩展与配置清理

**第三方包、扩展和技能**

查看已配置的 Pi 包：

```bash
pi list
```

删除某个包：

```bash
pi remove <source>
```

例如：

```bash
pi remove npm:@example/pi-tools
```

项目级包使用：

```bash
pi remove --local <source>
```

也可以用：

```bash
pi config
```

查看和调整已发现的扩展、技能、提示模板和主题。

清理前要注意：Pi 包可能包含可执行扩展，且技能可以影响模型行为。先阅读包来源和配置，再删除或禁用。临时试用包时可使用：

```bash
pi -e npm:@example/pi-tools
```

这种方式不会把包加入永久配置，但仍应审查它的代码。

**用户级和项目级资源**

用户级资源目录（`~` 表示当前用户主目录）：

```text
~/.pi/agent/extensions/
~/.pi/agent/skills/
~/.pi/agent/prompts/
~/.pi/agent/themes/
```

项目级资源目录：

```text
项目目录/.pi/extensions/
项目目录/.pi/skills/
项目目录/.pi/prompts/
项目目录/.pi/themes/
```

删除资源后，在运行中的 Pi 会话中执行：

```text
/reload
```

如果是项目资源，删除前检查项目是否依赖它们。尤其不要随意删除：

- `.pi/settings.json`
- `.pi/mcp.json`
- `.pi/SYSTEM.md`
- `.pi/APPEND_SYSTEM.md`
- `AGENTS.md`
- `models.json`

这些文件可能包含项目工作约定、MCP 配置、模型端点或上下文指令。

### 11.4 导出文件、日志与恢复边界

**清理导出文件和诊断日志**

`/export` 生成的 HTML 或 JSONL 不在会话目录中时，需要按导出路径单独删除：

```bash
rm -f ./backup-session.html ./backup-session.jsonl
```

`/debug` 生成的诊断日志通常位于 Pi agent 目录中。诊断日志可能包含提示、工具输出、文件内容和终端数据。检查确认不再需要后再删除：

```bash
find "$HOME/.pi/agent" -type f -name 'pi-debug.log' -print
```

**清理前检查清单**

```text
1. 退出所有 Pi 进程。
2. 运行 /session 或 /resume，确认目标会话。
3. 需要保留的会话先用 /export 备份。
4. 确认是否还需要 API Key、模型配置和项目指令。
5. 优先移动到临时备份目录，不要直接永久删除。
6. 删除后重新启动 Pi，运行 /model、/resume 和 /reload 验证。
```

**不能恢复的内容**

永久删除本地 JSONL 会话后，Pi 没有内置回收站。导出的 HTML 或 JSONL 也不会被 Pi 自动重新关联为原会话。若误删，只能从文件备份、系统回收站、云盘版本或磁盘恢复工具中尝试恢复。

`/share` 产生的远程分享内容也需要在对应的分享服务中单独处理；删除本地会话不会自动删除远程分享链接。

## 12. 常见问题排查

### 12.1 启动与命令环境

**`pi` 不是命令**

检查 npm 全局可执行目录是否在 `PATH` 中：

```bash
npm prefix -g
command -v pi
```

重新打开终端后再试，并确认 npm 全局可执行目录已加入 `PATH`。

**Bash 不可用**

确认当前环境可用 Bash；如果需要指定其它 Bash，可在 `~/.pi/agent/settings.json` 中设置 `shellPath`，例如：

```json
{
  "shellPath": "/path/to/bash"
}
```

### 12.2 模型与接口故障

**模型不显示**

依次检查：

1. `/login` 是否已配置凭据。
2. `/model` 中是否能看到服务商。
3. `pi --list-models` 是否能列出目标模型。
4. 自定义模型的 `models.json` 中 `api`、`baseUrl` 和模型 ID 是否匹配。
5. 环境变量 API Key 是否存在于启动 Pi 的那个终端进程中。

查看凭据状态，但不要随便打印密钥：

```bash
pi auth check --provider <provider> --json
```

`pi auth print-api-key` 会输出真实密钥，只应在明确需要时使用，避免粘贴到聊天或日志中。

**`stream_read_error`、`Stream ended without finish_reason`**

这类错误通常表示模型服务的流式响应提前中断或缺少正常结束标记。它不自动等于超时，也不自动等于模型生成了错误格式。

排查顺序：

1. 重新发送一次较短任务。
2. 使用 `/model` 切换到另一个已验证稳定的模型或服务商。
3. 用 `/thinking` 降低思考级别。
4. 将大文件写入拆成多个较短任务。
5. 检查服务商状态、代理和网络日志。
6. 用 `/debug` 生成 Pi 诊断信息。
7. 需要反馈给 Pi 时使用 `/bug`，但先检查报告内容。

如果工具调用停在 `write ...`，先检查目标文件是否真的存在。工具调用只显示在终端，不代表已成功执行。

### 12.3 会话中断与终端显示

**会话“中断”后文件在哪里**

文件只有在 `write` 或 `edit` 工具成功返回后才算完成。可以在 Bash 终端检查：

```bash
ls -la
cat ./path/to/file
```

在 Shell 中可使用 `ls` 和 `cat` 检查；若当前终端提供其它文件查看命令，也可以使用对应命令。

会话可以用：

```bash
pi --continue
```

继续，但不要假设最后一次未完成的工具调用已经落盘。恢复后先让 Pi 检查工作区状态。

**工具输出太长**

- `Ctrl+O` 折叠或展开工具输出。
- 让 Pi 只返回摘要或关键行。
- 用命令过滤输出，例如 `git diff --stat`。
- 使用 `/compact` 压缩上下文。

**中文或快捷键显示异常**

确认终端字体支持中文，输入 `/hotkeys` 查看 Pi 当前识别到的快捷键。不同终端可能拦截或改写组合键；遇到异常时查看终端设置和 `/hotkeys`，或改用 Pi 当前显示的替代快捷键。

## 13. 安全和版本控制建议

Pi 会以当前用户权限执行命令，使用前建议：

- 重要项目先提交 Git 或建立备份。
- 不要在提示中粘贴 API Key、密码、Cookie 或生产数据。
- 不要随便批准陌生项目中的扩展、MCP server 或技能。
- 先阅读项目中的 `AGENTS.md`、`.pi/` 和脚本，再决定是否信任。
- 让 Pi 修改生产项目时，限定目录和任务范围。
- 先让 Pi 解释计划，再允许它执行高风险命令。
- 检查 `git diff`、测试结果和生成文件。
- 分享或导出会话前，确认其中没有密钥、私有代码和敏感命令输出。

项目级信任不是完整沙箱。即使拒绝信任，已启用的工具仍然按照当前操作系统权限运行。

## 14. 推荐日常模板

**新功能**

```text
请为当前项目实现 [功能]。
先检查项目结构、现有约定和相关测试，不要立即修改。
确认方案后再实现，限制修改范围，不要重写无关代码。
完成后运行相关测试和构建，并总结：
1. 修改了哪些文件
2. 做了哪些行为变化
3. 执行了哪些验证
4. 还有哪些风险或待办
```

**Bug 修复**

```text
请调查 [问题]。
先复现或定位原因，记录相关文件和调用链。
不要通过隐藏错误或放宽测试来绕过问题。
修复后添加或更新回归测试，并运行最小相关测试集。
```

**代码审查**

```text
请审查当前 git diff。
优先报告真实问题，按严重程度排序，并给出文件和行号。
重点检查正确性、数据丢失、安全、并发、兼容性和测试缺口。
如果没有发现问题，明确说明剩余风险和测试不足。
```

**只读分析**

```text
只分析，不修改文件，也不要执行有副作用的命令。
请说明你的依据、涉及文件、结论和不确定性。
```

## 15. 一页速查

**启动**

```bash
cd /path/to/project
pi
```

**恢复**

```bash
pi --continue
pi --resume
```

**交互命令**

```text
/login
/model
/thinking
/new
/name 任务名称
/session
/compact
/reload
/hotkeys
/quit
```

**终端快捷键**

| 快捷键 | 作用 |
| --- | --- |
| `Enter` | 发送 |
| `Shift+Enter` | 换行 |
| `Esc` | 停止当前任务 |
| `Ctrl+O` | 折叠/展开工具输出 |
| `Ctrl+T` | 显示/隐藏思考块 |
| `Ctrl+L` | 选择模型 |
| `Shift+Tab` | 切换思考级别 |
| `Ctrl+G` | 外部编辑器 |
| `Ctrl+D` | 空编辑器时退出 |
| `Alt+Enter` | 在支持该快捷键的终端中排队后续消息 |
| `Alt+Up` | 恢复已排队消息（具体以 `/hotkeys` 为准） |

## 16. 官方文档入口

当前安装版本随包附带完整文档，通常位于：

```text
<node 全局目录>/node_modules/@earendil-works/pi-coding-agent/docs
```

重点参考：

- `quickstart.md`：安装和首次使用
- `usage.md`：交互模式
- `cli.md`：命令行参数和脚本模式
- `models.md`：模型、服务商和自定义端点
- `sessions.md`：会话与上下文
- `configuration.md`：配置目录和项目资源
- `security.md`：安全边界
- `keybindings.md`：快捷键

遇到版本差异时，优先执行：

```bash
pi --help
```

并在 Pi 内输入 `/` 查看当前版本实际提供的命令。

## 17. 插件选型与推荐组合

Pi 插件可以补充搜索、联网、外部服务、长期记忆和任务编排能力，但插件不是越多越好。插件会增加工具、规则和执行行为；功能重叠会令流程冲突，也更难排错。建议从实际瓶颈出发，少量安装，再根据效果增减。

> 本节根据 [Pi Agent 插件推荐指南](https://itbug.shop/blog/pi-agent-plugins-recommendation-guide) 整理。原文以 Pi Agent 0.84.x 和作者当时使用的插件版本为背景，而本指南以 Pi 1.0.x 为背景。包名、命令、配置及兼容性都可能变化；安装前请检查插件当前 README、维护状态、版本要求和权限范围。

### 17.1 安装与管理

```bash
pi install npm:<package-name>
pi install -l npm:<package-name>
pi list
pi update --extensions
pi remove npm:<package-name>
```

第一条全局安装，第二条仅安装到当前项目。安装后重启 Pi 最稳妥；确认插件支持热加载时，可尝试 `/reload`。

第三方扩展在 Pi 进程中运行，可能以当前用户权限读写文件、启动进程或访问网络。安装前检查包来源、对应源码、实际注册的工具和依赖；MCP Token 使用环境变量或安全凭据机制。删除、发布、付款等高影响操作应保留人工审批。多 Agent 和自动化编排不是操作系统沙箱。

### 17.2 插件用途速查

| 插件 | 主要用途 | 适用时机与注意事项 |
| --- | --- | --- |
| `@ff-labs/pi-fff` | 模糊查找、预索引和相关性排序 | 大型仓库定位文件困难时；从项目目录启动，避免索引过大范围 |
| `pi-web-access` | 网页搜索和正文读取，以及 GitHub、PDF、视频研究 | 查最新资料时；重要结论回到原始来源核验 |
| `pi-mcp-adapter` | 接入 GitHub、Notion、数据库和内部 MCP 服务 | 确实需要外部服务时；按需连接工具并保护凭据 |
| `@juicesharp/rpiv-ask-user-question` | 结构化澄清问题 | 架构、兼容、迁移等关键选择无法从代码确认时；避免琐碎步骤也提问 |
| `@fradser/pi-monitor` | 后台等待测试、构建、部署等任务终态 | 长任务或日志量大时；成功条件须精确匹配真正终态 |
| `@fradser/pi-memory` | 保存跨会话的项目决策和技术事实 | 长期项目；只记短小、可验证且长期有用的信息，不记密钥或临时状态 |
| `pi-simplify` | 整理最近修改的代码并保持行为不变 | 功能完成后；检查 diff，不能替代审查和测试 |
| `pi-taskflow` | 多阶段、并行、可恢复的工作流 | 审计、批量迁移、研究汇总；核对当前版本成熟度并设置预算和质量门禁 |
| `@fradser/pi-agent-teams` | 常驻 Agent、角色协作和共享任务板 | 多角色需要持续协作时；定义清晰分工、权限和验证责任 |
| `@narumitw/pi-goal` | 围绕单一目标连续推进 | 验收条件明确且允许多轮执行时；设定预算和停止条件 |

以上能力和包名是原文的整理，不构成当前版本可用性的保证。请以各插件当前文档和安装后实测为准。

### 17.3 任务编排与插件组合

**Goal、Taskflow 与 Agent Teams 如何选择**

| 需求 | 优先考虑 | 理由 |
| --- | --- | --- |
| 一个明确目标，希望当前 Agent 连续推进并验证 | Goal | 围绕单一完成条件执行 |
| 有限流程需要拆阶段、并行、质量门禁或恢复 | Taskflow | 适合有阶段依赖的流水线 |
| 多个角色需要长期存在、互发消息和共享任务板 | Agent Teams | 适合持续角色协作，而非一次性并行 |

例如，修复 Bug 并补回归测试可考虑 Goal；批量审计并汇总报告可考虑 Taskflow；实现与安全复查需要长期交替可考虑 Agent Teams。先选一个主要执行模型，不要无差别叠加。无论采用哪一种，都要检查实际改动、测试结果和权限边界。

**按需组合**

- **轻量辅助**：文件搜索、联网研究、关键需求澄清、后台长任务通知。
- **长期开发**：在轻量组合上，按需要增加项目记忆、改动整理或目标驱动执行。
- **复杂自动化**：需要外部系统时考虑 MCP；需要可重复的多阶段流程时考虑 Taskflow；需要常驻角色协作时考虑 Agent Teams。

这只是按用途分层，不代表必须安装整套。先用 Pi 内置能力；遇到高频、具体的摩擦，再添加一个插件并验证收益。

**筛选标准**：插件是否解决高频问题、行为边界是否清楚、过程是否可观察、出错后是否容易定位。安装前审查代码和权限；使用中限定任务范围并保留人工检查；不再需要时用 `pi remove` 移除，并检查用户级与项目级配置是否有残留。

来源：[Pi Agent 插件推荐：我真正会长期保留的 10 个插件（附使用教程）](https://itbug.shop/blog/pi-agent-plugins-recommendation-guide)（访问日期：2026-10-04）。
