import { test, expect } from '@playwright/test';
import { validateSchema } from './_helpers/schema';

// ============================================================
// 配置：API_BASE_URL / AUTH_TOKEN 由执行环境注入，禁止硬编码
// ============================================================
const BASE_URL = (process.env.API_BASE_URL || '').trim();
if (!BASE_URL) {
  throw new Error(
    'API_BASE_URL is not set. ' +
    'Configure it in Project Settings > Environments or pass execution_config.base_url.'
  );
}

const AUTH_TOKEN = process.env.AUTH_TOKEN;
if (!AUTH_TOKEN) {
  throw new Error(
    'AUTH_TOKEN is not set. ' +
    'Configure it in Project Settings > Environments or pass execution_config.env.AUTH_TOKEN.'
  );
}

// ============================================================
// 请求头
// ============================================================
const authHeaders: Record<string, string> = {
  'Authorization': `Bearer ${AUTH_TOKEN}`,
  'Content-Type': 'application/json'
};

// ============================================================
// 响应 Schema（来自 OpenAPI 响应定义）
// 基于 trace 分析：成功时 code="2000", 参数错误时 code="4009"
// ============================================================
const SCHEMA = {
  type: 'object',
  required: ['code', 'message'],
  properties: {
    code: { type: 'string' },
    message: { type: 'string' }
  }
} as const;

const API_PATH = '/xmetrix-data/customer';

// ============================================================
// 测试套件
// ============================================================
test.describe('POST /xmetrix-data/customer - 新增客户', () => {

  test('正向 - 有效请求新增客户', async () => {
    // Arrange
    const payload = {
      name: `测试客户-${Date.now()}`,
      description: '接口自动化测试创建的客户',
      samplingSiteIds: [] // 空数组已验证可通过，避免使用臆测的非法 site ID
    };

    // Act
    const url = `${BASE_URL.replace(/\/$/, '')}${API_PATH}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify(payload)
    });

    // Assert - 协议层
    expect(response.status).toBe(200);

    // Assert - 结构/业务层
    const body = await response.json();
    expect(validateSchema(body, SCHEMA).valid).toBe(true);
    // 成功码为 "2000"（基于 trace 分析确认）
    expect(body.code).toBe('2000');
    expect(typeof body.message).toBe('string');
    expect(body.message).toBe('success');
  });

  test('异常 - 缺少必填字段 name', async () => {
    // Arrange - 故意省略必填字段 name
    const payload = {
      description: '缺少name字段',
      samplingSiteIds: ['site-001']
    };

    // Act
    const url = `${BASE_URL.replace(/\/$/, '')}${API_PATH}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify(payload)
    });

    // Assert - 该 API 始终返回 200，通过业务 code 区分成功/失败
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(validateSchema(body, SCHEMA).valid).toBe(true);
    // 缺少必填字段应返回业务错误码 "4009"
    expect(body.code).toBe('4009');
    expect(typeof body.message).toBe('string');
    expect(body.message).toBe('参数输入不规范');
  });

  test('边界 - samplingSiteIds 空数组', async () => {
    // Arrange
    const payload = {
      name: `边界测试-${Date.now()}`,
      description: '测试空数组边界',
      samplingSiteIds: []
    };

    // Act
    const url = `${BASE_URL.replace(/\/$/, '')}${API_PATH}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify(payload)
    });

    // Assert - 空数组应被接受为合法输入
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(validateSchema(body, SCHEMA).valid).toBe(true);
    expect(body.code).toBe('2000');
    expect(typeof body.message).toBe('string');
    expect(body.message).toBe('success');
  });
});
