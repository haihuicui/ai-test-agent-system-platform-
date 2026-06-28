const fs = require('fs');
const p = 'D:\\project\\ai-test-agent\\backend\\workspace\\testcase\\';

function fix(s) {
  let r = '';
  let n = false;
  for (let i = 0; i < s.length; i++) {
    let c = s[i];
    if (c === '"' && !n) {
      n = true;
      r += c;
    } else if (c === '"' && n) {
      let j = i + 1;
      while (j < s.length && (s[j] === ' ' || s[j] === '\n' || s[j] === '\t' || s[j] === '\r')) j++;
      if (j < s.length && (s[j] === ',' || s[j] === '}' || s[j] === ']')) {
        n = false;
        r += c;
      } else {
        r += '\\"';
      }
    } else {
      r += c;
    }
  }
  return r;
}

let t1 = fs.readFileSync(p + 'modules_1_2_4_5_updated.json', 'utf8');
let t2 = fs.readFileSync(p + 'merged_all_test_cases_final.json', 'utf8');
t1 = fix(t1);
t2 = fix(t2);

const f1 = JSON.parse(t1);
const f2 = JSON.parse(t2);
const m = f1.concat(f2);

console.log('File1: ' + f1.length);
console.log('File2: ' + f2.length);
console.log('Merged: ' + m.length);

fs.writeFileSync(p + 'merged_final_all.json', JSON.stringify(m, null, 2), 'utf8');
console.log('Done');
