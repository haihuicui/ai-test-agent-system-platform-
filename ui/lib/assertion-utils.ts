import { StepAssertion } from "@/types/scenario";

/**
 * 断言操作符的 canonical 值与中文显示文本。
 *
 * 后端执行引擎只识别短值：eq / ne / gt / lt / contains。
 * 前端 Select 使用这些值作为 value，label 保持中文。
 */
export const OPERATOR_LABELS: Record<string, string> = {
  eq: "等于",
  ne: "不等于",
  gt: "大于",
  lt: "小于",
  contains: "包含",
};

/**
 * 将任意 operator 值归一化为 canonical 值。
 *
 * - 空值/undefined/null 返回 "eq"
 * - 已兼容旧 UI 使用的 verbose 值：equals / not_equals / greater_than / less_than
 * - 未知值返回 "eq"，保证下拉框总有合法选中项
 */
export function normalizeOperator(value?: string | null): string {
  if (!value) {
    return "eq";
  }
  const canonical = Object.keys(OPERATOR_LABELS).find(
    (k) => k === value || OPERATOR_LABELS[k] === value
  );
  return canonical || "eq";
}

/**
 * 对从 API 加载的断言列表做 operator 归一化，避免旧 verbose 值导致
 * Select 组件显示为空。
 */
export function normalizeAssertions(assertions?: StepAssertion[]): StepAssertion[] {
  return (assertions || []).map((assertion) => ({
    ...assertion,
    operator: normalizeOperator(assertion.operator),
  }));
}
