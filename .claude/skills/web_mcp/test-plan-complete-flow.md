# 测试计划：SauceDemo 完整购物流程

## 概览
- **功能**: SauceDemo 完整购物流程
- **URL**: https://www.saucedemo.com
- **业务模块**: 电商演示
- **TestIdAttribute**: `data-test` — 生成脚本时必须配置 `test.use({ testIdAttribute: 'data-test' })`，然后使用 `getByTestId()`

## 前置条件
- **认证方式**：需 UI 登录（项目 storageState 对该应用不生效）
- **用户角色**：标准用户 (standard_user)
- **数据要求**：至少有一个商品在商品列表中
- **初始状态**：购物车为空

## Setup Steps
1. 导航到登录页
   - URL: `https://www.saucedemo.com`
   - **定位器**: N/A
   - **已验证**: ✅
2. 输入用户名
   - **元素**: 用户名输入框
   - **定位器**: `getByTestId('username')`
   - **数据**: `standard_user`
   - **已验证**: ✅
3. 输入密码
   - **元素**: 密码输入框
   - **定位器**: `getByTestId('password')`
   - **数据**: `secret_sauce`
   - **已验证**: ✅
4. 点击登录按钮
   - **元素**: 登录按钮
   - **定位器**: `getByTestId('login-button')`
   - **已验证**: ✅
5. 验证登录成功
   - **元素**: 商品页面加载
   - **定位器**: `getByTestId('inventory-container')`
   - **验证**: 页面跳转到 `inventory.html`，商品列表可见

## 测试数据
- **来源**: 登录页面显示的测试凭证
- **凭证**: standard_user / secret_sauce
- **测试账号**:
  | 用户名 | 类型 | 状态 |
  |--------|------|------|
  | standard_user | 标准用户 | 可用 |
  | locked_out_user | 锁定用户 | 不可用 |
  | problem_user | 问题用户 | 可登录但有已知 bug |
  | performance_glitch_user | 性能慢用户 | 可登录但加载慢 |
  | error_user | 错误用户 | 可登录但交互异常 |
  | visual_user | 视觉用户 | 可登录但渲染差异 |
- **默认密码**: secret_sauce（适用于所有用户）
- **结账信息**: First Name: John, Last Name: Doe, Zip/Postal Code: 12345

---

## 测试场景

### 场景 1: 完整购物流程 - 登录到结账完成（Happy Path）

**前置条件:**
- 用户未登录（需要执行 Setup Steps）

**测试步骤:**

1. 导航到登录页
   - URL: `https://www.saucedemo.com`
   - **定位器**: N/A
   - **已验证**: ✅
   - **上下文**: 首次访问，页面显示登录表单

2. 输入用户名
   - **元素**: 用户名输入框
   - **定位器**: `getByTestId('username')`
   - **数据**: `standard_user`
   - **已验证**: ✅
   - **上下文**: 使用标准用户登录

3. 输入密码
   - **元素**: 密码输入框
   - **定位器**: `getByTestId('password')`
   - **数据**: `secret_sauce`
   - **已验证**: ✅
   - **上下文**: 页面显示对所有用户通用密码

4. 点击登录按钮
   - **元素**: 登录按钮
   - **定位器**: `getByTestId('login-button')`
   - **已验证**: ✅
   - **上下文**: 登录后跳转到商品页面

5. 验证商品页面加载成功
   - **元素**: 商品列表容器
   - **定位器**: `getByTestId('inventory-container')`
   - **已验证**: ✅
   - **上下文**: 确认页面包含商品列表

6. 添加 "Sauce Labs Backpack" 到购物车
   - **元素**: "Add to cart" 按钮 - Sauce Labs Backpack
   - **定位器**: `getByTestId('add-to-cart-sauce-labs-backpack')`
   - **已验证**: ✅
   - **上下文**: 按钮文字应变为 "Remove"

7. 点击购物车链接
   - **元素**: 购物车链接（右上角）
   - **定位器**: `getByTestId('shopping-cart-link')`
   - **已验证**: ✅
   - **上下文**: 购物车角标显示 "1"

8. 验证购物车页面
   - **元素**: 购物车标题
   - **定位器**: N/A（使用文本验证）
   - **验证**: 页面标题为 "Your Cart"
   - **上下文**: 购物车中包含 Sauce Labs Backpack，数量 1，价格 $29.99

9. 点击 Checkout 按钮
   - **元素**: Checkout 按钮
   - **定位器**: `getByTestId('checkout')`
   - **已验证**: ✅
   - **上下文**: 跳转到结账信息填写页面

10. 输入 First Name
    - **元素**: First Name 输入框
    - **定位器**: `getByTestId('firstName')`
    - **数据**: `John`
    - **已验证**: ✅

11. 输入 Last Name
    - **元素**: Last Name 输入框
    - **定位器**: `getByTestId('lastName')`
    - **数据**: `Doe`
    - **已验证**: ✅

