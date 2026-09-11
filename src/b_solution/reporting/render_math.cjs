// Render display equations with MathJax; source LaTeX stays in report.md.
const fs = require('fs');
const path = require('path');
function dependency(name) {
  try { return require(name); }
  catch (e) {
    const root = process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES;
    if (!root) throw e;
    return require(path.join(root, name));
  }
}
const {mathjax} = dependency('mathjax-full/js/mathjax.js');
const {TeX} = dependency('mathjax-full/js/input/tex.js');
const {SVG} = dependency('mathjax-full/js/output/svg.js');
const {liteAdaptor} = dependency('mathjax-full/js/adaptors/liteAdaptor.js');
const {RegisterHTMLHandler} = dependency('mathjax-full/js/handlers/html.js');
const {AllPackages} = dependency('mathjax-full/js/input/tex/AllPackages.js');
const sharp = dependency('sharp');
const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
const mathdoc = mathjax.document('', {InputJax: new TeX({packages: AllPackages}), OutputJax: new SVG({fontCache: 'local'})});
async function main() {
  const tasks = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const result = [];
  for (const task of tasks) {
    const html = adaptor.outerHTML(mathdoc.convert(task.latex, {display: true}));
    if (html.includes('data-mml-node="merror"')) throw new Error('MathJax equation error: ' + task.latex);
    let svg = html.slice(html.indexOf('<svg'), html.indexOf('</svg>') + 6);
    if (!svg.includes('xmlns=')) svg = svg.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ');
    let widthPx = 0;
    svg = svg.replace(/(width|height)="([0-9.]+)(ex|em)"/g, (_, attribute, number, unit) => {
      const px = parseFloat(number) * (unit === 'ex' ? 7.5 : 16.7);
      if (attribute === 'width') widthPx = px;
      return `${attribute}="${px}px"`;
    }).replace(/currentColor/g, '#000000');
    await sharp(Buffer.from(svg), {density: 360}).png().toFile(task.path);
    result.push({path: task.path, width_inches: widthPx / 96});
  }
  fs.writeFileSync(process.argv[3], JSON.stringify(result, null, 2));
}
main().catch(error => { console.error(error); process.exit(1); });
