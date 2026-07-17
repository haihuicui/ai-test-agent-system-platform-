import { test, expect } from '@playwright/test';
import { validateSchema } from './_helpers/schema';

// ============================================================
// POST /xmetrix-data/customer - 新增客户
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

const API_PATH = '/xmetrix-data/customer';

const authHeaders: Record<string, string> = {
  'Authorization': `Bearer ${AUTH_TOKEN}`,
  'Content-Type': 'application/json'
};

// 响应 Schema（来自 OpenAPI responses 200）
const SCHEMA = {
  type: 'object',
  required: ['code', 'message'],
  properties: {
    code: { type: 'string' },
    message: { type: 'string' }
  }
} as const;

// 动态测试数据生成
function generateCustomerName(prefix: string): string {
  return `${prefix}-${Date.now()}`;
}

test.describe('POST /xmetrix-data/customer - 新增客户', () => {

  test('正向 - 使用完整必填字段成功创建客户', async () => {
    // Arrange
    const payload = {
      name: generateCustomerName('测试客户'),
      description: '由自动化测试创建的客户',
      samplingSiteIds: ['site-001']
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
    expect(typeof body.code).toBe('string');
    expect(typeof body.message).toBe('string');
    expect(body.message.length).toBeGreaterThan(0);
  });

  test('正向 - 使用多个采样点ID成功创建客户', async () => {
    // Arrange
    const payload = {
      name: generateCustomerName('测试客户-多采样点'),
      description: '包含多个采样点的客户',
      samplingSiteIds: ['site-001', 'site-002', 'site-003']
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
    expect(typeof body.code).toBe('string');
    expect(typeof body.message).toBe('string');
    expect(body.message.length).toBeGreaterThan(0);
  });

  test('正向 - 含中文和特殊字符的客户名称成功创建客户', async () => {
    // Arrange
    const payload = {
      name: `ABC测试客户-${Date.now()}（总部）`,
      description: '名称含特殊字符的客户',
      samplingSiteIds: ['site-001']
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
    expect(typeof body.code).toBe('string');
    expect(typeof body.message).toBe('string');
    expect(body.message.length).toBeGreaterThan(0);
  });

});
