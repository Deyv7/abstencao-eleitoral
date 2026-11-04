// Carrega os dados exportados por src/exportar_web.py e calcula as posições de cada
// município em cada cena. Nenhum número da página é escrito à mão: os textos usam
// data-v="caminho.no.resumo" e são preenchidos aqui.

export const UF_NOMES = {
  AC: 'Acre', AL: 'Alagoas', AP: 'Amapá', AM: 'Amazonas', BA: 'Bahia', CE: 'Ceará',
  DF: 'Distrito Federal', ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão', MT: 'Mato Grosso',
  MS: 'Mato Grosso do Sul', MG: 'Minas Gerais', PA: 'Pará', PB: 'Paraíba', PR: 'Paraná',
  PE: 'Pernambuco', PI: 'Piauí', RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte',
  RS: 'Rio Grande do Sul', RO: 'Rondônia', RR: 'Roraima', SC: 'Santa Catarina', SP: 'São Paulo',
  SE: 'Sergipe', TO: 'Tocantins',
};

export const CORES_REGIAO = ['#5bc0a6', '#f2b44c', '#e07a5f', '#7aa7e8', '#c08fe0'];

// Domínios fixos das escalas (em pontos percentuais de abstenção).
export const Y_DOMINIO = [5, 45];
export const COR_DOMINIO = [10, 35];
export const RESID_LIMITE = 8;

const nf = (min, max = min) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: min, maximumFractionDigits: max });
const F = {
  int: (v) => nf(0).format(v),
  pct2: (v) => nf(2).format(v) + '%',
  pct1: (v) => nf(1).format(v) + '%',
  dec1: (v) => nf(1).format(v),
  dec2: (v) => nf(2).format(v),
  abs2: (v) => nf(2).format(Math.abs(v)),
  // fração -> porcentagem, sem casa decimal inútil: 0.43 -> 43%, 0.345 -> 34,5%
  fr: (v) => nf(0, 1).format(v * 100) + '%',
};
export const formatar = (v, f) => (F[f] ? F[f](v) : String(v));

// "regressao.variaveis[termo=pct_70_mais].coef"
export function caminho(obj, rota) {
  let atual = obj;
  for (const parte of rota.split('.')) {
    if (atual == null) return undefined;
    const m = parte.match(/^(\w+)\[(\w+)=([\w-]+)\]$/);
    if (m) {
      atual = (atual[m[1]] || []).find((x) => String(x[m[2]]) === m[3]);
    } else {
      atual = atual[parte];
    }
  }
  return atual;
}

function listaUfs(itens) {
  const partes = itens.map((x) => `${UF_NOMES[x.uf] || x.uf} (${F.pct2(x.pct)})`);
  return partes.slice(0, -1).join(', ') + ' e ' + partes.at(-1);
}

export function preencherTextos(resumo) {
  const regs = [...resumo.regioes].sort((a, b) => a.mediana - b.mediana);
  resumo.derivado = {
    razao_armadilha: Math.round(resumo.armadilha.aptos_sem_filtro / resumo.armadilha.aptos_com_filtro),
    reg_min: regs[0],
    reg_max: regs.at(-1),
  };
  for (const el of document.querySelectorAll('[data-v]')) {
    const v = caminho(resumo, el.dataset.v);
    if (v === undefined) {
      console.warn('valor ausente no resumo:', el.dataset.v);
      continue;
    }
    el.dataset.valor = v;
    el.textContent = typeof v === 'number' ? formatar(v, el.dataset.f) : v;
  }
  for (const el of document.querySelectorAll('[data-lista]')) {
    el.textContent = listaUfs(resumo[el.dataset.lista]);
  }
  for (const el of document.querySelectorAll('[data-lista-picos]')) {
    const partes = resumo.picos[el.dataset.listaPicos].map((p) => `${p.nome} (${p.uf}), com ${F.pct2(p.pct)}`);
    el.textContent = partes.slice(0, -1).join('; ') + ' e ' + partes.at(-1);
  }
  for (const el of document.querySelectorAll('[data-uf-nome]')) {
    const uf = caminho(resumo, el.dataset.ufNome);
    el.textContent = UF_NOMES[uf] || uf;
  }
}

// Gerador pseudoaleatório com semente, para a nuvem e o espalhamento serem sempre iguais.
function aleatorio(semente) {
  let s = semente >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const escala = (v, [a, b], [c, d]) => c + ((v - a) / (b - a)) * (d - c);
const limitar = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));

export const yAbst = (pct) => escala(pct, Y_DOMINIO, [-0.9, 0.9]);
export const X_REGIOES = [-0.88, -0.44, 0, 0.44, 0.88];

