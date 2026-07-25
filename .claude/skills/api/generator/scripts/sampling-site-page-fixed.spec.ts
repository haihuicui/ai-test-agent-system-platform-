import { test, expect } from '@playwright/test';
import { validateSchema } from './_helpers/schema';

// ============================================================
// API: POST /xmetrix-data/sampling-site/page
// 描述: 分页获取采样点列表
// 标签: xmetrix-data/采样点
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

const API_PATH = '/xmetrix-data/sampling-site/page';

const authHeaders: Record<string, string> = {
  'Authorization': `Bearer ${AUTH_TOKEN}`,
  'Content-Type': 'application/json'
};

// 响应体 Schema（基于实际 API 响应调整：current/size/pages/total 返回字符串）
const SCHEMA_200 = {
  type: 'object',
  required: ['code', 'message', 'data', 'current', 'size', 'pages', 'total'],
  properties: {
    code: { type: 'string' },
    message: { type: 'string' },
    data: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'name', 'address', 'createdTime'],
        properties: {
          id: { type: 'string' },
          name: { type: 'string' },
          address: { type: 'string' },
          createdTime: { type: 'string' },
          description: { type: 'string' }
        }
      }
    },
    current: { type: 'string' },
    size: { type: 'string' },
    pages: { type: 'string' },
    total: { type: 'string' }
  }
} as const;

test.describe('POST /xmetrix-data/sampling-site/page - 分页获取采样点列表', () => {

  test('[P0] 正常场景 - 有效分页请求采样点列表', async () => {
    // Arrange - 构造有效分页请求
    const payload = {
      current: 1,
      size: 10,
      orders: [
        {
          field: 'createdTime',
          direction: 'descend',
          dataType: 'cn',
          alias: ''
        }
      ],
      operator: 'and',
      params: [],
      filters: []
    };

    const url = `${BASE_URL.replace(/\/$/, '')}${API_PATH}`;

    // Act - 发送请求
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify(payload)
    });

    // Assert - 协议层: 状态码 200
    expect(response.status).toBe(200);

    const body = await response.json();

    // Assert - 契约校验: 响应体符合 schema
    const validation = validateSchema(body, SCHEMA_200);
    expect(validation.valid).toBe(true);

    // Assert - 业务层: 业务成功码
    expect(body.code).toBe('2000');
    expect(body.message).toBe('success');

    // Assert - 分页结构: data 为数组
    expect(Array.isArray(body.data)).toBe(true);

    // Assert - 分页字段存在性（实际返回字符串类型）
    expect(body).toHaveProperty('current');
    expect(body).toHaveProperty('size');
    expect(body).toHaveProperty('pages');
    expect(body).toHaveProperty('total');
  });

  test('[P1] 异常场景 - 缺少必填字段 current', async () => {
    // Arrange - 构造缺少 current 的请求体
    const payload = {
      // 省略 current
      size: 10,
      orders: [
        {
          field: 'createdTime',
          direction: 'descend',
          dataType: 'cn',
          alias: ''
        }
      ],
      operator: 'and',
      params: [],
      filters: []
    };

    const url = `${BASE_URL.replace(/\/$/, '')}${API_PATH}`;

    // Act - 发送请求
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify(payload)
    });

    const body = await response.json();

    // Assert - 缺少必填字段，预期返回 400 或业务错误码
    // 根据 schema 定义 current 为必填字段，若 API 返回 200 则属 API 缺陷
    if (response.status === 200) {
      // HTTP 200 但业务拒绝 — 验业务码
      expect(body).toHaveProperty('code');
      expect(body.code).not.toBe('2000');
    } else {
      // HTTP 4xx — 验状态码
      expect(response.status).toBe(400);
      expect(body).toHaveProperty('message');
    }
  });

});
