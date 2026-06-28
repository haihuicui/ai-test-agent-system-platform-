const fs = require('fs');  
const p = 'D:\\project\\ai-test-agent\\backend\\workspace\\testcase\\';  
const f1 = JSON.parse(fs.readFileSync(p + 'modules_1_2_4_5_updated.json', 'utf8'));  
const f2 = JSON.parse(fs.readFileSync(p + 'merged_all_test_cases_final.json', 'utf8'));  
const merged = f1.concat(f2);  
console.log('文件1:', f1.length, '条');  
console.log('文件2:', f2.length, '条');  
console.log('合并后:', merged.length, '条');  
const counts = {};  
