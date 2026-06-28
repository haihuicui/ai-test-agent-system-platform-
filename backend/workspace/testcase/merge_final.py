import json

# ========== Load File 2 (complete_merged_test_cases.json) - 49 items ==========
# This file has test_case_steps format (array of {step, result} objects)
# It contains: TD管(18) + 物资流转(15) + 地点管理(10) + 定标记录(6) = 49 items

def fix_json_with_inner_quotes(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    text = data.decode('utf-8')
    
    result = []
    i = 0
    in_string = False
    
    while i < len(text):
        c = text[i]
        
        if not in_string:
            if c == '"':
                in_string = True
            result.append(c)
            i += 1
        else:
            if c == '\\':
                result.append(c)
                i += 1
                if i < len(text):
                    result.append(text[i])
                    i += 1
            elif c == '"':
                j = i + 1
                while j < len(text) and text[j] in ' \t\n\r':
                    j += 1
                if j < len(text) and text[j] in ',:]}':
                    in_string = False
                    result.append(c)
                    i += 1
                else:
                    result.append('\\"')
                    i += 1
            else:
                result.append(c)
                i += 1
    
    fixed_text = ''.join(result)
    return json.loads(fixed_text)

print("Loading File 2...")
f2 = fix_json_with_inner_quotes('complete_merged_test_cases.json')
print(f"File 2: {len(f2)} items")

print("\nLoading File 3...")
with open('s52_modules_9_10_11_12_test_cases_complete.json', 'r', encoding='utf-8') as f:
    f3 = json.load(f)
print(f"File 3: {len(f3)} items")

# ========== Module mapping ==========
# Based on the case IDs:
# TC-PR1-TD-* -> TD管管理 (模块3)
# TC-PR1-WZ-* -> 物资流转 (模块8)
# TC-PR1-M6-* -> 地点管理 (模块6)
# TC-PR1-M7-* -> 定标记录 (模块7)
# TC-M9-* -> 质控任务 (模块9)
# TC-M10-* -> 异常TD任务 (模块10)
# TC-M11-* -> 角色权限 (模块11)
# TC-M12-* -> 其他变更 (模块12)

def get_module(case_id):
    if case_id.startswith('TC-PR1-TD'):
        return 'TD管管理'
    elif case_id.startswith('TC-PR1-WZ'):
        return '物资流转'
    elif case_id.startswith('TC-PR1-M6'):
        return '地点管理'
    elif case_id.startswith('TC-PR1-M7'):
        return '定标记录'
    elif case_id.startswith('TC-M9'):
        return '质控任务'
    elif case_id.startswith('TC-M10'):
        return '异常TD任务'
    elif case_id.startswith('TC-M11'):
        return '角色权限'
    elif case_id.startswith('TC-M12'):
        return '其他变更'
    return '未知模块'

def get_case_type(description, name, steps):
    """Determine case type from content."""
    combined = (description + ' ' + name).lower()
    if any(kw in combined for kw in ['边界', '边界值', '边界场景']):
        return '边界值测试'
    elif any(kw in combined for kw in ['异常', '错误', '无效', '不存在', '已停用', '空值', '必填', '校验']):
        return '异常测试'
    elif any(kw in combined for kw in ['权限']):
        return '权限测试'
    elif any(kw in combined for kw in ['安全']):
        return '安全测试'
    elif any(kw in combined for kw in ['性能', '并发']):
        return '性能测试'
    else:
        return '功能测试'

def convert_steps_to_text(test_case_steps):
    """Convert test_case_steps array to step/result text."""
    steps_list = []
    results_list = []
    for s in test_case_steps:
        steps_list.append(s.get('step', ''))
        results_list.append(s.get('result', ''))
    steps_text = '\n'.join(steps_list)
    results_text = '\n'.join(results_list)
    return steps_text, results_text

# ========== Convert File 2 items (test_case_steps format) ==========
all_cases = []

for item in f2:
    name = item.get('name', '')
    # Extract case ID from name (before the colon)
    case_id = name.split(':')[0].strip() if ':' in name else name
    
    # Convert test_case_steps to text
    steps_text = ''
    results_text = ''
    if 'test_case_steps' in item and item['test_case_steps']:
        steps_text, results_text = convert_steps_to_text(item['test_case_steps'])
    
    case = {
        '用例编号': case_id,
        '所属模块': get_module(case_id),
        '用例标题': name,
        '优先级': item.get('priority', 'medium'),
        '前置条件': item.get('preconditions', ''),
        '测试步骤': steps_text,
        '预期结果': results_text,
        '用例类型': get_case_type(item.get('description', ''), name, item.get('test_case_steps', []))
    }
    all_cases.append(case)

# ========== Convert File 3 items (already has 用例编号/测试步骤/预期结果 format) ==========
for item in f3:
    case_id = item.get('用例编号', '')
    
    case = {
        '用例编号': case_id,
        '所属模块': get_module(case_id),
        '用例标题': item.get('用例标题', ''),
        '优先级': item.get('优先级', 'medium'),
        '前置条件': item.get('前置条件', ''),
        '测试步骤': item.get('测试步骤', ''),
        '预期结果': item.get('预期结果', ''),
        '用例类型': get_case_type(item.get('用例标题', ''), item.get('用例标题', ''), [])
    }
    all_cases.append(case)

print(f"\nTotal merged cases: {len(all_cases)}")

# Count by module
from collections import Counter
module_counts = Counter(c['所属模块'] for c in all_cases)
print("\n=== By Module ===")
for module, count in sorted(module_counts.items()):
    print(f"  {module}: {count}")

# Count by priority
priority_counts = Counter(c['优先级'] for c in all_cases)
print("\n=== By Priority ===")
for p, count in sorted(priority_counts.items()):
    print(f"  {p}: {count}")

# Output the full JSON
output_path = 'merged_all_test_cases_final.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(all_cases, f, ensure_ascii=False, indent=2)
print(f"\nOutput written to: {output_path}")
print(f"File size: {len(json.dumps(all_cases, ensure_ascii=False, indent=2))} chars")
