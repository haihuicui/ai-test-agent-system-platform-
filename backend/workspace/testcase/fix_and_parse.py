import json
import re

def fix_and_parse(filepath):
    """Fix the JSON by escaping inner double quotes in string values."""
    with open(filepath, 'rb') as f:
        data = f.read()
    text = data.decode('utf-8')
    
    # The issue is that Chinese text contains unescaped " inside JSON string values
    # Pattern: after a " that starts a value, any " that appears before the next , or } 
    #   and is followed by Chinese chars needs to be escaped
    # Better approach: parse line by line and fix
    
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Skip structural lines
        if stripped in ['[', ']', '{', '},', '}', ',']:
            fixed_lines.append(line)
            continue
        
        # For key-value lines, we need to handle the value part
        # Pattern: "key": "value with inner quotes",
        # We need to escape inner quotes in the value
        
        # Find the colon to split key and value
        colon_idx = line.find(':')
        if colon_idx == -1:
            fixed_lines.append(line)
            continue
        
        key_part = line[:colon_idx+1]
        value_part = line[colon_idx+1:]
        
        # The value part starts with " and ends with ", or ", 
        # We need to escape any " inside the value
        
        # Find the start of the value string (first " after :)
        first_quote = value_part.find('"')
        if first_quote == -1:
            fixed_lines.append(line)
            continue
        
        # Find the end - last " before , or end
        # The value ends with either ", or "
        value_start = first_quote + 1
        
        # Find the last quote that ends the value
        # It's either the last " before a comma, or the last "
        if value_part.rstrip().endswith('",'):
            last_quote = value_part.rstrip().rfind('"', 0, -1)  # second to last "
            # Actually find the last " that's followed by , or nothing
            last_quote = -1
            for i in range(len(value_part)-1, -1, -1):
                if value_part[i] == '"':
                    # Check if this is the closing quote
                    rest = value_part[i+1:].strip()
                    if rest == '' or rest.startswith(','):
                        last_quote = i
                        break
            
            if last_quote > value_start:
                inner = value_part[value_start:last_quote]
                # Escape any unescaped " in inner
                escaped_inner = inner.replace('"', '\\"')
                new_value_part = value_part[:value_start] + escaped_inner + value_part[last_quote:]
                line = key_part + new_value_part
        
        fixed_lines.append(line)
    
    fixed_text = '\n'.join(fixed_lines)
    
    try:
        result = json.loads(fixed_text)
        return result
    except json.JSONDecodeError as e:
        print(f"Still broken at line {e.lineno}, col {e.colno}")
        print(f"Context: {repr(fixed_text.split(chr(10))[e.lineno-1][max(0,e.colno-20):e.colno+20])}")
        return None

# Fix and parse file 1
print("=== File 1: all_merged_test_cases.json ===")
f1 = fix_and_parse('all_merged_test_cases.json')
if f1:
    print(f"Parsed OK: {len(f1)} items")
    for item in f1:
        name = item.get('name', '')
        print(f"  {name}")

print("\n=== File 2: complete_merged_test_cases.json ===")
f2 = fix_and_parse('complete_merged_test_cases.json')
if f2:
    print(f"Parsed OK: {len(f2)} items")
    for item in f2:
        name = item.get('name', '')
        print(f"  {name}")

# File 3
print("\n=== File 3: s52_modules_9_10_11_12_test_cases_complete.json ===")
with open('s52_modules_9_10_11_12_test_cases_complete.json', 'r', encoding='utf-8') as f:
    f3 = json.load(f)
print(f"Parsed OK: {len(f3)} items")
for item in f3:
    print(f"  {item.get('用例编号', '')}")
