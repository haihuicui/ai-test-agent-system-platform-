const fs = require('fs');
const path = require('path');

const cwd = process.cwd();
const raw = fs.readFileSync(path.join(cwd, 'all_137_test_cases.json'), 'utf-8');

// The JSON has unescaped ASCII double quotes inside string values
// Let's fix them by replacing Chinese curly quotes approach
// Actually, let's just use a simple approach: parse by counting braces

function repairAndParse(jsonStr) {
    // Replace Chinese left/right double quotes with a placeholder
    // \u201c = " (LEFT DOUBLE QUOTATION MARK)
    // \u201d = " (RIGHT DOUBLE QUOTATION MARK)
    // These are valid in JSON strings, so they should be fine
    
    // The issue is ASCII double quotes (0x22) inside string values
    // Let's find them and escape them
    
    let result = '';
    let inString = false;
    let escape = false;
    
    for (let i = 0; i < jsonStr.length; i++) {
        const ch = jsonStr[i];
        const code = ch.charCodeAt(0);
        
        if (escape) {
            result += ch;
            escape = false;
            continue;
        }
        
        if (ch === '\\') {
            result += ch;
            escape = true;
            continue;
        }
        
        if (code === 0x22) { // ASCII double quote
            if (inString) {
                // Check if this is actually the end of the string
                // Look ahead to see if next non-whitespace is a valid JSON token
                let j = i + 1;
                while (j < jsonStr.length && (jsonStr[j] === ' ' || jsonStr[j] === '\t' || jsonStr[j] === '\n' || jsonStr[j] === '\r')) {
                    j++;
                }
                const next = jsonStr[j];
                if (next === ',' || next === ']' || next === '}' || next === ':') {
                    // This is a real string terminator
                    result += ch;
                    inString = false;
                } else {
                    // This is an unescaped quote inside a string - escape it
                    result += '\\' + ch;
                }
            } else {
                result += ch;
                inString = true;
            }
        } else {
            result += ch;
        }
    }
    
    return JSON.parse(result);
}

const data = repairAndParse(raw);
console.log('Total items:', data.length);

// Batch 1: first 50
const b1 = data.slice(0, 50);
fs.writeFileSync(path.join(cwd, 'batch1.json'), JSON.stringify(b1, null, 2), 'utf-8');
console.log('batch1.json: ' + b1.length + ' items');

// Batch 2: items 51-100
const b2 = data.slice(50, 100);
fs.writeFileSync(path.join(cwd, 'batch2.json'), JSON.stringify(b2, null, 2), 'utf-8');
console.log('batch2.json: ' + b2.length + ' items');

// Batch 3: items 101-137
const b3 = data.slice(100);
fs.writeFileSync(path.join(cwd, 'batch3.json'), JSON.stringify(b3, null, 2), 'utf-8');
console.log('batch3.json: ' + b3.length + ' items');

// Verify
const v1 = JSON.parse(fs.readFileSync(path.join(cwd, 'batch1.json'), 'utf-8'));
const v2 = JSON.parse(fs.readFileSync(path.join(cwd, 'batch2.json'), 'utf-8'));
const v3 = JSON.parse(fs.readFileSync(path.join(cwd, 'batch3.json'), 'utf-8'));
console.log('---');
console.log('Verified - batch1: ' + v1.length + ', batch2: ' + v2.length + ', batch3: ' + v3.length);
console.log('Total: ' + (v1.length + v2.length + v3.length));
