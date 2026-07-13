import re

FILE = r'd:\project\ai-test-agent\.claude\skills\api\generator\SKILL.md'

with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the example dialogue block
start_marker = '// 步骤 3: 解析并生成测试代码'
end_marker = '// 步骤 4: 保存测试脚本'

start = content.find(start_marker)
end = content.find(end_marker)

if start == -1 or end == -1:
    print('ERROR: Could not find example dialogue markers')
    exit(1)

block = content[start:end]

# Replace each request.post with fetch

def repl(match):
    indent = match.group(1)
    inner_indent = indent + '  '
    options = match.group(2)
    headers_match = re.search(r'headers:\s*({[^}]+})', options, re.DOTALL)
    data_match = re.search(r'data:\s*({.*})\s*$', options, re.DOTALL)
    if not data_match:
        data_match = re.search(r'data:\s*({.*})\n', options, re.DOTALL)

    headers = headers_match.group(1) if headers_match else 'authHeaders'
    data = data_match.group(1) if data_match else '{}'

    url_line = inner_indent + "const url = `{BASE_URL.replace(/\\\\/$/, '')}/auth/login`;"
    fetch_lines = [
        inner_indent + "const response = await fetch(url, {",
        inner_indent + "  method: 'POST',",
        inner_indent + "  headers: " + headers + ",",
        inner_indent + "  body: JSON.stringify(" + data + ")",
        inner_indent + "});"
    ]
    return url_line + '\n' + '\n'.join(fetch_lines)

# In the file, the escaped backtick is represented as \\` (one backslash before backtick)
# In a Python regex string, to match a literal backslash we need \\\\ in the source
# Let's use a more flexible pattern that captures the escaping naturally
pattern = re.compile(r"(    )const response = await request\.post\((\\`\\\$\{BASE_URL\}/auth/login\\`),\s*({.*?})\);\s*", re.DOTALL)
new_block, count = pattern.subn(repl, block)

if count != 3:
    print(f'WARNING: Replaced {count} request.post calls, expected 3')

content = content[:start] + new_block + content[end:]

with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Example dialogue updated: {count} replacements')
