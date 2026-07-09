import { test, expect } from '@playwright/test';

// ============================================================
// 场景测试：采样点完整管理流程
// 描述：测试采样点的完整生命周期
//   步骤1: 新增采样点 → 通过列表查询提取 siteId
//   步骤2: 分页查询采样点列表 → 验证新采样点存在
//   步骤3: 编辑采样点 → 验证编辑成功
//   步骤4: 再次查询采样点列表 → 验证编辑已生效
// ============================================================

const BASE_URL = (process.env.API_BASE_URL || '').trim();
if (!BASE_URL) {
  throw new Error(
    'API_BASE_URL is not set. ' +
    'Configure it in Project Settings > Environments or pass execution_config.base_url.'
  );
}

/**
 * 根据环境变量构建认证请求头。
 * 该函数被内联到脚本中，因为脚本会在临时目录执行，无法依赖外部模块。
 */
function buildAuthHeaders(): Record<string, string> {
  const authType = process.env.AUTH_TYPE || 'none';
  const secret = process.env.AUTH_SECRET || process.env.AUTH_TOKEN || '';
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  if (authType === 'bearer' || authType === 'oauth2') {
    if (secret) {
      headers['Authorization'] = `Bearer ${secret}`;
    }
  } else if (authType === 'api_key') {
    let apiKeyHeader = 'X-API-Key';
    try {
      const authConfig = JSON.parse(process.env.AUTH_CONFIG_JSON || '{}');
      if (authConfig.api_key_header) {
        apiKeyHeader = authConfig.api_key_header;
      }
    } catch {
      // ignore
    }
    if (secret) {
      headers[apiKeyHeader] = secret;
    }
  } else if (authType === 'dynamic_bearer') {
    const token = process.env.AUTH_TOKEN || secret;
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  return headers;
}

/**
 * 安全拼接 BASE_URL 与 API path，避免 new URL 丢失 /api 前缀。
 */
function buildUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, '')}${path}`;
}

const authHeaders = buildAuthHeaders();

// 测试数据
const TEST_SITE = {
  name: `API场景测试-自动创建-${Date.now()}`,
  address: '北京市朝阳区测试路100号',
  description: '由API场景测试自动创建的采样点',
};

const UPDATED_SITE = {
  name: `已编辑-API场景测试-${Date.now()}`,
  address: '上海市浦东新区测试路200号',
  description: '由API场景测试编辑后的采样点',
};

let createdSiteId: string;

test.describe('采样点完整管理流程场景测试', () => {

  test('步骤1: 新增采样点 - 创建新的采样点', async ({ request }) => {
    const url = buildUrl(BASE_URL, '/xmetrix-data/sampling-site');

    const response = await request.post(url, {
      headers: authHeaders,
      data: TEST_SITE,
    });

    // 断言：状态码 200
    expect(response.status()).toBe(200);

    const body = await response.json();
    console.log('新增采样点响应:', JSON.stringify(body));

    // 断言：响应码为 2000
    expect(body.code).toBe('2000');
    expect(body.message).toBe('success');

    // POST 新增接口返回的响应中没有 data.id，需要通过步骤2列表查询获取
  });

  test('步骤2: 分页查询采样点列表 - 验证新采样点存在并获取 siteId', async ({ request }) => {
    const url = buildUrl(BASE_URL, '/xmetrix-data/sampling-site/page');

    const response = await request.post(url, {
      headers: authHeaders,
      data: {
        current: 1,
        size: 50,
        orders: [{ field: 'createdTime', direction: 'descend', dataType: 'date', alias: '' }],
        operator: 'and',
        params: [],
        filters: [],
      },
    });

    expect(response.status()).toBe(200);

    const body = await response.json();
    console.log('分页查询响应:', JSON.stringify(body));

    expect(body.code).toBe('2000');
    expect(body.data).toBeDefined();
    expect(Array.isArray(body.data)).toBe(true);
    expect(body.data.length).toBeGreaterThan(0);

    // 查找我们刚创建的采样点
    const createdSite = body.data.find((site: any) => site.name === TEST_SITE.name);
    expect(createdSite).toBeDefined();
    expect(createdSite.name).toBe(TEST_SITE.name);
    expect(createdSite.address).toBe(TEST_SITE.address);

    // 保存 siteId 供后续步骤使用
    createdSiteId = createdSite.id;
    console.log(`找到新创建的采样点，ID: ${createdSiteId}`);
  });

  test('步骤3: 编辑采样点 - 修改采样点名称和地址', async ({ request }) => {
    // 确保步骤2已执行并获取了 siteId
    expect(createdSiteId).toBeDefined();

    const url = buildUrl(BASE_URL, `/xmetrix-data/sampling-site/${createdSiteId}`);

    const response = await request.put(url, {
      headers: authHeaders,
      data: UPDATED_SITE,
    });

    expect(response.status()).toBe(200);

    const body = await response.json();
    console.log('编辑采样点响应:', JSON.stringify(body));

    expect(body.code).toBe('2000');
    expect(body.message).toBe('success');
  });

  test('步骤4: 再次查询采样点列表 - 验证编辑已生效', async ({ request }) => {
    // 确保步骤2已执行并获取了 siteId
    expect(createdSiteId).toBeDefined();

    const url = buildUrl(BASE_URL, '/xmetrix-data/sampling-site/page');

    const response = await request.post(url, {
      headers: authHeaders,
      data: {
        current: 1,
        size: 50,
        orders: [{ field: 'createdTime', direction: 'descend', dataType: 'date', alias: '' }],
        operator: 'and',
        params: [],
        filters: [],
      },
    });

    expect(response.status()).toBe(200);

    const body = await response.json();
    console.log('编辑后查询响应:', JSON.stringify(body));

    expect(body.code).toBe('2000');
    expect(body.data).toBeDefined();
    expect(Array.isArray(body.data)).toBe(true);

    // 业务断言：通过 siteId 找到编辑后的记录，验证名称和地址已更新
    const updatedSite = body.data.find((site: any) => site.id === createdSiteId);
    expect(updatedSite).toBeDefined();
    expect(updatedSite.name).toBe(UPDATED_SITE.name);
    expect(updatedSite.address).toBe(UPDATED_SITE.address);

    console.log(`验证成功：采样点 ${createdSiteId} 已更新为 "${UPDATED_SITE.name}"`);
  });
});
