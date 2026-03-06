const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
    AlignmentType, BorderStyle, WidthType, ShadingType, UnderlineType } = require('/tmp/docx_npm/node_modules/docx');
const fs = require('fs');

const data = JSON.parse(fs.readFileSync('__JSON_PATH__', 'utf8'));

const bn = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const nb = { top: bn, bottom: bn, left: bn, right: bn };

function p(text, o) {
    o = o || {};
    return new Paragraph({
        spacing: { after: o.after !== undefined ? o.after : 120, before: o.before || 0 },
        alignment: o.align || AlignmentType.LEFT,
        children: [new TextRun({ text: text, bold: o.bold || false, size: o.size || 22,
            font: 'Arial', color: o.color || '000000',
            underline: o.underline ? { type: UnderlineType.SINGLE } : undefined,
            italics: o.italic || false })]
    });
}

function pr(runs, o) {
    o = o || {};
    return new Paragraph({
        spacing: { after: o.after !== undefined ? o.after : 120, before: o.before || 0 },
        alignment: o.align || AlignmentType.LEFT,
        children: runs.map(function(r) {
            return new TextRun({ text: r.text, bold: r.bold || false, size: r.size || 22,
                font: 'Arial', color: r.color || '000000',
                underline: r.underline ? { type: UnderlineType.SINGLE } : undefined,
                italics: r.italic || false });
        })
    });
}

function div() {
    return new Paragraph({ spacing: { after: 160, before: 160 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: '1A5276', space: 1 } },
        children: [] });
}

function sh(text) {
    return new Paragraph({ spacing: { after: 100, before: 240 },
        children: [new TextRun({ text: text.toUpperCase(), bold: true, size: 20,
            font: 'Arial', color: '1A5276', characterSpacing: 40 })] });
}

function ir(label, value) {
    return new TableRow({ children: [
        new TableCell({ width: { size: 2800, type: WidthType.DXA }, borders: nb,
            margins: { top: 60, bottom: 60, left: 0, right: 120 },
            children: [new Paragraph({ children: [new TextRun({ text: label, bold: true, size: 20, font: 'Arial', color: '555555' })] })] }),
        new TableCell({ width: { size: 200, type: WidthType.DXA }, borders: nb,
            margins: { top: 60, bottom: 60, left: 0, right: 0 },
            children: [new Paragraph({ children: [new TextRun({ text: ':', bold: true, size: 20, font: 'Arial', color: '555555' })] })] }),
        new TableCell({ width: { size: 6638, type: WidthType.DXA }, borders: nb,
            margins: { top: 60, bottom: 60, left: 120, right: 0 },
            children: [new Paragraph({ children: [new TextRun({ text: String(value || ''), size: 20, font: 'Arial' })] })] }),
    ]});
}

var oc = { 'Verbal Warning': 'E67E22', 'Written Warning': 'E67E22', 'Final Warning': 'C0392B',
    'Suspension': '8E44AD', 'Demotion': '8E44AD', 'Termination': 'C0392B', 'Cleared / No Action': '1E8449' };
var col = oc[data.decision_outcome] || '1A5276';

var extra = [];
if (data.termination_type) extra.push(ir('Termination Type', data.termination_type));
if (data.notice_period) extra.push(ir('Notice Period', data.notice_period));
if (data.suspension_days) extra.push(ir('Suspension Duration', data.suspension_days + ' days (' + data.suspension_with_pay + ')'));
if (data.warning_expiry) extra.push(ir('Warning Active Until', data.warning_expiry));

var obox = [
    new Paragraph({ spacing: { after: 60 }, children: [
        new TextRun({ text: data.decision_outcome.toUpperCase(), bold: true, size: 28, font: 'Arial', color: col })] }),
    new Paragraph({ children: [
        new TextRun({ text: 'Issued under Ethiopian Labour Proclamation No. 1156/2019', size: 18, font: 'Arial', color: '777777', italics: true })] }),
];

