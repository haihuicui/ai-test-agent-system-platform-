const fs = require('fs');

const basePath = 'D:/project/ai-test-agent/backend/workspace/testcase/';

const d1 = JSON.parse(fs.readFileSync(basePath + 'modules_1_2_4_5.json', 'utf8'));
const d2 = JSON.parse(fs.readFileSync(basePath + 'merged_all_test_cases_final.json', 'utf8'));

const merged = d1.concat(d2);

fs.writeFileSync(basePath + 'all_135_test_cases.json', JSON.stringify(merged, null, 2), 'utf8');

console.log('文件1用例数:', d1.length);
console.log('文件2用例数:', d2.length);
console.log('合并后总用例数:', merged.length);
