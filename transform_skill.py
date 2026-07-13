import re

FILE = r'd:\project\ai-test-agent\.claude\skills\api\generator\SKILL.md'

with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Global replacements
content = content.replace('const BASE_URL = process.env.API_BASE_URL;', "const BASE_URL = (process.env.API_BASE_URL || '').trim();")
content = content.replace('async ({ request })', 'async ()')
content = content.replace('response.status()', 'response.status')
content = content.replace('getResponse.status()', 'getResponse.status')


def find_matching_paren(text, start):
    """Find index right after the matching closing parenthesis. start is the index after the opening paren."""
    depth = 1
    i = start
    in_string = False
    string_char = None
    while i < len(text) and depth > 0:
        c = text[i]
        if in_string:
            if c == '\\':
                i += 2
                continue
            if c == string_char:
                in_string = False
        else:
            if c in "'\"`":
                in_string = True
                string_char = c
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
        i += 1
    return i


def find_top_level_comma(s):
    depth = 0
    in_string = False
    string_char = None
    for i, c in enumerate(s):
        if in_string:
            if c == '\\':
                continue
            if c == string_char:
                in_string = False
        else:
            if c in "'\"`":
                in_string = True
                string_char = c
            elif c in '({[<':
                depth += 1
            elif c in ')}]>':
                depth -= 1
            elif c == ',' and depth == 0:
                return i
    return -1


def parse_options(s):
    s = s.strip()
    if not (s.startswith('{') and s.endswith('}')):
        return {}
    s = s[1:-1].strip()
    items = {}
    depth = 0
    in_string = False
    string_char = None
    start = 0
    i = 0
    while i < len(s):
        c = s[i]
        if in_string:
            if c == '\\':
                i += 2
                continue
            if c == string_char:
                in_string = False
        else:
            if c in "'\"`":
                in_string = True
                string_char = c
            elif c in '({[<':
                depth += 1
            elif c in ')}]>':
                depth -= 1
            elif c == ':' and depth == 0:
                key = s[start:i].strip()
                value_start = i + 1
                vd = 0
                v_in_string = False
                v_string_char = None
                j = value_start
                while j < len(s):
                    vc = s[j]
                    if v_in_string:
                        if vc == '\\':
                            j += 2
                            continue
                        if vc == v_string_char:
                            v_in_string = False
                    else:
                        if vc in "'\"`":
                            v_in_string = True
                            v_string_char = vc
                        elif vc in '({[<':
                            vd += 1
                        elif vc in ')}]>':
                            vd -= 1
                        elif vc == ',' and vd == 0:
                            break
                    j += 1
                value = s[value_start:j].strip()
                items[key] = value
                start = j + 1
                i = j
        i += 1
    return items


def trim_url(url_expr):
    return re.sub(r'\$\{BASE_URL\}', r"${BASE_URL.replace(/\\/$/, '')}", url_expr)


def make_url_assignment(url_expr, method, options):
    url_expr_trimmed = trim_url(url_expr)

    if method == 'GET' and 'params' in options:
        params_val = options['params']
        if params_val.startswith('{') and params_val.endswith('}'):
            inner = params_val[1:-1].strip()
            pairs = []
            depth = 0
            in_string = False
            string_char = None
            start = 0
            for i, c in enumerate(inner):
                if in_string:
                    if c == '\\':
                        continue
                    if c == string_char:
                        in_string = False
                else:
                    if c in "'\"`":
                        in_string = True
                        string_char = c
                    elif c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                    elif c == ',' and depth == 0:
                        pairs.append(inner[start:i].strip())
                        start = i + 1
            pairs.append(inner[start:].strip())
            entries = []
            for pair in pairs:
                if ':' in pair:
                    k, v = pair.split(':', 1)
                    k = k.strip()
                    v = v.strip()
                    if not (v.startswith("'") or v.startswith('"') or v.startswith('`')):
                        v = f'String({v})'
                    entries.append(f'  {k}: {v}')
            return [
                'const queryParams = new URLSearchParams({',
                ',\n'.join(entries),
                '}).toString();',
                f'const url = `{url_expr_trimmed[2:-1]}?${{queryParams}}`;'
            ]
        else:
            return [
                f'const queryParams = new URLSearchParams({params}).toString();',
                f'const url = `{url_expr_trimmed[2:-1]}?${{queryParams}}`;'
            ]

    if url_expr.startswith('`') and url_expr.endswith('`'):
        return [f'const url = `{url_expr_trimmed[2:-1]}`;']
    return [f'const url = {url_expr_trimmed};']


def transform_statement(prefix, method, text, call_start, call_end):
    """Transform a full `const response = await request.METHOD(...)` statement."""
    args_text = text[call_start:call_end - 1]
    comma_idx = find_top_level_comma(args_text)
    if comma_idx == -1:
        url_expr = args_text.strip()
        options_text = '{}'
    else:
        url_expr = args_text[:comma_idx].strip()
        options_text = args_text[comma_idx + 1:].strip()

    options = parse_options(options_text)

    url_lines = make_url_assignment(url_expr, method, options)

    # Handle multipart file upload
    if 'multipart' in options:
        multipart = options['multipart']
        name_match = re.search(r"name:\s*['\"`]([^'\"`]+)['\"`]", multipart)
        mime_match = re.search(r"mimeType:\s*['\"`]([^'\"`]+)['\"`]", multipart)
        file_name = name_match.group(1) if name_match else 'test.txt'
        mime_type = mime_match.group(1) if mime_match else 'text/plain'
        form_lines = [
            "const formData = new FormData();",
            f"formData.append('file', new Blob(['file content'], {{ type: '{mime_type}' }}), '{file_name}');"
        ]
        headers = options.get('headers', '{ }')
        fetch_call = f"fetch(url, {{ method: 'POST', headers: {headers}, body: formData }})"
        all_lines = form_lines + url_lines + [f'{prefix}{fetch_call}']
        return '\n    '.join(all_lines)

    fetch_options = [f"method: '{method}'"]
    if 'headers' in options:
        fetch_options.append(f"headers: {options['headers']}")
    if 'data' in options:
        fetch_options.append(f"body: JSON.stringify({options['data']})")

    fetch_options_str = ', '.join(fetch_options)
    fetch_call = f'fetch(url, {{ {fetch_options_str} }})'
    all_lines = url_lines + [f'{prefix}{fetch_call}']
    return '\n    '.join(all_lines)


# Match full statements like: const response = await request.get(...)
stmt_pattern = re.compile(r'(const\s+\w+\s+=\s+await\s+)request\.(get|post|put|patch|delete)\s*\(', re.IGNORECASE)

matches = list(stmt_pattern.finditer(content))
for match in reversed(matches):
    prefix = match.group(1)
    method = match.group(2).upper()
    call_start = match.end()
    call_end = find_matching_paren(content, call_start)
    replacement = transform_statement(prefix, method, content, call_start, call_end)
    content = content[:match.start()] + replacement + content[call_end:]

with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print('Transformation complete.')
print(f'Replaced {len(matches)} request.* statements.')
