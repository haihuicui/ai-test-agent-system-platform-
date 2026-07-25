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

    // Assert - 分页字段存在性
    expect(body).toHaveProperty('current');
    expect(body).toHaveProperty('size');
    expect(body).toHaveProperty('pages');
    expect(body).toHaveProperty('total');
  });

  test('[P1] 安全测试 - 缺少认证 Token', async () => {
    // Arrange - 构造有效请求体但不带认证头
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

    // Act - 发送请求（无 Authorization 头）
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    // Assert - 缺少认证应返回 401 Unauthorized
    // 若返回 200 则属安全缺陷
    if (response.status === 200) {
      const body = await response.json();
      expect(body).toHaveProperty('code');
      expect(body.code).not.toBe('2000');
    } else {
      expect([401, 403]).toContain(response.status);
    }
  });

});
