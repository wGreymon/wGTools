#!/usr/bin/env python3
"""查询 OpenAI 兼容服务的模型列表。仅使用 Python 标准库。"""

import argparse
import getpass
import json
import math
import os
from pathlib import Path
import socket
import ssl
import sys
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


# 可以直接填写这里，也可以运行脚本后按提示输入。
# 优先级：命令行参数 > 环境变量 > 这里的配置 > 交互输入。
BASE_URL = ""  # 例如：https://api.example.com/v1
API_KEY = ""   # 例如：sk-xxxxxxxx


class ModelQueryError(Exception):
    """适合直接展示给用户的查询错误。"""


def model_urls(base_url):
    """保留自定义前缀和查询参数，补全 models 路径。"""
    base_url = base_url.strip()
    if not base_url or any(char.isspace() for char in base_url):
        raise ModelQueryError("URL 不能为空，也不能含有空白字符。")
    if "://" not in base_url:
        base_url = "https://" + base_url
    try:
        parts = urlsplit(base_url)
        valid_host = bool(parts.hostname)
        parts.port  # 提前验证端口是否合法。
    except ValueError as exc:
        raise ModelQueryError("URL 的域名或端口格式不正确。") from exc
    if parts.scheme not in ("http", "https") or not valid_host:
        raise ModelQueryError("请输入有效的 http:// 或 https:// 服务地址。")
    if parts.username is not None or parts.password is not None:
        raise ModelQueryError("请单独填写 API Key，不要把用户名或密码放在 URL 中。")
    if parts.fragment:
        raise ModelQueryError("URL 中不能包含 # 片段，请填写 API 服务地址。")

    path = parts.path.rstrip("/")
    if not path:
        paths = ["/v1/models", "/models"]
    elif path.endswith("/models"):
        paths = [path]
    else:
        # 也接受常见的完整调用地址，例如 /v1/chat/completions。
        for suffix in ("/chat/completions", "/responses", "/messages", "/completions", "/embeddings"):
            if path.endswith(suffix):
                path = path[:-len(suffix)]
                break
        paths = [path + "/models"]
    return [urlunsplit((parts.scheme, parts.netloc, path, parts.query, "")) for path in paths]


