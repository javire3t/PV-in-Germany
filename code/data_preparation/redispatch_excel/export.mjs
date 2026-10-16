import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const specs = JSON.parse(await fs.readFile(path.join(root, 'data/work/redispatch_excel_tables.json'), 'utf8'));
const wb = Workbook.create();
let tableIndex = 0;
for (const spec of specs) {
  const ws = wb.worksheets.add(spec.name);
  ws.showGridLines = false;
  const n = spec.rows.length, m = spec.rows[0].length;
  ws.getRangeByIndexes(0, 0, n, m).values = spec.rows;
  const body = ws.getRangeByIndexes(0, 0, n, m);
  body.format.font = { name: 'Arial', size: 10, color: '#24343D' };
  body.format.rowHeight = 22;
  body.format.verticalAlignment = 'center';
  ws.getRangeByIndexes(0, 0, 1, m).format = {
    fill: '#294757', font: { name: 'Arial', size: 10, color: '#FFFFFF', bold: true },
    rowHeight: 42, wrapText: true, horizontalAlignment: 'center', verticalAlignment: 'center'
  };
  for (let j = 0; j < m; j++) {
    const header = spec.rows[0][j];
    const col = ws.getRangeByIndexes(0, j, n, 1);
    col.format.columnWidth = /source_url|source$|scope_note/.test(header) ? 60 : /state|reason|status|scope/.test(header) ? 34 : 24;
    if (n > 1) {
      const data = ws.getRangeByIndexes(1, j, n - 1, 1);
      if (spec.rows.slice(1).every(r => r[j] === null || typeof r[j] === 'number')) {
        data.setNumberFormat(/share/.test(header) ? '0.0%' : /year|page|count|sum|pixels/.test(header) ? '0' : '#,##0.00');
        data.format.horizontalAlignment = 'right';
      }
    }
  }
  if (spec.name === 'Overview') {
    ws.getRangeByIndexes(0, 0, n, 1).format.columnWidth = 28;
    ws.getRangeByIndexes(0, 1, n, 1).format.columnWidth = 110;
    ws.getRangeByIndexes(1, 1, n - 1, 1).format.wrapText = true;
    ws.getRangeByIndexes(1, 0, n - 1, 2).format.rowHeight = 40;
  } else {
    ws.freezePanes.freezeRows(1);
    const table = ws.tables.add(ws.getRangeByIndexes(0, 0, n, m), true, `RedispatchTable${++tableIndex}`);
    table.showFilterButton = true;
  }
  const include = spec.rows[0].indexOf('included');
  if (include >= 0) for (let i = 1; i < n; i++) {
    if (!spec.rows[i][include]) ws.getRangeByIndexes(i, 0, 1, m).format.fill = '#E2E2E2';
  }
}
wb.recalculate();
console.log((await wb.inspect({kind:'region', sheetId:'Compare 2016-2021', range:'A1:G7', maxChars:1500})).ndjson);
const preview = await wb.render({sheetName:'North and South', range:'A1:H9', scale:1.25, format:'png'});
await fs.writeFile(path.join(root, 'data/work/redispatch_excel_preview.png'), new Uint8Array(await preview.arrayBuffer()));
const xlsx = await SpreadsheetFile.exportXlsx(wb);
const out = path.join(root, 'results/excel/redispatch_curtailment.xlsx');
await xlsx.save(out);
try {
  await fs.rename(`${out}.inspect.ndjson`, path.join(root, 'data/work/redispatch_curtailment.xlsx.inspect.ndjson'));
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
console.log(out);
