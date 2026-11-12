// Build ASRC_Presentation_2026_11_09.pptx (reports/weekly/): latest results deck.
// Usage: NODE_PATH=<dir with pptxgenjs> node build_presentation_2026_11_09.js [path/to/apply_theme.js]
const path = require('path');
const fs = require('fs');
const pptxgen = require('pptxgenjs');

const HERE = __dirname;
const ROOT = path.resolve(HERE, '..', '..');
const STUDY = path.join(ROOT, 'simulations', 'u4m2');
const BB = path.join(STUDY, 'backbone_20261108', 'results');
const OUT = path.join(ROOT, 'reports', 'weekly', 'ASRC_Presentation_2026_11_09.pptx');
const DATA = JSON.parse(fs.readFileSync(path.join(HERE, 'presentation_2026_11_09_chartdata.json'), 'utf8'));

const THEME = {
  name: 'ASRC Fuel Tank',
  headFontFace: 'Cambria',
  bodyFontFace: 'Calibri',
  colors: {
    dk1: '1F2933', lt1: 'FFFFFF', dk2: '14213D', lt2: 'E8EEF4',
    accent1: '2A9D8F', accent2: 'F2A541', accent3: 'D1495B', accent4: '3A6EA5',
    accent5: '8D99AE', accent6: '6A4C93', hlink: '3A6EA5', folHlink: '6A4C93',
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.333 x 7.5 in
pres.author = 'ASRC';
pres.title = 'ASRC fuel tank robot: NiTi backbone results';
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, H = 7.5;
const FOOT = 'ASRC fuel tank inspection robot  ·  Simulation results 6–9 November 2026';

// ---------- layouts
pres.defineSlideMaster({
  title: 'TITLE_DARK',
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.8, y: 2.1, w: 11.7, h: 1.8, fontSize: 40, bold: true, color: C.background1, valign: 'bottom', align: 'left', margin: 0 }, text: '' } },
    { placeholder: { options: { name: 'body', type: 'body', x: 0.8, y: 4.15, w: 11.7, h: 1.2, fontSize: 20, color: C.background2, valign: 'top', align: 'left', margin: 0 }, text: '' } },
  ],
});
pres.defineSlideMaster({
  title: 'CONTENT',
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.6, y: 0.35, w: 12.1, h: 0.9, fontSize: 32, bold: true, color: C.text2, valign: 'middle', align: 'left', margin: 0 }, text: '' } },
    { text: { text: FOOT, options: { x: 0.6, y: 7.0, w: 9, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.accent5, align: 'right' },
});
pres.defineSlideMaster({
  title: 'CONTENT_DARK',
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.6, y: 0.35, w: 12.1, h: 0.9, fontSize: 32, bold: true, color: C.background1, valign: 'middle', align: 'left', margin: 0 }, text: '' } },
    { text: { text: FOOT, options: { x: 0.6, y: 7.0, w: 9, h: 0.3, fontSize: 10, color: C.background2, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.background2, align: 'right' },
});

