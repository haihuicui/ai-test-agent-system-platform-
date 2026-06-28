import json

# Load all three files
with open('all_merged_test_cases.json', 'r', encoding='utf-8') as f:
    file1 = json.load(f)

with open('complete_merged_test_cases.json', 'r', encoding='utf-8') as f:
    file2 = json.load(f)

with open('s52_modules_9_10_11_12_test_cases_complete.json', 'r', encoding='utf-8') as f:
    file3 = json.load(f)

print(f"File 1: {len(file1)} items")
print(f"File 2: {len(file2)} items")
print(f"File 3: {len(file3)} items")

# Show first and last items
print(f"\nFile 1 first: {file1[0].get('name', file1[0].get('用例编号', 'N/A'))}")
print(f"File 1 last: {file1[-1].get('name', file1[-1].get('用例编号', 'N/A'))}")

print(f"\nFile 2 first: {file2[0].get('name', file2[0].get('用例编号', 'N/A'))}")
print(f"File 2 last: {file2[-1].get('name', file2[-1].get('用例编号', 'N/A'))}")

print(f"\nFile 3 first: {file3[0].get('name', file3[0].get('用例编号', 'N/A'))}")
print(f"File 3 last: {file3[-1].get('name', file3[-1].get('用例编号', 'N/A'))}")

# Check for duplicates between file1 and file2
names1 = set()
for item in file1:
    name = item.get('name', item.get('用例编号', ''))
    names1.add(name)

names2 = set()
for item in file2:
    name = item.get('name', item.get('用例编号', ''))
    names2.add(name)

names3 = set()
for item in file3:
    name = item.get('name', item.get('用例编号', ''))
    names3.add(name)

overlap_12 = names1 & names2
overlap_13 = names1 & names3
overlap_23 = names2 & names3

print(f"\nOverlap between File 1 and File 2: {len(overlap_12)} items")
if overlap_12:
    for n in sorted(overlap_12):
        print(f"  - {n}")

print(f"\nOverlap between File 1 and File 3: {len(overlap_13)} items")
if overlap_13:
    for n in sorted(overlap_13):
        print(f"  - {n}")

print(f"\nOverlap between File 2 and File 3: {len(overlap_23)} items")
if overlap_23:
    for n in sorted(overlap_23):
        print(f"  - {n}")

# Show the keys of items in each file
print(f"\nFile 1 item keys (sample): {list(file1[0].keys())}")
print(f"File 2 item keys (sample): {list(file2[0].keys())}")
print(f"File 3 item keys (sample): {list(file3[0].keys())}")