export function dominios(m) {
  const max = (a) => a.reduce((x, y) => (y > x ? y : x), -Infinity);
  const min = (a) => a.reduce((x, y) => (y < x ? y : x), Infinity);
  return {
    esc: [0, Math.ceil(max(m.baixa_esc) / 10) * 10],
    idade: [0, Math.ceil(max(m.p70) / 5) * 5],
    // Começa em 1 mil eleitores, para a primeira marca do eixo caber.
    tam: [Math.min(Math.log2(1000), Math.floor(min(m.log2_aptos))), Math.ceil(max(m.log2_aptos))],
  };
}

export function montarLayouts(m) {
  const n = m.id.length;
  const rnd = aleatorio(2022);
  const dom = dominios(m);
  const L = {
    n,
    dom,
    mapa: new Float32Array(n * 3),
    nuvem: new Float32Array(n * 3),
    reg: new Float32Array(n * 3),
    esc: new Float32Array(n * 3),
    tam: new Float32Array(n * 3),
    idade: new Float32Array(n * 3),
    abst: new Float32Array(n),
    resid: new Float32Array(n),
    residViz: new Float32Array(n),
    regiao: new Float32Array(n),
    peso: new Float32Array(n),
    idx: new Float32Array(n),
    // Índice do estado de cada município, para a cena acender um estado só.
    ufLista: [...new Set(m.uf)].sort(),
    uf: new Float32Array(n),
  };
  const ufIdx = new Map(L.ufLista.map((u, k) => [u, k]));

  // Mapa: equirretangular corrigida pela latitude média do país.
  const lon0 = -52.5, lat0 = -14.2, k = Math.cos((15 * Math.PI) / 180), div = 19;
  const lmin = dom.tam[0], lmax = dom.tam[1];

  for (let i = 0; i < n; i++) {
    const j = i * 3;
    L.mapa[j] = ((m.lon[i] - lon0) * k) / div;
    L.mapa[j + 1] = (m.lat[i] - lat0) / div;

    // Nuvem: elipsoide achatado, mais denso no centro.
    const u = rnd(), v = rnd(), w = Math.cbrt(rnd());
    const th = 2 * Math.PI * u, ph = Math.acos(2 * v - 1);
    const r = 1.35 * w;
    L.nuvem[j] = r * Math.sin(ph) * Math.cos(th);
    L.nuvem[j + 1] = 0.75 * r * Math.cos(ph);
    L.nuvem[j + 2] = r * Math.sin(ph) * Math.sin(th);

    const y = yAbst(m.abst[i]);
    const jit = () => (rnd() - 0.5) * 0.012;
    L.esc[j] = escala(m.baixa_esc[i], dom.esc, [-1, 1]);
    L.esc[j + 1] = y + jit();
    L.tam[j] = escala(m.log2_aptos[i], dom.tam, [-1, 1]);
    L.tam[j + 1] = y + jit();
    L.idade[j] = escala(m.p70[i], dom.idade, [-1, 1]);
    L.idade[j + 1] = y + jit();

    L.abst[i] = limitar((m.abst[i] - COR_DOMINIO[0]) / (COR_DOMINIO[1] - COR_DOMINIO[0]));
    L.resid[i] = limitar(m.residuo[i] / RESID_LIMITE, -1, 1);
    // A média dos vizinhos varia menos que o erro de cada município: escala de metade
    // do tamanho, para as manchas aparecerem com a mesma força de cor.
    L.residViz[i] = limitar(m.residuo_vizinhos[i] / (RESID_LIMITE / 2), -1, 1);
    L.regiao[i] = m.regiao[i];
    L.peso[i] = limitar((m.log2_aptos[i] - lmin) / (lmax - lmin));
    L.idx[i] = i;
    L.uf[i] = ufIdx.get(m.uf[i]);
  }

  // Colunas por região em forma de violino: os municípios de cada faixa de 0,5 p.p.
  // se espalham para os lados, então a largura mostra quantos há em cada altura.
  const faixa = 0.5;
  const grupos = new Map();
  for (let i = 0; i < n; i++) {
    const chave = m.regiao[i] * 1000 + Math.floor(m.abst[i] / faixa);
    if (!grupos.has(chave)) grupos.set(chave, []);
    grupos.get(chave).push(i);
  }
  for (const membros of grupos.values()) {
    membros.sort((a, b) => m.abst[a] - m.abst[b]);
    const q = membros.length;
    const passo = Math.min(0.0065, 0.36 / Math.max(q, 1));
    membros.forEach((i, kk) => {
      const lado = kk % 2 === 0 ? 1 : -1;
      const dx = lado * Math.ceil(kk / 2) * passo;
      const j = i * 3;
      L.reg[j] = X_REGIOES[m.regiao[i]] + dx;
      L.reg[j + 1] = yAbst(m.abst[i]);
    });
  }
  return L;
}

export async function carregar() {
  const base = import.meta.env.BASE_URL;
  const [municipios, resumo] = await Promise.all([
    fetch(`${base}dados/municipios.json`).then((r) => r.json()),
    fetch(`${base}dados/resumo.json`).then((r) => r.json()),
  ]);
  return { municipios, resumo };
}