// ---------- helpers
function fitImage(slide, file, px, x, y, w, h, name) {
  const ar = px[0] / px[1];
  let iw = w, ih = w / ar;
  if (ih > h) { ih = h; iw = h * ar; }
  slide.addImage({ path: file, x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih, objectName: name, altText: name });
}
function card(slide, x, y, w, h, fill, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: fill }, objectName: name });
}
function stat(slide, x, y, w, big, label, opts = {}) {
  const fg = opts.fg || C.text2, sub = opts.sub || C.text1;
  const bh = opts.bh || 0.95;
  slide.addText(big, { x, y, w, h: bh, fontFace: THEME.headFontFace, fontSize: opts.size || 44, bold: true, color: fg, margin: 0, isTextBox: true, objectName: 'stat ' + big });
  slide.addText(label, { x, y: y + bh, w, h: opts.lh || 0.9, fontSize: 14, color: sub, margin: 0, valign: 'top', isTextBox: true, objectName: 'stat label ' + big });
}
function bullets(slide, items, x, y, w, h, opts = {}) {
  const runs = items.map((t, i) => {
    const parts = Array.isArray(t) ? t : [{ text: t }];
    return parts.map((p, j) => ({ text: p.text, options: Object.assign({ bold: !!p.bold }, j === 0 ? { bullet: true } : {}, j === parts.length - 1 && i < items.length - 1 ? { breakLine: true } : {}) }));
  }).flat();
  slide.addText(runs, { x, y, w, h, fontSize: opts.size || 16, color: opts.color || C.text1, valign: 'top', paraSpaceAfter: 8, margin: 0, isTextBox: true, objectName: opts.name || 'bullets' });
}
function caption(slide, text, x, y, w) {
  slide.addText(text, { x, y, w, h: 0.35, fontSize: 11, italic: true, color: C.accent5, margin: 0, isTextBox: true, objectName: 'caption' });
}
const chartText = { catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt', legendFontFace: '+mn-lt', titleFontFace: '+mn-lt',
  catAxisTitleFontFace: '+mn-lt', valAxisTitleFontFace: '+mn-lt', catAxisLabelColor: HEX.dk1, valAxisLabelColor: HEX.dk1,
  catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, legendFontSize: 11, catAxisTitleFontSize: 12, valAxisTitleFontSize: 12,
  catAxisTitleColor: HEX.dk1, valAxisTitleColor: HEX.dk1, titleColor: HEX.dk2 };

// ---------- 1. title
pres.addSection({ title: 'Overview' });
let s = pres.addSlide({ masterName: 'TITLE_DARK', sectionTitle: 'Overview' });
s.addText('A NiTi backbone makes the U4+M2 front work', { placeholder: 'title' });
s.addText('ASRC fuel tank inspection robot  ·  Simulation results, 6–9 November 2026', { placeholder: 'body' });
s.addNotes('This deck summarises three days of simulation work on the flexible front of the fuel tank inspection robot. The headline: adding a thin NiTi rod down the centre of the soft M modules turns a front that could not hold itself straight into one that straightens, enters the tank and steers at the working angle with small rope forces. Everything shown is simulation; the physical module tests are next.');

// ---------- 2. key message
s = pres.addSlide({ masterName: 'CONTENT_DARK', sectionTitle: 'Overview' });
s.addText('One design change fixes both blocking problems', { placeholder: 'title' });
const stats2 = [
  ['0.1%', 'axial strain to hold the front straight (was 17%)'],
  ['180°', 'yaw with the head held at the 20° working angle (was none)'],
  ['7–15 N', 'peak rope force for that sweep, smooth 5° steps'],
  ['≥ 12.6 mm', 'clearance to the full 3D tank during the sweep'],
];
stats2.forEach(([b, l], i) => {
  const x = 0.6 + i * 3.08;
  card(s, x, 1.75, 2.85, 2.6, C.background1, 'stat card ' + i);
  stat(s, x + 0.25, 2.05, 2.4, b, l, { size: 34, lh: 1.2, bh: 0.85 });
});
s.addText([
  { text: 'The change: ', options: { bold: true } },
  { text: 'a 1.8 mm superelastic NiTi rod down the centre of each M module (+1.6 g per module).' },
], { x: 0.6, y: 4.75, w: 12.1, h: 0.5, fontSize: 18, color: C.background1, margin: 0, isTextBox: true, objectName: 'change line' });
s.addText('Rules that come with it: install at 20°, keep ≥ 1 N on every rope, control rope length (not tension). All results are simulations with calculated rod properties; module tests are next.',
  { x: 0.6, y: 5.4, w: 12.1, h: 0.9, fontSize: 16, color: C.background2, margin: 0, valign: 'top', isTextBox: true, objectName: 'rules line' });
s.addNotes('Four numbers summarise the result. Before the change, the front needed 17 percent axial strain to straighten, far beyond the 5 percent diagnostic, and it could not hold the head near the working angle at all. With the rod, straightening needs about 0.1 percent strain; the head can be swept through 180 degrees of yaw while held at 20 degrees; the largest rope force in that sweep is 7 to 15 newtons; and the whole sweep stays at least 12.6 mm clear of the real 3D tank. Three operating rules come with it, which I will explain.');

