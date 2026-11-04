import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';
import { animate, inView } from 'motion';
import { carregar, preencherTextos, montarLayouts, formatar, CORES_REGIAO, UF_NOMES } from './dados.js';
import { graficoCoeficientes, graficoModelos } from './graficos.js';
import { criarPainel } from './painel.js';

gsap.registerPlugin(ScrollTrigger);

// Endereço do repositório no GitHub. Vazio enquanto ele não for publicado.
const REPO_URL = '';

const reduzido = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if (reduzido) document.body.classList.add('sem-animacao');

// ---------------------------------------------------------------------------
// Estados da cena. Cada passo da história tem um; entre um passo e o próximo, o scroll
// interpola todos os números. Pesos de posição (w*) e de cor (c*) somam 1.
// ---------------------------------------------------------------------------
const BASE = {
  wNuvem: 0, wMapa: 0, wReg: 0, wEsc: 0, wTam: 0, wIdade: 0,
  cNeutro: 0, cAbst: 0, cReg: 0, cResid: 0,
  altura: 0, haste: 0, tam: 1, tamAptos: 0, brilho: 1,
  fantasma: 0, espalhar: 0,
  tilt: 0, yaw: 0, dist: 1, alvoX: 0, alvoY: 0,
  eixoY: 0, legAbst: 0, legReg: 0, legResid: 0, legViz: 0, interativo: 0,
  // picos: rótulos dos três maiores; destaque: acende o exemplo e apaga o resto;
  // suave: troca o erro de cada município pela média do erro dos vizinhos.
  picos: 0, destaque: 0, suave: 0,
  // clicavel: clicar num município abre o painel do estado dele.
  clicavel: 0,
};
const mapa = { wMapa: 1, interativo: 1 };
const disp = { cReg: 1, eixoY: 1, legReg: 1, interativo: 1, tamAptos: 0.5 };
const ESTADOS = {
  abertura: { wNuvem: 1, cNeutro: 0.55, cAbst: 0.45, tam: 1.3, brilho: 0.7, dist: 1.08, alvoX: -0.32 },
  mapa: { ...mapa, cNeutro: 1 },
  cor: { ...mapa, cAbst: 1, legAbst: 1, clicavel: 1 },
  relevo: { ...mapa, cAbst: 1, legAbst: 1, altura: 0.34, haste: 1, tilt: 0.86, yaw: -0.3, dist: 0.98, alvoY: 0.08, picos: 1, clicavel: 1 },
  pico: { ...mapa, cAbst: 1, legAbst: 1, altura: 0.34, haste: 1, tilt: 0.86, yaw: -0.3, dist: 0.98, alvoY: 0.08, destaque: 1, clicavel: 1 },
  armadilha: { wMapa: 1, cNeutro: 1, fantasma: 1, espalhar: 1, tilt: 1.02, yaw: 0.3, dist: 1.05, alvoY: 0.1 },
  filtro: { ...mapa, cAbst: 1, legAbst: 1, tilt: 0.35, dist: 1 },
  regioes: { ...disp, wReg: 1, tamAptos: 0 },
  escolaridade: { ...disp, wEsc: 1 },
  tamanho: { ...disp, wTam: 1 },
  idade: { ...disp, wIdade: 1 },
  coeficientes: { wMapa: 1, cAbst: 1, brilho: 0.16, dist: 1.1 },
  residuos: { ...mapa, cResid: 1, legResid: 1 },
  vizinhos: { ...mapa, cResid: 1, legViz: 1, suave: 1 },
  modelos: { wMapa: 1, cResid: 1, brilho: 0.18, dist: 1.1 },
  limites: { wNuvem: 1, cNeutro: 0.6, cAbst: 0.4, brilho: 0.4, tam: 1.2, dist: 1.15 },
  explorar: { ...mapa, cAbst: 1, legAbst: 1 },
  // O fim volta à nuvem do começo, agora centrada.
  // alvoX positivo desfaz o deslocamento da câmera para a direita dos cartões.
  fim: { wNuvem: 1, cNeutro: 0.5, cAbst: 0.5, tam: 1.25, brilho: 0.5, dist: 1.05, alvoX: 0.42 },
};
for (const k of Object.keys(ESTADOS)) ESTADOS[k] = { ...BASE, ...ESTADOS[k] };
const CHAVES = Object.keys(BASE);

const suave = (t) => t * t * (3 - 2 * t);