class SameOriginRedirectHandler(HTTPRedirectHandler):
    """避免重定向把 Authorization 发给另一个服务。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        def origin(url):
            parsed = urlsplit(url)
            return (parsed.scheme, parsed.hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80))

        if origin(req.full_url) != origin(newurl):
            raise ModelQueryError("接口重定向到了另一个服务地址，请直接填写最终的 API 地址后重试。")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# 成功 HTTP 状态或任意 JSON 都不足以证明兼容，必须校验各自的响应结构。
UPSTREAM_FORMATS = (
    ("openai_chat", "OpenAI Chat", "chat/completions"),
    ("openai_responses", "OpenAI Responses", "responses"),
    ("anthropic_messages", "Anthropic Messages", "messages"),
)


def api_base_urls(base_url):
    """把用户填写的 URL 转成一个或多个 API 基础路径。"""
    result = []
    for endpoint in model_urls(base_url):
        parts = urlsplit(endpoint)
        result.append(urlunsplit((parts.scheme, parts.netloc, parts.path[:-len("/models")],
                                  parts.query, "")))
    return result


def _format_request(format_name, model, max_tokens=128,
                    chat_token_param="max_completion_tokens"):
    """返回用于真实能力探测的最小请求体和请求头。"""
    if format_name == "openai_chat":
        body = {"model": model, "messages": [{"role": "user", "content": "Reply only OK."}],
                chat_token_param: max_tokens, "stream": False}
        headers = {}
    elif format_name == "openai_responses":
        body = {"model": model, "input": "Reply only OK.",
                "max_output_tokens": max_tokens, "stream": False}
        headers = {}
    elif format_name == "anthropic_messages":
        body = {"model": model, "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": "Reply only OK."}], "stream": False}
        headers = {"anthropic-version": "2023-06-01"}
    else:
        raise ModelQueryError("未知的上游格式：{}".format(format_name))
    return body, headers


def _probe_status(status):
    """失败状态只描述当前请求，不能据此推断整个服务不支持协议。"""
    if status in (404, 405, 501):
        return "unavailable", "当前路径或模型不可用；不能据此断定整个服务不支持该协议"
    if status in (401, 403):
        return "auth_error", "鉴权失败，请检查 Key、权限和该协议的鉴权方式"
    if status == 429:
        return "rate_limited", "被限流或额度不足，无法判断协议兼容性"
    if 400 <= status < 500:
        return "rejected", "模型或请求参数被拒绝，不能判定协议不支持"
    if 500 <= status < 600:
        return "server_error", "服务端错误，暂时无法判断"
    return "unknown", "无法根据 HTTP 状态确定协议兼容性"


def _has_text(blocks, block_type):
    return isinstance(blocks, list) and any(
        isinstance(block, dict) and block.get("type") == block_type
        and isinstance(block.get("text"), str) and block["text"].strip()
        for block in blocks
    )


def _validate_protocol_response(format_name, payload):
    """检查协议标识及助手内容，防止网关的通用成功页造成假阳性。"""
    if not isinstance(payload, dict):
        return "invalid_response", "响应不是 JSON 对象"
    if payload.get("error"):
        return "server_error", "响应中包含 error，即使 HTTP 200 也不能判定通过"
    if not isinstance(payload.get("id"), str) or not payload["id"]:
        return "invalid_response", "响应缺少有效 id，无法确认对应协议"

    has_text = False
    if format_name == "openai_chat":
        choices = payload.get("choices")
        if payload.get("object") != "chat.completion" or not isinstance(choices, list) or not choices:
            return "invalid_response", "缺少 Chat Completions 的 object 或 choices"
        for choice in choices:
            message = choice.get("message") if isinstance(choice, dict) else None
            if not isinstance(message, dict) or message.get("role") != "assistant":
                return "invalid_response", "choices 中缺少 assistant message"
            content = message.get("content")
            has_text = has_text or (isinstance(content, str) and bool(content.strip()))
            has_text = has_text or _has_text(content, "text")
    elif format_name == "openai_responses":
        output = payload.get("output")
        if payload.get("object") != "response" or not isinstance(output, list):
            return "invalid_response", "缺少 Responses 的 object 或 output"
        if payload.get("status") == "failed":
            return "server_error", "Responses 返回了 failed 状态"
        if payload.get("status") not in ("completed", "incomplete"):
            return "inconclusive", "Responses 尚未产生完成或截断的结果"
        has_text = any(isinstance(item, dict) and item.get("type") == "message"
                       and item.get("role") == "assistant"
                       and _has_text(item.get("content"), "output_text") for item in output)
    elif format_name == "anthropic_messages":
        if (payload.get("type") != "message" or payload.get("role") != "assistant"
                or not isinstance(payload.get("content"), list)):
            return "invalid_response", "缺少 Anthropic 的 type、role 或 content"
        has_text = _has_text(payload["content"], "text")
    if not has_text:
        return "inconclusive", "已识别协议结构但没有文本输出；推理模型可增大 --max-tokens 后复测"
    return "supported", "已收到符合该协议的助手文本；基础非流式调用通过"


def _safe_detail(text, api_key, endpoint):
    secrets = [api_key] if api_key else []
    secrets.extend(value for _, value in parse_qsl(urlsplit(endpoint).query) if value)
    for secret in sorted(set(secrets), key=len, reverse=True):
        text = text.replace(secret, "[已隐藏]").replace(quote(secret, safe=""), "[已隐藏]")
    text = "".join(" " if unicodedata.category(char).startswith("C") else char for char in text)
    return " ".join(text.split())[:400]


def _error_detail(raw):
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error", payload)
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        return " / ".join(str(error[key]) for key in ("type", "code", "message")
                          if isinstance(error.get(key), (str, int)))
    return ""


def probe_upstream_format(base_url, api_key, model, format_name, timeout=30,
                          max_tokens=128, chat_token_param="max_completion_tokens",
                          anthropic_auth="x-api-key"):
    """探测单个模型是否能通过指定上游协议路由。"""
    path_suffix = next(item[2] for item in UPSTREAM_FORMATS if item[0] == format_name)
    body, format_headers = _format_request(format_name, model, max_tokens, chat_token_param)
    encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ModelList/1.0",
    }
    headers.update(format_headers)
    if api_key:
        if any(char.isspace() for char in api_key):
            raise ModelQueryError("API Key 不能包含空格或换行。")
        if format_name != "anthropic_messages" or anthropic_auth in ("bearer", "both"):
            headers["Authorization"] = "Bearer " + api_key
        if format_name == "anthropic_messages" and anthropic_auth in ("x-api-key", "both"):
            headers["x-api-key"] = api_key

    opener = build_opener(SameOriginRedirectHandler())
    candidates = []
    for api_base in api_base_urls(base_url):
        parsed = urlsplit(api_base)
        path = parsed.path.rstrip("/") + "/" + path_suffix
        candidates.append(urlunsplit((parsed.scheme, parsed.netloc, path,
                                     parsed.query, "")))

    attempts = []
    for endpoint in candidates:
        started = time.monotonic()
        parts = urlsplit(endpoint)
        public_endpoint = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        result = {"endpoint": _safe_detail(public_endpoint, api_key, endpoint),
                  "status": "unknown", "http_status": None,
                  "auth": (anthropic_auth if format_name == "anthropic_messages" else "bearer")
                          if api_key else "none"}
        request = Request(endpoint, data=encoded_body, headers=headers, method="POST")
        retry_path = False
        try:
            with opener.open(request, timeout=timeout) as response:
                result["http_status"] = response.status
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    result.update(status="invalid_response", detail="响应超过 2 MiB，未继续读取")
                else:
                    try:
                        decoded = json.loads(raw)
                    except (ValueError, UnicodeError):
                        result.update(status="invalid_response", detail="响应不是有效 JSON，可能为 HTML 或 SSE；本次检测为非流式请求")
                    else:
                        kind, detail = _validate_protocol_response(format_name, decoded)
                        result.update(status=kind, detail=detail)
                        if isinstance(decoded, dict) and isinstance(decoded.get("model"), str):
                            result["response_model"] = _safe_detail(decoded["model"], api_key, endpoint)
        except HTTPError as exc:
            status = exc.code
            try:
                reason = _error_detail(exc.read(16384))
            except OSError:
                reason = ""
            exc.close()
            kind, detail = _probe_status(status)
            result.update(status=kind, http_status=status,
                          detail=detail + ("；服务提示：" + reason if reason else ""))
            # 仅裸域名有备用路径；模型不存在时换路径没有意义。
            retry_path = status in (404, 405) and "model" not in reason.lower() and "模型" not in reason
        except (socket.timeout, TimeoutError):
            result.update(status="timeout", detail="请求超时，可用 --timeout 60 复测")
        except URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                detail = "TLS 证书验证失败，暂时无法判断"
            elif isinstance(exc.reason, (socket.timeout, TimeoutError)):
                detail = "请求超时，暂时无法判断"
            else:
                detail = "无法连接探测接口，暂时无法判断"
            result.update(status="network_error", detail=detail)
        except ModelQueryError as exc:
            result.update(status="unknown", detail=str(exc))
        except (OSError, UnicodeError, ValueError):
            result.update(status="network_error", detail="读取响应失败或请求编码错误")
        result["detail"] = _safe_detail(result["detail"], api_key, endpoint)
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        attempts.append(dict(result))
        if not retry_path:
            break
    result["attempts"] = attempts
    return result


def check_upstream_formats(base_url, api_key, identifiers, timeout=30,
                           max_tokens=128, chat_token_param="max_completion_tokens",
                           anthropic_auth="x-api-key", progress=False):
    """按模型探测三种上游格式，返回适合终端和 JSON 使用的报告。"""
    report = {}
    total = len(identifiers) * len(UPSTREAM_FORMATS)
    index = 0
    for model in identifiers:
        report[model] = {}
        for format_name, label, _ in UPSTREAM_FORMATS:
            index += 1
            if progress:
                print("[{}/{}] {} · {} …".format(index, total, model, label),
                      end=" ", file=sys.stderr, flush=True)
            result = probe_upstream_format(base_url, api_key, model, format_name, timeout,
                                           max_tokens, chat_token_param, anthropic_auth)
            result["label"] = label
            report[model][format_name] = result
            if progress:
                print(STATUS_LABELS.get(result["status"], "未确定"), file=sys.stderr, flush=True)
    return report


STATUS_LABELS = {
    "supported": "通过", "unavailable": "不可用", "inconclusive": "需复测",
    "auth_error": "鉴权失败", "rate_limited": "限流/额度", "rejected": "请求被拒",
    "server_error": "服务错误", "invalid_response": "格式不符", "timeout": "超时",
    "network_error": "网络错误", "unknown": "未确定",
}


def print_format_report(report):
    """打印紧凑的格式支持矩阵。"""
    labels = [(name, label) for name, label, _ in UPSTREAM_FORMATS]
    columns = ["模型"] + [label for _, label in labels]
    rows = []
    for model, formats in report.items():
        rows.append([model] + [STATUS_LABELS.get(formats[name]["status"], "未确定") for name, _ in labels])
    def display_width(value):
        return sum(2 if unicodedata.east_asian_width(char) in ("W", "F") else 1 for char in value)
    widths = [display_width(column) for column in columns]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], display_width(value))
    def format_row(row):
        return "  ".join(value + " " * (widths[index] - display_width(value))
                         for index, value in enumerate(row))
    print("\n上游格式检测（基础非流式请求）：")
    print(format_row(columns))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(format_row(row))


def build_agent_templates(base_url, report=None, anthropic_auth="x-api-key", no_auth=False):
    """只生成模板文本，不读取或修改用户的 Agent 配置，也不接收真实 Key。"""
    report = report or {}
    default_base = urlsplit(api_base_urls(base_url)[0])

    def select_model(protocol):
        for model, formats in report.items():
            result = formats.get(protocol, {})
            if result.get("status") == "supported":
                return model, result
        return None, {}

    def without_query(parts, path):
        return urlunsplit((parts.scheme, parts.netloc, path, "", ""))

    # Codex 在 base_url 后追加 /responses，因此保留 /v1 或自定义前缀。
    codex_model, codex_result = select_model("openai_responses")
    codex_endpoint = urlsplit(codex_result.get("endpoint", ""))
    if codex_endpoint.path.endswith("/responses"):
        codex_base = without_query(codex_endpoint, codex_endpoint.path[:-len("/responses")])
    else:
        codex_base = without_query(default_base, default_base.path)
    quote_toml = lambda value: json.dumps(value, ensure_ascii=False)
    codex_lines = [
        'model_provider = "custom"',
        'model = ' + quote_toml(codex_model or "YOUR_RESPONSES_MODEL"),
        '',
        '[model_providers.custom]',
        'name = "My API"',
        'base_url = ' + quote_toml(codex_base),
        'wire_api = "responses"',
        'requires_openai_auth = false',
    ]
    codex_commands = "codex"
    if not no_auth:
        codex_lines.append('experimental_bearer_token = "YOUR_API_KEY"')
    codex_notes = []
    if codex_model is None:
        codex_notes.append("Responses 尚无通过的模型，请填写 YOUR_RESPONSES_MODEL。")

    # Claude Code 追加 /v1/messages，只能在这个后缀完全匹配时自动推导。
    claude_model, claude_result = select_model("anthropic_messages")
    claude_endpoint = urlsplit(claude_result.get("endpoint", ""))
    claude_notes = []
    route_matches = True
    if claude_endpoint.path.endswith("/v1/messages"):
        claude_base = without_query(claude_endpoint, claude_endpoint.path[:-len("/v1/messages")])
    elif claude_model is not None:
        claude_base = "YOUR_CLAUDE_BASE_URL"
        route_matches = False
        claude_notes.append("通过的路径不是 /v1/messages 结尾，请填写能提供该路径的 YOUR_CLAUDE_BASE_URL。")
    else:
        path = default_base.path
        if path.endswith("/v1"):
            path = path[:-len("/v1")]
        claude_base = without_query(default_base, path)
    if claude_model is None:
        claude_notes.append("Messages 尚无通过的模型，请填写 YOUR_MESSAGES_MODEL，并核对服务的 /v1/messages 路径。")
    auth_mode = claude_result.get("auth", anthropic_auth)
    claude_env = {"ANTHROPIC_BASE_URL": claude_base}
    if no_auth or auth_mode == "none":
        claude_env["ANTHROPIC_API_KEY"] = "NOT_REQUIRED"
        claude_notes.append("免鉴权服务：NOT_REQUIRED 是 Claude Code 客户端的占位 Key。")
    elif auth_mode == "bearer":
        claude_env["ANTHROPIC_AUTH_TOKEN"] = "YOUR_API_KEY"
    else:
        claude_env["ANTHROPIC_API_KEY"] = "YOUR_API_KEY"
        if auth_mode == "both":
            claude_notes.append("本次用了两种鉴权头；模板采用 x-api-key，请用 --anthropic-auth x-api-key 单独复测。")
    selected_model = claude_model or "YOUR_MESSAGES_MODEL"
    for name in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
                 "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
        claude_env[name] = selected_model

    if default_base.query:
        note = "模板未包含 URL 查询参数，如服务要求这些参数，请另行配置。"
        codex_notes.append(note)
        claude_notes.append(note)
    return {
        "codex": {
            "file": str(Path.home() / ".codex" / "config.toml"),
            "language": "toml", "model": codex_model,
            "protocol_verified": codex_model is not None,
            "content": "\n".join(codex_lines) + "\n",
            "powershell": codex_commands, "notes": codex_notes,
        },
        "claude_code": {
            "file": str(Path.home() / ".claude" / "settings.json"),
            "language": "json", "model": claude_model,
            "protocol_verified": claude_model is not None,
            "route_matches": route_matches,
            "content": json.dumps({"env": claude_env}, ensure_ascii=False, indent=2) + "\n",
            "powershell": "claude", "notes": claude_notes,
        },
    }


def print_agent_templates(templates):
    """在普通终端输出末尾提供可复制的配置内容。"""
    for name, label in (("codex", "Codex"), ("claude_code", "Claude Code")):
        item = templates[name]
        print("\n{} 配置模板：{}".format(label, item["file"]))
        for note in item["notes"]:
            print(note)
        print("```" + item["language"])
        print(item["content"], end="")
        print("```")
        print("启动（PowerShell）：")
        print("```powershell")
        print(item["powershell"])
        print("```")


def fetch_models(base_url, api_key, timeout=30):
    """返回接口原始 JSON；只有根地址的 404/405 才尝试备用路径。"""
    endpoints = model_urls(base_url)
    headers = {"Accept": "application/json", "User-Agent": "ModelList/1.0"}
    if api_key:
        if any(char.isspace() for char in api_key):
            raise ModelQueryError("API Key 不能包含空格或换行。")
        headers["Authorization"] = "Bearer " + api_key
    opener = build_opener(SameOriginRedirectHandler())
    for index, endpoint in enumerate(endpoints):
        request = Request(endpoint, headers=headers, method="GET")
        try:
            with opener.open(request, timeout=timeout) as response:
                body = response.read()
        except HTTPError as exc:
            status = exc.code
            exc.close()
            if status in (404, 405) and index + 1 < len(endpoints):
                continue
            explanations = {
                400: "请求被服务拒绝，请检查 URL 和服务的接口要求。",
                401: "鉴权失败，请检查 API Key 是否正确、是否已过期。",
                403: "没有访问权限，请检查 API Key 权限或服务的访问限制。",
                404: "未找到模型列表接口，请确认 API 地址；也可以直接填写完整 /models 地址。",
                405: "该地址不支持 GET 请求，请确认它是模型列表接口。",
                429: "请求过于频繁或额度受限，请稍后重试并检查服务配额。",
            }
            message = explanations.get(status, "服务暂时异常，请稍后重试。" if status >= 500
                                       else "请求失败，请检查服务地址和接口要求。")
            raise ModelQueryError("HTTP {}：{}".format(status, message)) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise ModelQueryError("请求超时，可使用 --timeout 60 增加等待时间。") from exc
        except URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                message = "TLS 证书验证失败，请检查服务证书或本机证书配置。"
            elif isinstance(exc.reason, (socket.timeout, TimeoutError)):
                message = "请求超时，可使用 --timeout 60 增加等待时间。"
            else:
                message = "无法连接服务，请检查域名、端口、网络和代理设置。"
            raise ModelQueryError(message) from exc
        except UnicodeError as exc:
            raise ModelQueryError("URL 或 API Key 含有不支持的字符，请检查输入。") from exc
        try:
            return json.loads(body)
        except (ValueError, UnicodeError) as exc:
            raise ModelQueryError("服务返回的不是有效 JSON，可能填写了网站首页或遇到了代理错误页。") from exc


def model_ids(payload):
    """识别常见列表包装；不把异常响应当成空列表。"""
    if isinstance(payload, dict):
        if "error" in payload:
            raise ModelQueryError("接口返回了错误信息，请检查 API Key、配额和服务状态。")
        entries = payload.get("data", payload.get("models"))
    else:
        entries = payload
    if not isinstance(entries, list):
        raise ModelQueryError("响应中没有模型列表；预期格式为 {\"data\": [{\"id\": \"模型名\"}]}。")

    result = set()
    for entry in entries:
        identifier = entry.get("id") if isinstance(entry, dict) else entry
        if not isinstance(identifier, str) or not identifier.strip():
            raise ModelQueryError("模型列表中存在缺少有效 id 的条目，接口可能不兼容。")
        result.add(identifier)
    return sorted(result, key=lambda value: (value.casefold(), value))


def positive_timeout(value):
    try:
        timeout = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("超时时间必须是大于 0 的秒数。")
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("超时时间必须是大于 0 的有限秒数。")
    return timeout


def positive_tokens(value):
    try:
        tokens = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("输出 token 上限必须是正整数。")
    if tokens <= 0:
        raise argparse.ArgumentTypeError("输出 token 上限必须是正整数。")
    return tokens


def build_parser():
    parser = argparse.ArgumentParser(
        description="查询 OpenAI 兼容服务支持的模型（无需安装第三方依赖）。",
        epilog="直接运行可交互输入；也可设置 MODEL_API_URL 和 MODEL_API_KEY 环境变量。",
    )
    parser.add_argument("--url", default=os.environ.get("MODEL_API_URL") or BASE_URL,
                        help="服务域名、API 基础地址或完整 models 地址")
    auth = parser.add_mutually_exclusive_group()
    auth.add_argument("--api-key", "--key", dest="api_key",
                      default=os.environ.get("MODEL_API_KEY") or API_KEY,
                      help="API Key；省略时隐藏输入")
    auth.add_argument("--no-auth", action="store_true", help="不发送鉴权头，适用于无需 Key 的服务")
    parser.add_argument("--timeout", type=positive_timeout, default=30, metavar="秒",
                        help="请求超时时间，默认 30 秒")
    parser.add_argument("--json", action="store_true", help="输出 JSON；检测模式包含完整检测报告")
    parser.add_argument("--output", metavar="文件", help="保存模型 JSON 或检测报告，例如 report.json")
    parser.add_argument("--check-formats", action="store_true",
                        help="逐个模型检测 OpenAI Chat、Responses 和 Anthropic Messages")
    parser.add_argument("--format-json", action="store_true",
                        help="以 JSON 输出格式检测报告（自动启用 --check-formats）")
    parser.add_argument("--model", action="append", metavar="模型名",
                        help="检测指定模型，可重复；自动开启检测并跳过模型列表查询")
    parser.add_argument("--max-tokens", type=positive_tokens, default=128,
                        help="每次检测的输出 token 上限，默认 128；推理模型可适当增加")
    parser.add_argument("--chat-token-param", choices=("max_completion_tokens", "max_tokens"),
                        default="max_completion_tokens", help="Chat 协议的限额字段，兼容旧接口时可选 max_tokens")
    parser.add_argument("--anthropic-auth", choices=("x-api-key", "bearer", "both"),
                        default="x-api-key", help="Messages 鉴权方式，默认原生 x-api-key；按网关要求调整")
    parser.add_argument("--no-templates", action="store_true",
                        help="不生成末尾的 Codex 和 Claude Code 配置模板")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    api_key = ""
    try:
        if args.format_json or args.model:
            args.check_formats = True
        base_url = args.url.strip()
        if not base_url:
            if not sys.stdin.isatty():
                raise ModelQueryError("请通过 --url、MODEL_API_URL 或脚本顶部配置填写 URL。")
            print("请输入服务 URL：", end="", file=sys.stderr, flush=True)
            base_url = input().strip()
        model_urls(base_url)  # 在询问 Key 之前验证地址。

        if not args.no_auth:
            api_key = args.api_key.strip()
            if not api_key:
                if not sys.stdin.isatty():
                    raise ModelQueryError("请设置 MODEL_API_KEY 或 --api-key；免鉴权服务可使用 --no-auth。")
                api_key = getpass.getpass("请输入 API Key（输入不显示）：", stream=sys.stderr).strip()
            if not api_key:
                raise ModelQueryError("API Key 不能为空；免鉴权服务请使用 --no-auth。")

        if args.model:
            if any(not model.strip() for model in args.model):
                raise ModelQueryError("--model 不能为空。")
            payload = {"object": "list", "data": [{"id": model.strip()} for model in args.model]}
        else:
            payload = fetch_models(base_url, api_key, args.timeout)
        identifiers = model_ids(payload)
        format_report = None
        if args.check_formats:
            if not identifiers:
                print("服务返回了空模型列表，跳过上游格式检测。", file=sys.stderr)
            else:
                print("将对 {} 个模型进行 {} 次基础调用，每次输出上限 {} token，可能消耗额度。".format(
                    len(identifiers), len(identifiers) * len(UPSTREAM_FORMATS), args.max_tokens), file=sys.stderr)
                format_report = check_upstream_formats(
                    base_url, api_key, identifiers, args.timeout, args.max_tokens,
                    args.chat_token_param, args.anthropic_auth, progress=True)
        output_payload = payload
        templates = None
        if not args.no_templates:
            templates = build_agent_templates(base_url, format_report, args.anthropic_auth, args.no_auth)
        if args.check_formats:
            output_payload = {
                "schema_version": 1,
                "models_source": "manual" if args.model else "api",
                "models": payload,
                "probe": {"mode": "non_streaming", "max_output_tokens": args.max_tokens,
                          "chat_token_param": args.chat_token_param,
                          "anthropic_auth": args.anthropic_auth,
                          "note": "仅验证基础调用；未验证 SSE 流式、工具调用、图片及长上下文"},
                "format_support": format_report or {},
            }
            if templates is not None:
                output_payload["config_templates"] = templates
        rendered = json.dumps(output_payload, ensure_ascii=False, indent=2)
        if args.output:
            destination = Path(args.output).expanduser()
            destination.write_text(rendered + "\n", encoding="utf-8")
            print("已保存 JSON：{}".format(destination.resolve()), file=sys.stderr)

        if args.format_json or args.json:
            print(rendered)
        elif identifiers:
            print("共获取 {} 个模型：\n".format(len(identifiers)))
            for identifier in identifiers:
                print(identifier)
            if format_report is not None:
                print_format_report(format_report)
        else:
            print("请求成功，但服务返回了空模型列表。")
        if templates is not None and not (args.format_json or args.json):
            print_agent_templates(templates)
        return 0
    except (ModelQueryError, OSError, EOFError) as exc:
        message = str(exc)
        if api_key:
            message = message.replace(api_key, "[已隐藏]")
        print("错误：" + message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