// ---------- 3. concept
pres.addSection({ title: 'Problem' });
s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Problem' });
s.addText('Concept: a tendon-driven front fed through the tank floor', { placeholder: 'title' });
fitImage(s, path.join(HERE, 'figures', 'overall_mechanism.png'), [2200, 1400], 0.5, 1.4, 7.6, 5.4, 'installation concept');
card(s, 8.4, 1.5, 4.3, 5.2, C.background2, 'spec card');
bullets(s, [
  [{ text: 'Targets: ', bold: true }, { text: '500 g camera + thermography head, ~1.5 m reach, Ø < 100 mm' }],
  [{ text: 'Front: ', bold: true }, { text: 'U4+M2, Ø63 mm, 96 mm modules' }],
  [{ text: 'U modules: ', bold: true }, { text: 'PA12 + NiTi, stiff against gravity' }],
  [{ text: 'M modules: ', bold: true }, { text: 'PA12, compliant for steering' }],
  [{ text: 'Actuation: ', bold: true }, { text: 'up to 3 anchor sets × 4 ropes, 24 mm from the axis, driven from the base' }],
  [{ text: 'Rear: ', bold: true }, { text: 'telescopic, axial motion only, locked angle' }],
], 8.65, 1.75, 3.85, 4.8, { size: 15, name: 'spec bullets' });
s.addNotes('The robot is mounted outside the tank on an independent stand. A telescopic rear feeds the flexible front through a bottom access opening along a locked oblique axis. The front is four stiff U modules followed by two compliant M modules, 63 mm diameter, steered by ropes anchored at module ends and driven from the base. The head is a 500 g sensor package.');

// ---------- 4. problem
s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Problem' });
s.addText('6 November: the front could not hold the head up', { placeholder: 'title' });
const probs = [
  ['17%', 'axial strain needed to straighten the front; the diagnostic limit is 5%'],
  ['−66°', 'head elevation at maximum yaw: the head points down, not at the target'],
  ['770×', 'U module axial stiffness relative to M (128,122 N vs 167 N)'],
];
probs.forEach(([b, l], i) => {
  const x = 0.6 + i * 4.1;
  card(s, x, 1.6, 3.8, 2.6, C.background2, 'problem card ' + i);
  stat(s, x + 0.3, 1.85, 3.2, b, l, { fg: C.accent3, size: 48, lh: 1.2 });
});
s.addText([
  { text: 'Why: ', options: { bold: true } },
  { text: 'ropes that lift the head also squeeze the M modules. At 5% strain an M module carries only about 8 N, while holding the head up needs about 39 N of rope force. Every lifting rope crushes M instead of lifting the head.' },
], { x: 0.6, y: 4.6, w: 12.1, h: 1.3, fontSize: 18, color: C.text1, margin: 0, valign: 'top', isTextBox: true, objectName: 'why text' });
caption(s, 'Source: Report 6 November 2026, U4+M2 at 20°, 500 g head.', 0.6, 6.4, 12.1);
s.addNotes('On 6 November we found two blocking problems. Straightening the front needed 17 percent axial strain, and when steering, the best low-strain pose had the head pointing 66 degrees down. Both trace to one number: the M module is about 770 times softer axially than the U module. Ropes pull along the outside of the modules, so lifting the head also compresses M, and M simply collapses.');

// ---------- 5. root cause
pres.addSection({ title: 'Fix' });
s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Fix' });
s.addText('Stiffening M axially alone is not enough', { placeholder: 'title' });
fitImage(s, path.join(STUDY, 'm_axial_sweep_20261108', 'results', 'm_stiffness_requirement.png'), [2125, 816], 0.6, 1.35, 12.1, 4.65, 'EA EI sweep figure');
bullets(s, [
  [{ text: 'Axial stiffness alone ', bold: true }, { text: 'straightens the front but leaves a 7° angle error: between anchors, the head weight bends each soft M module.' }],
  [{ text: 'First combination that passes: ', bold: true }, { text: 'M axial stiffness ×5 (≈ 830 N) and bending stiffness ×1.25 (≈ 0.055 N·m²), anchors at modules 4, 5, 6.' }],
], 0.6, 6.05, 12.1, 0.9, { size: 14, name: 'sweep bullets' });
s.addNotes('To find what M actually needs, we scaled only the M module stiffness in the existing solver. Raising axial stiffness alone gets the offset down to 3 mm but leaves a 7 degree angle error that never goes away, because between anchor points the head weight bends the soft M module. A hand calculation gives the same 7 degrees. The first combination that passes every check is five times the axial stiffness plus 25 percent more bending stiffness.');