function sigRow(n1, t1, n2, t2) {
    return new Table({ width: { size: 9638, type: WidthType.DXA }, columnWidths: [4319, 1000, 4319],
        rows: [new TableRow({ children: [
            new TableCell({ borders: nb, children: [
                new Paragraph({ border: { top: { style: BorderStyle.SINGLE, size: 4, color: '1A5276' } },
                    children: [new TextRun({ text: n1, bold: true, size: 22, font: 'Arial' })] }),
                p(t1, { size: 20, color: '555555', after: 0 }),
                p(data.org_name, { size: 20, color: '555555' }) ] }),
            new TableCell({ borders: nb, children: [p('')] }),
            new TableCell({ borders: nb, children: [
                new Paragraph({ border: { top: { style: BorderStyle.SINGLE, size: 4, color: '1A5276' } },
                    children: [new TextRun({ text: n2, bold: true, size: 22, font: 'Arial' })] }),
                p(t2, { size: 20, color: '555555', after: 0 }),
                p('Witness', { size: 20, color: '555555' }) ] }),
        ]})] });
}

var empSig = new Table({ width: { size: 9638, type: WidthType.DXA }, columnWidths: [4319, 1000, 4319],
    rows: [new TableRow({ children: [
        new TableCell({ borders: nb, children: [
            new Paragraph({ border: { top: { style: BorderStyle.SINGLE, size: 4, color: 'AAAAAA' } },
                children: [new TextRun({ text: data.employee_name, bold: true, size: 22, font: 'Arial' })] }),
            p('Employee Signature & Date', { size: 18, color: '777777' }) ] }),
        new TableCell({ borders: nb, children: [p('')] }),
        new TableCell({ borders: nb, children: [
            new Paragraph({ border: { top: { style: BorderStyle.SINGLE, size: 4, color: 'AAAAAA' } },
                children: [new TextRun({ text: ' ', size: 22, font: 'Arial' })] }),
            p('Date Received', { size: 18, color: '777777' }) ] }),
    ]})] });

var children = [
    new Paragraph({ spacing: { after: 0 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: data.org_name.toUpperCase(), bold: true, size: 36, font: 'Arial', color: '1A5276' })] }),
    new Paragraph({ spacing: { after: 0 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: [data.org_address, data.org_phone, data.org_email].filter(Boolean).join('  |  '), size: 16, font: 'Arial', color: '777777' })] }),
    new Paragraph({ spacing: { after: 240, before: 80 },
        border: { bottom: { style: BorderStyle.THICK, size: 12, color: '1A5276', space: 1 } }, children: [] }),
    new Paragraph({ spacing: { after: 60, before: 80 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: 'DISCIPLINARY DECISION LETTER', bold: true, size: 28, font: 'Arial', color: '1A5276' })] }),
    new Paragraph({ spacing: { after: 0 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: 'Decision: ' + data.decision_outcome.toUpperCase(), bold: true, size: 24, font: 'Arial', color: col })] }),
    div(),
    new Table({ width: { size: 9638, type: WidthType.DXA }, columnWidths: [4819, 4819],
        rows: [new TableRow({ children: [
            new TableCell({ borders: nb, margins: { top: 0, bottom: 0, left: 0, right: 0 },
                children: [pr([{ text: 'Ref: ', bold: true, size: 20, color: '555555' }, { text: data.ref_number, size: 20 }], { after: 0 })] }),
            new TableCell({ borders: nb, margins: { top: 0, bottom: 0, left: 0, right: 0 },
                children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
                    new TextRun({ text: 'Date: ' + data.letter_date, size: 20, font: 'Arial', color: '555555' })] })] }),
        ]})] }),
    p('', { after: 160 }),
    p('TO:', { bold: true, size: 20, color: '555555', after: 60 }),
    p(data.employee_name, { bold: true }),
    p(data.employee_position + (data.employee_department ? ' — ' + data.employee_department : ''), { size: 20, color: '555555', after: 60 }),
    p('Employee ID: ' + data.employee_id, { size: 20, color: '555555', after: 200 }),
    new Paragraph({ spacing: { after: 200 }, children: [
        new TextRun({ text: 'SUBJECT: ', bold: true, size: 22, font: 'Arial' }),
        new TextRun({ text: 'NOTICE OF DISCIPLINARY DECISION — ' + data.decision_outcome.toUpperCase(),
            bold: true, size: 22, font: 'Arial', underline: { type: UnderlineType.SINGLE }, color: col }) ] }),
    div(),
    p('Dear ' + data.employee_name + ',', { after: 160 }),
    new Paragraph({ spacing: { after: 200 }, children: [
        new TextRun({ text: 'This letter serves as formal notification of the disciplinary decision reached by ' + data.org_name + ' following a thorough review of the incident that occurred on ' + data.incident_date + ', concerning: ', size: 22, font: 'Arial' }),
        new TextRun({ text: data.offense + '.', size: 22, font: 'Arial', bold: true }) ] }),
    sh('Case Details'),
    new Table({ width: { size: 9638, type: WidthType.DXA }, columnWidths: [2800, 200, 6638],
        rows: [ir('Case Reference', data.ref_number), ir('Incident Date', data.incident_date),
            ir('Nature of Offense', data.offense), ir('Employee', data.employee_name),
            ir('Position', data.employee_position + (data.employee_department ? ', ' + data.employee_department : ''))] }),
    p('', { after: 120 }),
    sh('Disciplinary Decision'),
    new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: 'Having considered all relevant facts and evidence, the decision of ', size: 22, font: 'Arial' }),
        new TextRun({ text: data.org_name, size: 22, font: 'Arial', bold: true }),
        new TextRun({ text: ' is as follows:', size: 22, font: 'Arial' }) ] }),
    new Table({ width: { size: 9638, type: WidthType.DXA }, columnWidths: [9638],
        rows: [new TableRow({ children: [new TableCell({
            borders: { top: { style: BorderStyle.THICK, size: 8, color: col },
                bottom: { style: BorderStyle.SINGLE, size: 2, color: 'CCCCCC' },
                left: { style: BorderStyle.THICK, size: 8, color: col },
                right: { style: BorderStyle.SINGLE, size: 2, color: 'CCCCCC' } },
            shading: { fill: 'F8F9FA', type: ShadingType.CLEAR },
            margins: { top: 160, bottom: 160, left: 200, right: 200 },
            children: obox }) ] })] }),
];

