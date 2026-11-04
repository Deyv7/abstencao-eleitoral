// Painel que abre ao clicar num município do mapa: leva ao estado dele e mostra por que
// a taxa do estado não é a do pico. Tudo sai de resumo.ufs e de municipios.json.
import { animate } from 'motion';
import { formatar, UF_NOMES, COR_DOMINIO } from './dados.js';

const NS = 'http://www.w3.org/2000/svg';
const RAMPA = ['#3d4fa8', '#7b4fb3', '#d0587e', '#f78f5a', '#fbd78a'];

// A mesma rampa de cor do mapa, para o gráfico falar a mesma língua.
function corAbst(pct) {
  const t = Math.min(Math.max((pct - COR_DOMINIO[0]) / (COR_DOMINIO[1] - COR_DOMINIO[0]), 0), 1) * 4;
  const k = Math.min(Math.floor(t), 3), f = t - k;
  const a = RAMPA[k], b = RAMPA[k + 1];
  const c = (h, i) => parseInt(h.slice(1 + i * 2, 3 + i * 2), 16);
  return `rgb(${[0, 1, 2].map((i) => Math.round(c(a, i) + (c(b, i) - c(a, i)) * f)).join(',')})`;
}

const el = (tag, attrs = {}, pai) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (pai) pai.appendChild(e);
  return e;
};

const ordinal = (k) => `${k}ª`;
const pp = (v) => `${formatar(Math.abs(v), 'dec1')} p.p.`;

function lista(nomes, n) {
  if (n === 1) return nomes[0];
  const vis = nomes.slice(0, 2).join(', ');
  return n > 2 ? `${vis} e mais ${n - 2}` : nomes.join(' e ');
}

// Enxame: um círculo por município, na posição da taxa, com área proporcional ao
// eleitorado. Os grandes ficam por baixo do texto da conta: é deles que vem a média.
function enxame(svg, membros, municipios, i, dadosUf, nacional) {
  const W = 340, H = 118, mx = 14, topo = 22, base = H - 18;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = '';
  const valores = membros.map((j) => municipios.abst[j]);
  const lo = Math.max(0, Math.floor(Math.min(...valores, dadosUf.pct, nacional) / 5) * 5);
  const hi = Math.ceil(Math.max(...valores, dadosUf.pct, nacional) / 5) * 5;
  const x = (v) => mx + ((v - lo) / (hi - lo)) * (W - mx * 2);
  const meio = (topo + base) / 2;

  for (let t = lo; t <= hi; t += 5) {
    el('line', { x1: x(t), x2: x(t), y1: topo - 4, y2: base, class: 'grade' }, svg);
    const tx = el('text', { x: x(t), y: H - 4, class: 'tick' }, svg);
    tx.textContent = `${t}%`;
  }

  const maxAptos = Math.max(...membros.map((j) => municipios.aptos[j]));
  const rMax = membros.length > 300 ? 11 : 14;
  const circ = membros
    .map((j) => ({ j, x: x(municipios.abst[j]), r: Math.max(1.7, rMax * Math.sqrt(municipios.aptos[j] / maxAptos)) }))
    .sort((a, b) => b.r - a.r);
  const postos = [];
  const passo = 1.4, lim = (base - topo) / 2;
  for (const c of circ) {
    let y = 0;
    for (let k = 0; k < 200; k++) {
      const dy = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * passo;
      if (Math.abs(dy) > lim - c.r) { y = 0; break; }
      if (!postos.some((o) => Math.abs(o.x - c.x) < o.r + c.r && Math.hypot(o.x - c.x, o.y - dy) < o.r + c.r + 0.4)) { y = dy; break; }
    }
    c.y = y;
    postos.push(c);
  }
  const grupo = el('g', {}, svg);
  const nos = [];
  for (const c of circ) {
    if (c.j === i) continue;
    nos.push(el('circle', { cx: c.x, cy: meio + c.y, r: c.r, fill: corAbst(municipios.abst[c.j]), class: 'mun' }, grupo));
  }

  // Linhas de referência: Brasil (tracejada) e o estado (cheia, em destaque).
  const linha = (v, classe, texto, ancora) => {
    el('line', { x1: x(v), x2: x(v), y1: topo - 6, y2: base, class: classe }, svg);
    const t = el('text', { x: x(v) + (ancora === 'end' ? -4 : 4), y: topo - 10, class: `${classe}-rot`, 'text-anchor': ancora }, svg);
    t.textContent = texto;
  };
  const ladoUf = dadosUf.pct >= nacional ? 'start' : 'end';
  linha(nacional, 'ref-br', `Brasil ${formatar(nacional, 'pct1')}`, ladoUf === 'start' ? 'end' : 'start');
  linha(dadosUf.pct, 'ref-uf', `Estado ${formatar(dadosUf.pct, 'pct1')}`, ladoUf);

  const sel = circ.find((c) => c.j === i);
  const anel = el('circle', { cx: sel.x, cy: meio + sel.y, r: sel.r + 4, class: 'anel' }, svg);
  const ponto = el('circle', { cx: sel.x, cy: meio + sel.y, r: Math.max(sel.r, 3.2), class: 'sel' }, svg);
  return { nos, anel, ponto };
}