// ---------- 6. the fix
s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Fix' });
s.addText('The fix: a 1.8 mm NiTi rod down the centre of each M module', { placeholder: 'title' });
const rows6 = [
  ['Property (per M module)', 'Current M', 'M + rod, E 40 GPa', 'M + rod, E 75 GPa', 'Needed'],
  ['Axial stiffness EA, N', '167', '101,954', '191,018', '≥ 833'],
  ['Bending stiffness EI, N·m²', '0.044', '0.065', '0.083', '≥ 0.055'],
  ['Mass, g', '23.9', '25.5', '25.5', '—'],
];
s.addTable(rows6.map((r, i) => r.map((c, j) => ({ text: c, options: {
  bold: i === 0 || j === 0, color: i === 0 ? HEX.lt1 : HEX.dk1, fill: { color: i === 0 ? HEX.dk2 : (i % 2 ? HEX.lt1 : HEX.lt2) },
  fontSize: 15, align: j === 0 ? 'left' : 'center', valign: 'middle' } }))),
  { x: 0.6, y: 1.55, w: 7.6, colW: [2.6, 1.15, 1.35, 1.35, 1.15], rowH: 0.55, border: { type: 'solid', pt: 0.5, color: HEX.lt2 }, objectName: 'rod property table' });
caption(s, 'E 40–75 GPa brackets the uncertain NiTi phase (martensite to austenite). Values calculated, not measured.', 0.6, 3.9, 7.6);
const fixes = [
  ['Guides every 24 mm', 'Rod buckles at 353 N (40 GPa) vs a 248 N design load'],
  ['Rod ends carry load', 'End fittings must pass 250 N into the anchor disks without slip'],
  ['Small penalty', '+1.6 g per module; surface strain 1.5% at a 180° bend'],
];
fixes.forEach(([t, d], i) => {
  const y = 1.55 + i * 1.65;
  card(s, 8.7, y, 4.0, 1.45, C.background2, 'fix card ' + i);
  s.addText(t, { x: 8.95, y: y + 0.15, w: 3.5, h: 0.45, fontSize: 18, bold: true, color: C.text2, margin: 0, isTextBox: true, objectName: 'fix title ' + i });
  s.addText(d, { x: 8.95, y: y + 0.62, w: 3.5, h: 0.75, fontSize: 14, color: C.text1, margin: 0, valign: 'top', isTextBox: true, objectName: 'fix text ' + i });
});
s.addText('The rod raises axial stiffness about 600× while adding only 50–90% bending stiffness, so M stays steerable.',
  { x: 0.6, y: 4.5, w: 7.6, h: 1.0, fontSize: 18, color: C.text2, bold: true, margin: 0, valign: 'top', isTextBox: true, objectName: 'rod message' });
s.addNotes('The proposed implementation is a superelastic NiTi rod of 1.8 mm diameter down the centre of each M module, fixed to the module end disks. It meets both requirements with margin: hundreds of times the needed axial stiffness and 50 to 90 percent more bending stiffness. It needs internal guides every 24 mm to stop it buckling, and the rod end joints become critical parts. A 1.5 mm rod would be marginal at the low modulus.');

// ---------- 7. straight + entry
pres.addSection({ title: 'Results' });
s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Results' });
s.addText('Straight at 0.1% strain, and it now enters the tank', { placeholder: 'title' });
fitImage(s, path.join(BB, 'entry_screen.png'), [2125, 833], 0.6, 1.3, 12.1, 4.45, 'entry screen figure');
const st7 = [['1–2 mm', 'offset from the straight axis at 15–25°'], ['0.1%', 'axial strain (current M: 17%)'], ['47 / 65 / 19 mm', 'entry clearance in full 3D tank at 15 / 20 / 25°']];
st7.forEach(([b, l], i) => stat(s, 0.6 + i * 4.1, 5.85, 3.9, b, l, { size: 26, lh: 0.45, bh: 0.55 }));
s.addNotes('With the rod, the front holds itself straight with 1 to 2 mm offset at only 0.1 percent strain, at all three installation angles. Fed through the bottom opening, the straight shape now clears the tank; every low-strain shape on 6 November hit the tank. The left plot shows the rod shape at four feed positions in orange and the old shape hitting the tank in blue. The clearances were confirmed against the full 3D tank model.');

