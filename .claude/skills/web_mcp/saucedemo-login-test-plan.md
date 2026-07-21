# 测试计划：用户登录

## 功能概述
验证 SauceDemo 网站的用户登录功能，使用页面显示的测试凭证进行登录测试。

## 前置条件
- **认证方式**：需 UI 登录（项目 storageState 对该应用不生效）
- **用户角色**：标准用户
- **数据需求**：需使用页面显示的有效用户名和密码
- **初始状态**：用户未登录，位于登录页面
- **TestIdAttribute**: `data-test` — 应用使用 `data-test` 属性，脚本必须配置 `test.use({ testIdAttribute: 'data-test' })`

## 测试数据
- **来源**：从登录页面内容提取
- **凭证**：
  | 用户名 | 类型 | 状态 |
  |--------|------|------|
  | standard_user | 标准用户 | 可用 |
  | locked_out_user | 锁定用户 | 不可用 |
  | problem_user | 问题用户 | 可登录但有已知 bug |
  | performance_glitch_user | 性能问题用户 | 可登录但加载慢 |
  | error_user | 错误用户 | 可登录 |
  | visual_user | 视觉用户 | 可登录 |
- **默认密码**: secret_sauce（适用于所有用户）
- **错误类型**:
  - 空用户名: "Epic sadface: Username is required"
  - 空密码: "Epic sadface: Password is required"
  - 无效凭证: "Epic sadface: Username and password do not match any user in this service"

## 测试场景

### 场景 1：使用有效凭证成功登录

**前置条件:**
- 用户位于登录页面（https://www.saucedemo.com）
- 用户未登录

**设置步骤:**
1. 导航到 SauceDemo 登录页面
   - URL: `https://www.saucedemo.com`
   - **定位器**: N/A
   - **已验证**: ✅

2. 填写用户名
   - **元素**: 用户名输入框
   - **定位器**: `getByTestId('username')`
   - **备用**: `locator('[data-test="username"]')`
   - **数据**: `standard_user`
   - **已验证**: ✅

3. 填写密码
   - **元素**: 密码输入框
   - **定位器**: `getByTestId('password')`
   - **备用**: `locator('[data-test="password"]')`
   - **数据**: `secret_sauce`
   - **已验证**: ✅

4. 点击登录按钮
   - **元素**: 登录按钮
   - **定位器**: `getByTestId('login-button')`
   - **备用**: `locator('[data-test="login-button"]')`
   - **已验证**: ✅

**预期结果:**
- URL 跳转到 `https://www.saucedemo.com/inventory.html`
- 商品列表页面加载，显示标题 "Products"
- **验证定位器**: `getByTestId('inventory-container')`

**清理:**
- 无（后续测试依赖已登录状态）

### 场景 2：使用无效凭证登录失败

**前置条件:**
- 用户位于登录页面（https://www.saucedemo.com）

**设置步骤:**
1. 导航到 SauceDemo 登录页面
   - URL: `https://www.saucedemo.com`
   - **定位器**: N/A
   - **已验证**: ✅

**测试步骤:**

1. 填写无效用户名
   - **元素**: 用户名输入框
   - **定位器**: `getByTestId('username')`
   - **备用**: `locator('[data-test="username"]')`
   - **数据**: `invalid_user`
   - **已验证**: ✅

2. 填写密码
   - **元素**: 密码输入框
   - **定位器**: `getByTestId('password')`
   - **备用**: `locator('[data-test="password"]')`
   - **数据**: `wrong_password`
   - **已验证**: ✅

3. 点击登录按钮
   - **元素**: 登录按钮
   - **定位器**: `getByTestId('login-button')`
   - **备用**: `locator('[data-test="login-button"]')`
   - **已验证**: ✅

**预期结果:**
- 页面 URL 不变，仍为 `https://www.saucedemo.com`
- 显示错误消息: "Epic sadface: Username and password do not match any user in this service"
- **验证定位器**: `getByTestId('error')`

### 场景 3：使用锁定用户登录被拒

**前置条件:**
- 用户位于登录页面（https://www.saucedemo.com）

**测试步骤:**

1. 填写锁定用户用户名
   - **元素**: 用户名输入框
   - **定位器**: `getByTestId('username')`
   - **备用**: `locator('[data-test="username"]')`
   - **数据**: `locked_out_user`
   - **已验证**: ✅

2. 填写密码
   - **元素**: 密码输入框
   - **定位器**: `getByTestId('password')`
   - **备用**: `locator('[data-test="password"]')`
   - **数据**: `secret_sauce`
   - **已验证**: ✅

3. 点击登录按钮
   - **元素**: 登录按钮
   - **定位器**: `getByTestId('login-button')`
   - **备用**: `locator('[data-test="login-button"]')`
   - **已验证**: ✅

**预期结果:**
- 页面 URL 不变，仍为 `https://www.saucedemo.com`
- 显示错误消息: "Epic sadface: Sorry, this user has been locked out."
- **验证定位器**: `getByTestId('error')`