12. 输入 Zip/Postal Code
    - **元素**: Zip/Postal Code 输入框
    - **定位器**: `getByTestId('postalCode')`
    - **数据**: `12345`
    - **已验证**: ✅

13. 点击 Continue 按钮
    - **元素**: Continue 按钮
    - **定位器**: `getByTestId('continue')`
    - **已验证**: ✅
    - **上下文**: 跳转到订单概览页面

14. 验证订单概览信息
    - **验证项**:
      - 商品: Sauce Labs Backpack
      - 价格: $29.99
      - 数量: 1
      - 支付信息: SauceCard #31337
      - 配送信息: Free Pony Express Delivery!
      - 商品总价: Item total: $29.99
      - 税金: Tax: $2.40
      - 总计: Total: $32.39

15. 点击 Finish 按钮完成订单
    - **元素**: Finish 按钮
    - **定位器**: `getByTestId('finish')`
    - **已验证**: ✅
    - **上下文**: 跳转到订单完成页面

16. 验证订单完成
    - **验证项**:
      - 页面标题: "Checkout: Complete!"
      - 成功消息: "Thank you for your order!"
      - 描述: "Your order has been dispatched, and will arrive just as fast as the pony can get there!"

**预期结果:**
- 用户成功登录
- 商品成功添加到购物车
- 购物车显示正确商品
- 结账信息成功提交
- 订单成功完成，显示感谢信息

**清理:**
- 可点击 "Back Home" 按钮（`getByTestId('back-to-products')`）返回商品页面

---

### 场景 2: 结账信息验证 - 必填字段为空

**前置条件:**
- 用户已登录并已将商品添加到购物车
- 用户已在购物车页面点击 Checkout 按钮

**测试步骤:**

1. 不填 First Name，直接点击 Continue
   - **定位器**: `getByTestId('continue')`
   - **预期错误**: "Error: First Name is required"

2. 填写 First Name，不填 Last Name，点击 Continue
   - **数据**: First Name = John
   - **预期错误**: "Error: Last Name is required"

3. 填写 First Name 和 Last Name，不填 Zip/Postal Code，点击 Continue
   - **数据**: First Name = John, Last Name = Doe
   - **预期错误**: "Error: Postal Code is required"

**预期结果:**
- 系统阻止继续结账
- 显示相应的错误提示信息
- 错误信息可通过点击错误框的关闭按钮消除

---

### 场景 3: 下单后返回商品首页

**前置条件:**
- 用户已完成完整购物流程（从登录到结账完成）

**测试步骤:**

1. 在结账完成页面，点击 "Back Home" 按钮
   - **元素**: Back Home 按钮
   - **定位器**: `getByTestId('back-to-products')`
   - **已验证**: ✅

2. 验证返回商品页面
   - **定位器**: `getByTestId('inventory-container')`
   - **验证**: 成功返回商品列表页

**预期结果:**
- 成功返回商品页面
- 购物车角标不再显示（已清空）

---

## 元素定位器总表

| 页面 | 元素 | 定位器 | 来源 |
|------|------|--------|------|
| 登录页 | 用户名输入框 | `getByTestId('username')` | `data-test="username"` |
| 登录页 | 密码输入框 | `getByTestId('password')` | `data-test="password"` |
| 登录页 | 登录按钮 | `getByTestId('login-button')` | `data-test="login-button"` |
| 商品页 | 商品列表容器 | `getByTestId('inventory-container')` | `data-test="inventory-container"` |
| 商品页 | 添加 Sauce Labs Backpack | `getByTestId('add-to-cart-sauce-labs-backpack')` | `data-test="add-to-cart-sauce-labs-backpack"` |
| 商品页 | 购物车链接 | `getByTestId('shopping-cart-link')` | `data-test="shopping-cart-link"` |
| 购物车 | Checkout 按钮 | `getByTestId('checkout')` | `data-test="checkout"` |
| 购物车 | Continue Shopping | `getByTestId('continue-shopping')` | `data-test="continue-shopping"` |
| 结账-信息 | First Name 输入框 | `getByTestId('firstName')` | `data-test="firstName"` |
| 结账-信息 | Last Name 输入框 | `getByTestId('lastName')` | `data-test="lastName"` |
| 结账-信息 | Zip/Postal Code 输入框 | `getByTestId('postalCode')` | `data-test="postalCode"` |
| 结账-信息 | Continue 按钮 | `getByTestId('continue')` | `data-test="continue"` |
| 结账-信息 | Cancel 按钮 | `getByTestId('cancel')` | `data-test="cancel"` |
| 结账-概览 | Finish 按钮 | `getByTestId('finish')` | `data-test="finish"` |
| 结账-概览 | Cancel 按钮 | `getByTestId('cancel')` | `data-test="cancel"` |
| 结账-完成 | Back Home 按钮 | `getByTestId('back-to-products')` | `data-test="back-to-products"` |