// ---------- 8. stability & control rules
s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Results' });
s.addText('Two control rules from the 3D stability checks', { placeholder: 'title' });
const rules = [
  ['Keep ≥ 1 N on every rope', 'With only the up ropes pulled, the straight front can buckle sideways in 3D; the 2D model could not see this. A 1 N pretension on all ropes makes every case stable, and straightening and entry still pass.', 'unstable → stable', 'with 1 N pretension'],
  ['Control rope length, not tension', 'With fixed rope tensions the straight front is unstable: adding 0.5 N to one rope makes the head snap 258 mm. With winch (length) control the ropes act as springs and the same pose is stable.', '258 mm', 'snap under tension control'],
];
rules.forEach(([t, d, b, l], i) => {
  const x = 0.6 + i * 6.2;
  card(s, x, 1.55, 5.9, 5.1, C.background2, 'rule card ' + i);
  s.addText(t, { x: x + 0.3, y: 1.8, w: 5.3, h: 0.6, fontSize: 22, bold: true, color: C.text2, margin: 0, isTextBox: true, objectName: 'rule title ' + i });
  s.addText(d, { x: x + 0.3, y: 2.5, w: 5.3, h: 2.2, fontSize: 16, color: C.text1, margin: 0, valign: 'top', isTextBox: true, objectName: 'rule text ' + i });
  stat(s, x + 0.3, 4.95, 5.3, b, l, { fg: i ? C.accent3 : C.accent1, size: 36, lh: 0.5 });
});
s.addNotes('Two operating rules came out of the 3D checks. First, the straight front with only the up ropes tensioned is laterally unstable in 3D, a mode the 2D model cannot show. One newton of pretension on every rope fixes it. Second, if the drives control rope tension directly, the straight pose is unstable: half a newton on one rope makes the head snap 258 mm. Under winch length control the same pose is stable. So the drives must be position-controlled, or use fast feedback.');

// ---------- 9. steering force (native chart)
s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Results' });
s.addText('Full yaw at the working angle needs only 7–15 N', { placeholder: 'title' });
s.addChart(pres.charts.LINE, DATA.force.series.map(([name, values]) => ({ name, labels: DATA.force.yaw.map(String), values })), Object.assign({
  x: 0.6, y: 1.4, w: 7.7, h: 5.3, objectName: 'peak force chart',
  chartColors: [HEX.accent1, HEX.accent4, HEX.accent2], lineSize: 2.5, lineDataSymbol: 'none',
  showTitle: true, title: 'Peak rope force, head held at 20°, 20° installation', titleFontSize: 14,
  showLegend: true, legendPos: 'b', showCatAxisTitle: true, catAxisTitle: 'Yaw, deg', showValAxisTitle: true, valAxisTitle: 'Largest rope tension, N',
  valAxisMinVal: 0, valAxisMaxVal: 25, valAxisMajorUnit: 5, catAxisLabelFrequency: 3,
  valGridLine: { color: HEX.lt2, size: 0.75 }, catGridLine: { style: 'none' },
}, chartText));
stat(s, 8.75, 1.6, 4.0, '7–15 N', 'peak rope force with anchors at modules 4, 5, 6 (8 Nov allocation: 46–98 N)', { size: 40, lh: 0.9 });
bullets(s, [
  'Yaw 0° → 175° in 5° steps, each solved from the previous pose',
  'Rope changes ≤ 5 N and head moves ≤ 56 mm per step: no jumps',
  'Up to ~60° the head pans almost horizontally; beyond ~90° the front curls up and over',
], 8.75, 3.7, 4.0, 3.0, { size: 15, name: 'force bullets' });
s.addNotes('Holding the head at exactly 20 degrees while stepping yaw from 0 to 175 degrees needs a largest rope force of only 7 to 15 newtons with anchors at modules 4, 5 and 6. Yesterday\'s allocations needed 46 to 98 newtons only because they maximised angle without minimising force. Each pose is solved from the previous one; rope tensions change by at most 5 newtons per step and the head moves smoothly. Up to about 60 degrees the head pans nearly horizontally; larger yaw is reached by curling the M section up and over.');

