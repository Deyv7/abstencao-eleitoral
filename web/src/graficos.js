// Gráficos em SVG dos cartões "Tudo junto" e "Aprendizado de máquina".
// Os valores vêm de resumo.json; aqui só se desenha.
import { animate, stagger } from 'motion';
import { formatar } from './dados.js';

const NS = 'http://www.w3.org/2000/svg';
function el(tag, attrs = {}, pai) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (pai) pai.appendChild(e);
  return e;
}
function texto(pai, x, y, conteudo, attrs = {}) {
  const t = el('text', { x, y, ...attrs }, pai);
  t.textContent = conteudo;
  return t;
}
const sinal = (v, f) => (v > 0 ? '+' : v < 0 ? '−' : '') + formatar(Math.abs(v), f);

// Rótulos curtos para as linhas do gráfico de coeficientes.
const CURTO = {
  pct_baixa_escolaridade: 'Analfabeto ou só lê e escreve',
  log2_aptos: 'Tamanho do eleitorado',
  pct_70_mais: '70 anos ou mais',
  pct_feminino: 'Eleitorado feminino',
  razao_aptos_populacao: 'Eleitores por habitante',
  log2_pib_per_capita: 'PIB per capita',
  pct_superior: 'Superior completo',
  pct_16_17: '16 e 17 anos',
  log2_densidade: 'Densidade demográfica',
  'regiao_Centro-Oeste': 'Centro-Oeste',
  regiao_Norte: 'Norte',
  regiao_Sul: 'Sul',
  regiao_Nordeste: 'Nordeste',
};

export function graficoCoeficientes(fig, regressao) {
  const vars = [...regressao.variaveis].sort((a, b) => b.q13 - a.q13)
    .map((v) => ({ rotulo: CURTO[v.termo] || v.descricao, c: v.q13, ic: v.q13_ic, p: v.p }));
  const regs = [...regressao.regioes].sort((a, b) => b.coef - a.coef)
    .map((v) => ({ rotulo: CURTO[v.termo] || v.descricao, c: v.coef, ic: v.ic, p: v.p }));

  const W = 560, rotX = 168, valX = 520, lin = 26, topoG = 22;
  const linhas = [{ grupo: 'Do 1º ao 3º quartil' }, ...vars, { grupo: 'Região, comparada ao Sudeste' }, ...regs];
  const H = topoG + linhas.length * lin + 18;
  const todos = [...vars, ...regs].flatMap((d) => d.ic);
  const min = Math.min(0, ...todos), max = Math.max(0, ...todos);
  const x0 = rotX + 14, x1 = valX - 46;
  const sx = (v) => x0 + ((v - min) / (max - min)) * (x1 - x0);

  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img' });
  el('line', { x1: sx(0), x2: sx(0), y1: 8, y2: H - 14, class: 'zero' }, svg);
  for (const t of [-6, -4, -2, 0, 2, 4]) {
    if (t < min || t > max) continue;
    texto(svg, sx(t), H - 2, (t > 0 ? '+' : t < 0 ? '−' : '') + Math.abs(t), { class: 'mono', 'text-anchor': 'middle' });
  }
  const animaveis = [];
  linhas.forEach((d, i) => {
    const y = topoG + i * lin;
    if (d.grupo) {
      texto(svg, 0, y + 4, d.grupo, { class: 'grupo' });
      return;
    }
    const sig = d.p < 0.05;
    const g = el('g', { class: sig ? 'sig' : 'nsig' }, svg);
    texto(g, rotX, y + 4, d.rotulo, { 'text-anchor': 'end', style: `fill: ${sig ? 'var(--tinta)' : 'var(--apagado)'}` });
    const ic = el('line', { x1: sx(d.ic[0]), x2: sx(d.ic[1]), y1: y, y2: y, class: 'ic' }, g);
    const ponto = el('circle', { cx: sx(d.c), cy: y, r: 4.5, class: 'ponto' }, g);
    texto(g, W, y + 4, sinal(d.c, 'dec1'), { class: 'mono', 'text-anchor': 'end', style: `fill: ${sig ? 'var(--acento)' : 'var(--apagado)'}` });
    animaveis.push({ ic, ponto });
  });
  fig.appendChild(svg);
  return () => {
    animate(animaveis.map((a) => a.ic), { transform: ['scaleX(0)', 'scaleX(1)'], opacity: [0, 1] },
      { duration: 0.7, delay: stagger(0.05), ease: [0.22, 1, 0.36, 1] });
    animate(animaveis.map((a) => a.ponto), { transform: ['scale(0)', 'scale(1)'] },
      { type: 'spring', bounce: 0.25, visualDuration: 0.45, delay: stagger(0.05, { startDelay: 0.25 }) });
  };
}