if (extra.length) {
    children.push(p('', { after: 40 }));
    children.push(new Table({ width: { size: 9638, type: WidthType.DXA }, columnWidths: [2800, 200, 6638], rows: extra }));
}

children = children.concat([
    p('', { after: 80 }),
    sh('Rationale for Decision'),
    new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: data.rationale, size: 22, font: 'Arial' })] }),
    sh('Expected Conduct Going Forward'),
    new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ size: 22, font: 'Arial',
        text: 'You are hereby required to comply fully with all workplace policies, procedures, and the terms of your employment contract. Any recurrence of similar misconduct will result in further disciplinary action, up to and including termination of employment in accordance with Article 27 or Article 28 of the Ethiopian Labour Proclamation No. 1156/2019.' })] }),
    sh('Your Right to Appeal'),
    new Paragraph({ spacing: { after: 200 }, children: [
        new TextRun({ text: 'In accordance with Ethiopian Labour Proclamation No. 1156/2019, you have the right to appeal this decision within ', size: 22, font: 'Arial' }),
        new TextRun({ text: '15 working days', size: 22, font: 'Arial', bold: true }),
        new TextRun({ text: ' of the date of this notice' + (data.appeal_deadline ? ' (deadline: ' + data.appeal_deadline + ')' : '') + '. To appeal, submit your written grounds to the Human Resources department.', size: 22, font: 'Arial' }) ] }),
    div(),
    sh('Authorized By'),
    p('', { after: 400 }),
    sigRow(data.hr_name, data.hr_title, data.witness_name, data.witness_title),
    p('', { after: 200 }),
    sh('Employee Acknowledgment of Receipt'),
    new Paragraph({ spacing: { after: 160 }, children: [new TextRun({
        text: 'I, the undersigned, acknowledge that I have received and read this disciplinary decision letter. Acknowledgment of receipt does not imply acceptance of the decision.',
        size: 20, font: 'Arial', italics: true, color: '555555' })] }),
    p('', { after: 400 }),
    empSig,
    new Paragraph({ spacing: { before: 400, after: 0 }, alignment: AlignmentType.CENTER,
        border: { top: { style: BorderStyle.SINGLE, size: 2, color: 'CCCCCC', space: 1 } },
        children: [new TextRun({ text: 'This document is issued under the authority of ' + data.org_name + ' in accordance with Ethiopian Labour Proclamation No. 1156/2019. Confidential HR Document.', size: 16, font: 'Arial', italics: true, color: '999999' })] }),
]);

var doc = new Document({
    styles: { default: { document: { run: { font: 'Arial', size: 22 } } } },
    sections: [{ properties: { page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1134, right: 1134, bottom: 1134, left: 1134 }
    } }, children: children }]
});

Packer.toBuffer(doc).then(function(buffer) {
    fs.writeFileSync('__OUTPUT_PATH__', buffer);
    console.log('OK');
});