// ---------- 10. 3D tank (native chart)
s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Results' });
s.addText('The whole sweep fits inside the real 3D tank', { placeholder: 'title' });
s.addChart(pres.charts.LINE, DATA.clear.series.map(([name, values]) => ({ name, labels: DATA.clear.yaw.map(String), values })), Object.assign({
  x: 0.6, y: 1.4, w: 7.7, h: 5.3, objectName: 'tank clearance chart',
  chartColors: [HEX.accent1, HEX.accent4, HEX.accent2, HEX.accent3], lineSize: 2.5, lineDataSymbol: 'none',
  showTitle: true, title: 'Clearance to 3D tank during yaw to the right (rod 40 GPa, 20°)', titleFontSize: 14,
  showLegend: true, legendPos: 'b', showCatAxisTitle: true, catAxisTitle: 'Yaw, deg (head held at 20°)', showValAxisTitle: true, valAxisTitle: 'Minimum clearance, mm',
  valAxisMinVal: -10, valAxisMaxVal: 70, valAxisMajorUnit: 10, catAxisLabelFrequency: 3,
  valGridLine: { color: HEX.lt2, size: 0.75 }, catGridLine: { style: 'none' },
}, chartText));
stat(s, 8.75, 1.6, 4.0, '≥ 12.6 mm', 'clearance on both sides with the clamp 0–30 mm past the opening', { size: 40, lh: 0.9 });
bullets(s, [
  'All 362 tank solids meshed from the STEP model (461,524 triangles)',
  'Deeper clamping lifts the curled front into the tank roof',
  '25° installation hits the roof at every depth: use 20°',
], 8.75, 3.7, 4.0, 3.0, { size: 15, name: 'tank bullets' });
s.addNotes('We then placed every pose of that sweep inside the full 3D tank model, all 362 solids from the STEP file, and measured the gap to the 63 mm envelope. With the base clamp 0 to 30 mm past the opening, every pose clears by at least 12.6 mm on both sides. Clamping deeper lifts the curled front into the roof, which is the only limiting surface. At 25 degrees installation the sweep hits the roof at every depth, so 20 degrees is the angle to use.');

// ---------- 11. horizontal flexibility
s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Results' });
s.addText('Side ropes: the tip rope steers, but alone the head droops', { placeholder: 'title' });
fitImage(s, path.join(BB, 'sidepull.png'), [2380, 748], 0.6, 1.3, 12.1, 3.8, 'side pull figure');
const st11 = [['1.25°/mm', 'yaw per mm of tip rope reeled in, smooth and stable'], ['±20°', 'yaw before the head leaves 20 ± 5° when only one rope moves'], ['≈ 0', 'useful yaw from anchors 4 and 5 (they just compress the front)']];
st11.forEach(([b, l], i) => stat(s, 0.6 + i * 4.1, 5.3, 3.8, b, l, { size: 30, lh: 0.8, bh: 0.65 }));
s.addNotes('Here we started from the straight front and reeled in only one right-side rope with a winch. The rope at the tip is the effective actuator: about 1.25 degrees of yaw per millimetre, smooth and stable. But with the other ropes locked, the head droops; it leaves the working band after about 20 degrees. Larger yaw at the working angle needs the up ropes reeled in together, which is exactly what the coordinated sweep on the previous slides does. Ropes at modules 4 and 5 hardly turn the head.');

