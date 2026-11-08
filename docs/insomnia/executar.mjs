// Executa uma exportação v4 do Insomnia contra uma API, imitando os scripts (insomnia.*) — TK-020.
// Uso: node executar.mjs <collection.json> <overrides.json> <pasta-fixtures>
// PULAR=00a,08 pula as pastas cujo nome começa com esses prefixos.
// O jeito normal de rodar é scripts/rodar_collection.sh, que sobe a API local e monta o overrides.json.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const [, , arqCollection, arqOverrides, dirFixtures] = process.argv;
const exp = JSON.parse(fs.readFileSync(arqCollection, 'utf8'));
const over = JSON.parse(fs.readFileSync(arqOverrides, 'utf8'));
const R = exp.resources;
const baseEnv = R.find(r => r._type === 'environment' && r.parentId === exp.resources.find(x => x._type === 'workspace')?._id);
const subEnv = R.find(r => r._type === 'environment' && r.name.startsWith('Local'));
if (!subEnv) { console.error('a collection não tem um ambiente "Local"'); process.exit(2); }
// Como o Insomnia: ambiente base, depois o sub-ambiente, depois os valores desta execução
const env = { ...(baseEnv?.data || {}), ...subEnv.data, ...over };

const render = (s) => typeof s !== 'string' ? s : s.replace(/\{\{\s*_\.([a-zA-Z0-9_]+)\s*\}\}/g, (_, k) => (env[k] ?? ''));

function expect(v) {
  const fail = (m) => { throw new Error(m); };
  const api = {
    equal: (x) => { if (v !== x) fail(`esperado ${JSON.stringify(x)}, veio ${JSON.stringify(v)}`); },
    eql: (x) => { if (JSON.stringify(v) !== JSON.stringify(x)) fail(`esperado ${JSON.stringify(x)}, veio ${JSON.stringify(v)}`); },
    include: (x) => { if (!String(v).includes(x)) fail(`"${String(v).slice(0, 160)}" não contém "${x}"`); },
    oneOf: (arr) => { if (!arr.includes(v)) fail(`${JSON.stringify(v)} não está em ${JSON.stringify(arr)}`); },
  };
  return { to: { ...api, be: api } };
}

function rodarScript(codigo, resposta, resultados) {
  if (!codigo) return;
  const insomnia = {
    environment: { get: (k) => env[k], set: (k, v) => { env[k] = v; }, unset: (k) => { delete env[k]; } },
    test: (nome, fn) => { try { fn(); resultados.push({ nome, ok: true }); } catch (e) { resultados.push({ nome, ok: false, erro: e.message }); } },
    expect,
    response: resposta,
  };
  vm.runInNewContext(codigo, { insomnia, console, Date, Math, String, JSON, Array, parseInt, Error }, { timeout: 5000 });
}

// PULAR=00a,08: compara o código da pasta (o primeiro termo do nome), não um prefixo qualquer
const pular = (process.env.PULAR || '').split(',').map(x => x.trim()).filter(Boolean);
const pastas = R.filter(r => r._type === 'request_group' && !pular.includes(r.name.split(' ')[0])).sort((a, b) => a.metaSortKey - b.metaSortKey);
let total = 0, falhas = 0;
for (const p of pastas) {
  console.log(`\n## ${p.name}`);
  const reqs = R.filter(r => r._type === 'request' && r.parentId === p._id).sort((a, b) => a.metaSortKey - b.metaSortKey);
  for (const q of reqs) {
    const resultados = [];
    try { rodarScript(q.preRequestScript, undefined, resultados); } catch (e) { resultados.push({ nome: 'script antes da requisição', ok: false, erro: e.message }); }
    let url = render(q.url);
    const qs = (q.parameters || []).filter(x => !x.disabled).map(x => `${encodeURIComponent(x.name)}=${encodeURIComponent(render(x.value))}`);
    if (qs.length) url += (url.includes('?') ? '&' : '?') + qs.join('&');
    const headers = {};
    for (const h of q.headers || []) if (!h.disabled && !(q.body?.mimeType === 'multipart/form-data' && h.name.toLowerCase() === 'content-type')) headers[h.name] = render(h.value);
    if (q.authentication?.type === 'bearer' && !q.authentication.disabled) headers['Authorization'] = 'Bearer ' + render(q.authentication.token);
    let body;
    if (q.body?.mimeType === 'application/json') body = render(q.body.text);
    else if (q.body?.mimeType === 'multipart/form-data') {
      body = new FormData();
      for (const prm of q.body.params) {
        if (prm.type === 'file') {
          const buf = fs.readFileSync(path.join(dirFixtures, prm.fixture));
          body.append(prm.name, new Blob([buf]), prm.fixture);
        } else body.append(prm.name, render(prm.value));
      }
    }
    let res, texto = '', ct = '';
    try {
      res = await fetch(url, { method: q.method, headers, body, signal: AbortSignal.timeout(30000) });
      const buf = Buffer.from(await res.arrayBuffer());
      ct = res.headers.get('content-type') || '';
      texto = ct.includes('json') ? buf.toString('utf8') : `<${buf.length} bytes ${ct}>`;
    } catch (e) {
      resultados.push({ nome: 'requisição', ok: false, erro: e.message });
    }
    if (res) {
      const resposta = {
        code: res.status,
        json: () => JSON.parse(texto),
        text: () => texto,
        headers: { get: (n) => res.headers.get(n) },
      };
      try { rodarScript(q.afterResponseScript, resposta, resultados); } catch (e) { resultados.push({ nome: 'script', ok: false, erro: e.message }); }
    }
    const ruins = resultados.filter(x => !x.ok);
    total++; if (ruins.length) falhas++;
    console.log(`${ruins.length ? 'FALHOU' : 'ok    '} ${res ? res.status : '---'} ${q.method.padEnd(6)} ${q.name}`);
    for (const x of ruins) console.log(`         ✗ ${x.nome}: ${x.erro}${texto && !texto.startsWith('<') ? '\n           corpo: ' + texto.slice(0, 220) : ''}`);
  }
}
console.log(`\n${total - falhas}/${total} requisições com todos os testes passando`);
process.exit(falhas ? 1 : 0);
