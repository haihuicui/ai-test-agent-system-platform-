import { test, expect } from '@playwright/test';

// ============================================================
// 客户管理完整流程 - 场景测试脚本
// 业务流程：新增客户 → 分页列表验证 → 查询客户明细 → 编辑客户 → 验证编辑结果
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

const authHeaders: Record<string, string> = {
  'Authorization': `Bearer ${AUTH_TOKEN}`,
  'Content-Type': 'application/json',
  'Accept': 'application/json',
};

// 测试数据
const TEST_CUSTOMER = {
  name: `AutoTest_Customer_${Date.now()}`,
  description: '由自动化场景测试创建的客户，用于验证完整业务流程',
  samplingSiteIds: [] as string[],
};

const UPDATED_CUSTOMER = {
  name: `AutoTest_Customer_Edited_${Date.now()}`,
  description: '由自动化场景测试编辑更新',
  samplingSiteIds: [] as string[],
};

let createdCustomerId: string;

test.describe('客户管理完整流程 - 场景测试', () => {

  test('步骤1: 新增客户', async () => {
    const url = `${BASE_URL.replace(/\/$/, '')}/xmetrix-data/customer`;
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify(TEST_CUSTOMER),
    });

    expect(response.status).toBe(200);
    const data = await response.json();

    // 验证业务响应码
    expect(data.code).toBe('2000');
    expect(data.message).toBe('success');
  });

  test('步骤2: 分页查询客户列表 - 获取刚创建的客户ID', async () => {
    const url = `${BASE_URL.replace(/\/$/, '')}/xmetrix-data/customer/page`;
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify({
        current: 1,
        size: 20,
        operator: 'and',
        orders: [],
        params: [],
        filters: [],
      }),
    });

    expect(response.status).toBe(200);
    const data = await response.json();

    // 验证业务响应码
    expect(data.code).toBe('2000');

    // 验证分页数据结构
    expect(data.data).toBeInstanceOf(Array);
    expect(data.data.length).toBeGreaterThan(0);

    // 查找刚创建的客户（按名称匹配）
    const createdCustomer = data.data.find(
      (c: { id: string; name: string }) => c.name === TEST_CUSTOMER.name
    );
    expect(createdCustomer).toBeDefined();
    expect(createdCustomer.id).toBeDefined();
    expect(typeof createdCustomer.id).toBe('string');

    // 保存客户ID供后续步骤使用
    createdCustomerId = createdCustomer.id;

    // 验证客户基本信息
    expect(createdCustomer.name).toBe(TEST_CUSTOMER.name);
    expect(createdCustomer.description).toBe(TEST_CUSTOMER.description);
    expect(createdCustomer.samplingSiteCount).toBe(0);
  });

  test('步骤3: 查询客户明细', async () => {
    expect(createdCustomerId).toBeDefined();

    const url = `${BASE_URL.replace(/\/$/, '')}/xmetrix-data/customer/${createdCustomerId}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: authHeaders,
    });

    expect(response.status).toBe(200);
    const data = await response.json();

    // 验证业务响应码
    expect(data.code).toBe('2000');

    // 验证客户详情
    expect(data.data).toBeDefined();
    expect(data.data.id).toBe(createdCustomerId);
    expect(data.data.name).toBe(TEST_CUSTOMER.name);
    expect(data.data.description).toBe(TEST_CUSTOMER.description);
  });

  test('步骤4: 编辑客户', async () => {
    expect(createdCustomerId).toBeDefined();

    const url = `${BASE_URL.replace(/\/$/, '')}/xmetrix-data/customer/${createdCustomerId}`;
    const response = await fetch(url, {
      method: 'PUT',
      headers: authHeaders,
      body: JSON.stringify(UPDATED_CUSTOMER),
    });

    expect(response.status).toBe(200);
    const data = await response.json();

    // 验证业务响应码
    expect(data.code).toBe('2000');
    expect(data.message).toBe('success');
  });

  test('步骤5: 验证编辑结果 - 再次查询客户明细', async () => {
    expect(createdCustomerId).toBeDefined();

    const url = `${BASE_URL.replace(/\/$/, '')}/xmetrix-data/customer/${createdCustomerId}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: authHeaders,
    });

    expect(response.status).toBe(200);
    const data = await response.json();

    // 验证业务响应码
    expect(data.code).toBe('2000');

    // 验证编辑已生效
    expect(data.data).toBeDefined();
    expect(data.data.id).toBe(createdCustomerId);
    expect(data.data.name).toBe(UPDATED_CUSTOMER.name);
    expect(data.data.description).toBe(UPDATED_CUSTOMER.description);
  });
});
