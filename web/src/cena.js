// Cena three.js: os 5.570 municípios como pontos. Cada cena da história é uma mistura
// de posições (nuvem, mapa, colunas por região, três dispersões) e de cores (neutra,
// abstenção, região, resíduo). A mistura roda na GPU; o scroll só muda os pesos.
import * as THREE from 'three';
import { CORES_REGIAO, X_REGIOES, yAbst } from './dados.js';

const FUNDO = 0x0b0d12;

const RAMPA_GLSL = /* glsl */ `
vec3 rampa(float t) {
  vec3 c0 = vec3(0.239, 0.310, 0.659);
  vec3 c1 = vec3(0.482, 0.310, 0.702);
  vec3 c2 = vec3(0.816, 0.345, 0.494);
  vec3 c3 = vec3(0.969, 0.561, 0.353);
  vec3 c4 = vec3(0.984, 0.843, 0.541);
  t = clamp(t, 0.0, 1.0) * 4.0;
  if (t < 1.0) return mix(c0, c1, t);
  if (t < 2.0) return mix(c1, c2, t - 1.0);
  if (t < 3.0) return mix(c2, c3, t - 2.0);
  return mix(c3, c4, t - 3.0);
}
vec3 divergente(float r) {
  vec3 abaixo = vec3(0.290, 0.639, 0.875);
  vec3 meio = vec3(0.361, 0.369, 0.412);
  vec3 acima = vec3(1.0, 0.478, 0.349);
  r = clamp(r, -1.0, 1.0);
  return r < 0.0 ? mix(meio, abaixo, -r) : mix(meio, acima, r);
}`;

const VERTICE = /* glsl */ `
uniform float uW[6];
uniform float uC[4];
uniform vec3 uRegCor[5];
uniform float uAltura, uTempo, uEscala, uTam, uTamAptos, uBrilho, uSel, uSelDim, uHaste, uSuave, uUf, uUfDim;
attribute vec3 aNuvem;
attribute vec3 aReg;
attribute vec3 aEsc;
attribute vec3 aTam;
attribute vec3 aIdade;
attribute float aAbst, aResid, aResidViz, aRegiao, aPeso, aIdx, aUf;
#ifdef HASTE
attribute float aTopo;
#endif
varying vec3 vCor;
varying float vAlpha;
${RAMPA_GLSL}
void main() {
  float ang = uTempo * 0.035;
  float cs = cos(ang), sn = sin(ang);
  vec3 nv = vec3(aNuvem.x * cs - aNuvem.z * sn, aNuvem.y, aNuvem.x * sn + aNuvem.z * cs);
  vec3 p = nv * uW[0] + position * uW[1] + aReg * uW[2] + aEsc * uW[3] + aTam * uW[4] + aIdade * uW[5];
  float h = aAbst * uAltura * uW[1];
#ifdef HASTE
  p.z += h * aTopo;
#else
  p.z += h;
#endif
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;

  bool sel = abs(aIdx - uSel) < 0.5;
  vec3 cor = vec3(0.914, 0.886, 0.827) * uC[0]
           + rampa(aAbst) * uC[1]
           + uRegCor[int(aRegiao + 0.5)] * uC[2]
           + divergente(mix(aResid, aResidViz, uSuave)) * uC[3];
  float a = uBrilho;
  if (uSel > -0.5 && !sel) a *= 1.0 - 0.75 * uSelDim;
  // Estado aberto no painel: o resto do país fica como contorno apagado.
  bool foraUf = uUf > -0.5 && abs(aUf - uUf) > 0.5;
  if (foraUf) a *= 1.0 - 0.86 * uUfDim;
#ifdef HASTE
  if (!foraUf && uUf > -0.5) a *= 1.0 + 1.2 * uUfDim;
  vCor = cor;
  vAlpha = a * uHaste * (0.04 + 0.3 * aTopo);
#else
  float s = uTam * mix(1.0, 0.55 + aPeso * 2.1, uTamAptos);
  if (foraUf) s *= 1.0 - 0.3 * uUfDim;
  if (sel && uSel > -0.5) { s = max(s * 3.2, 6.5); cor = mix(cor, vec3(1.0), 0.55); a = 1.0; }
  gl_PointSize = s * uEscala / -mv.z;
  vCor = cor;
  vAlpha = a;
#endif
}`;