// Os 27 estados em ordem de taxa, como uma régua: onde este estado fica no país.
function ranking(svg, ufs, uf) {
  const ordem = Object.entries(ufs).sort((a, b) => a[1].posicao_menor - b[1].posicao_menor);
  const W = 340, H = 46, gap = 3;
  const larg = (W - gap * (ordem.length - 1)) / ordem.length;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = '';
  const min = ordem[0][1].pct, max = ordem.at(-1)[1].pct;
  const barras = ordem.map(([u, d], k) => {
    const h = 10 + ((d.pct - min) / (max - min)) * (H - 14);
    const b = el('rect', { x: k * (larg + gap), y: H - h, width: larg, height: h, rx: 1.5, class: u === uf ? 'barra ativa' : 'barra' }, svg);
    const t = el('title', {}, b);
    t.textContent = `${UF_NOMES[u]}: ${formatar(d.pct, 'pct2')}`;
    return b;
  });
  return barras;
}

export function criarPainel({ raiz, municipios, resumo, reduzido }) {
  const conteudo = raiz.querySelector('.conteudo');
  const curva = [0.22, 1, 0.36, 1];
  const porUf = new Map();
  municipios.uf.forEach((u, j) => {
    if (!porUf.has(u)) porUf.set(u, []);
    porUf.get(u).push(j);
  });
  const nacional = resumo.nacional.abst_pct;

  function preencher(i) {
    const uf = municipios.uf[i];
    const d = resumo.ufs[uf];
    const membros = porUf.get(uf);
    const nome = municipios.nome[i];
    const pctMun = municipios.abst[i];
    const dif = pctMun - d.pct;
    const parcelaMun = municipios.aptos[i] / d.aptos;
    const total = Object.keys(resumo.ufs).length;

    // Posição do município entre os do estado (1 = maior taxa).
    const posicao = membros.filter((j) => municipios.abst[j] > pctMun).length + 1;

    // Quanto este município move a taxa do estado: a conta refeita sem ele, com as
    // contagens exatas de eleitores e abstenções.
    let leitura;
    if (d.municipios === 1) {
      leitura = `${nome} é o único município do ${UF_NOMES[uf]}: a taxa da cidade é a do estado.`;
    } else {
      const sem = (100 * (d.abstencoes - municipios.abstencoes[i])) / (d.aptos - municipios.aptos[i]);
      const efeito = d.pct - sem;
      const peso = parcelaMun < 0.001 ? 'menos de 0,1%' : formatar(parcelaMun, 'fr');
      const lado = Math.abs(dif) < 0.05 ? 'ficou praticamente na taxa do estado'
        : `ficou ${pp(dif)} ${dif > 0 ? 'acima' : 'abaixo'} da taxa do estado`;
      leitura = `${nome} tem ${peso} dos eleitores do estado e ${lado}. `
        + (Math.abs(efeito) < 0.05
          ? `Sem ${nome}, a taxa do estado mudaria menos de 0,05 p.p.: um município desse tamanho quase não pesa na conta.`
          : `Sem ${nome}, a taxa do estado seria ${formatar(sem, 'pct2')}, ${pp(efeito)} ${efeito > 0 ? 'a menos' : 'a mais'}.`);
    }

    conteudo.innerHTML = `
      <header>
        <p class="sobre">${d.regiao} · ${formatar(d.municipios, 'int')} ${d.municipios === 1 ? 'município' : 'municípios'}</p>
        <h3 id="estado-nome">${UF_NOMES[uf]}</h3>
      </header>
      <div class="taxa">
        <strong>${formatar(d.pct, 'pct2')}</strong>
        <span>de abstenção no estado, somando os ${formatar(d.aptos, 'int')} eleitores</span>
      </div>
      <div class="bloco">
        <p class="rotulo">${d.posicao_menor <= total / 2
          ? `<b>${ordinal(d.posicao_menor)} menor</b> taxa entre as ${total} unidades da federação`
          : `<b>${ordinal(total + 1 - d.posicao_menor)} maior</b> taxa entre as ${total} unidades da federação`}</p>
        <svg class="ranking" role="img" aria-label="Taxa das ${total} unidades da federação, da menor para a maior"></svg>
      </div>
      <div class="clicado">
        <span class="nome">${nome}</span>
        <span class="valor">${formatar(pctMun, 'pct2')}</span>
        <span class="dif ${dif >= 0 ? 'acima' : 'abaixo'}">${dif >= 0 ? '+' : '−'}${pp(dif)} vs. estado</span>
        ${d.municipios > 1 ? `<span class="pos">${ordinal(posicao)} maior taxa entre os ${formatar(d.municipios, 'int')} do estado</span>` : ''}
      </div>
      <figure class="bloco">
        <svg class="enxame" role="img" aria-label="Abstenção de cada município do estado"></svg>
        <figcaption>Cada círculo é um município do estado, do tamanho do seu eleitorado.</figcaption>
      </figure>
      ${d.resto.n ? `<div class="metades">
        <div><i class="grande"></i><p>${d.metade.n === 1 ? 'Maior município' : `${d.metade.n} maiores municípios`}<small>${lista(d.metade.nomes, d.metade.n)} · ${formatar(d.metade.parcela, 'fr')} dos eleitores</small></p><b>${formatar(d.metade.pct, 'pct2')}</b></div>
        <div><i class="pequeno"></i><p>Demais municípios<small>${formatar(d.resto.n, 'int')} municípios · ${formatar(1 - d.metade.parcela, 'fr')} dos eleitores</small></p><b>${formatar(d.resto.pct, 'pct2')}</b></div>
        <div><i class="media"></i><p>Média simples dos municípios<small>sem pesar o eleitorado</small></p><b>${formatar(d.media_simples, 'pct2')}</b></div>
      </div>` : ''}
      <p class="leitura">${leitura}</p>`;

    const barras = ranking(conteudo.querySelector('.ranking'), resumo.ufs, uf);
    const { nos, anel, ponto } = enxame(conteudo.querySelector('.enxame'), membros, municipios, i, d, nacional);

    if (reduzido) return;
    animate(conteudo.children, { opacity: [0, 1], transform: ['translateY(10px)', 'translateY(0)'] },
      { duration: 0.6, ease: curva, delay: (k) => 0.08 + k * 0.05 });
    animate(barras, { transform: ['scaleY(0)', 'scaleY(1)'] }, { duration: 0.6, ease: curva, delay: (k) => 0.2 + k * 0.012 });
    // Os círculos entram do maior para o menor, que é a ordem do peso na conta.
    const atraso = Math.min(0.9 / Math.max(nos.length, 1), 0.02);
    animate(nos, { opacity: [0, 0.9], transform: ['scale(0)', 'scale(1)'] }, { duration: 0.5, ease: curva, delay: (k) => 0.3 + k * atraso });
    animate([anel, ponto], { opacity: [0, 1], transform: ['scale(2.2)', 'scale(1)'] }, { duration: 0.7, ease: curva, delay: 0.9 });
    const contador = conteudo.querySelector('.taxa strong');
    animate(nacional, d.pct, { duration: 1.1, ease: [0.16, 1, 0.3, 1], onUpdate: (v) => { contador.textContent = formatar(v, 'pct2'); } });
  }

  let aberto = false;
  function abrir(i) {
    preencher(i);
    if (!aberto) {
      raiz.hidden = false;
      if (!reduzido) animate(raiz, { opacity: [0, 1], transform: ['translateY(16px) scale(0.98)', 'translateY(0) scale(1)'], filter: ['blur(8px)', 'blur(0px)'] }, { duration: 0.6, ease: curva });
    }
    aberto = true;
  }
  function fechar() {
    if (!aberto) return;
    aberto = false;
    if (reduzido) { raiz.hidden = true; return; }
    animate(raiz, { opacity: 0, transform: 'translateY(12px) scale(0.98)', filter: 'blur(6px)' }, { duration: 0.35, ease: 'easeIn' })
      .then(() => { if (!aberto) raiz.hidden = true; });
  }
  return { abrir, fechar, aberto: () => aberto };
}