// ---------- 12. limitations
pres.addSection({ title: 'Wrap-up' });
s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Wrap-up' });
s.addText('What is not yet proven', { placeholder: 'title' });
const lim = [
  ['Rod properties', 'Stiffness, buckling and joint strength are calculated. NiTi phase state, hysteresis and fatigue are not modelled.'],
  ['Motion between poses', 'Poses are checked every 5°. States in between and real winch dynamics are not yet simulated.'],
  ['Head and cables', 'The 500 g head is a point mass with a 63 mm envelope. Real head CAD and cable routing are missing.'],
  ['Twist and friction', 'Mid-range yaw uses 30–55° of twist along the front. Rope friction is not modelled.'],
];
lim.forEach(([t, d], i) => {
  const x = 0.6 + (i % 2) * 6.2, y = 1.55 + Math.floor(i / 2) * 2.6;
  card(s, x, y, 5.9, 2.35, C.background2, 'limit card ' + i);
  s.addText(t, { x: x + 0.3, y: y + 0.2, w: 5.3, h: 0.5, fontSize: 20, bold: true, color: C.text2, margin: 0, isTextBox: true, objectName: 'limit title ' + i });
  s.addText(d, { x: x + 0.3, y: y + 0.8, w: 5.3, h: 1.4, fontSize: 16, color: C.text1, margin: 0, valign: 'top', isTextBox: true, objectName: 'limit text ' + i });
});
s.addNotes('To be clear about the evidence: everything is simulation with calculated rod properties. We have checked poses every 5 degrees but not the transitions or the winch dynamics. The head is a point mass with a provisional envelope, and mid-range yaw relies on 30 to 55 degrees of twist that hardware must confirm.');

// ---------- 13. decisions & next steps
s = pres.addSlide({ masterName: 'CONTENT_DARK', sectionTitle: 'Wrap-up' });
s.addText('Decisions and next steps', { placeholder: 'title' });
card(s, 0.6, 1.55, 5.9, 5.1, C.background1, 'decision card');
s.addText('Decisions', { x: 0.9, y: 1.8, w: 5.3, h: 0.5, fontSize: 22, bold: true, color: C.text2, margin: 0, isTextBox: true, objectName: 'decision title' });
bullets(s, [
  'Develop U4+M2 with a 1.8 mm NiTi rod in each M module',
  'Install at 20°; steer with the clamp 0–30 mm past the opening',
  'Keep ≥ 1 N on every rope; drive ropes by length (winch position)',
  'Longer fronts (U6+M3, U8+M4) are not viable with ≤ 3 anchor sets',
], 0.9, 2.45, 5.3, 4.0, { size: 16, name: 'decision bullets' });
const nexts = [
  ['1', 'Build and test the rod M module', 'stiffness, buckling, joint slip'],
  ['2', 'Coordinated winch-control test', 'smooth 0–175° at 20° between poses'],
  ['3', 'Tank-aware steering, twist limits', 'optimise poses with the tank as a constraint'],
  ['4', 'Head CAD, entry, storage, rear', 'then integrated validation'],
];
nexts.forEach(([n, t, d], i) => {
  const y = 1.55 + i * 1.3;
  s.addShape(pres.shapes.OVAL, { x: 6.9, y: y + 0.15, w: 0.75, h: 0.75, fill: { color: C.accent2 }, line: { color: C.accent2 }, objectName: 'step dot ' + n });
  s.addText(n, { x: 6.9, y: y + 0.15, w: 0.75, h: 0.75, fontSize: 22, bold: true, color: C.text2, align: 'center', valign: 'middle', margin: 0, isTextBox: true, objectName: 'step number ' + n });
  s.addText(t, { x: 7.9, y: y + 0.08, w: 4.8, h: 0.5, fontSize: 18, bold: true, color: C.background1, margin: 0, isTextBox: true, objectName: 'step title ' + n });
  s.addText(d, { x: 7.9, y: y + 0.58, w: 4.8, h: 0.45, fontSize: 15, color: C.background2, margin: 0, isTextBox: true, objectName: 'step text ' + n });
});
s.addNotes('We propose to adopt the NiTi rod design for U4+M2, install at 20 degrees, keep pretension on every rope and use length-controlled winches. Longer fronts are off the table for now. The physical rod module tests are the gate: if measured bending stiffness falls short, the fallback is a 2 mm rod or closer guides. In parallel we will simulate the coordinated winch motion between poses and add the tank as a constraint on steering.');

(async () => {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  await pres.writeFile({ fileName: OUT });
  const applyPath = process.argv[2];
  if (applyPath) {
    const { applyTheme } = require(applyPath);
    await applyTheme(OUT, THEME);
  }
  console.log('wrote', OUT);
})();
