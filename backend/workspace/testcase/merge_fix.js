const fs = require('fs');
const p = 'D:\\project\\ai-test-agent\\backend\\workspace\\testcase\\';

function fixJson(str) {
  let result = '';
  let inString = false;
  for (let i = 0; i < str.length; i++) {
    const ch = str[i];
    if (ch === '"' && !inString) {
      inString = true;
      result += ch;
    } else if (ch === '"' && inString) {
      // Check if this is the closing quote of a string value
      let nextIdx = i + 1;
      while (nextIdx < str.length && (str[nextIdx] === ' ' || str[nextIdx] === '\n' || str[nextIdx] === '\t' || str[nextIdx] === '\r')) nextIdx++;
      if (nextIdx < str.length && (str[nextIdx] === ',' || str[nextIdx] === '}' || str[nextIdx] === ']')) {
        inString = false;
        result += ch;
      } else {
        // This is an unescaped quote inside a string value
        result += '\\"';
      }
    } else {
      result += ch;
    }
  }
  return result;
}

let t1 = fs.readFileSync(p + 'modules_1_2_4_5_updated.json', 'utf8');
let t2 = fs.readFileSync(p + 'merged_all_test_cases_final.json', 'utf8');
t1 = fixJson(t1);
t2 = fixJson(t2);

const f1 = JSON.parse(t1);
const f2 = JSON.parse(t2);
const merged = f1.concat(f2);

console.log('文件1:', f1.length, '条');
console.log('文件2:', f2.length, '条');
console.log('合并后:', merged.length, '条');

const counts = {};
merged.forEach(tc => {
  const mod = tc['所属模块'] || '未知';
  counts[mod] = (counts[mod] || 0) + 1;
});
Object.entries(counts).forEach(([k, v]) => console.log('  ' + k + ': ' + v + '条'));

fs.writeFileSync(p + 'merged_final_all.json', JSON.stringify(merged, null, 2), 'utf8');
console.log('已写入 merged_final_all.json');
