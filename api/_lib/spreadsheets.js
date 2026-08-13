// =====================================================================================
// spreadsheets.js — تحويلات البيانات الجدولية: Excel / CSV / JSON
// =====================================================================================

const XLSX = require('xlsx');
const { parseCsv, badRequest } = require('./validation');

function sendFile(res, buffer, contentType, filename) {
  res.setHeader('Content-Type', contentType);
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  return res.status(200).send(buffer);
}

const handlers = {
  async 'text-to-excel'({ res, text }) {
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(text.split('\n').map((l) => l.split(/[\t,]/)));
    XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
    const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
    return sendFile(res, buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'converted.xlsx');
  },

  async 'json-to-excel'({ res, text, json }) {
    const data = JSON.parse(json || text);
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.json_to_sheet(Array.isArray(data) ? data : [data]);
    XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
    const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
    return sendFile(res, buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'converted.xlsx');
  },

  async 'excel-to-json'({ res, fileBase64 }) {
    if (!fileBase64) return badRequest(res, 'No file provided');
    const wb = XLSX.read(Buffer.from(fileBase64, 'base64'), { type: 'buffer' });
    const data = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
    return res.status(200).json({ result: JSON.stringify(data, null, 2) });
  },

  async 'csv-to-json'({ res, text }) {
    const rows = parseCsv(text);
    const headers = rows[0];
    const data = rows.slice(1).map((r) =>
      headers.reduce((acc, h, i) => {
        acc[h.trim()] = (r[i] || '').trim();
        return acc;
      }, {})
    );
    return res.status(200).json({ result: JSON.stringify(data, null, 2) });
  },

  async 'text-to-csv'({ res, text }) {
    const buf = Buffer.from('\uFEFF' + text, 'utf-8');
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', 'attachment; filename="converted.csv"');
    return res.status(200).send(buf);
  },

  async 'word-to-csv'({ res, text }) {
    const buf = Buffer.from('\uFEFF' + text, 'utf-8');
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', 'attachment; filename="converted.csv"');
    return res.status(200).send(buf);
  },
};

module.exports = { handlers };
