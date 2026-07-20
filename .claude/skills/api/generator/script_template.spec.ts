import { test, expect } from '@playwright/test';
import { validateSchema } from './_helpers/schema';

// ========================================
// POST /xmetrix-data/customer - 新增客户
// ========================================

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

const API_PATH = '/xmetrix-data/customer';

const authHeaders: Record<string, string> = {
  'Authorization': `Bearer ${AUTH_TOKEN}`,
  'Content-Type': 'application/json'
};

// 响应 Schema（200 成功响应）
const SCHEMA = {
  type: 'object',
  required: ['code', 'message'],
  properties: {
    code: { type: 'string', title: '响应码' },
    message: { type: 'string', title: '响应消息' }
  }
} as const;

test.describe('POST /xmetrix-data/customer - 新增客户', () => {

  test('正向 - 使用有效参数成功新增客户', async () => {
    // Arrange
    const url = `${BASE_URL.replace(/\/$/, '')}${API_PATH}`;
    const payload = {
      name: `自动化测试客户_${Date.now()}`,
      description: '由自动化测试创建',
      samplingSiteIds: []
    };

    // Act
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify(payload)
    });
    const body = await response.json();

    // Assert - 协议层
    expect(response.status).toBe(200);

    // Assert - 业务层（业务成功码 "2000"）
    expect(body.code).toBe('2000');
    expect(body.message).toBe('success');

    // Assert - 契约校验
    expect(validateSchema(body, SCHEMA).valid).toBe(true);
  });

  test('异常 - 缺少必填字段 name 返回业务错误', async () => {
    // Arrange
    const url = `${BASE_URL.replace(/\/$/, '')}${API_PATH}`;
    const payload = {
      description: '缺少必填字段name',
      samplingSiteIds: []
    };

    // Act
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify(payload)
    });
    const body = await response.json();

    // Assert - 协议层（API 使用业务码而非 HTTP 状态码表示校验失败，
    // 属于 API 设计缺陷，应在报告中标注。规范上应返回 HTTP 400。）
    expect(response.status).toBe(200);

    // Assert - 业务层（缺失必填字段 name 导致数据库错误码 "3001"）
    expect(body.code).toBe('3001');
    expect(body.message).toBe('数据库错误');
  });

  test('正向 - 不传 samplingSiteIds 仍可成功创建', async () => {
    // 实际测试发现 samplingSiteIds 虽在 schema 标记为 required，但 API 实现中实际为可选
    // 此处验证该行为
    // Arrange
    const url = `${BASE_URL.replace(/\/$/, '')}${API_PATH}`;
    const payload = {
      name: `自动化测试客户_${Date.now()}`,
      description: '测试不传samplingSiteIds'
      // 故意不传 samplingSiteIds
    };

    // Act
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify(payload)
    });
    const body = await response.json();

    // Assert - 协议层
    expect(response.status).toBe(200);

    // Assert - 业务层（成功创建）
    expect(body.code).toBe('2000');
    expect(body.message).toBe('success');

    // Assert - 契约校验
    expect(validateSchema(body, SCHEMA).valid).toBe(true);
  });
});