const FRAG_PONTO = /* glsl */ `
varying vec3 vCor;
varying float vAlpha;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;
  // Núcleo nítido com a cor do dado e um halo fraco em volta, no lugar de um bloom de
  // tela inteira (que acinzentava o fundo e lavava as cores das regiões densas).
  float nucleo = smoothstep(0.26, 0.17, d);
  float halo = pow(1.0 - d * 2.0, 2.2) * 0.22;
  float a = clamp(nucleo + halo, 0.0, 1.0);
  gl_FragColor = vec4(vCor * (1.0 + 0.25 * nucleo), vAlpha * a);
}`;

const FRAG_HASTE = /* glsl */ `
varying vec3 vCor;
varying float vAlpha;
void main() { gl_FragColor = vec4(vCor, vAlpha); }`;

const VERT_FANTASMA = /* glsl */ `
uniform float uFantasma, uEspalhar, uEscala, uTam;
attribute float aCamada, aAbst;
varying float vA;
varying vec3 vCor;
void main() {
  vec3 p = position;
  p.z += aCamada * uEspalhar * 0.17;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = uTam * 0.9 * uEscala / -mv.z;
  vA = uFantasma * (1.0 - aCamada * 0.12);
  vCor = mix(vec3(0.914, 0.886, 0.827), vec3(0.961, 0.690, 0.255), min(aCamada / 3.0, 1.0));
}`;

const FRAG_FANTASMA = /* glsl */ `
varying float vA;
varying vec3 vCor;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;
  gl_FragColor = vec4(vCor, vA * smoothstep(0.5, 0.1, d) * 0.8);
}`;

