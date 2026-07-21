# Test Plan: 精智呼析云 - 采样点列表新增采样点

## Feature Overview
在精智呼析云平台中，登录后选择进入"精智呼析云"，在客户管理下的采样点列表中新增采样点。

## Prerequisites
- **认证方式**：需 UI 登录（项目 storageState 对该应用不生效）
- **用户角色**：拥有精智呼析云平台访问权限的用户
- **数据要求**：无特殊数据要求
- **初始状态**：未登录状态

**Setup Steps:**
1. 导航到登录页面
   - URL: `https://xcloud-sit-15000.chromxhealth.com/login`
2. 点击"密码"切换到密码登录方式
   - **Locator**: `locator('div').filter({ hasText: /^密码$/ }).nth(1)` ✅ 已验证
3. 输入手机号
   - **Locator**: `getByRole('textbox', { name: '手机号' })` ✅ 已验证
   - **Data**: `18819497582`
4. 输入密码
   - **Locator**: `getByRole('textbox', { name: '密码' })` ✅ 已验证
   - **Data**: `Cuihh0722@@`
5. 输入验证码
   - **Locator**: `getByRole('textbox', { name: '验证码' })` ✅ 已验证
   - **Data**: `123`
6. 点击登录
   - **Locator**: `getByRole('button', { name: '登录' })` ✅ 已验证
7. 在系统选择页面，选择"精智呼析云"
   - **Locator**: `getByText('精智呼析云')` ✅ 已验证
8. 等待精智呼析云首页加载
9. 在侧边栏点击"采样点列表"
   - **Locator**: `getByRole('menuitem', { name: '采样点列表' })` ✅ 已验证

## Test Data
- **Source**: 用户提供
- **Credentials**:
  - 手机号: `18819497582`
  - 密码: `Cuihh0722@@`
  - 验证码: `123`
- **Default 验证码**: `123` (固定验证码，测试环境使用)

## Test Scenarios

### 场景 1: 成功新增采样点（完整填写必填+可选字段）

**前置条件**:
- 已登录并进入精智呼析云
- 已在采样点列表页面

**测试步骤**:
1. 点击"新增"按钮
   - **Locator**: `getByRole('button', { name: '新增' })` ✅ 已验证
   - **预期**: 弹出"新增采样点"对话框
2. 在"采样点名称"输入框中输入测试采样点名称
   - **Locator**: `getByRole('textbox', { name: '采样点名称' })` ✅ 已验证
   - **Data**: `测试采样点_自动化_${timestamp}`
3. 在"描述"输入框中输入描述信息
   - **Locator**: `getByRole('textbox', { name: '描述' })` ✅ 已验证
   - **Data**: `自动化测试创建的采样点`
4. 在"地址"输入框中输入地址
   - **Locator**: `getByRole('textbox', { name: '地址' })` ✅ 已验证
   - **Data**: `广东省广州市测试地址100号`
5. 点击"确定"按钮
   - **Locator**: `getByRole('button', { name: '确定' })` ✅ 已验证
   - **预期**: 对话框关闭，采样点列表刷新，新创建的采样点出现在列表中，页面可能出现成功提示

### 场景 2: 取消新增采样点

**前置条件**:
- 已登录并进入精智呼析云
- 已在采样点列表页面

**测试步骤**:
1. 点击"新增"按钮
   - **Locator**: `getByRole('button', { name: '新增' })` ✅ 已验证
   - **预期**: 弹出"新增采样点"对话框
2. 在"采样点名称"输入框中输入采样点名称
   - **Locator**: `getByRole('textbox', { name: '采样点名称' })` ✅ 已验证
   - **Data**: `测试采样点_待取消`
3. 点击"取消"按钮
   - **Locator**: `getByRole('button', { name: '取消' })` ✅ 已验证
   - **预期**: 对话框关闭，采样点列表不变

### 场景 3: 必填字段验证 - 空名称提交

**前置条件**:
- 已登录并进入精智呼析云
- 已在采样点列表页面

**测试步骤**:
1. 点击"新增"按钮
   - **Locator**: `getByRole('button', { name: '新增' })` ✅ 已验证
2. 填写地址（不填写名称）
   - **Locator**: `getByRole('textbox', { name: '地址' })` ✅ 已验证
   - **Data**: `广东省广州市`
3. 点击"确定"按钮
   - **Locator**: `getByRole('button', { name: '确定' })` ✅ 已验证
   - **预期**: 提交被阻止，提示请输入采样点名称
4. 点击"取消"关闭对话框
   - **Locator**: `getByRole('button', { name: '取消' })` ✅ 已验证

## Coverage Analysis
| 场景 | 类型 | 覆盖 |
|------|------|------|
| 场景 1 | Happy Path | 完整新增流程，含全部字段 |
| 场景 2 | 取消操作 | 验证取消不保存 |
| 场景 3 | 异常/验证 | 必填字段校验 |

## Priority
- 场景 1: High (核心功能)
- 场景 2: Medium
- 场景 3: Medium

## Estimated Time
- 场景 1: ~30s
- 场景 2: ~20s
- 场景 3: ~20s
- Total: ~70s
