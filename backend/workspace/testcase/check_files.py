import json

# Check file 3 first (it should be valid JSON since it uses 用例编号 format)
with open('s52_modules_9_10_11_12_test_cases_complete.json', 'rb') as f:
    data3 = f.read()
text3 = data3.decode('utf-8')
lines3 = text3.split('\n')
print(f"File 3 line 3: {repr(lines3[2][:80])}")
print(f"File 3 size: {len(data3)} bytes")

# Try to parse file 3
try:
    f3 = json.loads(text3)
    print(f"File 3 parsed OK: {len(f3)} items")
except json.JSONDecodeError as e:
    print(f"File 3 parse error: {e}")

# Check file 1
with open('all_merged_test_cases.json', 'rb') as f:
    data1 = f.read()
text1 = data1.decode('utf-8')
print(f"\nFile 1 size: {len(data1)} bytes")
print(f"File 1 line 3: {repr(text1.split(chr(10))[2][:80])}")

# Check file 2
with open('complete_merged_test_cases.json', 'rb') as f:
    data2 = f.read()
text2 = data2.decode('utf-8')
print(f"\nFile 2 size: {len(data2)} bytes")
print(f"File 2 line 3: {repr(text2.split(chr(10))[2][:80])}")