export function criarCena({ canvas, layouts, municipios, camadasArmadilha, rotulosEl, picos }) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setClearColor(FUNDO, 1);
  const cena = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.05, 50);
  const L = layouts;
  const n = L.n;

  // ---------- pontos ----------
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(L.mapa, 3));
  geo.setAttribute('aNuvem', new THREE.BufferAttribute(L.nuvem, 3));
  geo.setAttribute('aReg', new THREE.BufferAttribute(L.reg, 3));
  geo.setAttribute('aEsc', new THREE.BufferAttribute(L.esc, 3));
  geo.setAttribute('aTam', new THREE.BufferAttribute(L.tam, 3));
  geo.setAttribute('aIdade', new THREE.BufferAttribute(L.idade, 3));
  for (const [nome, arr] of [['aAbst', L.abst], ['aResid', L.resid], ['aResidViz', L.residViz], ['aRegiao', L.regiao], ['aPeso', L.peso], ['aIdx', L.idx], ['aUf', L.uf]]) {
    geo.setAttribute(nome, new THREE.BufferAttribute(arr, 1));
  }

  const uniforms = {
    uW: { value: [1, 0, 0, 0, 0, 0] },
    uC: { value: [1, 0, 0, 0] },
    uRegCor: { value: CORES_REGIAO.map((c) => new THREE.Color(c)) },
    uAltura: { value: 0 },
    uTempo: { value: 0 },
    uEscala: { value: 10 },
    uTam: { value: 1 },
    uTamAptos: { value: 0 },
    uBrilho: { value: 1 },
    uSel: { value: -1 },
    uSelDim: { value: 0 },
    uHaste: { value: 0 },
    uSuave: { value: 0 },
    uUf: { value: -1 },
    uUfDim: { value: 0 },
  };
  // As cores das regiões vêm em sRGB e o shader escreve sem conversão.
  uniforms.uRegCor.value.forEach((c) => c.convertLinearToSRGB());

  const matPontos = new THREE.ShaderMaterial({
    uniforms, vertexShader: VERTICE, fragmentShader: FRAG_PONTO,
    transparent: true, depthWrite: false,
  });
  const pontos = new THREE.Points(geo, matPontos);
  pontos.frustumCulled = false;
  cena.add(pontos);

  // ---------- hastes (linhas do chão até o ponto, na vista de relevo) ----------
  const geoH = new THREE.BufferGeometry();
  const dup = (src, comp) => {
    const out = new Float32Array(src.length * 2);
    for (let i = 0; i < src.length / comp; i++) {
      for (let c = 0; c < comp; c++) {
        out[i * 2 * comp + c] = src[i * comp + c];
        out[i * 2 * comp + comp + c] = src[i * comp + c];
      }
    }
    return new THREE.BufferAttribute(out, comp);
  };
  for (const nome of ['position', 'aNuvem', 'aReg', 'aEsc', 'aTam', 'aIdade']) geoH.setAttribute(nome, dup(geo.getAttribute(nome).array, 3));
  for (const nome of ['aAbst', 'aResid', 'aResidViz', 'aRegiao', 'aPeso', 'aIdx', 'aUf']) geoH.setAttribute(nome, dup(geo.getAttribute(nome).array, 1));
  const topo = new Float32Array(n * 2);
  for (let i = 0; i < n; i++) topo[i * 2 + 1] = 1;
  geoH.setAttribute('aTopo', new THREE.BufferAttribute(topo, 1));
  const matHastes = new THREE.ShaderMaterial({
    uniforms, vertexShader: VERTICE, fragmentShader: FRAG_HASTE, defines: { HASTE: '' },
    transparent: true, depthWrite: false,
  });
  const hastes = new THREE.LineSegments(geoH, matHastes);
  hastes.frustumCulled = false;
  cena.add(hastes);

  // ---------- camadas da armadilha (o mesmo mapa contado várias vezes) ----------
  const extras = Math.max(camadasArmadilha - 1, 1);
  const posF = new Float32Array(n * extras * 3);
  const camF = new Float32Array(n * extras);
  const abstF = new Float32Array(n * extras);
  for (let c = 0; c < extras; c++) {
    posF.set(L.mapa, c * n * 3);
    camF.fill(c + 1, c * n, (c + 1) * n);
    abstF.set(L.abst, c * n);
  }
  const geoF = new THREE.BufferGeometry();
  geoF.setAttribute('position', new THREE.BufferAttribute(posF, 3));
  geoF.setAttribute('aCamada', new THREE.BufferAttribute(camF, 1));
  geoF.setAttribute('aAbst', new THREE.BufferAttribute(abstF, 1));
  const uniF = { uFantasma: { value: 0 }, uEspalhar: { value: 0 }, uEscala: uniforms.uEscala, uTam: uniforms.uTam };
  const fantasma = new THREE.Points(geoF, new THREE.ShaderMaterial({
    uniforms: uniF, vertexShader: VERT_FANTASMA, fragmentShader: FRAG_FANTASMA,
    transparent: true, depthWrite: false,
  }));
  fantasma.frustumCulled = false;
  cena.add(fantasma);

  // ---------- eixos e grades das dispersões ----------
  const grupos = {};
  const linhas = (segs, opacidade = 1) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(segs.flat(2), 3));
    const mat = new THREE.LineBasicMaterial({ color: 0xece6da, transparent: true, opacity: 0, depthWrite: false });
    mat.userData.base = opacidade;
    const l = new THREE.LineSegments(g, mat);
    l.frustumCulled = false;
    cena.add(l);
    return l;
  };
  const yTicks = [10, 20, 30, 40];
  grupos.y = [
    linhas(yTicks.map((t) => [[-1.05, yAbst(t), 0], [1.05, yAbst(t), 0]]), 0.07),
    linhas([[[-1.05, -0.95, 0], [1.05, -0.95, 0]]], 0.22),
  ];

  // Rótulos em HTML posicionados pela projeção da câmera a cada quadro.
  const rotulos = [];
  // `curto` é o texto usado em tela estreita, onde os nomes inteiros se sobrepõem.
  const rotulo = (texto, x, y, grupo, classe = '', ancora = 'centro', curto = texto) => {
    const el = document.createElement('span');
    el.textContent = texto;
    if (classe) el.className = classe;
    rotulosEl.appendChild(el);
    rotulos.push({ el, pos: new THREE.Vector3(x, y, 0), grupo, ancora, texto, curto, visivel: false });
  };
  for (const t of yTicks) rotulo(`${t}%`, -1.08, yAbst(t), 'y', '', 'direita');
  rotulo('Abstenção', -1.08, 0.98, 'y', 'titulo', 'direita');

  const SIGLAS_REGIAO = { Norte: 'N', Nordeste: 'NE', 'Centro-Oeste': 'CO', Sudeste: 'SE', Sul: 'S' };
  const regioes = municipios.regioes;
  regioes.forEach((r, i) => rotulo(r, X_REGIOES[i], -1.02, 'reg', 'regiao', 'centro', SIGLAS_REGIAO[r] || r));

  const { dom } = L;
  const xs = (v, [a, b]) => -1 + ((v - a) / (b - a)) * 2;
  for (let t = dom.esc[0]; t <= dom.esc[1]; t += 10) rotulo(`${t}%`, xs(t, dom.esc), -1.02, 'esc');
  rotulo('Eleitorado analfabeto ou que só lê e escreve', 0, -1.12, 'esc', 'titulo');
  for (let t = dom.idade[0]; t <= dom.idade[1]; t += 5) rotulo(`${t}%`, xs(t, dom.idade), -1.02, 'idade');
  rotulo('Eleitorado com 70 anos ou mais', 0, -1.12, 'idade', 'titulo');
  const marcas = [[1e3, '1 mil'], [1e4, '10 mil'], [1e5, '100 mil'], [1e6, '1 milhão']];
  for (const [v, txt] of marcas) {
    const l2 = Math.log2(v);
    if (l2 >= dom.tam[0] && l2 <= dom.tam[1]) rotulo(txt, xs(l2, dom.tam), -1.02, 'tam');
  }
  rotulo('Eleitores aptos (escala logarítmica)', 0, -1.12, 'tam', 'titulo');

  // Rótulos presos a um município: seguem o ponto (no topo da haste) em vez de um
  // lugar fixo. Os três picos mais altos e o exemplo do capítulo "pico e estado".
  const pct = (p) => new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(p) + '%';
  const presos = [];
  const prender = (p, grupo, classe) => {
    rotulo(`${p.nome} (${p.uf}) ${pct(p.pct)}`, 0, 0, grupo, classe, 'centro', `${p.nome} ${pct(p.pct)}`);
    presos.push({ r: rotulos.at(-1), idx: p.idx });
  };
  if (picos) {
    for (const p of picos.maiores) prender(p, 'pico', 'nomeado');
    prender(picos.exemplo, 'exemplo', 'nomeado exemplo');
  }
  // O município clicado: o texto e o índice mudam a cada clique.
  prender({ nome: '', uf: '', pct: 0, idx: 0 }, 'clicado', 'nomeado exemplo');
  const clicado = presos.at(-1);
  function marcar(i) {
    clicado.idx = i;
    clicado.r.texto = `${municipios.nome[i]} (${municipios.uf[i]}) ${pct(municipios.abst[i])}`;
    clicado.r.curto = `${municipios.nome[i]} ${pct(municipios.abst[i])}`;
    clicado.r.el.textContent = W < 600 ? clicado.r.curto : clicado.r.texto;
  }

  // Caixa de cada estado no mapa, para a câmera enquadrar o estado clicado.
  const caixas = L.ufLista.map(() => [Infinity, Infinity, -Infinity, -Infinity]);
  for (let i = 0; i < n; i++) {
    const c = caixas[L.uf[i]], x = L.mapa[i * 3], y = L.mapa[i * 3 + 1];
    c[0] = Math.min(c[0], x); c[1] = Math.min(c[1], y); c[2] = Math.max(c[2], x); c[3] = Math.max(c[3], y);
  }

  // ---------- tamanho e enquadramento ----------
  let escalaBase = 10;
  let W = 1, H = 1, desloc = 0, baseDist = 3.6, celular = false, larguraUtilAtual = 1, offsetAtual = null;
  const tanMeia = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  function redimensionar(larguraCartoes) {
    W = window.innerWidth;
    H = window.innerHeight;
    celular = W < 900;
    for (const r of rotulos) r.el.textContent = W < 600 ? r.curto : r.texto;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr);
    renderer.setSize(W, H, false);
    camera.aspect = W / H;

    // No computador os cartões ficam à esquerda: o conteúdo é centrado no espaço que
    // sobra à direita. No celular os cartões ficam embaixo, e o conteúdo sobe.
    let larguraUtil = W, alturaUtil = H;
    if (celular) {
      alturaUtil = H * 0.58;
      camera.setViewOffset(W, H, 0, H * 0.2, W, H);
    } else {
      desloc = Math.min(larguraCartoes, W * 0.5) / 2;
      larguraUtil = W - desloc * 2;
      camera.setViewOffset(W, H, -desloc, 0, W, H);
    }
    larguraUtilAtual = larguraUtil;
    offsetAtual = null;
    camera.updateProjectionMatrix();
    const meiaAltura = 1.12, meiaLargura = 1.22;
    baseDist = Math.max(meiaAltura / tanMeia * (H / alturaUtil), meiaLargura / (tanMeia * (larguraUtil / H)));
    escalaBase = (H * dpr) / 46;
    uniforms.uEscala.value = escalaBase;
  }

  // ---------- câmera a partir do estado ----------
  const alvo = new THREE.Vector3();
  function posicionarCamera(S, foco) {
    const d = baseDist * S.dist * (1 - (foco.z ?? 0.55) * foco.v);
    alvo.set(S.alvoX + (foco.x - S.alvoX) * foco.v, S.alvoY + (foco.y - S.alvoY) * foco.v, 0);
    const st = Math.sin(S.tilt), ct = Math.cos(S.tilt);
    camera.position.set(alvo.x + Math.sin(S.yaw) * st * d, alvo.y - Math.cos(S.yaw) * st * d, ct * d);
    // "Para cima" é sempre o norte: só degeneraria com a câmera inclinada 90°, e a
    // inclinação máxima da história é de uns 60°.
    camera.up.set(0, 1, 0);
    camera.lookAt(alvo);
  }

  // ---------- rótulos ----------
  const v = new THREE.Vector3();
  function atualizarRotulos(S, foco) {
    const pesos = {
      y: S.eixoY, reg: S.wReg * S.eixoY, esc: S.wEsc * S.eixoY, tam: S.wTam * S.eixoY, idade: S.wIdade * S.eixoY,
      pico: S.picos * S.wMapa * (1 - foco.ufDim), exemplo: S.destaque * S.wMapa * (1 - foco.ufDim),
      clicado: foco.ufDim * S.wMapa,
    };
    for (const p of presos) {
      if ((pesos[p.r.grupo] || 0) < 0.02) continue;
      posicaoAtual(p.idx, S, p.r.pos);
      p.r.pos.z += 0.02;
    }
    const postos = [];
    for (const r of rotulos) {
      const o = pesos[r.grupo] || 0;
      if (o < 0.02) {
        if (r.visivel) { r.el.style.opacity = '0'; r.visivel = false; }
        continue;
      }
      v.copy(r.pos).project(camera);
      let x = (v.x * 0.5 + 0.5) * W, y = (-v.y * 0.5 + 0.5) * H;
      const w = r.el.offsetWidth;
      if (r.ancora === 'direita') x -= w; else x -= w / 2;
      x = Math.min(Math.max(x, 6), W - w - 6);
      if (r.el.classList.contains('nomeado')) {
        // Fica acima do ponto; se bater num rótulo já posto (os dois picos de Minas
        // são vizinhos), sobe até sair de cima dele.
        const h = r.el.offsetHeight;
        // No computador, não passa por cima do trilho de capítulos à direita.
        if (!celular) x = Math.min(x, W - w - 56 - (foco.painel || 0) * foco.ufDim);
        y -= h + 10;
        for (const o of postos) {
          if (x < o.x + o.w && x + w > o.x && y < o.y + o.h && y + h > o.y) y = o.y - h - 4;
        }
        postos.push({ x, y, w, h });
      } else {
        y -= 6;
      }
      r.el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
      r.el.style.opacity = o.toFixed(3);
      r.visivel = true;
    }
    for (const l of grupos.y) l.material.opacity = l.material.userData.base * S.eixoY * (1 - S.wMapa);
  }

  // ---------- posição atual de um município (para o mouse) ----------
  function posicaoAtual(i, S, out) {
    const j = i * 3;
    out.set(
      L.mapa[j] * S.wMapa + L.reg[j] * S.wReg + L.esc[j] * S.wEsc + L.tam[j] * S.wTam + L.idade[j] * S.wIdade,
      L.mapa[j + 1] * S.wMapa + L.reg[j + 1] * S.wReg + L.esc[j + 1] * S.wEsc + L.tam[j + 1] * S.wTam + L.idade[j + 1] * S.wIdade,
      L.abst[i] * S.altura * S.wMapa,
    );
    return out;
  }
  const tmp = new THREE.Vector3();
  function maisProximo(px, py, S, raio = 14) {
    let melhor = -1, menor = raio * raio;
    for (let i = 0; i < n; i++) {
      posicaoAtual(i, S, tmp).project(camera);
      const dx = (tmp.x * 0.5 + 0.5) * W - px, dy = (-tmp.y * 0.5 + 0.5) * H - py;
      const d2 = dx * dx + dy * dy;
      if (d2 < menor) { menor = d2; melhor = i; }
    }
    return melhor;
  }
  function telaDe(i, S) {
    posicaoAtual(i, S, tmp).project(camera);
    return [(tmp.x * 0.5 + 0.5) * W, (-tmp.y * 0.5 + 0.5) * H];
  }

  // ---------- quadro ----------
  function desenhar(S, foco, tempo) {
    const u = uniforms;
    u.uW.value[0] = S.wNuvem; u.uW.value[1] = S.wMapa; u.uW.value[2] = S.wReg;
    u.uW.value[3] = S.wEsc; u.uW.value[4] = S.wTam; u.uW.value[5] = S.wIdade;
    u.uC.value[0] = S.cNeutro; u.uC.value[1] = S.cAbst; u.uC.value[2] = S.cReg; u.uC.value[3] = S.cResid;
    u.uAltura.value = S.altura;
    u.uHaste.value = S.haste;
    u.uTam.value = S.tam;
    u.uTamAptos.value = S.tamAptos;
    u.uBrilho.value = S.brilho;
    u.uTempo.value = tempo;
    // Ao aproximar, a perspectiva incha os pontos; compensa a maior parte disso para
    // um estado pequeno não virar um borrão.
    const aprox = 1 - (foco.z ?? 0.55) * foco.v;
    u.uEscala.value = escalaBase * (0.3 + 0.7 * aprox);
    u.uSelDim.value = foco.selDim;
    u.uUf.value = foco.uf;
    u.uUfDim.value = foco.ufDim;
    // Com o painel do estado aberto à direita, o conteúdo se centra no espaço entre
    // os cartões e o painel.
    if (!celular) {
      const off = Math.round(-desloc + (foco.painel || 0) * 0.5 * foco.ufDim);
      if (off !== offsetAtual) {
        camera.setViewOffset(W, H, off, 0, W, H);
        camera.updateProjectionMatrix();
        offsetAtual = off;
      }
    }
    u.uSuave.value = S.suave;
    uniF.uFantasma.value = S.fantasma;
    uniF.uEspalhar.value = S.espalhar;
    fantasma.visible = S.fantasma > 0.01;
    hastes.visible = S.haste > 0.01;
    posicionarCamera(S, foco);
    atualizarRotulos(S, foco);
    renderer.render(cena, camera);
  }

  function selecionar(i) { uniforms.uSel.value = i; }
  function posMapa(i) { return [L.mapa[i * 3], L.mapa[i * 3 + 1]]; }

  // Centro e aproximação da câmera para mostrar o estado inteiro. `painelPx` é a
  // largura que o painel tira da área livre.
  function enquadrarEstado(k, painelPx = 0) {
    const [x0, y0, x1, y1] = caixas[k];
    const livre = celular ? 1 : larguraUtilAtual / Math.max(larguraUtilAtual - painelPx, 200);
    // No celular o painel sobe por baixo e sobra menos altura para o mapa.
    const f = Math.max(((x1 - x0) / 2 / 1.22) * livre, (y1 - y0) / 2 / 1.12) * (celular ? 1.9 : 1.45);
    return { x: (x0 + x1) / 2, y: (y0 + y1) / 2, z: 1 - Math.min(Math.max(f, 0.3), 0.95) };
  }

  return { redimensionar, desenhar, maisProximo, telaDe, selecionar, posMapa, enquadrarEstado, marcar, ufLista: L.ufLista };
}
