/**
 * API 端点 prompt 构建工具
 *
 * 统一 AI 生成入口中展示给用户的接口描述格式，
 * 避免对话记录中只显示接口 ID。
 */

export interface EndpointPromptInput {
  id?: string;
  display_name: string;
  method: string;
  path: string;
  summary?: string | null;
  description?: string | null;
  tag_group?: string | null;
}

/**
 * 为单个端点生成 human-readable 的 prompt 块。
 *
 * 示例输出：
 * ```
 * 【POST】创建订单 /api/v1/orders
 * 名称：创建订单
 * 描述：创建新订单
 * 标签：订单管理
 * ```
 */
export function buildEndpointPromptBlock(
  endpoint: EndpointPromptInput,
  options?: { includeId?: boolean }
): string {
  const { includeId = false } = options ?? {};
  const desc = endpoint.summary || endpoint.description || "";
  const tag = endpoint.tag_group || "";

  const lines: string[] = [
    `【${endpoint.method.toUpperCase()}】${endpoint.display_name} ${endpoint.path}`,
  ];

  if (includeId && endpoint.id) {
    lines.push(`接口 ID：${endpoint.id}`);
  }

  lines.push(`名称：${endpoint.display_name}`);

  if (desc) {
    lines.push(`描述：${desc}`);
  }

  if (tag) {
    lines.push(`标签：${tag}`);
  }

  return lines.join("\n");
}

/**
 * 为多个端点生成 prompt 块，用于 AI 生成场景测试。
 *
 * 示例输出：
 * ```
 * 已选接口（共 2 个）：
 * 1. 【GET】获取用户详情 /api/v1/users/{id}
 *    名称：获取用户详情
 *    描述：根据用户 ID 查询基本信息
 *    接口 ID：xxx
 *
 * 2. 【POST】创建订单 /api/v1/orders
 *    名称：创建订单
 *    描述：创建新订单
 *    接口 ID：yyy
 * ```
 */
export function buildEndpointsListPrompt(
  endpoints: EndpointPromptInput[],
  options?: { includeId?: boolean }
): string {
  if (!endpoints.length) {
    return "未选择接口";
  }

  const { includeId = true } = options ?? {};

  const blocks = endpoints.map((endpoint, index) => {
    const block = buildEndpointPromptBlock(endpoint, { includeId });
    // 为除第一行外的每一行追加缩进，形成列表项
    const lines = block.split("\n");
    return lines
      .map((line, lineIndex) =>
        lineIndex === 0 ? `${index + 1}. ${line}` : `   ${line}`
      )
      .join("\n");
  });

  return `已选接口（共 ${endpoints.length} 个）：\n${blocks.join("\n\n")}`;
}

/**
 * 为单个端点生成 AI 生成测试用例的 prompt。
 */
export function buildSingleEndpointTestPrompt(
  endpoint: EndpointPromptInput,
  requirements?: string
): string {
  const desc = endpoint.summary || endpoint.description || "无";
  const tag = endpoint.tag_group ? `\n标签：${endpoint.tag_group}` : "";

  let prompt = `请为接口 ${endpoint.display_name} 生成测试用例。

接口信息：
- 方法: ${endpoint.method.toUpperCase()}
- 路径: ${endpoint.path}
- 描述: ${desc}${tag}

请生成：
1. 完整的测试用例
2. 测试脚本
3. 包含正常场景、边界条件、异常处理`;

  if (requirements?.trim()) {
    prompt += `\n\n用户要求:\n${requirements.trim()}`;
  }

  return prompt;
}

/**
 * 为多个端点生成 AI 生成场景测试的 prompt。
 */
export function buildScenarioGenerationPrompt(
  endpoints: EndpointPromptInput[],
  customRequirements?: string
): string {
  const listBlock = buildEndpointsListPrompt(endpoints, { includeId: true });

  let prompt = `创建 API 场景测试

${listBlock}

请基于这些接口分析业务关联性，使用场景测试技能（scenario）创建完整的测试场景。
创建完成后必须执行场景测试，根据执行结果自动修复数据依赖、断言或请求参数，确保场景可正常运行。`;

  if (customRequirements?.trim()) {
    prompt += `\n\n---\n\n自定义要求:\n${customRequirements.trim()}`;
  }

  return prompt;
}
