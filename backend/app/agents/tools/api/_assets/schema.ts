// tests/_helpers/schema.ts
//
// 零依赖 JSON Schema 校验器（常用子集），用于 API 响应契约断言。
// 背景：workspace 无法安装 ajv（npm 不可靠），故内置一个覆盖常用子集的校验器，
//       让生成脚本无需任何新依赖即可做整体契约校验。
//
// 覆盖：type(含类型数组 / nullable) / required / properties(递归) / items /
//       additionalProperties / enum / minItems·maxItems / minLength·maxLength /
//       minimum·maximum / allOf(合并) / anyOf·oneOf(至少其一)。
// $ref 已由后端 get_response_schema 尽力内联，未解的替换为 {}（此处视为“任意”，跳过）。
//
// 用法（生成脚本中）：
//   import { validateSchema } from './_helpers/schema';
//   const body = await response.json();
//   expect(validateSchema(body, SCHEMA).valid).toBe(true);   // 失败时自动 console.error 全部错误

export interface SchemaValidationResult {
  valid: boolean;
  errors: string[];
}

function typeOf(v: unknown): string {
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'array';
  return typeof v;
}

function matchType(v: unknown, t: string): boolean {
  switch (t) {
    case 'string': return typeof v === 'string';
    case 'number': return typeof v === 'number' && !Number.isNaN(v as number);
    case 'integer': return typeof v === 'number' && Number.isInteger(v as number);
    case 'boolean': return typeof v === 'boolean';
    case 'object': return v !== null && typeof v === 'object' && !Array.isArray(v);
    case 'array': return Array.isArray(v);
    case 'null': return v === null;
    default: return true; // 未知类型不约束
  }
}

function join(base: string, key: string): string {
  return base ? `${base}.${key}` : key;
}

function validate(value: any, schema: any, path: string, errors: string[]): void {
  if (schema === null || typeof schema !== 'object') return; // {} / 非法 → 不约束
  if (schema.$ref) return;                                    // 未解 $ref → 跳过

  // allOf：全部满足
  if (Array.isArray(schema.allOf)) {
    for (const s of schema.allOf) validate(value, s, path, errors);
  }
  // anyOf / oneOf：至少一个满足
  for (const key of ['anyOf', 'oneOf'] as const) {
    if (Array.isArray(schema[key])) {
      const ok = (schema[key] as any[]).some((s) => {
        const sub: string[] = [];
        validate(value, s, path, sub);
        return sub.length === 0;
      });
      if (!ok) errors.push(`${path || '$'} 不匹配 ${key} 中任何子 schema`);
    }
  }

  // enum
  if (Array.isArray(schema.enum)) {
    const hit = (schema.enum as any[]).some((e) => JSON.stringify(e) === JSON.stringify(value));
    if (!hit) {
      errors.push(`${path || '$'} 值 ${JSON.stringify(value)} 不在枚举 ${JSON.stringify(schema.enum)} 内`);
      return;
    }
  }

  // type
  if (schema.type !== undefined) {
    const types: string[] = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!types.some((t) => matchType(value, t))) {
      errors.push(`${path || '$'} 类型应为 ${types.join('|')}，实际 ${typeOf(value)}`);
      return; // 类型不符，后续子校验无意义
    }
  }

  const vt = typeOf(value);
  if (vt === 'object') {
    const required: string[] = Array.isArray(schema.required) ? schema.required : [];
    for (const r of required) {
      if (value === null || !(r in (value as object))) {
        errors.push(`${path || '$'} 缺少必填字段 ${r}`);
      }
    }
    const props = (schema.properties && typeof schema.properties === 'object') ? schema.properties : {};
    for (const k of Object.keys(props)) {
      if (value !== null && k in (value as object)) {
        validate((value as any)[k], props[k], join(path, k), errors);
      }
    }
    const allowed = new Set(Object.keys(props));
    if (schema.additionalProperties === false) {
      for (const k of Object.keys(value as object)) {
        if (!allowed.has(k)) errors.push(`${path || '$'} 存在未定义字段 ${k}`);
      }
    } else if (schema.additionalProperties && typeof schema.additionalProperties === 'object') {
      for (const k of Object.keys(value as object)) {
        if (!allowed.has(k)) validate((value as any)[k], schema.additionalProperties, join(path, k), errors);
      }
    }
  } else if (vt === 'array') {
    const arr = value as any[];
    if (typeof schema.minItems === 'number' && arr.length < schema.minItems) {
      errors.push(`${path || '$'} 数组长度 ${arr.length} < minItems ${schema.minItems}`);
    }
    if (typeof schema.maxItems === 'number' && arr.length > schema.maxItems) {
      errors.push(`${path || '$'} 数组长度 ${arr.length} > maxItems ${schema.maxItems}`);
    }
    const items = schema.items;
    if (Array.isArray(items)) {
      arr.forEach((v, i) => { if (items[i]) validate(v, items[i], `${path || '$'}[${i}]`, errors); });
    } else if (items && typeof items === 'object') {
      arr.forEach((v, i) => validate(v, items, `${path || '$'}[${i}]`, errors));
    }
  } else if (vt === 'string') {
    const s = value as string;
    if (typeof schema.minLength === 'number' && s.length < schema.minLength) {
      errors.push(`${path || '$'} 长度 ${s.length} < minLength ${schema.minLength}`);
    }
    if (typeof schema.maxLength === 'number' && s.length > schema.maxLength) {
      errors.push(`${path || '$'} 长度 ${s.length} > maxLength ${schema.maxLength}`);
    }
  } else if (vt === 'number') {
    const num = value as number;
    if (typeof schema.minimum === 'number' && num < schema.minimum) {
      errors.push(`${path || '$'} 值 ${num} < minimum ${schema.minimum}`);
    }
    if (typeof schema.maximum === 'number' && num > schema.maximum) {
      errors.push(`${path || '$'} 值 ${num} > maximum ${schema.maximum}`);
    }
  }
}

/** 校验响应体是否符合 JSON Schema。失败时 console.error 全部错误并返回 valid=false。 */
export function validateSchema(body: unknown, schema: unknown): SchemaValidationResult {
  const errors: string[] = [];
  validate(body, schema, '', errors);
  if (errors.length) {
    // eslint-disable-next-line no-console
    console.error('[schema 校验失败]\n' + errors.join('\n'));
  }
  return { valid: errors.length === 0, errors };
}

export default validateSchema;