export function graficoModelos(fig, modelos) {
  const nomes = [['media', 'Média (referência)'], ['regressao_linear', 'Regressão linear'],
    ['gradient_boosting', 'Gradient boosting'], ['random_forest', 'Random forest']];
  const W = 560, rotX = 150, lin = 40, topo = 40;
  const H = topo + nomes.length * lin + 22;
  const min = -0.05, max = 0.6;
  const x0 = rotX + 16, x1 = W - 70;
  const sx = (v) => x0 + ((Math.max(v, min) - min) / (max - min)) * (x1 - x0);

  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img' });
  const chave = el('g', {}, svg);
  el('circle', { cx: x0 + 4, cy: 10, r: 5, class: 'kfold' }, chave);
  texto(chave, x0 + 16, 14, 'municípios misturados', { class: 'chave' });
  el('circle', { cx: x0 + 200, cy: 10, r: 5, class: 'gkf' }, chave);
  texto(chave, x0 + 212, 14, 'estado inteiro fora do treino', { class: 'chave' });
  texto(svg, W, topo - 8, 'erro, estado fora', { class: 'grupo', 'text-anchor': 'end' });

  for (const t of [0, 0.2, 0.4, 0.6]) {
    el('line', { x1: sx(t), x2: sx(t), y1: topo - 4, y2: H - 18, class: t === 0 ? 'zero' : 'eixo' }, svg);
    texto(svg, sx(t), H - 2, formatar(t, 'dec1'), { class: 'mono', 'text-anchor': 'middle' });
  }
  const ligacoes = [], pontosK = [], pontosG = [];
  nomes.forEach(([k, rot], i) => {
    const y = topo + i * lin + 12;
    const kf = modelos.kfold[k], gk = modelos.groupkfold_uf[k];
    texto(svg, rotX, y + 4, rot, { 'text-anchor': 'end', style: 'fill: var(--tinta)' });
    ligacoes.push(el('line', { x1: sx(gk.r2), x2: sx(kf.r2), y1: y, y2: y, class: 'ligacao ic' }, svg));
    pontosK.push(el('circle', { cx: sx(kf.r2), cy: y, r: 5.5, class: 'kfold ponto' }, svg));
    pontosG.push(el('circle', { cx: sx(gk.r2), cy: y, r: 5.5, class: 'gkf ponto' }, svg));
    texto(svg, W, y + 4, `${formatar(gk.mae, 'dec1')} p.p.`, { class: 'mono', 'text-anchor': 'end', style: 'fill: var(--acento)' });
  });
  texto(svg, x0 + (x1 - x0) / 2, H + 14, 'R²', { class: 'mono', 'text-anchor': 'middle' });
  svg.setAttribute('viewBox', `0 0 ${W} ${H + 18}`);
  fig.appendChild(svg);
  return () => {
    animate(pontosK, { transform: ['scale(0)', 'scale(1)'] }, { type: 'spring', bounce: 0.2, visualDuration: 0.4, delay: stagger(0.08) });
    animate(ligacoes, { transform: ['scaleX(0)', 'scaleX(1)'], opacity: [0, 1] }, { duration: 0.6, delay: stagger(0.08, { startDelay: 0.3 }), ease: [0.22, 1, 0.36, 1] });
    animate(pontosG, { transform: ['scale(0)', 'scale(1)'] }, { type: 'spring', bounce: 0.2, visualDuration: 0.4, delay: stagger(0.08, { startDelay: 0.55 }) });
  };
}