function iniciarHistoria({ cena, municipios, resumo }) {
  const passos = [...document.querySelectorAll('.passo')];
  const S = { ...ESTADOS[passos[0].dataset.cena] };
  // foco: câmera (v, x, y, z = quanto aproxima) e destaque (selDim, uf, ufDim, painel).
  const foco = { v: 0, x: 0, y: 0, z: 0.55, selDim: 0, uf: -1, ufDim: 0, painel: 0 };
  let marcos = [];
  let passoAtual = 0;

  // Onde cada passo começa, em pixels de scroll. A transição para o estado do passo i
  // acontece enquanto o topo dele sobe de 85% a 35% da altura da tela.
  function medir() {
    const h = window.innerHeight;
    marcos = passos.map((p) => {
      const topo = p.getBoundingClientRect().top + window.scrollY;
      return { ini: topo - h * 0.85, fim: topo - h * 0.35, estado: ESTADOS[p.dataset.cena] };
    });
  }

  function estadoEm(y) {
    let de = marcos[0].estado, para = de, t = 0, k = 0;
    for (let i = 1; i < marcos.length; i++) {
      const m = marcos[i];
      if (y < m.ini) break;
      de = marcos[i - 1].estado;
      para = m.estado;
      t = y >= m.fim ? 1 : suave((y - m.ini) / (m.fim - m.ini));
      k = i;
    }
    passoAtual = t >= 0.5 ? k : Math.max(k - 1, 0);
    for (const k of CHAVES) S[k] = de[k] + (para[k] - de[k]) * t;
  }

  // ---------- legendas ----------
  const legReg = document.querySelector('[data-legenda="reg"]');
  legReg.innerHTML = municipios.regioes.map((r, i) => `<em style="--c:${CORES_REGIAO[i]}">${r}</em>`).join('');
  const legendas = {
    legAbst: document.querySelector('[data-legenda="abst"]'),
    legReg,
    legResid: document.querySelector('[data-legenda="resid"]'),
    legViz: document.querySelector('[data-legenda="viz"]'),
  };

  // ---------- dica do mouse ----------
  const dica = document.getElementById('dica');
  let mouse = null, pendente = false, atual = -1;
  const canvas = document.getElementById('cena');
  canvas.addEventListener('pointermove', (e) => {
    mouse = [e.clientX, e.clientY];
    pendente = true;
  });
  canvas.addEventListener('pointerleave', () => { mouse = null; pendente = true; });

  function conteudoDica(i) {
    const nome = `${municipios.nome[i]} (${municipios.uf[i]})`;
    const abst = municipios.abst[i];
    if (S.cResid > 0.5 && S.suave > 0.5) {
      const r = municipios.residuo[i], rv = municipios.residuo_vizinhos[i];
      const sinal = (x) => `${x >= 0 ? '+' : '−'}${formatar(Math.abs(x), 'dec1')} p.p.`;
      return `<b>${nome}</b><br>erro do município: ${sinal(r)}<br>erro médio dos vizinhos: <span class="valor">${sinal(rv)}</span>`;
    }
    if (S.cResid > 0.5) {
      const prev = abst - municipios.residuo[i];
      const r = municipios.residuo[i];
      return `<b>${nome}</b><span class="valor">${formatar(abst, 'pct1')}</span><br>previsto pela regressão: ${formatar(prev, 'pct1')}<br>${r >= 0 ? 'acima' : 'abaixo'} em ${formatar(Math.abs(r), 'dec1')} p.p.`;
    }
    const extra = S.wEsc > 0.5 ? `analfabeto ou só lê e escreve: ${formatar(municipios.baixa_esc[i], 'pct1')}`
      : S.wIdade > 0.5 ? `70 anos ou mais: ${formatar(municipios.p70[i], 'pct1')}`
        : S.wTam > 0.5 || S.wReg > 0.5 ? `${formatar(municipios.aptos[i], 'int')} eleitores aptos`
          : `${formatar(municipios.aptos[i], 'int')} eleitores aptos`;
    const convite = S.clicavel > 0.5 && !painel.aberto() ? `<em class="clique">${toque ? 'toque' : 'clique'} para ver o estado</em>` : '';
    return `<b>${nome}</b><span class="valor">${formatar(abst, 'pct1')}</span> de abstenção<br>${extra}${convite}`;
  }

  function atualizarDica() {
    if (!pendente) return;
    pendente = false;
    if (!mouse || S.interativo < 0.9) {
      dica.classList.remove('visivel');
      atual = -1;
      canvas.style.cursor = '';
      return;
    }
    const i = cena.maisProximo(mouse[0], mouse[1], S);
    if (i < 0) {
      dica.classList.remove('visivel');
      canvas.style.cursor = '';
      atual = -1;
      return;
    }
    if (i !== atual) dica.innerHTML = conteudoDica(i);
    atual = i;
    canvas.style.cursor = 'pointer';
    const [x, y] = cena.telaDe(i, S);
    const w = dica.offsetWidth, h = dica.offsetHeight;
    const dx = x + 16 + w > window.innerWidth ? x - w - 16 : x + 16;
    dica.style.transform = `translate(${dx}px, ${Math.max(8, y - h - 12)}px)`;
    dica.classList.add('visivel');
  }

  // ---------- painel do estado ----------
  const toque = window.matchMedia('(hover: none)').matches;
  const raizPainel = document.getElementById('painel-estado');
  const painel = criarPainel({ raiz: raizPainel, municipios, resumo, reduzido });
  const convite = document.querySelector('.convite');
  convite.lastChild.textContent = `${toque ? 'Toque' : 'Clique'} num ponto para ver o estado`;
  let estadoSel = -1, abertoEm = -1, tokenEstado = 0;
  const curvaFoco = [0.22, 1, 0.36, 1];

  function abrirEstado(i) {
    const k = cena.ufLista.indexOf(municipios.uf[i]);
    const largo = window.innerWidth >= 900;
    const q = cena.enquadrarEstado(k, largo ? 360 + 66 : 0);
    const jaAberto = painel.aberto();
    tokenEstado++;
    estadoSel = i;
    abertoEm = passoAtual;
    foco.uf = k;
    foco.painel = largo ? 360 + 66 : 0;
    if (!jaAberto && foco.v < 0.01) { foco.x = q.x; foco.y = q.y; foco.z = q.z; }
    cena.marcar(i);
    painel.abrir(i);
    animate(foco, { x: q.x, y: q.y, z: q.z, v: 1, ufDim: 1 }, { duration: reduzido ? 0 : 1.5, ease: curvaFoco });
    dica.classList.remove('visivel');
    if (!jaAberto) raizPainel.querySelector('.fechar').focus({ preventScroll: true });
  }
  function fecharEstado() {
    if (!painel.aberto()) return;
    painel.fechar();
    const token = ++tokenEstado;
    animate(foco, { v: 0, ufDim: 0 }, { duration: reduzido ? 0 : 1, ease: curvaFoco })
      .then(() => { if (token === tokenEstado) { estadoSel = -1; foco.uf = -1; } });
  }
  canvas.addEventListener('click', (e) => {
    if (S.clicavel < 0.9) return;
    const i = cena.maisProximo(e.clientX, e.clientY, S, toque ? 22 : 16);
    if (i >= 0) abrirEstado(i);
    else fecharEstado();
  });
  raizPainel.querySelector('.fechar').addEventListener('click', fecharEstado);
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape') fecharEstado(); });

  // ---------- numeração ----------
  // O número de cada capítulo sai da ordem no HTML: inserir um capítulo não exige
  // renumerar os outros à mão.
  passos.filter((p) => !p.classList.contains('abertura')).forEach((p, k) => {
    const el = p.querySelector('.num');
    if (el) el.textContent = String(k + 1).padStart(2, '0');
  });

  // ---------- progresso e trilho ----------
  const barra = document.querySelector('.progresso i');
  const trilho = document.querySelector('.trilho');
  const links = passos.map((p, i) => {
    if (!p.id) p.id = `passo-${i}`;
    const a = document.createElement('a');
    a.href = `#${p.id}`;
    a.innerHTML = `<span>${p.dataset.titulo}</span>`;
    a.setAttribute('aria-label', p.dataset.titulo);
    trilho.appendChild(a);
    return a;
  });

  // ---------- scroll ----------
  let lenis = null;
  if (!reduzido) {
    lenis = new Lenis({ lerp: 0.085, wheelMultiplier: 0.9 });
    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add((t) => lenis.raf(t * 1000));
    gsap.ticker.lagSmoothing(0);
  }
  links.forEach((a, i) => a.addEventListener('click', (e) => {
    e.preventDefault();
    if (lenis) lenis.scrollTo(passos[i], { offset: i === 0 ? 0 : -window.innerHeight * 0.05, duration: 1.6 });
    else passos[i].scrollIntoView();
  }));

  // Um ScrollTrigger por passo marca o capítulo ativo; outro, na história inteira,
  // move a barra de progresso.
  passos.forEach((p, i) => ScrollTrigger.create({
    trigger: p,
    start: 'top 55%',
    end: 'bottom 55%',
    onToggle: (st) => links[i].classList.toggle('ativo', st.isActive),
  }));
  ScrollTrigger.create({
    trigger: '#historia',
    start: 'top top',
    end: 'bottom bottom',
    onUpdate: (st) => { barra.style.transform = `scaleX(${st.progress.toFixed(4)})`; },
  });
  ScrollTrigger.addEventListener('refresh', medir);
  medir();

  // ---------- cartões e números (Motion) ----------
  const curva = [0.22, 1, 0.36, 1];
  for (const cartao of document.querySelectorAll('.passo:not(.abertura) .cartao')) {
    if (reduzido) { cartao.style.opacity = 1; continue; }
    inView(cartao, () => {
      animate(cartao, { opacity: [0, 1], transform: ['translateY(28px)', 'translateY(0)'], filter: ['blur(8px)', 'blur(0px)'] },
        { duration: 0.9, ease: curva });
      return () => animate(cartao, { opacity: 0, filter: 'blur(6px)' }, { duration: 0.4 });
    }, { amount: 0.35 });
  }
  if (!reduzido) {
    const ab = document.querySelector('.abertura .cartao');
    animate(ab.children, { opacity: [0, 1], transform: ['translateY(18px)', 'translateY(0)'] },
      { duration: 1.1, ease: curva, delay: (i) => 0.15 + i * 0.12 });
  }
  for (const el of document.querySelectorAll('[data-contar]')) {
    const alvo = Number(el.dataset.valor);
    const f = el.dataset.f;
    if (reduzido || !Number.isFinite(alvo)) continue;
    inView(el, () => {
      animate(0, alvo, {
        duration: 1.8, ease: [0.16, 1, 0.3, 1],
        onUpdate: (v) => { el.textContent = formatar(f === 'int' ? Math.round(v) : v, f); },
      });
    }, { amount: 0.8 });
  }

  // ---------- gráficos ----------
  const animarCoef = graficoCoeficientes(document.getElementById('g-coef'), resumo.regressao);
  const animarMod = graficoModelos(document.getElementById('g-modelos'), resumo.modelos);
  if (!reduzido) {
    inView('#g-coef', () => { animarCoef(); }, { amount: 0.4 });
    inView('#g-modelos', () => { animarMod(); }, { amount: 0.4 });
  }

  // ---------- busca ----------
  const lista = document.getElementById('lista-municipios');
  const indice = new Map();
  const opcoes = [];
  municipios.nome.forEach((nome, i) => {
    const rot = `${nome} (${municipios.uf[i]})`;
    indice.set(rot.toLowerCase(), i);
    opcoes.push(`<option value="${rot.replace(/"/g, '&quot;')}"></option>`);
  });
  lista.innerHTML = opcoes.join('');
  const entrada = document.getElementById('busca-municipio');
  const ficha = document.querySelector('.ficha');
  let selBusca = -1;
  const exemplo = resumo.picos.exemplo.idx;
  function escolher(i) {
    selBusca = i;
    foco.z = 0.55;
    if (i < 0) {
      animate(foco, { v: 0 }, { duration: 0.8, ease: curva });
      ficha.hidden = true;
      return;
    }
    const [x, y] = cena.posMapa(i);
    foco.x = x; foco.y = y;
    animate(foco, { v: 1 }, { duration: reduzido ? 0 : 1.2, ease: curva });
    const r = municipios.residuo[i];
    const prev = municipios.abst[i] - r;
    ficha.innerHTML = `
      <h3>${municipios.nome[i]} <small>${UF_NOMES[municipios.uf[i]]}</small></h3>
      <div><dt>Abstenção</dt><dd>${formatar(municipios.abst[i], 'pct2')}</dd></div>
      <div><dt>Eleitores aptos</dt><dd>${formatar(municipios.aptos[i], 'int')}</dd></div>
      <div><dt>Previsto pela regressão</dt><dd>${formatar(prev, 'pct1')}</dd></div>
      <div><dt>Diferença</dt><dd class="${r >= 0 ? 'acima' : 'abaixo'}">${r >= 0 ? '+' : '−'}${formatar(Math.abs(r), 'dec1')} p.p.</dd></div>
      <div><dt>Analfabeto ou só lê e escreve</dt><dd>${formatar(municipios.baixa_esc[i], 'pct1')}</dd></div>
      <div><dt>70 anos ou mais</dt><dd>${formatar(municipios.p70[i], 'pct1')}</dd></div>`;
    ficha.hidden = false;
    if (!reduzido) animate(ficha.children, { opacity: [0, 1], transform: ['translateY(8px)', 'translateY(0)'] }, { duration: 0.5, delay: (k) => k * 0.04 });
  }
  entrada.addEventListener('input', () => {
    const i = indice.get(entrada.value.trim().toLowerCase());
    if (i !== undefined) escolher(i);
  });
  document.querySelector('.busca').addEventListener('submit', (e) => {
    e.preventDefault();
    const termo = entrada.value.trim().toLowerCase();
    if (!termo) return;
    let i = indice.get(termo);
    if (i === undefined) {
      const achado = [...indice.keys()].find((k) => k.startsWith(termo));
      i = achado ? indice.get(achado) : undefined;
    }
    if (i !== undefined) { entrada.value = `${municipios.nome[i]} (${municipios.uf[i]})`; escolher(i); }
  });
  document.querySelector('.busca .limpar').addEventListener('click', () => { entrada.value = ''; escolher(-1); entrada.focus(); });
  // Sair da seção de busca desfaz o foco no município.
  ScrollTrigger.create({ trigger: '#explorar', start: 'top 60%', onLeaveBack: () => escolher(-1) });

  // ---------- laço de desenho ----------
  let tempo = 0;
  gsap.ticker.add((_, dt) => {
    if (!reduzido) tempo += dt / 1000;
    estadoEm(window.scrollY);
    // No celular o título fica por cima da cena: a nuvem fica centrada e mais apagada.
    if (window.innerWidth < 900) { S.alvoX = 0; S.brilho *= 1 - 0.45 * S.wNuvem; }
    for (const [k, el] of Object.entries(legendas)) el.style.opacity = S[k].toFixed(3);
    // Recalcula a dica a cada quadro enquanto o mouse está na cena: com o scroll, os
    // pontos andam por baixo de um mouse parado.
    if (mouse) pendente = true;
    // Sair do capítulo (ou dos mapas clicáveis) fecha o estado.
    if (painel.aberto() && (S.clicavel < 0.5 || passoAtual !== abertoEm)) fecharEstado();
    convite.style.opacity = (S.clicavel * (1 - foco.ufDim) * (S.clicavel > 0.98 ? 1 : 0)).toFixed(3);
    atualizarDica();
    cena.selecionar(selBusca >= 0 ? selBusca : estadoSel >= 0 ? estadoSel : S.destaque > 0.02 ? exemplo : -1);
    foco.selDim = selBusca >= 0 ? foco.v : S.destaque * (1 - foco.ufDim);
    cena.desenhar(S, foco, tempo);
  });

  return { medir };
}

