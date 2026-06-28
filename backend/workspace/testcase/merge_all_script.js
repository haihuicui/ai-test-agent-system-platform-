const fs = require('fs');
const path = 'D:\\project\\ai-test-agent\\backend\\workspace\\testcase\\';
const f1 = JSON.parse(fs.readFileSync(path + 'modules_1_2_4_5_updated.json', 'utf-8'));
const f2 = JSON.parse(fs.readFileSync(path + 'merged_all_test_cases_final.json', 'utf-8'));
const merged = f1.concat(f2);
console.log('文件1:', f1.length, '条');
console.log('文件2:', f2.length, '条');
console.log('合并后:', merged.length, '条');
const counts = {};
merged.forEach(tc => {
  const mod = tc['所属模块'] || '未知';
  counts[mod] = (counts[mod] || 0) + 1;
});
Object.entries(counts).forEach(([k,v]) => console.log('  ' + k + ': ' + v + '条'));
fs.writeFileSync(path + 'merged_final_all.json', JSON.stringify(merged, null, 2), 'utf-8');
console.log('已写入 merged_final_all.json');
