# 渗透测试报告模板使用说明

## 📁 文件位置

模板文件：`/Users/huimingliao/Documents/code/pentest-skills/templates/pentest_report_template.md`

---

## 🔧 使用方法

### 方法 1：在提示词中引用模板（最可靠）⭐

每次生成报告时，在提示词中明确说明：

```
请按照以下模板格式生成渗透测试报告：

模板文件位置：/Users/huimingliao/Documents/code/pentest-skills/templates/pentest_report_template.md

或直接粘贴模板内容到提示词中。
```

**示例提示词**：
```
我需要生成一份渗透测试报告，请严格按照以下格式：

# 渗透测试报告：[目标系统名称/项目名称]

| 项目信息 | 内容 |
| :--- | :--- |
| **测试目标** | [URL/IP] |
...

（完整模板内容）

目标系统：localhost:9999
测试日期：2026-02-15
发现的漏洞：SQL注入、XSS等

请按此格式生成完整报告。
```

### 方法 2：创建 Skill（自动化）

使用你的自定义 skill 功能，创建一个 "pentest-report" skill：

**技能配置**：
- 名称：`pentest-report`
- 描述：按照标准格式生成渗透测试报告
- 模板内容：包含完整的报告格式

**使用方式**：
```
/skill pentest-report 目标=localhost:9999 日期=2026-02-15
```

### 方法 3：每次对话时明确格式要求

在每次需要生成报告时，都包含格式说明：

```
请生成渗透测试报告，格式要求：
1. 包含项目信息表
2. 漏洞发现清单（ID、标题、风险等级、状态）
3. 每个漏洞包含：属性表、描述、复现步骤、证据截图、修复建议
4. 附录包含：风险等级定义、CVSS说明、词汇表等

具体格式参考：/Users/huimingliao/Documents/code/pentest-skills/reports/pentest_report_localhost_9999_v2.md
```

---

## 📋 格式检查清单

生成报告后，检查是否包含：

- [ ] 标题：`# 渗透测试报告：[目标名称]`
- [ ] 项目信息表（4个字段）
- [ ] 漏洞发现清单（表格形式，ID VL-XXX）
- [ ] 漏洞详情（每个漏洞独立章节）
- [ ] 每个漏洞包含：属性表 + 4个子章节（2.1-2.4）
- [ ] 附录（风险等级定义、工具参考、词汇表）
- [ ] 报告签署和免责声明

---

## ⚠️ 重要提醒

**为什么需要每次明确格式？**

1. **AI 的记忆限制**：我在新对话中无法记住之前的格式要求
2. **上下文窗口**：长对话可能遗忘早期的格式说明
3. **一致性保证**：明确引用模板可以确保 100% 符合格式

**最佳实践**：

✅ 每次都明确说明"按照 XX 格式生成报告"
✅ 提供模板文件路径或粘贴模板内容
✅ 生成后检查是否符合格式要求

❌ 不要假设我"应该记得"之前的格式
❌ 不要在很长的对话后期望格式保持一致
❌ 不要只在对话开始时说一次格式

---

## 🎯 推荐工作流程

1. **准备阶段**：
   - 创建并保存标准模板（已完成）
   - 记录模板文件路径

2. **生成报告时**：
   ```
   请生成渗透测试报告。

   格式模板：/Users/huimingliao/Documents/code/pentest-skills/templates/pentest_report_template.md

   目标信息：
   - URL: http://example.com
   - 日期: 2026-02-15
   - 漏洞: SQL注入 (CVSS 9.8)
   ```

3. **验证阶段**：
   - 检查生成的报告是否符合模板格式
   - 如不符合，要求重新生成

---

## 📚 参考资料

- 标准报告格式：`reports/pentest_report_localhost_9999_v2.md`
- 报告示例：`reports/pentest_report_localhost_9999_v2.md`
- 模板文件：`templates/pentest_report_template.md`

---

**更新日期**: 2026-02-15