async function iniciar() {
  const { municipios, resumo, contorno } = await carregar();
  preencherTextos(resumo);
  if (REPO_URL) {
    const p = document.querySelector('.repo');
    p.hidden = false;
    p.querySelector('a').href = REPO_URL;
    p.querySelector('a').textContent = REPO_URL.replace(/^https?:\/\//, '');
  }

  let cena = null;
  try {
    const { criarCena } = await import('./cena.js');
    const layouts = montarLayouts(municipios);
    cena = criarCena({
      canvas: document.getElementById('cena'),
      layouts,
      municipios,
      camadasArmadilha: resumo.derivado.razao_armadilha,
      rotulosEl: document.getElementById('rotulos'),
      picos: resumo.picos,
      contorno,
    });
  } catch (erro) {
    console.error('WebGL indisponível; a história segue só com o texto.', erro);
    document.body.classList.add('sem-webgl');
    for (const c of document.querySelectorAll('.cartao')) c.style.opacity = 1;
    return;
  }

  const larguraCartoes = () => {
    const c = document.querySelector('.passo:not(.abertura):not(.largo) .cartao');
    return c ? c.getBoundingClientRect().right + 32 : 520;
  };
  cena.redimensionar(larguraCartoes());
  const historia = iniciarHistoria({ cena, municipios, resumo });
  let espera;
  window.addEventListener('resize', () => {
    clearTimeout(espera);
    espera = setTimeout(() => { cena.redimensionar(larguraCartoes()); historia.medir(); }, 120);
  });
  document.fonts?.ready.then(() => ScrollTrigger.refresh());
}

iniciar();
