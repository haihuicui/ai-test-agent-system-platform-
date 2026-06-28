import json
import re

def fix_json_with_inner_quotes(filepath):
    """Fix JSON that has unescaped double quotes inside string values.
    
    The strategy: parse the file manually, tracking when we're inside a string value,
    and escape any unescaped double quotes that appear within string content.
    """
    with open(filepath, 'rb') as f:
        data = f.read()
    text = data.decode('utf-8')
    
    result = []
    i = 0
    in_string = False
    string_start = -1
    
    while i < len(text):
        c = text[i]
        
        if not in_string:
            if c == '"':
                in_string = True
                string_start = i
            result.append(c)
            i += 1
        else:
            # We're inside a string
            if c == '\\':
                # Escape sequence - skip next char
                result.append(c)
                i += 1
                if i < len(text):
                    result.append(text[i])
                    i += 1
            elif c == '"':
                # Check if this is the end of the string
                # Look ahead to see if next non-whitespace is , or ] or } or :
                j = i + 1
                while j < len(text) and text[j] in ' \t\n\r':
                    j += 1
                if j < len(text) and text[j] in ',:]}':
                    # This is the closing quote
                    in_string = False
                    result.append(c)
                    i += 1
                else:
                    # This is an inner quote - escape it
                    result.append('\\"')
                    i += 1
            else:
                result.append(c)
                i += 1
    
    fixed_text = ''.join(result)
    
    try:
        return json.loads(fixed_text)
    except json.JSONDecodeError as e:
        print(f"Error at line {e.lineno}, col {e.colno}")
        lines = fixed_text.split('\n')
        if e.lineno - 1 < len(lines):
            line = lines[e.lineno - 1]
            print(f"Line: {repr(line[max(0,e.colno-30):e.colno+30])}")
        return None

# Fix and parse file 1
print("=== File 1: all_merged_test_cases.json ===")
f1 = fix_json_with_inner_quotes('all_merged_test_cases.json')
if f1:
    print(f"Parsed OK: {len(f1)} items")
    for item in f1:
        name = item.get('name', '')
        print(f"  {name[:60]}...")

print("\n=== File 2: complete_merged_test_cases.json ===")
f2 = fix_json_with_inner_quotes('complete_merged_test_cases.json')
if f2:
    print(f"Parsed OK: {len(f2)} items")
    for item in f2:
        name = item.get('name', '')
        print(f"  {name[:60]}...")

# File 3
print("\n=== File 3: s52_modules_9_10_11_12_test_cases_complete.json ===")
with open('s52_modules_9_10_11_12_test_cases_complete.json', 'r', encoding='utf-8') as f:
    f3 = json.load(f)
print(f"Parsed OK: {len(f3)} items")
