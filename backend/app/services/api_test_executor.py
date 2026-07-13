"""
API 测试执行器

负责异步执行 API 测试并收集结果
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import shutil
import time
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.api_test import APITest, APITestRun, APITestResult
from app.models.attachment import Attachment, AttachmentEntityType
from app.repositories.api_test_repo import (
    APITestRepository,
    APITestRunRepository,
    APITestResultRepository,
)
from app.config.minio_client import MinIOClient
from app.config.database import async_session_factory
from app.schemas.enums import TestResultStatus
from app.models.mongodb.api_test_log import APITestDetailLog
from app.services.environment_service import EnvironmentService
from app.utils.exceptions import BadRequestException
from app.utils.sync_executor import run_sync

logger = logging.getLogger(__name__)

# Playwright trace helper 文件名（放在 api_workspace_root 目录，与测试脚本目录 tests/ 同级）
TRACE_HELPER_FILE = "api-trace-helper.ts"

# trace helper 在仓库中的源路径（相对当前模块）
_TRACE_HELPER_SOURCE = Path(__file__).parent.parent.parent / "workspace" / "api" / TRACE_HELPER_FILE


def _cleanup_old_trace_helpers(workspace_dir: Path, max_age_seconds: float = 3600) -> None:
    """
    清理 workspace 中过期的临时 trace helper 文件。

    Windows 下主文件可能被占用，_ensure_trace_helper 会回退到临时文件名。
    这些临时文件不会自动删除，长期运行可能累积，因此每次执行前清理超过
    1 小时的旧临时文件（并发运行 1 小时内通常已完成，较安全）。
    """
    try:
        cutoff = time.time() - max_age_seconds
        for p in workspace_dir.glob("api-trace-helper-*.ts"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    logger.info("[APITestExecutor] 清理旧临时 trace helper: %s", p)
            except Exception:
                pass
    except Exception:
        pass


def _ensure_trace_helper(workspace_dir: Path) -> Path:
    """
    确保 workspace/api 目录存在最新版本的 api-trace-helper.ts。

    每次执行都会从仓库模板重新复制；若模板不存在，则写入一个最小可用版本。
    这样 helper 代码更新后能自动生效，不需要手动清理 workspace。

    Windows 下目标文件可能被占用，此时先尝试重命名，再不行就使用临时文件名。
    """
    target = workspace_dir / TRACE_HELPER_FILE
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # 清理过期的临时 helper 文件，避免 Windows 文件占用回退时无限累积
    _cleanup_old_trace_helpers(workspace_dir)

    if _TRACE_HELPER_SOURCE.exists():
        # 源文件已经在目标位置（例如 settings.api_workspace_root 指向 workspace/，
        # helper 源在 workspace/api/，目标也在 workspace/api/），直接复用
        if _TRACE_HELPER_SOURCE.resolve() == target.resolve():
            logger.info("[APITestExecutor] trace helper 已位于目标目录: %s", target)
            return target

        try:
            if target.exists():
                target.unlink()
            shutil.copy2(_TRACE_HELPER_SOURCE, target)
            logger.info("[APITestExecutor] 已复制 trace helper: %s", target)
            return target
        except PermissionError:
            # 文件被占用，先尝试重命名再复制
            try:
                backup = target.with_suffix('.ts.bak')
                if backup.exists():
                    backup.unlink()
                target.rename(backup)
                shutil.copy2(_TRACE_HELPER_SOURCE, target)
                logger.info("[APITestExecutor] 目标被占用，重命名后复制 trace helper: %s", target)
                return target
            except PermissionError:
                # 重命名也失败，使用临时文件名
                target = workspace_dir / f"api-trace-helper-{uuid4().hex}.ts"
                shutil.copy2(_TRACE_HELPER_SOURCE, target)
                logger.info("[APITestExecutor] 目标被占用，使用临时 trace helper: %s", target)
                return target

    # 兜底：写入最小可用版本
    minimal_helper = '''// NOTE: Keep this helper in sync with backend/app/services/api_test_executor.py.
// The `minimal_helper` string in that file is the embedded fallback used when
// this standalone template is not available.
import { test as baseTest, APIRequestContext, APIResponse } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

function ensureDir(filePath: string): void {
  const dir = path.dirname(filePath);
  if (dir && dir !== '.' && !fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function appendTrace(traceFile: string, entry: any): void {
  try {
    ensureDir(traceFile);
    fs.appendFileSync(traceFile, JSON.stringify(entry) + '\\n', 'utf-8');
  } catch (e) { /* ignore */ }
}

// ---------------------------------------------------------------------------
// 脱敏与大小配置（支持环境变量覆盖）
// ---------------------------------------------------------------------------
const DEFAULT_SENSITIVE_HEADERS = ['authorization', 'cookie', 'x-api-key', 'x-auth-token'];
const DEFAULT_SENSITIVE_BODY_FIELDS = [
  'password', 'token', 'secret', 'apikey', 'api_key',
  'accesstoken', 'refreshtoken', 'auth_token',
];
const DEFAULT_TRUNCATE_THRESHOLD = 50_000;
const DEFAULT_PREVIEW_LENGTH = 2_000;

function parseEnvList(name: string, defaults: string[]): string[] {
  const raw = process.env[name];
  if (!raw) return defaults;
  return raw.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
}

function parseEnvInt(name: string, defaultValue: number): number {
  const raw = process.env[name];
  if (!raw) return defaultValue;
  const parsed = parseInt(raw, 10);
  return Number.isNaN(parsed) ? defaultValue : parsed;
}

const SENSITIVE_HEADERS = new Set(parseEnvList('API_TEST_SENSITIVE_HEADERS', DEFAULT_SENSITIVE_HEADERS));
const SENSITIVE_BODY_FIELDS = new Set(parseEnvList('API_TEST_SENSITIVE_BODY_FIELDS', DEFAULT_SENSITIVE_BODY_FIELDS));
const BODY_TRUNCATE_THRESHOLD = parseEnvInt('API_TEST_BODY_TRUNCATE_THRESHOLD', DEFAULT_TRUNCATE_THRESHOLD);
const BODY_PREVIEW_LENGTH = parseEnvInt('API_TEST_BODY_PREVIEW_LENGTH', DEFAULT_PREVIEW_LENGTH);

function sanitizeHeaders(headers: Record<string, string> | undefined): Record<string, string> | undefined {
  if (!headers) return headers;
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(headers)) {
    result[key] = SENSITIVE_HEADERS.has(key.toLowerCase()) ? '***' : value;
  }
  return result;
}

function sanitizeBody(body: any): any {
  if (body === null || body === undefined) return body;
  if (typeof body === 'string') {
    try {
      const parsed = JSON.parse(body);
      const sanitized = sanitizeBody(parsed);
      return JSON.stringify(sanitized);
    } catch {
      return body;
    }
  }
  if (Array.isArray(body)) return body.map(sanitizeBody);
  if (typeof body !== 'object') return body;
  const result: any = {};
  for (const [key, value] of Object.entries(body)) {
    result[key] = SENSITIVE_BODY_FIELDS.has(key.toLowerCase()) ? '***' : sanitizeBody(value);
  }
  return result;
}

function getBodyMeta(body: any): { originalSize: number; truncated: boolean } {
  if (body === null || body === undefined) {
    return { originalSize: 0, truncated: false };
  }
  const serialized = typeof body === 'string' ? body : JSON.stringify(body);
  const originalSize = Buffer.byteLength(serialized, 'utf8');
  return { originalSize, truncated: originalSize > BODY_TRUNCATE_THRESHOLD };
}

function parseHeaders(h: HeadersInit | undefined): Record<string, string> | undefined {
  if (!h) return undefined;
  if (h instanceof Headers) {
    const result: Record<string, string> = {};
    h.forEach((v, k) => { result[k] = v; });
    return result;
  }
  if (Array.isArray(h)) return Object.fromEntries(h);
  return h as Record<string, string>;
}

function wrapResponse(response: APIResponse, testName: string, testTitle: string, traceFile: string, startTime: number, requestInfo: any): APIResponse {
  let bodyRecorded = false;
  const record = (responseBody?: any) => {
    if (bodyRecorded && responseBody === undefined) return;
    if (responseBody !== undefined) bodyRecorded = true;
    let body = responseBody;
    if (typeof body === 'string') { try { body = JSON.parse(body); } catch { /* keep text */ } }

    const sanitizedReqHeaders = sanitizeHeaders(requestInfo.headers);
    const sanitizedRespHeaders = sanitizeHeaders(response.headers());
    const sanitizedReqBody = sanitizeBody(requestInfo.body);
    const sanitizedRespBody = sanitizeBody(body);
    const reqBodyMeta = getBodyMeta(sanitizedReqBody);
    const respBodyMeta = getBodyMeta(sanitizedRespBody);

    appendTrace(traceFile, {
      testName, testTitle,
      method: requestInfo.method, url: requestInfo.url,
      requestHeaders: sanitizedReqHeaders,
      requestParams: requestInfo.params,
      requestBody: sanitizedReqBody,
      requestBodyOriginalSize: reqBodyMeta.originalSize,
      requestBodyTruncated: reqBodyMeta.truncated,
      status: response.status(), statusText: response.statusText(),
      responseHeaders: sanitizedRespHeaders,
      responseBody: sanitizedRespBody,
      responseBodyOriginalSize: respBodyMeta.originalSize,
      responseBodyTruncated: respBodyMeta.truncated,
      durationMs: Date.now() - startTime, timestamp: new Date().toISOString(),
    });
  };
  return new Proxy(response, {
    get(target, prop, receiver) {
      if (prop === 'json') return async () => { const body = await target.json(); record(body); return body; };
      if (prop === 'text') return async () => { const text = await target.text(); record(text); return text; };
      if (['status','statusText','headers','ok','url'].includes(prop as string)) record();
      return Reflect.get(target, prop, receiver);
    },
  });
}

function wrapContext(context: APIRequestContext, testName: string, testTitle: string, traceFile: string): APIRequestContext {
  const methods = ['get','post','put','delete','patch','head'];
  const recordRequest = (method: string, url: string, options: any, startTime: number, extra: any = {}) => {
    const sanitizedReqHeaders = sanitizeHeaders(options?.headers);
    const sanitizedReqBody = sanitizeBody(options?.data);
    const reqBodyMeta = getBodyMeta(sanitizedReqBody);

    appendTrace(traceFile, {
      testName, testTitle,
      method, url,
      requestHeaders: sanitizedReqHeaders,
      requestParams: options?.params,
      requestBody: sanitizedReqBody,
      requestBodyOriginalSize: reqBodyMeta.originalSize,
      requestBodyTruncated: reqBodyMeta.truncated,
      ...extra,
      durationMs: Date.now() - startTime, timestamp: new Date().toISOString(),
    });
  };
  return new Proxy(context, {
    get(target, prop, receiver) {
      if (typeof prop === 'string' && methods.includes(prop.toLowerCase())) {
        return async (url: string, options?: any) => {
          const startTime = Date.now();
          try {
            const response = await target[prop](url, options);
            return wrapResponse(response, testName, testTitle, traceFile, startTime, {
              method: prop.toUpperCase(), url,
              headers: options?.headers, params: options?.params, body: options?.data,
            });
          } catch (error) {
            recordRequest(prop.toUpperCase(), url, options, startTime, {
              status: null, statusText: String(error),
              responseHeaders: {}, responseBody: null,
              error: String(error),
            });
            throw error;
          }
        };
      }
      if (prop === 'fetch') {
        return async (urlOrRequest: string | Request, options?: any) => {
          const url = typeof urlOrRequest === 'string' ? urlOrRequest : urlOrRequest.url;
          const startTime = Date.now();
          try {
            const response = await target.fetch(urlOrRequest, options);
            return wrapResponse(response, testName, testTitle, traceFile, startTime, {
              method: options?.method?.toUpperCase() || 'GET', url,
              headers: options?.headers, params: options?.params, body: options?.data,
            });
          } catch (error) {
            recordRequest(options?.method?.toUpperCase() || 'GET', url, options, startTime, {
              status: null, statusText: String(error),
              responseHeaders: {}, responseBody: null,
              error: String(error),
            });
            throw error;
          }
        };
      }
      return Reflect.get(target, prop, receiver);
    },
  });
}

// ---------------------------------------------------------------------------
// 全局 fetch 拦截：兼容使用原生 fetch 的测试脚本
// ---------------------------------------------------------------------------
let currentTestName = '';
let currentTestTitle = '';

function parseUrlParams(url: string): Record<string, string> | undefined {\n  try {\n    const parsed = new URL(url, 'http://localhost');\n    const params: Record<string, string> = {};\n    parsed.searchParams.forEach((value, key) => {\n      params[key] = value;\n    });\n    return Object.keys(params).length > 0 ? params : undefined;\n  } catch {\n    return undefined;\n  }\n}\n\nconst originalFetch = globalThis.fetch;
console.log('[api-trace-helper] global fetch patch installed, API_TRACE_OUTPUT_FILE=', process.env.API_TRACE_OUTPUT_FILE);
globalThis.fetch = async function fetch(input: RequestInfo | URL, init?: RequestInit) {
  const traceFile = process.env.API_TRACE_OUTPUT_FILE;
  console.log('[api-trace-helper] fetch intercepted, currentTestName=', currentTestName, 'url=', typeof input === 'string' ? input : (input as any).url);
  if (!traceFile || !currentTestName) {
    return originalFetch(input, init);
  }

  const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
  const method = init?.method?.toUpperCase() || 'GET';
  const startTime = Date.now();

  try {
    const response = await originalFetch(input, init);
    const cloned = response.clone();
    let responseBody: any;
    try {
      const contentType = cloned.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        responseBody = await cloned.json();
      } else {
        responseBody = await cloned.text();
      }
    } catch { /* ignore body parse errors */ }

    const sanitizedReqHeaders = sanitizeHeaders(parseHeaders(init?.headers));
    const sanitizedRespHeaders = sanitizeHeaders(Object.fromEntries(response.headers.entries()));
    const sanitizedReqBody = sanitizeBody(init?.body);
    const sanitizedRespBody = sanitizeBody(responseBody);
    const reqBodyMeta = getBodyMeta(sanitizedReqBody);
    const respBodyMeta = getBodyMeta(sanitizedRespBody);

    appendTrace(traceFile, {
      testName: currentTestName,
      testTitle: currentTestTitle,
      method, url,
      requestHeaders: sanitizedReqHeaders,
      requestParams: parseUrlParams(url),
      requestBody: sanitizedReqBody,
      requestBodyOriginalSize: reqBodyMeta.originalSize,
      requestBodyTruncated: reqBodyMeta.truncated,
      status: response.status,
      statusText: response.statusText,
      responseHeaders: sanitizedRespHeaders,
      responseBody: sanitizedRespBody,
      responseBodyOriginalSize: respBodyMeta.originalSize,
      responseBodyTruncated: respBodyMeta.truncated,
      durationMs: Date.now() - startTime,
      timestamp: new Date().toISOString(),
    });

    return response;
  } catch (error) {
    appendTrace(traceFile, {
      testName: currentTestName,
      testTitle: currentTestTitle,
      method, url,
      requestHeaders: sanitizeHeaders(parseHeaders(init?.headers)),
      requestBody: sanitizeBody(init?.body),
      status: null,
      statusText: String(error),
      responseHeaders: {},
      responseBody: null,
      error: String(error),
      durationMs: Date.now() - startTime,
      timestamp: new Date().toISOString(),
    });
    throw error;
  }
};

export const test = baseTest.extend({
  request: async ({ request }, use, testInfo) => {
    const traceFile = process.env.API_TRACE_OUTPUT_FILE;
    if (!traceFile) { await use(request); return; }
    const wrapped = wrapContext(request, testInfo.titlePath.join(' › '), testInfo.title, traceFile);
    await use(wrapped as APIRequestContext);
  },
});

// 记录当前用例标题，供全局 fetch 拦截使用
test.beforeEach(async ({}, testInfo) => {
  currentTestName = testInfo.titlePath.join(' › ');
  currentTestTitle = testInfo.title;
  console.log('[api-trace-helper] beforeEach set currentTestName=', currentTestName);
});

test.afterEach(() => {
  currentTestName = '';
  currentTestTitle = '';
});

export { expect } from '@playwright/test';
export { request, APIRequestContext, APIResponse, Page, BrowserContext, Browser, chromium, firefox, webkit, devices, defineConfig } from '@playwright/test';


'''
    # 兜底字符串中的 \n 是字面量，需要转成真正的换行，否则生成的 .ts 文件
    # 会把代码中的 \n 也当作反斜杠+n，导致 TypeScript 语法错误。
    target.write_text(minimal_helper.replace('\\n', '\n'), encoding="utf-8")
    logger.warning("[APITestExecutor] 使用最小 trace helper: %s", target)
    return target


def _rewrite_script_imports(script_content: str, helper_path: str = "../api-trace-helper") -> str:
    """
    把脚本里对 @playwright/test 的 import/require 替换为本地 api-trace-helper。

    测试脚本实际写在 workspace/tests/ 下，而 helper 在 workspace 根目录，
    因此默认使用相对路径 ../api-trace-helper。
    调用方（如 execution_tools.py）可通过 helper_path 指定其他相对路径。
    """
    import re

    # ES Module: import { test, expect } from '@playwright/test'
    rewritten = re.sub(
        r"(import\s+\{[^}]*\}\s+from\s+['\"])@playwright/test(['\"])",
        rf"\1{helper_path}\2",
        script_content,
    )
    # CommonJS: const { test, expect } = require('@playwright/test')
    rewritten = re.sub(
        r"(require\s*\(\s*['\"])@playwright/test(['\"]\s*\))",
        rf"\1{helper_path}\2",
        rewritten,
    )
    return rewritten


def _parse_api_trace(trace_file: Path) -> List[Dict[str, Any]]:
    """
    解析 api-trace.jsonl 文件，返回 trace 条目列表。
    """
    if not trace_file.exists():
        return []

    entries: List[Dict[str, Any]] = []
    try:
        with trace_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("[APITestExecutor] 跳过非法 trace 行: %s", line[:200])
    except Exception as e:
        logger.error("[APITestExecutor] 解析 trace 文件失败: %s", e)

    return entries


def _get_npx_cmd() -> list[str]:
    """获取平台相关的 npx 命令。"""
    if os.name == "nt":  # Windows
        return ["npx.cmd"]
    return ["npx"]


def _ensure_node_in_path(env: dict[str, str]) -> dict[str, str]:
    """确保 PATH 包含常见的 Node.js 安装目录。"""
    node_paths = [
        r"C:\Program Files\nodejs",
        r"C:\Program Files (x86)\nodejs",
        os.path.expanduser(r"~\AppData\Roaming\npm"),
        "/usr/local/bin",
        "/usr/bin",
    ]
    current_path = env.get("PATH", "")
    paths_to_add = [p for p in node_paths if p not in current_path]
    if paths_to_add:
        env = {**env, "PATH": os.pathsep.join(paths_to_add + [current_path])}
    return env


async def _run_subprocess_with_fallback(
    cmd: list[str],
    cwd: str,
    env: dict[str, str],
    timeout: float = 300,
) -> tuple[str, str, int]:
    """
    执行外部命令，优先使用 asyncio 子进程。

    Windows 上如果当前 EventLoop 是 SelectorEventLoop（不支持子进程），
    则降级到线程池执行同步 subprocess.run。
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        return (
            stdout_bytes.decode("utf-8", errors="replace"),
            stderr_bytes.decode("utf-8", errors="replace"),
            proc.returncode,
        )
    except NotImplementedError:
        logger.info("[APITestExecutor] 当前 EventLoop 不支持 asyncio 子进程，降级到同步 subprocess")
        try:
            result = await run_sync(
                subprocess.run,
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            raise asyncio.TimeoutError


# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW1wNk1BPT06ZWUzYTIzYTg=

class APITestExecutor:
    """
    API 测试执行器

    负责执行 Playwright API 测试并收集结果
    """

    def __init__(self, session: AsyncSession, mongodb=None):
        self.session = session
        self.mongodb = mongodb
        self.api_test_repo = APITestRepository(session)
        self.api_test_run_repo = APITestRunRepository(session)
        self.api_test_result_repo = APITestResultRepository(session)

    async def execute_test(
        self,
        api_test_id: UUID,
        execution_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        执行 API 测试（异步）

        Args:
            api_test_id: API 测试 ID
            execution_config: 执行配置

        Returns:
            str: 测试运行 ID
        """
        # 1. 获取 API 测试
        api_test = await self.api_test_repo.get_by_id(api_test_id)
        if not api_test:
            raise ValueError(f"API 测试不存在: {api_test_id}")

        # 2. 创建测试运行记录
        identifier = await self.api_test_run_repo.get_next_identifier(api_test_id)
        test_run = await self.api_test_run_repo.create(
            project_id=api_test.project_id,
            api_test_id=api_test_id,
            identifier=identifier,
            status="pending",
            execution_config=execution_config or {},
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            skipped_tests=0,
        )

        run_id = test_run.id

        # 3. 立即提交，确保后台任务的新 session 能读取到这条记录
        await self.session.commit()

        # 4. 在后台执行测试（只传递 primitive ID，不传递 ORM 实例）
        asyncio.create_task(
            self._execute_in_background(
                run_id=run_id,
                api_test_id=api_test_id,
                execution_config=execution_config or {},
            )
        )

        return str(run_id)
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW1wNk1BPT06ZWUzYTIzYTg=

    async def _execute_in_background(
        self,
        run_id: UUID,
        api_test_id: UUID,
        execution_config: Dict[str, Any],
    ):
        """
        Execute test in background with a new DB session.

        Workflow:
        1. Update status to RUNNING
        2. Fetch APITest by ID (avoid detached instance issues)
        3. Download test script from MinIO
        4. Prepare execution environment in workspace
        5. Run Playwright test (async subprocess, non-blocking)
        6. Parse test results
        7. Save results to database
        8. Update run status
        """
        async with async_session_factory() as session:
            run_repo = APITestRunRepository(session)
            result_repo = APITestResultRepository(session)
            api_test_repo = APITestRepository(session)

            try:
                # 1. 更新状态为 RUNNING
                run_record = await run_repo.get_by_id(run_id)
                logger.info("[APITestExecutor DEBUG] run_record=%s", run_record)
                if run_record is None:
                    raise ValueError(f"测试运行记录不存在: {run_id}")
                await run_repo.update(run_record, status="running")
                await session.commit()
                logger.info("[APITestExecutor DEBUG] status updated to running")

                # 2. 重新加载 APITest（避免跨 session 的 ORM 实例问题）
                api_test = await api_test_repo.get_by_id(api_test_id)
                logger.info("[APITestExecutor DEBUG] api_test=%s", api_test)
                if api_test is None:
                    raise ValueError(f"API 测试不存在: {api_test_id}")

                # 3. 下载测试脚本
                logger.info("[APITestExecutor DEBUG] downloading script from %s", api_test.script_path)
                script_content = MinIOClient.download_file(api_test.script_path)
                script_content = script_content.decode("utf-8")
                logger.info("[APITestExecutor DEBUG] script content length=%d", len(script_content))

                # 4. 准备执行环境：使用 api_workspace_root 目录（包含 package.json/node_modules）
                workspace_dir = Path(settings.api_workspace_root).resolve()
                tests_dir = workspace_dir / "tests"
                tests_dir.mkdir(parents=True, exist_ok=True)

                # 使用唯一文件名避免冲突
                script_file = tests_dir / f"run_{run_id}_{uuid4().hex[:8]}.spec.ts"
                script_file.write_text(script_content, encoding="utf-8")
                logger.info("[APITestExecutor DEBUG] script written to %s", script_file)

                try:
                    # 5. 执行测试（非阻塞异步子进程）
                    logger.info("[APITestExecutor DEBUG] running playwright test")
                    result = await self._run_playwright_test(
                        run_id=run_id,
                        script_path=script_file,
                        api_test=api_test,
                        execution_config=execution_config,
                    )
                    logger.info("[APITestExecutor DEBUG] playwright result: %s", result)

                    # 6. 解析结果并保存
                    await self._process_test_results(
                        run_repo=run_repo,
                        result_repo=result_repo,
                        run_id=run_id,
                        api_test=api_test,
                        test_result=result,
                    )
                    await session.commit()
                    logger.info("[APITestExecutor DEBUG] results saved")

                    # 7. 保存 HTML 测试报告到 MinIO 并创建附件记录
                    report_path = result.get("report_path")
                    if report_path:
                        try:
                            await self._save_html_report(
                                session=session,
                                run_record=run_record,
                                api_test=api_test,
                                report_path=report_path,
                            )
                            await session.commit()
                        except Exception as report_e:
                            logger.error("[APITestExecutor] 保存测试报告失败: %s", report_e)

                    # 8. 根据 Playwright 实际执行结果更新状态
                    run_record = await run_repo.get_by_id(run_id)
                    if run_record:
                        stdout = result.get("stdout", "")
                        stderr = result.get("stderr", "")
                        if result.get("status") != "passed":
                            await run_repo.update(
                                run_record,
                                status="failed",
                                error_message=result.get("error") or "测试执行失败",
                                stdout=stdout,
                                stderr=stderr,
                            )
                        elif (run_record.total_tests or 0) == 0:
                            # Playwright 返回成功但没有执行任何用例，视为异常
                            await run_repo.update(
                                run_record,
                                status="failed",
                                error_message="Playwright 未执行任何测试用例，请检查脚本或 trace helper",
                                stdout=stdout,
                                stderr=stderr,
                            )
                        else:
                            await run_repo.update(
                                run_record,
                                status="completed",
                                stdout=stdout,
                                stderr=stderr,
                            )
                        await session.commit()
                        logger.info("[APITestExecutor DEBUG] status updated to %s", run_record.status)

                finally:
                    # 清理临时脚本文件
                    if script_file.exists():
                        try:
                            script_file.unlink()
                            logger.info("[APITestExecutor] 已清理临时脚本: %s", script_file)
                        except Exception as e:
                            logger.warning("[APITestExecutor] 清理临时脚本失败: %s", e)

            except Exception as e:
                logger.exception("[APITestExecutor DEBUG] exception in _execute_in_background: %s", e)
                logger.exception("[APITestExecutor] 后台执行失败")
                # 更新为失败状态，尽量保留已产生的 stdout/stderr
                try:
                    run_record = await run_repo.get_by_id(run_id)
                    if run_record:
                        update_kwargs = {
                            "status": "failed",
                            "error_message": str(e),
                        }
                        result = locals().get("result")
                        if result is not None:
                            update_kwargs["stdout"] = result.get("stdout", "")
                            update_kwargs["stderr"] = result.get("stderr", "")
                        await run_repo.update(run_record, **update_kwargs)
                        await session.commit()
                except Exception as inner_e:
                    logger.error("[APITestExecutor] 更新失败状态也失败了: %s", inner_e)

    async def _run_playwright_test(
        self,
        run_id: UUID,
        script_path: Path,
        api_test: APITest,
        execution_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        运行 Playwright 测试（非阻塞异步子进程）

        Args:
            run_id: 测试运行 ID（用于生成独立的报告目录）
            script_path: 测试脚本路径
            api_test: API 测试对象
            execution_config: 执行配置

        Returns:
            dict: 测试结果
        """
        workspace_dir = Path(settings.api_workspace_root).resolve()
        proc: Optional[asyncio.subprocess.Process] = None

        try:
            # 准备环境变量：确保 PATH 包含 Node.js
            env = _ensure_node_in_path({**os.environ})

            # 通过 EnvironmentService 解析环境变量（支持 execution_config + 项目环境 fallback）
            env_service = EnvironmentService(self.session)
            try:
                env_id = execution_config.get("env_id") if execution_config else None
                env_vars = await env_service.get_execution_env_vars(
                    project_identifier=api_test.project_id,
                    execution_config=execution_config,
                    endpoint_id=None,
                    env_id=env_id if env_id else None,
                )
            except BadRequestException as e:
                return {
                    "status": "failed",
                    "error": f"环境配置错误: {e.message}",
                }

            # 注入环境变量
            env.update(env_vars)
            if "API_BASE_URL" in env_vars:
                logger.info("[APITestExecutor] 注入 API_BASE_URL: %s", env_vars["API_BASE_URL"])
            env["CI"] = "1"

            # 注入 trace 脱敏与截断配置（供 api-trace-helper.ts 读取）
            env["API_TEST_SENSITIVE_HEADERS"] = ",".join(settings.api_test_sensitive_headers)
            env["API_TEST_SENSITIVE_BODY_FIELDS"] = ",".join(settings.api_test_sensitive_body_fields)
            env["API_TEST_BODY_TRUNCATE_THRESHOLD"] = str(settings.api_test_body_truncate_threshold)
            env["API_TEST_BODY_PREVIEW_LENGTH"] = str(settings.api_test_body_preview_length)

            # 为每次运行使用独立的 HTML 报告目录，避免并发执行互相覆盖
            report_dir = workspace_dir / f"playwright-report-{run_id}"
            env["PLAYWRIGHT_HTML_OUTPUT_DIR"] = str(report_dir)
            env["PLAYWRIGHT_HTML_OUTPUT_FILE"] = "index.html"

            # 确保 trace helper 存在，并生成独立 trace 文件
            _ensure_trace_helper(workspace_dir)
            trace_file = workspace_dir / f"api-trace-{run_id}.jsonl"
            env["API_TRACE_OUTPUT_FILE"] = str(trace_file)

            # 把脚本中对 @playwright/test 的导入替换为本地 helper，以捕获真实请求/响应
            try:
                original_script = script_path.read_text(encoding="utf-8")
                rewritten_script = _rewrite_script_imports(original_script)
                if rewritten_script != original_script:
                    script_path.write_text(rewritten_script, encoding="utf-8")
                    logger.info("[APITestExecutor] 已重写脚本导入以启用 trace: %s", script_path)
                else:
                    logger.info("[APITestExecutor] 脚本已使用 trace helper，无需重写: %s", script_path)
            except Exception as e:
                logger.warning("[APITestExecutor] 重写脚本导入失败，继续执行原脚本: %s", e)

            npx_cmd = _get_npx_cmd()

            # 检查 npx 是否可用
            npx_stdout, npx_stderr, npx_rc = await _run_subprocess_with_fallback(
                [*npx_cmd, "--version"],
                cwd=str(workspace_dir),
                env=env,
                timeout=10,
            )
            if npx_rc != 0:
                raise Exception(f"npx 不可用: {npx_stderr}")

            # 计算相对路径
            relative_path = script_path.relative_to(workspace_dir)

            # 运行 Playwright 测试：同时输出 list reporter 到 stdout 并生成 HTML 报告
            stdout, stderr, returncode = await _run_subprocess_with_fallback(
                [*npx_cmd, "playwright", "test", relative_path.as_posix(), "--reporter=list,html"],
                cwd=str(workspace_dir),
                env=env,
                timeout=execution_config.get("timeout", 300),
            )

            report_path = str(report_dir) if report_dir.exists() else None

            return {
                "status": "passed" if returncode == 0 else "failed",
                "error": stderr if returncode != 0 else None,
                "stdout": stdout,
                "stderr": stderr,
                "returncode": returncode,
                "report_path": report_path,
                "trace_file": str(trace_file),
            }
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW1wNk1BPT06ZWUzYTIzYTg=

        except asyncio.TimeoutError:
            logger.warning("[APITestExecutor] Playwright 执行超时，正在终止...")
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except Exception:
                    pass
            return {
                "status": "failed",
                "error": f"测试执行超时（超过 {execution_config.get('timeout', 300)} 秒）",
                "stdout": "",
                "stderr": "",
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": f"测试执行失败: {str(e)}",
                "stdout": "",
                "stderr": "",
            }

    async def _process_test_results(
        self,
        run_id: UUID,
        api_test: APITest,
        test_result: Dict[str, Any],
        *,
        run_repo: Optional[APITestRunRepository] = None,
        result_repo: Optional[APITestResultRepository] = None,
    ):
        """
        处理测试结果

        Args:
            run_id: 测试运行 ID
            api_test: API 测试
            test_result: Playwright 测试结果（包含 stdout、trace_file）
        """
        try:
            stdout = test_result.get("stdout", "")
            parsed = self._parse_playwright_list_output(stdout)

            # 解析真实请求/响应 trace
            trace_file = test_result.get("trace_file")
            trace_entries = _parse_api_trace(Path(trace_file)) if trace_file else []
            logger.info("[APITestExecutor] trace_file=%s, entries=%d, first_entry=%s",
                        trace_file, len(trace_entries),
                        trace_entries[0] if trace_entries else None)

            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            skipped_tests = 0

            for item in parsed:
                total_tests += 1
                if item["status"] == "passed":
                    passed_tests += 1
                elif item["status"] == "failed":
                    failed_tests += 1
                elif item["status"] == "skipped":
                    skipped_tests += 1

                status = TestResultStatus.PASSED
                if item["status"] == "failed":
                    status = TestResultStatus.FAILED
                elif item["status"] == "skipped":
                    status = TestResultStatus.SKIPPED

                # 匹配当前用例的 trace 条目
                matched_traces = self._match_trace_entries(item["title"], trace_entries)
                logger.info("[APITestExecutor] test=%s matched_traces=%d", item["title"], len(matched_traces))

                await self._save_test_result(
                    run_id=run_id,
                    api_test=api_test,
                    test_name=item["title"],
                    status=status,
                    trace_entries=matched_traces,
                    result_repo=result_repo,
                )

            # 更新运行统计
            _run_repo = run_repo or self.api_test_run_repo
            run_record = await _run_repo.get_by_id(run_id)
            if run_record:
                await _run_repo.update(
                    run_record,
                    total_tests=total_tests,
                    passed_tests=passed_tests,
                    failed_tests=failed_tests,
                    skipped_tests=skipped_tests,
                )

        except Exception as e:
            logger.error("[APITestExecutor] 处理测试结果失败: %s", e)

    @staticmethod
    def _match_trace_entries(
        test_title: str,
        trace_entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        根据用例标题匹配 trace 条目。

        Playwright list reporter 解析出的 title 是完整路径（包含 describe 与叶子标题），
        而 trace 里 testTitle 是叶子标题，testName 是包含文件名的完整路径。
        因此需要多策略匹配：
        - 叶子标题相等
        - 完整路径相等
        - 完整路径以 list reporter 解析出的 title 结尾
        - list reporter 解析出的 title 以叶子标题结尾
        """
        matched: List[Dict[str, Any]] = []
        for entry in trace_entries:
            entry_title = entry.get("testTitle") or ""
            entry_name = entry.get("testName") or ""
            if entry_title == test_title:
                matched.append(entry)
            elif entry_name == test_title:
                matched.append(entry)
            elif entry_name.endswith(test_title):
                matched.append(entry)
            elif test_title.endswith(entry_title) and entry_title:
                matched.append(entry)
            elif entry_name.endswith(f" › {test_title}"):
                matched.append(entry)
        return matched

    @staticmethod
    def _parse_playwright_list_output(stdout: str) -> List[Dict[str, str]]:
        """
        从 Playwright list reporter 输出中解析每个测试用例的状态和标题。

        示例行：
          ✓  1 [chromium] > example.spec.ts:3:1 > GET /api/users (125ms)
          ✗  2 [chromium] > example.spec.ts:4:1 > POST /api/users (234ms)
          -  3 [chromium] > example.spec.ts:5:1 > PUT /api/users/1
        """
        import re

        results: List[Dict[str, str]] = []
        # 匹配行首状态符号、序号、可选项目信息、文件名位置、标题和可选耗时
        # Playwright 在不同终端/系统下可能输出 ok/x 或 ✓/✗，
        # 且分隔符可能是 Unicode '›' 或 ASCII '>'，这里同时兼容两者。
        pattern = re.compile(
            r"^\s*(ok|x|[✓✗\-+×])\s+\d+\s+(?:\[[^\]]+\]\s+)?[›>]\s+[^›>]+\s+[›>]\s+(.+?)(?:\s+\([\d.]+\s*(?:ms|s|m|h)\))?\s*$",
            re.MULTILINE,
        )
        status_map = {
            "ok": "passed",
            "✓": "passed",
            "x": "failed",
            "✗": "failed",
            "×": "failed",
            "-": "skipped",
            "+": "skipped",
        }

        for match in pattern.finditer(stdout):
            symbol = match.group(1)
            title = match.group(2).strip()
            # trace helper 中使用 '›' 作为 titlePath 分隔符，统一格式便于后续匹配
            title = title.replace(">", "›")
            results.append({
                "status": status_map.get(symbol, "failed"),
                "title": title,
            })

        return results

    async def _save_test_result(
        self,
        run_id: UUID,
        api_test: APITest,
        test_name: str,
        status: TestResultStatus,
        trace_entries: List[Dict[str, Any]],
        *,
        result_repo: Optional[APITestResultRepository] = None,
    ):
        """
        保存单个测试结果

        Args:
            run_id: 测试运行 ID
            api_test: API 测试
            test_name: 测试名称
            status: 测试状态
            trace_entries: 匹配到的真实请求/响应 trace 条目
            result_repo: 可选的结果仓储（后台任务使用新 session）
        """
        try:
            # 提取端点和 HTTP 方法（从测试名称中解析）
            endpoint, method = self._parse_endpoint_from_test_name(test_name)

            # 从 trace 中聚合真实请求/响应/断言
            request_data, response_data, assertion_results, duration_ms = self._build_trace_summary(
                trace_entries, status
            )

            # 处理大响应体：完整 body 上传 MinIO，DB 只存截断预览
            if response_data and response_data.get("body_meta", {}).get("truncated"):
                try:
                    full_body = response_data["body"]
                    storage_path = f"api-test-bodies/{run_id}/{uuid4().hex}/response_body.json"
                    body_bytes = json.dumps(full_body).encode("utf-8")
                    MinIOClient.upload_bytes(storage_path, body_bytes, "application/json")
                    response_data["body_meta"]["storage_path"] = storage_path
                    logger.info("[APITestExecutor] 大响应体已上传 MinIO: %s", storage_path)
                except Exception as e:
                    logger.warning("[APITestExecutor] 上传响应体到 MinIO 失败: %s", e)
                    response_data["body_meta"]["storage_error"] = str(e)

            # 截断落库的 body（避免 JSONB 行过大）
            request_data = self._truncate_body_in_data(request_data)
            response_data = self._truncate_body_in_data(response_data)

            # 创建测试结果记录
            _result_repo = result_repo or self.api_test_result_repo
            result = await _result_repo.create(
                test_run_id=run_id,
                api_test_id=api_test.id,
                scenario_name=test_name,
                endpoint=endpoint,
                method=method,
                status=status,
                request_summary=request_data or {
                    "url": api_test.test_config.get("base_url", ""),
                    "method": method,
                },
                response_summary=response_data or {
                    "status_code": 200 if status == TestResultStatus.PASSED else 500,
                },
                request_data=request_data,
                response_data=response_data,
                assertion_results=assertion_results,
                error_message=None if status == TestResultStatus.PASSED else "测试失败",
                duration_ms=duration_ms,
                retry_count=0,
            )

            # 保存 MongoDB 详细日志（如果可用）
            detail_log_id = None
            if self.mongodb:
                detail_log_id = await self.save_detail_log(
                    test_result_id=result.id,
                    test_run_id=run_id,
                    api_test_id=api_test.id,
                    scenario_name=test_name,
                    endpoint=endpoint,
                    method=method,
                    request=request_data or {},
                    response=response_data or {},
                    status=status.value,
                    duration_ms=duration_ms or 0,
                    assertions=assertion_results or [],
                )
                if detail_log_id:
                    result.detail_log_id = detail_log_id

        except Exception as e:
            logger.error("[APITestExecutor] 保存测试结果失败: %s", e)

    @staticmethod
    def _build_trace_summary(
        trace_entries: List[Dict[str, Any]],
        status: TestResultStatus,
    ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[int]]:
        """
        从 trace 条目中构建请求/响应/断言摘要。

        策略：
        - 如果一个用例有多个 trace 条目，优先使用带有 responseBody 的条目；
          若都没有 body，则使用最后一条。
        - duration_ms 取所有条目 duration 的最大值（近似整个用例耗时）。
        - 断言结果至少包含一个对 status 的隐式断言。
        """
        if not trace_entries:
            return None, None, None, None

        # 优先选择有 responseBody 的条目
        chosen = None
        for entry in trace_entries:
            if entry.get("responseBody") is not None:
                chosen = entry
                break
        if chosen is None:
            chosen = trace_entries[-1]

        request_data = {
            "method": chosen.get("method", "GET"),
            "url": chosen.get("url", ""),
            "headers": chosen.get("requestHeaders") or {},
            "params": chosen.get("requestParams") or {},
            "body": chosen.get("requestBody"),
            "body_meta": {
                "original_size": chosen.get("requestBodyOriginalSize", 0),
                "truncated": chosen.get("requestBodyTruncated", False),
            },
        }

        response_status = chosen.get("status")
        response_data = {
            "status": response_status,
            "statusText": chosen.get("statusText", ""),
            "headers": chosen.get("responseHeaders") or {},
            "body": chosen.get("responseBody"),
            "body_meta": {
                "original_size": chosen.get("responseBodyOriginalSize", 0),
                "truncated": chosen.get("responseBodyTruncated", False),
            },
            "timing": chosen.get("durationMs"),
        }

        # 生成断言结果：status 断言
        assertions: List[Dict[str, Any]] = []
        if response_status is not None and isinstance(response_status, int):
            passed = 200 <= response_status < 300
            assertions.append({
                "assertion": {"type": "status", "expected": "2xx"},
                "passed": passed,
                "actual": response_status,
                "expected": "2xx",
                "message": f"HTTP 状态码断言{'通过' if passed else '失败'}: 预期 2xx，实际 {response_status}",
            })

        # 如果 Playwright 测试本身失败，追加一个通用失败断言
        if status == TestResultStatus.FAILED:
            assertions.append({
                "assertion": {"type": "test"},
                "passed": False,
                "actual": status.value,
                "expected": TestResultStatus.PASSED.value,
                "message": "Playwright 测试执行失败",
            })

        # 计算总耗时：取各请求耗时的最大值作为用例耗时近似
        duration_ms = max(
            (entry.get("durationMs") or 0 for entry in trace_entries),
            default=0,
        ) or None

        return request_data, response_data, assertions, duration_ms

    @staticmethod
    def _truncate_body_in_data(
        data: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        对请求/响应数据中的 body 进行截断，避免 JSONB 行过大。

        - 如果 body 未超过阈值，保持原样
        - 如果 body 超过阈值，保留前 preview_length 字符，并添加截断标记
        """
        if not data:
            return data

        body = data.get("body")
        body_meta = data.get("body_meta") or {}
        if not body_meta.get("truncated") or body is None:
            return data

        preview_length = settings.api_test_body_preview_length
        try:
            serialized = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
            if len(serialized) > preview_length:
                truncated = serialized[:preview_length] + "\n...[truncated]"
                data["body"] = truncated
                body_meta["preview_length"] = preview_length
        except Exception as e:
            logger.warning("[APITestExecutor] 截断 body 失败: %s", e)

        return data

    @staticmethod
    def _parse_endpoint_from_test_name(test_name: str) -> tuple[str, str]:
        """
        Parse endpoint and HTTP method from test name.

        Supports both simple titles like "GET /api/v1/users" and full Playwright
        title paths like "GET /api/v1/users › should return list".

        Input:  "GET /api/v1/users"
        Output: ("/api/v1/users", "GET")

        Input:  "GET /api/v1/users › should return list"
        Output: ("/api/v1/users", "GET")
        """
        import re

        # Try to match pattern: "METHOD /path" or "METHOD path" at the start.
        # The path stops at the first whitespace to avoid swallowing describe
        # text like "POST /api/users - create user".
        match = re.match(
            r'^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(/[^\s]+)',
            test_name,
            re.IGNORECASE,
        )
        if match:
            method = match.group(1).upper()
            endpoint = match.group(2)
            return endpoint, method

        # Default to GET if no explicit method found
        return test_name, "GET"

    async def _save_html_report(
        self,
        session: AsyncSession,
        run_record: APITestRun,
        api_test: APITest,
        report_path: str,
    ) -> Optional[str]:
        """
        将 Playwright HTML 报告打包上传到 MinIO，并创建附件记录。

        Args:
            session: 数据库会话
            run_record: 测试运行记录
            api_test: API 测试对象
            report_path: 本地 HTML 报告目录路径

        Returns:
            str: MinIO 对象路径
        """
        report_dir = Path(report_path)
        if not report_dir.exists() or not report_dir.is_dir():
            logger.warning("[APITestExecutor] HTML 报告目录不存在: %s", report_path)
            return None

        # 1. 查找关联的 endpoint
        from app.models.api_endpoint import APIEndpoint
        from sqlalchemy import select as sa_select

        endpoint_id: Optional[UUID] = None
        endpoint_display_name = api_test.name or f"API Test {api_test.identifier}"
        try:
            stmt = sa_select(APIEndpoint).where(
                APIEndpoint.api_test_ids.contains([str(api_test.id)])
            )
            ep_result = await session.execute(stmt)
            endpoint = ep_result.scalar_one_or_none()
            if endpoint:
                endpoint_id = endpoint.id
                endpoint_display_name = endpoint.display_name or endpoint_display_name
        except Exception as e:
            logger.warning("[APITestExecutor] 查找关联 endpoint 失败: %s", e)

        # 2. 打包报告为 ZIP
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_filename = f"api_test_report_{timestamp}.zip"
        workspace_dir = Path(settings.api_workspace_root).resolve()
        zip_path = workspace_dir / zip_filename

        def _create_zip() -> None:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in report_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(report_dir)
                        zipf.write(file_path, arcname)

        await run_sync(_create_zip)

        # 3. 上传到 MinIO
        zip_bytes = await run_sync(lambda p: open(p, 'rb').read(), zip_path)
        object_name = f"api-tests/{api_test.project_id}/runs/{run_record.id}/test-report-{timestamp}.zip"
        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=zip_bytes,
            content_type="application/zip",
        )
        logger.info("[APITestExecutor] 测试报告已上传: %s", object_name)

        # 4. 更新测试运行记录
        run_record.report_path = object_name

        # 5. 创建附件记录（只有找到 endpoint 时才创建，否则前端无法展示）
        if endpoint_id:
            description = f"API 测试报告 - {endpoint_display_name}\n"
            description += f"运行标识: {run_record.identifier}\n"
            description += f"通过: {run_record.passed_tests} | 失败: {run_record.failed_tests} | 跳过: {run_record.skipped_tests}"

            attachment = Attachment(
                entity_type=AttachmentEntityType.API_TEST_REPORT,
                entity_id=endpoint_id,
                project_id=api_test.project_id,
                file_name=zip_filename,
                file_size=len(zip_bytes),
                content_type="application/zip",
                object_name=object_name,
                description=description,
                created_by="api-agent",
            )
            session.add(attachment)
            logger.info("[APITestExecutor] 测试报告附件已创建，endpoint_id=%s", endpoint_id)

        # 6. 清理临时 ZIP 文件和报告目录
        try:
            await run_sync(zip_path.unlink)
        except Exception as e:
            logger.warning("[APITestExecutor] 清理临时 ZIP 失败: %s", e)
        try:
            await run_sync(shutil.rmtree, report_path)
        except Exception as e:
            logger.warning("[APITestExecutor] 清理报告目录失败: %s", e)

        return object_name

    async def _generate_allure_report(
        self,
        run_id: UUID,
        work_dir: Path,
    ) -> Optional[str]:
        """
        生成 Allure 测试报告

        Args:
            run_id: 测试运行 ID
            work_dir: 工作目录（包含 allure-results）

        Returns:
            str: 报告目录路径 (MinIO)
        """
        try:
            allure_results_dir = work_dir / "allure-results"

            # 检查 Allure 结果是否存在
            if not allure_results_dir.exists():
                logger.info("[APITestExecutor] 未找到 Allure 测试结果")
                return None

            # 生成 HTML 报告到临时目录
            allure_report_dir = work_dir / "allure-report"
            proc = await asyncio.create_subprocess_exec(
                "allure", "generate", str(allure_results_dir), "-o", str(allure_report_dir), "--clean",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)

            # 将报告打包为 ZIP 并上传到 MinIO
            import zipfile
            zip_path = work_dir / "allure-report.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in allure_report_dir.rglob('*'):
                    if file.is_file():
                        arcname = file.relative_to(allure_report_dir)
                        zipf.write(file, arcname)

            # 上传到 MinIO
            report_path = f"api-test-reports/{run_id}/allure-report.zip"
            with open(zip_path, 'rb') as f:
                MinIOClient.upload_bytes(
                    object_name=report_path,
                    data=f.read(),
                    content_type="application/zip",
                )
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW1wNk1BPT06ZWUzYTIzYTg=

            return report_path

        except Exception as e:
            logger.error("[APITestExecutor] 生成 Allure 报告失败: %s", e)
            return None

    async def save_detail_log(
        self,
        test_result_id: UUID,
        test_run_id: UUID,
        api_test_id: UUID,
        scenario_name: str,
        endpoint: str,
        method: str,
        request: Dict[str, Any],
        response: Dict[str, Any],
        status: str,
        duration_ms: int,
        assertions: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        保存详细日志到 MongoDB

        Args:
            test_result_id: 测试结果 ID
            test_run_id: 测试运行 ID
            api_test_id: API 测试 ID
            scenario_name: 场景名称
            endpoint: 端点
            method: HTTP 方法
            request: 请求数据
            response: 响应数据
            status: 状态
            duration_ms: 执行时长
            assertions: 断言结果列表

        Returns:
            str: MongoDB 日志 ID
        """
        if not self.mongodb:
            return None

        try:
            log = APITestDetailLog(
                log_id=str(uuid4()),
                test_result_id=test_result_id,
                test_run_id=test_run_id,
                api_test_id=api_test_id,
                scenario_name=scenario_name,
                endpoint=endpoint,
                method=method,
                request=request,
                response=response,
                assertions=assertions or [],
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                status=status,
                error=None if status == "passed" else {"message": "测试失败"},
            )

            # 保存到 MongoDB
            collection = self.mongodb.db.get_collection("api_test_logs")
            result = await collection.insert_one(log.to_document())

            return str(result.inserted_id)

        except Exception as e:
            logger.error("[APITestExecutor] 保存详细日志失败: %s", e)
            return None

    async def generate_test_report(
        self,
        run_id: UUID,
    ) -> Optional[str]:
        """
        生成测试报告（已废弃，使用 _generate_allure_report 代替）

        Args:
            run_id: 测试运行 ID

        Returns:
            str: 报告文件路径 (MinIO)
        """
        # 此方法已集成到 _execute_in_background 中
        # 保留是为了向后兼容
        test_run = await self.api_test_run_repo.get_by_id(run_id)
        if test_run and test_run.report_path:
            return test_run.report_path
        return None
