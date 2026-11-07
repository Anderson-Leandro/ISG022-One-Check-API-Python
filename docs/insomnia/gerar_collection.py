"""Gera a collection do Insomnia (formato de exportação v4) com a suíte de testes manuais da API.

Uso: python docs/insomnia/gerar_collection.py
Saída: docs/insomnia/onecheck-api.insomnia.json

Cada requisição tem um script "after-response" com os testes (status HTTP, campo `sucesso`,
mensagem) e, quando cria algo, grava o ID ou o token no ambiente ativo. As pastas são numeradas
na ordem de execução: rodadas em sequência pelo Collection Runner, uma prepara o que a próxima usa.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SAIDA = AQUI / "onecheck-api.insomnia.json"
WRK = "wrk_onecheck_api"

# Variáveis que o usuário preenche antes de rodar (as demais são gravadas pelos scripts)
VARS_USUARIO = {
    "base_url": "http://localhost:8000/api/v1",
    "email_admin": "admin@onecheck.local",
    "senha_admin": "",
    "email_gestor": "gestor@onecheck.local",
    "senha_gestor": "",
    "email_vistoriador": "vistoriador@onecheck.local",
    "senha_vistoriador": "",
    "mfa_secret": "",
    "mfa_secret_admin": "",
    "mfa_secret_gestor": "",
    "mfa_secret_vistoriador": "",
    "mfa_codigo": "",
    "senha_teste": "",
    "seed_secret": "",
}
# Variáveis gravadas pelos scripts (começam vazias)
VARS_AUTO = [
    "mfa_codigo_atual", "temp_token", "token_admin", "refresh_admin", "refresh_admin_antigo", "admin_id",
    "token_gestor", "gestor_id", "token_vistoriador", "vistoriador_id",
    "email_locatario_a", "locatario_a_id", "token_locatario_a",
    "email_locatario_b", "locatario_b_id", "token_locatario_b", "refresh_locatario_b",
    "email_visualizador", "visualizador_id", "token_visualizador",
    "sufixo", "hoje", "daqui_1_ano", "ontem", "daqui_7_dias",
    "imovel_id", "comodo_id", "comodo_extra_id", "contrato_id", "agendamento_id",
    "item_vistoria_id", "checklist_id", "checklist_item_id", "foto_id",
    "checklist2_id", "checklist2_item_id", "problema_id",
]

# Calcula o código TOTP (RFC 6238, SHA-1, 6 dígitos, 30 s) a partir de mfa_secret, sem dependências.
# Sem mfa_secret, usa o código digitado em mfa_codigo.
TOTP_JS = r"""
function _sha1(bytes) {
  const rotl = (n, s) => (n << s) | (n >>> (32 - s));
  const ml = bytes.length * 8;
  const msg = bytes.slice(); msg.push(0x80);
  while ((msg.length % 64) !== 56) msg.push(0);
  for (let i = 7; i >= 0; i--) msg.push(Math.floor(ml / Math.pow(2, 8 * i)) & 0xff);
  let h0 = 0x67452301, h1 = 0xEFCDAB89, h2 = 0x98BADCFE, h3 = 0x10325476, h4 = 0xC3D2E1F0;
  for (let off = 0; off < msg.length; off += 64) {
    const w = new Array(80);
    for (let i = 0; i < 16; i++) w[i] = (msg[off + 4*i] << 24) | (msg[off + 4*i + 1] << 16) | (msg[off + 4*i + 2] << 8) | msg[off + 4*i + 3];
    for (let i = 16; i < 80; i++) w[i] = rotl(w[i-3] ^ w[i-8] ^ w[i-14] ^ w[i-16], 1);
    let a = h0, b = h1, c = h2, d = h3, e = h4;
    for (let i = 0; i < 80; i++) {
      let f, k;
      if (i < 20) { f = (b & c) | (~b & d); k = 0x5A827999; }
      else if (i < 40) { f = b ^ c ^ d; k = 0x6ED9EBA1; }
      else if (i < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8F1BBCDC; }
      else { f = b ^ c ^ d; k = 0xCA62C1D6; }
      const t = (rotl(a, 5) + f + e + k + w[i]) | 0;
      e = d; d = c; c = rotl(b, 30); b = a; a = t;
    }
    h0 = (h0 + a) | 0; h1 = (h1 + b) | 0; h2 = (h2 + c) | 0; h3 = (h3 + d) | 0; h4 = (h4 + e) | 0;
  }
  const out = [];
  [h0, h1, h2, h3, h4].forEach(h => { for (let i = 3; i >= 0; i--) out.push((h >>> (8 * i)) & 0xff); });
  return out;
}
function _hmacSha1(key, data) {
  if (key.length > 64) key = _sha1(key);
  const k = key.slice(); while (k.length < 64) k.push(0);
  const ipad = k.map(b => b ^ 0x36), opad = k.map(b => b ^ 0x5c);
  return _sha1(opad.concat(_sha1(ipad.concat(data))));
}
function _base32(s) {
  const alf = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '', out = [];
  for (const ch of s.replace(/=+$/, '').replace(/\s/g, '').toUpperCase()) {
    const v = alf.indexOf(ch); if (v < 0) throw new Error('mfa_secret não é Base32');
    bits += v.toString(2).padStart(5, '0');
  }
  for (let i = 0; i + 8 <= bits.length; i += 8) out.push(parseInt(bits.slice(i, i + 8), 2));
  return out;
}
function totp(secret) {
  let c = Math.floor(Date.now() / 1000 / 30); const msg = [];
  for (let i = 7; i >= 0; i--) { msg[i] = c & 0xff; c = Math.floor(c / 256); }
  const h = _hmacSha1(_base32(secret), msg), o = h[19] & 0xf;
  const n = ((h[o] & 0x7f) << 24) | (h[o+1] << 16) | (h[o+2] << 8) | h[o+3];
  return String(n % 1000000).padStart(6, '0');
}
""".strip()


def totp_js(conta: str) -> str:
    """Script que grava mfa_codigo_atual: segredo da conta (mfa_secret_<conta>), senão mfa_secret, senão mfa_codigo."""
    return TOTP_JS + (
        f"\nconst _secret = insomnia.environment.get('mfa_secret_{conta}') || insomnia.environment.get('mfa_secret');"
        "\ninsomnia.environment.set('mfa_codigo_atual', _secret ? totp(_secret) : String(insomnia.environment.get('mfa_codigo') || ''));"
    )

DATAS_JS = r"""
const _d = (dias) => { const x = new Date(); x.setDate(x.getDate() + dias); return x.toISOString().slice(0, 10); };
insomnia.environment.set('hoje', _d(0));
insomnia.environment.set('ontem', _d(-1));
insomnia.environment.set('daqui_7_dias', _d(7) + 'T10:00:00');
insomnia.environment.set('daqui_1_ano', _d(365));
""".strip()


def email_unico(var: str, prefixo: str) -> str:
    return (f"insomnia.environment.set('{var}', '{prefixo}.' + Date.now() + '@onecheck.test');\n"
            "insomnia.environment.set('sufixo', String(Date.now()).slice(-6));")


@dataclass
class Caso:
    nome: str
    metodo: str
    caminho: str
    auth: str | None = None          # nome da variável com o token (ex.: token_admin) ou literal "!abc"
    corpo: dict | list | str | None = None
    form: list[dict] | None = None   # multipart: [{"name": "foto", "type": "file", "fixture": "foto-valida.png"}]
    query: dict | None = None
    headers: dict | None = None
    status: int | list[int] = 200
    sucesso: bool | None = None      # True/False confere o campo `sucesso`; None não confere
    erro: str | None = None          # trecho esperado em `erro` ou `detail`
    salvar: dict = field(default_factory=dict)   # variável -> expressão JS sobre `b` (corpo JSON)
    antes: str = ""                  # JS executado antes da requisição
    testes: str = ""                 # testes extras (JS), com `r` (resposta) e `b` (corpo)
    descricao: str = ""


def _id(prefixo: str, *partes: str) -> str:
    return prefixo + "_" + hashlib.sha1("|".join(partes).encode()).hexdigest()[:24]


def _depois(c: Caso) -> str:
    linhas = [
        "const r = insomnia.response;",
        "let b = {};",
        "try { b = r.json(); } catch (e) { b = {}; }",
    ]
    if isinstance(c.status, list):
        linhas.append(f"insomnia.test('HTTP {' ou '.join(map(str, c.status))}', () => insomnia.expect(r.code).to.be.oneOf({json.dumps(c.status)}));")
    else:
        linhas.append(f"insomnia.test('HTTP {c.status}', () => insomnia.expect(r.code).to.equal({c.status}));")
    if c.sucesso is not None:
        linhas.append(f"insomnia.test('sucesso = {str(c.sucesso).lower()}', () => insomnia.expect(b.sucesso).to.equal({str(c.sucesso).lower()}));")
    if c.erro:
        linhas.append(
            f"insomnia.test({json.dumps('mensagem contém: ' + c.erro, ensure_ascii=False)}, () => "
            f"insomnia.expect(String(b.erro || JSON.stringify(b.detail || ''))).to.include({json.dumps(c.erro, ensure_ascii=False)}));"
        )
    if c.testes:
        linhas.append(c.testes.strip())
    for var, expr in c.salvar.items():
        linhas.append(f"try {{ const v = {expr}; if (v !== undefined && v !== null) insomnia.environment.set('{var}', String(v)); }} catch (e) {{}}")
    return "\n".join(linhas)


def _requisicao(pasta_id: str, ordem: int, c: Caso) -> dict:
    rid = _id("req", pasta_id, c.nome)
    headers = [{"name": k, "value": v} for k, v in (c.headers or {}).items()]
    corpo: dict = {}
    if c.form is not None:
        params = []
        for p in c.form:
            if p.get("type") == "file":
                params.append({"name": p["name"], "type": "file", "fileName": "",
                               "description": f"Selecione docs/insomnia/fixtures/{p['fixture']}", "fixture": p["fixture"]})
            else:
                params.append({"name": p["name"], "value": p["value"]})
        corpo = {"mimeType": "multipart/form-data", "params": params}
        headers.append({"name": "Content-Type", "value": "multipart/form-data"})
    elif c.corpo is not None:
        texto = c.corpo if isinstance(c.corpo, str) else json.dumps(c.corpo, ensure_ascii=False, indent=2)
        corpo = {"mimeType": "application/json", "text": texto}
        headers.append({"name": "Content-Type", "value": "application/json"})
    auth: dict = {}
    if c.auth:
        token = c.auth[1:] if c.auth.startswith("!") else "{{ _.%s }}" % c.auth
        auth = {"type": "bearer", "token": token, "prefix": "", "disabled": False}
    return {
        "_id": rid,
        "_type": "request",
        "parentId": pasta_id,
        "name": c.nome,
        "description": c.descricao,
        "method": c.metodo,
        "url": "{{ _.base_url }}" + c.caminho,
        "parameters": [{"name": k, "value": v, "disabled": False} for k, v in (c.query or {}).items()],
        "headers": headers,
        "body": corpo,
        "authentication": auth,
        "preRequestScript": c.antes.strip(),
        "afterResponseScript": _depois(c),
        "metaSortKey": ordem,
        "isPrivate": False,
        "settingStoreCookies": False,
        "settingSendCookies": False,
        "settingDisableRenderRequestBody": False,
        "settingEncodeUrl": True,
        "settingRebuildPath": True,
        "settingFollowRedirects": "global",
    }


# ----------------------------------------------------------------------------------------------
# Casos
# ----------------------------------------------------------------------------------------------
ENDERECO = {"rua": "Rua das Flores", "numero": "100", "bairro": "Centro", "cidade": "Mauá",
            "estado": "SP", "cep": "09310-000", "latitude": -23.6677, "longitude": -46.4613}

PASTAS: list[tuple[str, str, list[Caso]]] = [
    ("00 Saúde e autenticação básica", "Sem login. Confere que as rotas protegidas recusam acesso anônimo.", [
        Caso("✅ Health check", "GET", "/health", sucesso=True, testes="insomnia.test('status ok', () => insomnia.expect(b.dados.status).to.equal('ok'));"),
        Caso("❌ Rota inexistente → 404", "GET", "/rota-que-nao-existe", status=404),
        Caso("❌ Rota protegida sem token → 401", "GET", "/usuarios/me", status=401, erro="Token ausente"),
        Caso("❌ Token malformado → 401", "GET", "/usuarios/me", auth="!abc.def.ghi", status=401),
        Caso("❌ Login sem senha → 422", "POST", "/auth/login", corpo={"email": "alguem@onecheck.test"}, status=422),
        Caso("❌ Login de e-mail inexistente → falha genérica", "POST", "/auth/login",
             corpo={"email": "nao.existe@onecheck.test", "senha": "Qualquer.Senha#1"}, sucesso=False, erro="Credenciais inválidas",
             descricao="A API responde HTTP 200 com sucesso=false (padrão de envelope) e a mesma mensagem de senha errada, para não revelar quais e-mails existem."),
    ]),
    ("00a Primeiro acesso: configurar o MFA (uma vez por conta)",
     "Só para contas que ainda não configuraram o autenticador (banco criado pelo POST /admin/seed fora de desenvolvimento). "
     "Grava mfa_secret_<conta> no ambiente; escaneie o QR (dados.qr_code_url) se quiser usar o app autenticador também. "
     "Se o login responder mfa_required em vez de mfa_setup_required, a conta já está configurada: pule para a pasta 01.", [
        Caso("✅ admin: login pede configuração do MFA", "POST", "/auth/login", corpo={"email": "{{ _.email_admin }}", "senha": "{{ _.senha_admin }}"},
             sucesso=True, salvar={"temp_token": "b.dados.temp_token"},
             testes="insomnia.test('pede configuração', () => insomnia.expect(b.dados.mfa_setup_required).to.equal(true));"),
        Caso("✅ admin: gerar o segredo do autenticador", "GET", "/auth/mfa/setup-login", query={"temp_token": "{{ _.temp_token }}"},
             sucesso=True, salvar={"mfa_secret_admin": "b.dados.secret"}),
        Caso("✅ admin: ativar o MFA com o primeiro código", "POST", "/auth/mfa/activate-login", corpo={"temp_token": "{{ _.temp_token }}", "codigo": "{{ _.mfa_codigo_atual }}"},
             antes=totp_js("admin"), sucesso=True, salvar={"token_admin": "b.dados.access_token", "admin_id": "b.dados.usuario.id"}),
        Caso("✅ gestor: login pede configuração do MFA", "POST", "/auth/login", corpo={"email": "{{ _.email_gestor }}", "senha": "{{ _.senha_gestor }}"},
             sucesso=True, salvar={"temp_token": "b.dados.temp_token"},
             testes="insomnia.test('pede configuração', () => insomnia.expect(b.dados.mfa_setup_required).to.equal(true));"),
        Caso("✅ gestor: gerar o segredo do autenticador", "GET", "/auth/mfa/setup-login", query={"temp_token": "{{ _.temp_token }}"},
             sucesso=True, salvar={"mfa_secret_gestor": "b.dados.secret"}),
        Caso("✅ gestor: ativar o MFA com o primeiro código", "POST", "/auth/mfa/activate-login", corpo={"temp_token": "{{ _.temp_token }}", "codigo": "{{ _.mfa_codigo_atual }}"},
             antes=totp_js("gestor"), sucesso=True, salvar={"token_gestor": "b.dados.access_token", "gestor_id": "b.dados.usuario.id"}),
        Caso("✅ vistoriador: login pede configuração do MFA", "POST", "/auth/login", corpo={"email": "{{ _.email_vistoriador }}", "senha": "{{ _.senha_vistoriador }}"},
             sucesso=True, salvar={"temp_token": "b.dados.temp_token"},
             testes="insomnia.test('pede configuração', () => insomnia.expect(b.dados.mfa_setup_required).to.equal(true));"),
        Caso("✅ vistoriador: gerar o segredo do autenticador", "GET", "/auth/mfa/setup-login", query={"temp_token": "{{ _.temp_token }}"},
             sucesso=True, salvar={"mfa_secret_vistoriador": "b.dados.secret"}),
        Caso("✅ vistoriador: ativar o MFA com o primeiro código", "POST", "/auth/mfa/activate-login", corpo={"temp_token": "{{ _.temp_token }}", "codigo": "{{ _.mfa_codigo_atual }}"},
             antes=totp_js("vistoriador"), sucesso=True, salvar={"token_vistoriador": "b.dados.access_token", "vistoriador_id": "b.dados.usuario.id"}),
        Caso("❌ Reusar o token de setup depois de ativar → 409", "GET", "/auth/mfa/setup-login", query={"temp_token": "{{ _.temp_token }}"},
             status=409, erro="MFA já configurado",
             descricao="Usa o token de primeiro acesso do vistoriador, que ainda está dentro da validade de 10 minutos. Como a conta já ativou o MFA, "
                       "a rota recusa gerar um segredo novo e o autenticador configurado continua valendo."),
        Caso("❌ Gerar segredo com token temporário inválido → 401", "GET", "/auth/mfa/setup-login", query={"temp_token": "token-invalido"}, status=401),
    ]),
    ("01 Login com MFA (admin, gestor, vistoriador)", "Contas do seed. Preencha senha_* e mfa_secret (ou mfa_codigo) no ambiente. Grava token_admin, token_gestor e token_vistoriador.", [
        Caso("✅ Login admin (etapa 1: senha)", "POST", "/auth/login", corpo={"email": "{{ _.email_admin }}", "senha": "{{ _.senha_admin }}"},
             sucesso=True, salvar={"temp_token": "b.dados.temp_token"},
             testes="insomnia.test('pede MFA', () => insomnia.expect(b.dados.mfa_required).to.equal(true));"),
        Caso("✅ Login admin (etapa 2: código MFA)", "POST", "/auth/mfa/verify", corpo={"temp_token": "{{ _.temp_token }}", "codigo": "{{ _.mfa_codigo_atual }}"},
             antes=totp_js("admin"), sucesso=True,
             salvar={"token_admin": "b.dados.access_token", "refresh_admin": "b.dados.refresh_token", "admin_id": "b.dados.usuario.id"},
             testes="insomnia.test('perfil admin', () => insomnia.expect(b.dados.usuario.role).to.equal('admin'));"),
        Caso("✅ Login gestor (etapa 1: senha)", "POST", "/auth/login", corpo={"email": "{{ _.email_gestor }}", "senha": "{{ _.senha_gestor }}"},
             sucesso=True, salvar={"temp_token": "b.dados.temp_token"}),
        Caso("❌ MFA com código errado", "POST", "/auth/mfa/verify", corpo={"temp_token": "{{ _.temp_token }}", "codigo": "000000"},
             sucesso=False, erro="Código MFA inválido",
             descricao="Conta 1 tentativa para o limite de 5 por conta em 15 minutos."),
        Caso("✅ Login gestor (etapa 2: código MFA)", "POST", "/auth/mfa/verify", corpo={"temp_token": "{{ _.temp_token }}", "codigo": "{{ _.mfa_codigo_atual }}"},
             antes=totp_js("gestor"), sucesso=True, salvar={"token_gestor": "b.dados.access_token", "gestor_id": "b.dados.usuario.id"}),
        Caso("✅ Login vistoriador (etapa 1: senha)", "POST", "/auth/login", corpo={"email": "{{ _.email_vistoriador }}", "senha": "{{ _.senha_vistoriador }}"},
             sucesso=True, salvar={"temp_token": "b.dados.temp_token"}),
        Caso("❌ Token de verificação não serve no setup-login → 401", "GET", "/auth/mfa/setup-login", query={"temp_token": "{{ _.temp_token }}"},
             status=401, erro="Token MFA inválido",
             descricao="O login de quem já tem autenticador emite um token do tipo mfa, que só vale no /auth/mfa/verify. "
                       "Aceitá-lo aqui permitiria trocar o segredo só com a senha (falha N1, SEC-021). "
                       "A requisição seguinte confirma que o segredo antigo continua valendo."),
        Caso("✅ Login vistoriador (etapa 2: código MFA)", "POST", "/auth/mfa/verify", corpo={"temp_token": "{{ _.temp_token }}", "codigo": "{{ _.mfa_codigo_atual }}"},
             antes=totp_js("vistoriador"), sucesso=True, salvar={"token_vistoriador": "b.dados.access_token", "vistoriador_id": "b.dados.usuario.id"}),
        Caso("❌ MFA com token temporário inválido", "POST", "/auth/mfa/verify", corpo={"temp_token": "token-invalido", "codigo": "123456"},
             sucesso=False, erro="Token MFA inválido"),
        Caso("✅ Renovar sessão (refresh) do admin", "POST", "/auth/refresh", corpo={"refresh_token": "{{ _.refresh_admin }}"},
             antes="insomnia.environment.set('refresh_admin_antigo', insomnia.environment.get('refresh_admin'));",
             sucesso=True, salvar={"token_admin": "b.dados.access_token", "refresh_admin": "b.dados.refresh_token"}),
        Caso("❌ Reusar o refresh token já trocado", "POST", "/auth/refresh", corpo={"refresh_token": "{{ _.refresh_admin_antigo }}"},
             sucesso=False, erro="Refresh token inválido", descricao="O refresh é rotativo: o anterior deixa de valer."),
        Caso("❌ Vistoriador não desliga o próprio MFA → 403", "POST", "/auth/mfa/desabilitar", auth="token_vistoriador",
             corpo={"senha": "{{ _.senha_vistoriador }}"}, status=403, erro="MFA é obrigatório"),
        Caso("❌ Admin não reseta o próprio MFA → 403", "POST", "/auth/mfa/disable", auth="token_admin",
             corpo={"usuario_id": "{{ _.admin_id }}"}, status=403, erro="próprio MFA"),
    ]),
    ("02 Usuários", "Cria locatário A, locatário B e visualizador (e-mails únicos a cada execução) e faz login com eles.", [
        Caso("✅ Admin cria locatário A", "POST", "/usuarios", auth="token_admin", antes=email_unico("email_locatario_a", "locatario.a"),
             corpo={"nome": "Locatário A (Insomnia)", "email": "{{ _.email_locatario_a }}", "senha": "{{ _.senha_teste }}", "role": "locatario"},
             sucesso=True, salvar={"locatario_a_id": "b.dados.id"}),
        Caso("✅ Gestor cria locatário B", "POST", "/usuarios", auth="token_gestor", antes=email_unico("email_locatario_b", "locatario.b"),
             corpo={"nome": "Locatário B (Insomnia)", "email": "{{ _.email_locatario_b }}", "senha": "{{ _.senha_teste }}", "role": "locatario"},
             sucesso=True, salvar={"locatario_b_id": "b.dados.id"}),
        Caso("✅ Admin cria visualizador", "POST", "/usuarios", auth="token_admin", antes=email_unico("email_visualizador", "visualizador"),
             corpo={"nome": "Visualizador (Insomnia)", "email": "{{ _.email_visualizador }}", "senha": "{{ _.senha_teste }}", "role": "visualizador"},
             sucesso=True, salvar={"visualizador_id": "b.dados.id"}),
        Caso("✅ Login locatário A (sem MFA)", "POST", "/auth/login", corpo={"email": "{{ _.email_locatario_a }}", "senha": "{{ _.senha_teste }}"},
             sucesso=True, salvar={"token_locatario_a": "b.dados.access_token"}),
        Caso("✅ Login locatário B", "POST", "/auth/login", corpo={"email": "{{ _.email_locatario_b }}", "senha": "{{ _.senha_teste }}"},
             sucesso=True, salvar={"token_locatario_b": "b.dados.access_token", "refresh_locatario_b": "b.dados.refresh_token"}),
        Caso("✅ Login visualizador", "POST", "/auth/login", corpo={"email": "{{ _.email_visualizador }}", "senha": "{{ _.senha_teste }}"},
             sucesso=True, salvar={"token_visualizador": "b.dados.access_token"}),
        Caso("❌ Login locatário A com senha errada", "POST", "/auth/login", corpo={"email": "{{ _.email_locatario_a }}", "senha": "Senha.Errada#2026"},
             sucesso=False, erro="Credenciais inválidas"),
        Caso("✅ Locatário A vê o próprio perfil", "GET", "/usuarios/me", auth="token_locatario_a", sucesso=True,
             testes="insomnia.test('é o locatário A', () => insomnia.expect(b.dados.email).to.equal(insomnia.environment.get('email_locatario_a')));"),
        Caso("✅ Locatário A altera o próprio nome", "PATCH", "/usuarios/me", auth="token_locatario_a", corpo={"nome": "Locatário A (alterado)"}, sucesso=True),
        Caso("❌ Trocar senha sem informar a atual", "PATCH", "/usuarios/me", auth="token_locatario_a", corpo={"senha_nova": "Outra.Senha#2026"},
             sucesso=False, erro="Informe a senha atual"),
        Caso("✅ Admin lista usuários", "GET", "/usuarios", auth="token_admin", sucesso=True),
        Caso("✅ Gestor lista só locatários", "GET", "/usuarios", auth="token_gestor", query={"role": "locatario"}, sucesso=True,
             testes="insomnia.test('todos são locatários', () => insomnia.expect((b.dados || []).every(u => u.role === 'locatario')).to.equal(true));"),
        Caso("✅ Admin vê o locatário A por ID", "GET", "/usuarios/{{ _.locatario_a_id }}", auth="token_admin", sucesso=True),
        Caso("✅ Gestor altera o nome do locatário B", "PUT", "/usuarios/{{ _.locatario_b_id }}", auth="token_gestor", corpo={"nome": "Locatário B (alterado)"}, sucesso=True),
        Caso("❌ E-mail já cadastrado", "POST", "/usuarios", auth="token_admin",
             corpo={"nome": "Duplicado", "email": "{{ _.email_locatario_a }}", "senha": "{{ _.senha_teste }}", "role": "locatario"},
             sucesso=False, erro="E-mail já cadastrado"),
        Caso("❌ Perfil inválido", "POST", "/usuarios", auth="token_admin",
             corpo={"nome": "Perfil errado", "email": "perfil.invalido@onecheck.test", "senha": "{{ _.senha_teste }}", "role": "superusuario"},
             sucesso=False, erro="Perfil inválido"),
        Caso("❌ Senha fraca → 422", "POST", "/usuarios", auth="token_admin",
             corpo={"nome": "Senha fraca", "email": "senha.fraca@onecheck.test", "senha": "123", "role": "locatario"}, status=422),
        Caso("❌ Gestor não cria admin → 403", "POST", "/usuarios", auth="token_gestor",
             corpo={"nome": "Escalada", "email": "escalada@onecheck.test", "senha": "{{ _.senha_teste }}", "role": "admin"}, status=403),
        Caso("❌ Gestor não altera o admin → 403", "PUT", "/usuarios/{{ _.admin_id }}", auth="token_gestor", corpo={"nome": "Hackeado"}, status=403),
        Caso("❌ Locatário não cria usuário → 403", "POST", "/usuarios", auth="token_locatario_a",
             corpo={"nome": "X", "email": "x.locatario@onecheck.test", "senha": "{{ _.senha_teste }}", "role": "locatario"}, status=403),
        Caso("❌ Visualizador não lista usuários → 403", "GET", "/usuarios", auth="token_visualizador", status=403),
        Caso("❌ Locatário B não vê o locatário A → 403", "GET", "/usuarios/{{ _.locatario_a_id }}", auth="token_locatario_b", status=403),
        Caso("❌ Usuário inexistente", "GET", "/usuarios/00000000-0000-0000-0000-000000000000", auth="token_admin", sucesso=False, erro="Usuário não encontrado"),
        Caso("❌ Admin não desativa a própria conta", "DELETE", "/usuarios/{{ _.admin_id }}", auth="token_admin", sucesso=False, erro="própria conta"),
        Caso("❌ Admin não define o segredo MFA de outro → 422", "POST", "/usuarios/{{ _.locatario_a_id }}/mfa/enable", auth="token_admin",
             corpo={"secret": "JBSWY3DPEHPK3PXP", "codigo": "123456"}, status=422, sucesso=False, erro="próprio usuário"),
    ]),
    ("03 Imóveis", "Cria um imóvel com endereço (com coordenadas, sem chamar o geocoding) e cômodos.", [
        Caso("✅ Admin cria imóvel com endereço", "POST", "/imoveis", auth="token_admin", antes=DATAS_JS + "\ninsomnia.environment.set('sufixo', String(Date.now()).slice(-6));",
             corpo={"codigo": "INS-{{ _.sufixo }}", "titulo": "Apartamento de teste (Insomnia)", "tipo": "apartamento", "tamanho": "60m²",
                    "garagem": True, "garagem_vagas": 1, "observacoes": "Criado pela collection do Insomnia", "endereco": ENDERECO},
             sucesso=True, salvar={"imovel_id": "b.dados.id"}),
        Caso("✅ Admin cria cômodo", "POST", "/imoveis/{{ _.imovel_id }}/comodos", auth="token_admin", corpo={"tipo": "sala", "descricao": "Sala de estar"},
             sucesso=True, salvar={"comodo_id": "b.dados.id"}),
        Caso("✅ Gestor cria cômodo extra", "POST", "/imoveis/{{ _.imovel_id }}/comodos", auth="token_gestor", corpo={"tipo": "quarto", "descricao": "Quarto (será excluído)"},
             sucesso=True, salvar={"comodo_extra_id": "b.dados.id"}),
        Caso("✅ Admin lista imóveis", "GET", "/imoveis", auth="token_admin", sucesso=True),
        Caso("✅ Gestor vê o imóvel", "GET", "/imoveis/{{ _.imovel_id }}", auth="token_gestor", sucesso=True),
        Caso("✅ Admin altera o título do imóvel", "PUT", "/imoveis/{{ _.imovel_id }}", auth="token_admin", corpo={"titulo": "Apartamento de teste (alterado)"}, sucesso=True),
        Caso("✅ Gestor vê o endereço", "GET", "/imoveis/{{ _.imovel_id }}/endereco", auth="token_gestor", sucesso=True),
        Caso("✅ Admin atualiza o endereço", "PUT", "/imoveis/{{ _.imovel_id }}/endereco", auth="token_admin", corpo={**ENDERECO, "complemento": "Apto 12"}, sucesso=True),
        Caso("✅ Admin lista os cômodos", "GET", "/imoveis/{{ _.imovel_id }}/comodos", auth="token_admin", sucesso=True),
        Caso("✅ Admin altera um cômodo", "PUT", "/imoveis/{{ _.imovel_id }}/comodos/{{ _.comodo_id }}", auth="token_admin", corpo={"descricao": "Sala de estar e jantar"}, sucesso=True),
        Caso("✅ Admin exclui o cômodo extra", "DELETE", "/imoveis/{{ _.imovel_id }}/comodos/{{ _.comodo_extra_id }}", auth="token_admin", sucesso=True),
        Caso("❌ Imóvel sem tipo → 422", "POST", "/imoveis", auth="token_admin", corpo={"titulo": "Sem tipo"}, status=422),
        Caso("❌ Locatário não cria imóvel → 403", "POST", "/imoveis", auth="token_locatario_a", corpo={"tipo": "casa"}, status=403),
        Caso("❌ Visualizador não cria imóvel → 403", "POST", "/imoveis", auth="token_visualizador", corpo={"tipo": "casa"}, status=403),
        Caso("❌ Vistoriador sem vistoria no imóvel não o vê → 403", "GET", "/imoveis/{{ _.imovel_id }}", auth="token_vistoriador", status=403),
        Caso("❌ Locatário sem contrato não vê o imóvel → 403", "GET", "/imoveis/{{ _.imovel_id }}", auth="token_locatario_b", status=403),
        Caso("❌ Imóvel inexistente", "GET", "/imoveis/00000000-0000-0000-0000-000000000000", auth="token_admin", sucesso=False, erro="Imóvel não encontrado"),
    ]),
    ("04 Contratos e agendamentos", "Contrato do imóvel com o locatário A.", [
        Caso("✅ Admin cria contrato para o locatário A", "POST", "/contratos", auth="token_admin", antes=DATAS_JS,
             corpo={"imovel_id": "{{ _.imovel_id }}", "locatario_id": "{{ _.locatario_a_id }}", "data_inicio": "{{ _.hoje }}",
                    "data_fim": "{{ _.daqui_1_ano }}", "valor_mensal": 2500},
             sucesso=True, salvar={"contrato_id": "b.dados.id"}),
        Caso("❌ Segundo contrato no imóvel já locado", "POST", "/contratos", auth="token_admin",
             corpo={"imovel_id": "{{ _.imovel_id }}", "locatario_id": "{{ _.locatario_b_id }}", "data_inicio": "{{ _.hoje }}", "data_fim": "{{ _.daqui_1_ano }}"},
             sucesso=False, erro="já"),
        Caso("❌ Data de fim antes da de início", "POST", "/contratos", auth="token_admin",
             corpo={"imovel_id": "{{ _.imovel_id }}", "locatario_id": "{{ _.locatario_b_id }}", "data_inicio": "{{ _.hoje }}", "data_fim": "{{ _.ontem }}"},
             sucesso=False, erro="data de fim"),
        Caso("❌ Locatário não cria contrato → 403", "POST", "/contratos", auth="token_locatario_a",
             corpo={"imovel_id": "{{ _.imovel_id }}", "locatario_id": "{{ _.locatario_a_id }}", "data_inicio": "{{ _.hoje }}", "data_fim": "{{ _.daqui_1_ano }}"}, status=403),
        Caso("✅ Locatário A lista os próprios contratos", "GET", "/contratos", auth="token_locatario_a", sucesso=True,
             testes="insomnia.test('contém o contrato criado', () => insomnia.expect((b.dados || []).some(c => c.id === insomnia.environment.get('contrato_id'))).to.equal(true));"),
        Caso("✅ Locatário A vê o próprio contrato", "GET", "/contratos/{{ _.contrato_id }}", auth="token_locatario_a", sucesso=True),
        Caso("✅ Locatário A agora vê o imóvel do contrato", "GET", "/imoveis/{{ _.imovel_id }}", auth="token_locatario_a", sucesso=True),
        Caso("❌ Locatário B não vê o contrato do A → 403", "GET", "/contratos/{{ _.contrato_id }}", auth="token_locatario_b", status=403),
        Caso("❌ Vistoriador sem vistoria não vê o contrato → 403", "GET", "/contratos/{{ _.contrato_id }}", auth="token_vistoriador", status=403),
        Caso("✅ Gestor agenda a vistoria inicial", "POST", "/contratos/{{ _.contrato_id }}/agendamentos", auth="token_gestor", antes=DATAS_JS,
             corpo={"tipo": "inicial", "data_agendada": "{{ _.daqui_7_dias }}", "observacao": "Agendado pelo Insomnia"},
             sucesso=True, salvar={"agendamento_id": "b.dados.id"}),
        Caso("❌ Agendamento com data no passado", "POST", "/contratos/{{ _.contrato_id }}/agendamentos", auth="token_gestor",
             corpo={"tipo": "inicial", "data_agendada": "{{ _.ontem }}T10:00:00"}, sucesso=False, erro="data futura"),
        Caso("❌ Agendamento com tipo inválido", "POST", "/contratos/{{ _.contrato_id }}/agendamentos", auth="token_gestor",
             corpo={"tipo": "mensal", "data_agendada": "{{ _.daqui_7_dias }}"}, sucesso=False, erro="Tipo inválido"),
        Caso("❌ Locatário não agenda vistoria → 403", "POST", "/contratos/{{ _.contrato_id }}/agendamentos", auth="token_locatario_a",
             corpo={"tipo": "inicial", "data_agendada": "{{ _.daqui_7_dias }}"}, status=403),
        Caso("✅ Admin lista os agendamentos do contrato", "GET", "/contratos/{{ _.contrato_id }}/agendamentos", auth="token_admin", sucesso=True),
        Caso("❌ Locatário não lista agendamentos → 403", "GET", "/contratos/{{ _.contrato_id }}/agendamentos", auth="token_locatario_a", status=403),
        Caso("✅ Gestor altera a observação do agendamento", "PUT", "/agendamentos/{{ _.agendamento_id }}", auth="token_gestor", corpo={"observacao": "Levar trena"}, sucesso=True),
        Caso("❌ Vistoriador não altera agendamento → 403", "PUT", "/agendamentos/{{ _.agendamento_id }}", auth="token_vistoriador", corpo={"observacao": "x"}, status=403),
    ]),
    ("05 Checklists, fotos, aceite e PDF", "Vistoria inicial (aceita pelo locatário A) e vistoria de encerramento (rejeitada).", [
        Caso("✅ Vistoriador lista o catálogo de itens", "GET", "/itens-vistoria", auth="token_vistoriador", sucesso=True,
             salvar={"item_vistoria_id": "b.dados[0].id"}),
        Caso("✅ Admin cria a vistoria inicial", "POST", "/contratos/{{ _.contrato_id }}/checklists", auth="token_admin",
             corpo={"tipo": "inicial", "vistoriador_id": "{{ _.vistoriador_id }}"}, sucesso=True, salvar={"checklist_id": "b.dados.id"}),
        Caso("❌ Segunda vistoria inicial no mesmo contrato", "POST", "/contratos/{{ _.contrato_id }}/checklists", auth="token_admin",
             corpo={"tipo": "inicial", "vistoriador_id": "{{ _.vistoriador_id }}"}, sucesso=False, erro="vistoria inicial"),
        Caso("❌ Vistoriador não cria vistoria → 403", "POST", "/contratos/{{ _.contrato_id }}/checklists", auth="token_vistoriador",
             corpo={"tipo": "encerramento", "vistoriador_id": "{{ _.vistoriador_id }}"}, status=403),
        Caso("❌ Locatário não cria vistoria → 403", "POST", "/contratos/{{ _.contrato_id }}/checklists", auth="token_locatario_a",
             corpo={"tipo": "encerramento", "vistoriador_id": "{{ _.vistoriador_id }}"}, status=403),
        Caso("✅ Vistoriador com vistoria agora vê o contrato", "GET", "/contratos/{{ _.contrato_id }}", auth="token_vistoriador", sucesso=True),
        Caso("✅ Vistoriador adiciona item", "POST", "/checklists/{{ _.checklist_id }}/itens", auth="token_vistoriador",
             corpo={"comodo_id": "{{ _.comodo_id }}", "item_vistoria_id": "{{ _.item_vistoria_id }}", "estado": "bom", "observacao": "Sem avarias"},
             sucesso=True, salvar={"checklist_item_id": "b.dados.id"}),
        Caso("❌ Item com estado inválido", "POST", "/checklists/{{ _.checklist_id }}/itens", auth="token_vistoriador",
             corpo={"comodo_id": "{{ _.comodo_id }}", "item_vistoria_id": "{{ _.item_vistoria_id }}", "estado": "excelente"}, sucesso=False, erro="Estado inválido"),
        Caso("❌ Locatário não adiciona item → 403", "POST", "/checklists/{{ _.checklist_id }}/itens", auth="token_locatario_a",
             corpo={"comodo_id": "{{ _.comodo_id }}", "item_vistoria_id": "{{ _.item_vistoria_id }}", "estado": "bom"}, status=403),
        Caso("✅ Vistoriador altera o estado do item", "PUT", "/checklists/{{ _.checklist_id }}/itens/{{ _.checklist_item_id }}", auth="token_vistoriador",
             corpo={"estado": "otimo", "observacao": "Pintura nova"}, sucesso=True),
        Caso("✅ Vistoriador envia foto do item", "POST", "/checklists/{{ _.checklist_id }}/itens/{{ _.checklist_item_id }}/fotos", auth="token_vistoriador",
             form=[{"name": "foto", "type": "file", "fixture": "foto-valida.png"}], sucesso=True, salvar={"foto_id": "b.dados.id"},
             descricao="Antes de rodar, selecione o arquivo docs/insomnia/fixtures/foto-valida.png no campo 'foto'."),
        Caso("❌ Arquivo que não é imagem", "POST", "/checklists/{{ _.checklist_id }}/itens/{{ _.checklist_item_id }}/fotos", auth="token_vistoriador",
             form=[{"name": "foto", "type": "file", "fixture": "foto-invalida.jpg"}], sucesso=False, erro="Envie uma imagem",
             descricao="Selecione docs/insomnia/fixtures/foto-invalida.jpg (texto com extensão .jpg)."),
        Caso("❌ Upload sem o campo foto", "POST", "/checklists/{{ _.checklist_id }}/itens/{{ _.checklist_item_id }}/fotos", auth="token_vistoriador",
             form=[{"name": "outro", "value": "x"}], sucesso=False, erro="campo 'foto'"),
        Caso("❌ Locatário não envia foto → 403", "POST", "/checklists/{{ _.checklist_id }}/itens/{{ _.checklist_item_id }}/fotos", auth="token_locatario_a",
             form=[{"name": "foto", "type": "file", "fixture": "foto-valida.png"}], status=403),
        Caso("✅ Vistoriador vê o checklist", "GET", "/checklists/{{ _.checklist_id }}", auth="token_vistoriador", sucesso=True),
        Caso("✅ Locatário A vê o checklist do próprio contrato", "GET", "/checklists/{{ _.checklist_id }}", auth="token_locatario_a", sucesso=True),
        Caso("✅ Gestor vê o checklist", "GET", "/checklists/{{ _.checklist_id }}", auth="token_gestor", sucesso=True),
        Caso("❌ Locatário B não vê o checklist do A → 403", "GET", "/checklists/{{ _.checklist_id }}", auth="token_locatario_b", status=403,
             descricao="Caso que a suíte automatizada não cobre hoje (SEC-032)."),
        Caso("✅ Locatário A lista as vistorias do contrato", "GET", "/contratos/{{ _.contrato_id }}/checklists", auth="token_locatario_a", sucesso=True),
        Caso("❌ Locatário B não lista as vistorias do A (HTTP 200 com sucesso=false)", "GET", "/contratos/{{ _.contrato_id }}/checklists", auth="token_locatario_b",
             sucesso=False, erro="Sem permissão",
             descricao="Única negação de acesso que responde HTTP 200 com sucesso=false em vez de 403."),
        Caso("❌ Locatário não submete o checklist → 403", "PATCH", "/checklists/{{ _.checklist_id }}/submeter", auth="token_locatario_a", status=403),
        Caso("✅ Vistoriador submete o checklist", "PATCH", "/checklists/{{ _.checklist_id }}/submeter", auth="token_vistoriador", sucesso=True,
             testes="insomnia.test('status pendente_aceite', () => insomnia.expect(b.dados.status).to.equal('pendente_aceite'));"),
        Caso("❌ Foto em checklist já enviado (trava)", "POST", "/checklists/{{ _.checklist_id }}/itens/{{ _.checklist_item_id }}/fotos", auth="token_vistoriador",
             form=[{"name": "foto", "type": "file", "fixture": "foto-valida.png"}], sucesso=False, erro="Não é possível adicionar fotos",
             descricao="Caso que a suíte automatizada não cobre hoje (SEC-033)."),
        Caso("❌ Editar item de checklist já enviado (trava)", "PUT", "/checklists/{{ _.checklist_id }}/itens/{{ _.checklist_item_id }}", auth="token_vistoriador",
             corpo={"estado": "ruim"}, sucesso=False, erro="Não é possível editar itens"),
        Caso("❌ Enviar para aceite um checklist já pendente", "PATCH", "/checklists/{{ _.checklist_id }}/enviar-para-aceite", auth="token_admin",
             sucesso=False, erro="Não é possível enviar para aceite"),
        Caso("❌ Vistoriador não aceita a própria vistoria → 403", "PATCH", "/checklists/{{ _.checklist_id }}/aceitar", auth="token_vistoriador", status=403),
        Caso("❌ Locatário B não aceita a vistoria do A → 403", "PATCH", "/checklists/{{ _.checklist_id }}/aceitar", auth="token_locatario_b", status=403,
             descricao="Caso que a suíte automatizada não cobre hoje (SEC-032)."),
        Caso("✅ Locatário A aceita a vistoria", "PATCH", "/checklists/{{ _.checklist_id }}/aceitar", auth="token_locatario_a", sucesso=True,
             testes="insomnia.test('status aceito', () => insomnia.expect(b.dados.status).to.equal('aceito'));"),
        Caso("❌ Aceitar de novo", "PATCH", "/checklists/{{ _.checklist_id }}/aceitar", auth="token_locatario_a", sucesso=False, erro="não está pendente"),
        Caso("✅ Locatário A baixa o laudo em PDF", "GET", "/checklists/{{ _.checklist_id }}/download", auth="token_locatario_a",
             testes="let ct = ''; try { ct = String(r.headers.get('Content-Type') || ''); } catch (e) {}\ninsomnia.test('é PDF', () => insomnia.expect(ct).to.include('pdf'));"),
        Caso("❌ Locatário B não baixa o laudo do A → 403", "GET", "/checklists/{{ _.checklist_id }}/download", auth="token_locatario_b", status=403),
        Caso("✅ Gestor cria a vistoria de encerramento", "POST", "/contratos/{{ _.contrato_id }}/checklists", auth="token_gestor",
             corpo={"tipo": "encerramento", "vistoriador_id": "{{ _.vistoriador_id }}"}, sucesso=True, salvar={"checklist2_id": "b.dados.id"}),
        Caso("❌ Enviar para aceite sem itens", "PATCH", "/checklists/{{ _.checklist2_id }}/enviar-para-aceite", auth="token_gestor", sucesso=False, erro="ao menos um item"),
        Caso("✅ Vistoriador adiciona item na vistoria de encerramento", "POST", "/checklists/{{ _.checklist2_id }}/itens", auth="token_vistoriador",
             corpo={"comodo_id": "{{ _.comodo_id }}", "item_vistoria_id": "{{ _.item_vistoria_id }}", "estado": "regular", "observacao": "Parede riscada"},
             sucesso=True, salvar={"checklist2_item_id": "b.dados.id"}),
        Caso("✅ Gestor envia a vistoria de encerramento para aceite", "PATCH", "/checklists/{{ _.checklist2_id }}/enviar-para-aceite", auth="token_gestor", sucesso=True),
        Caso("✅ Locatário A rejeita a vistoria de encerramento", "PATCH", "/checklists/{{ _.checklist2_id }}/rejeitar", auth="token_locatario_a",
             corpo={"motivo": "A parede já estava riscada na entrada"}, sucesso=True,
             testes="insomnia.test('status rejeitado', () => insomnia.expect(b.dados.status).to.equal('rejeitado'));"),
    ]),
    ("06 Problemas e atualizações", "Problema aberto pelo locatário A no próprio contrato.", [
        Caso("✅ Locatário A registra um problema", "POST", "/contratos/{{ _.contrato_id }}/problemas", auth="token_locatario_a",
             corpo={"titulo": "Torneira pingando", "descricao": "A torneira da cozinha pinga sem parar", "comodo_id": "{{ _.comodo_id }}", "prioridade": "alta"},
             status=[200, 201], sucesso=True, salvar={"problema_id": "b.dados.id"},
             testes="insomnia.test('nasce aberto', () => insomnia.expect(b.dados.status).to.equal('aberto'));"),
        Caso("❌ Problema sem título → 422", "POST", "/contratos/{{ _.contrato_id }}/problemas", auth="token_locatario_a",
             corpo={"descricao": "Sem título"}, status=422, sucesso=False),
        Caso("❌ Locatário B não registra problema no contrato do A → 403", "POST", "/contratos/{{ _.contrato_id }}/problemas", auth="token_locatario_b",
             corpo={"titulo": "Intruso"}, status=403),
        Caso("✅ Locatário A vê o próprio problema", "GET", "/problemas/{{ _.problema_id }}", auth="token_locatario_a", sucesso=True),
        Caso("✅ Gestor vê o problema", "GET", "/problemas/{{ _.problema_id }}", auth="token_gestor", sucesso=True),
        Caso("❌ Locatário B não vê o problema do A → 403", "GET", "/problemas/{{ _.problema_id }}", auth="token_locatario_b", status=403),
        Caso("✅ Locatário A lista os problemas do contrato", "GET", "/contratos/{{ _.contrato_id }}/problemas", auth="token_locatario_a", sucesso=True),
        Caso("✅ Gestor muda o status para em andamento", "PATCH", "/problemas/{{ _.problema_id }}/status", auth="token_gestor", corpo={"status": "em_andamento"}, sucesso=True),
        Caso("❌ Status inválido → 422", "PATCH", "/problemas/{{ _.problema_id }}/status", auth="token_gestor", corpo={"status": "esquecido"}, status=422, sucesso=False),
        Caso("❌ Locatário não muda o status → 403", "PATCH", "/problemas/{{ _.problema_id }}/status", auth="token_locatario_a", corpo={"status": "resolvido"}, status=403),
        Caso("✅ Admin registra uma atualização", "POST", "/problemas/{{ _.problema_id }}/atualizacoes", auth="token_admin",
             corpo={"descricao": "Encanador agendado para sexta-feira"}, status=[200, 201], sucesso=True),
        Caso("❌ Atualização curta demais → 422", "POST", "/problemas/{{ _.problema_id }}/atualizacoes", auth="token_admin", corpo={"descricao": "ok"}, status=422, sucesso=False),
        Caso("❌ Locatário não registra atualização → 403", "POST", "/problemas/{{ _.problema_id }}/atualizacoes", auth="token_locatario_a",
             corpo={"descricao": "Tentando atualizar"}, status=403),
        Caso("✅ Locatário A vê a linha do tempo", "GET", "/problemas/{{ _.problema_id }}/atualizacoes", auth="token_locatario_a", sucesso=True),
        Caso("❌ Problema inexistente → 404", "GET", "/problemas/00000000-0000-0000-0000-000000000000", auth="token_admin", status=404, sucesso=False),
    ]),
    ("07 Dashboard e logs", "O dashboard muda conforme o perfil; os logs são só de admin e gestor.", [
        Caso("✅ Dashboard do admin", "GET", "/dashboard", auth="token_admin", sucesso=True),
        Caso("✅ Dashboard do gestor", "GET", "/dashboard", auth="token_gestor", sucesso=True),
        Caso("✅ Dashboard do vistoriador", "GET", "/dashboard", auth="token_vistoriador", sucesso=True),
        Caso("✅ Dashboard do locatário A", "GET", "/dashboard", auth="token_locatario_a", sucesso=True),
        Caso("✅ Dashboard do visualizador", "GET", "/dashboard", auth="token_visualizador", sucesso=True),
        Caso("✅ Admin consulta os logs", "GET", "/logs", auth="token_admin", sucesso=True),
        Caso("✅ Admin filtra os logs por ação", "GET", "/logs", auth="token_admin", query={"acao": "login_falho"}, sucesso=True,
             testes="insomnia.test('só login_falho', () => insomnia.expect((b.dados || []).every(l => l.acao === 'login_falho')).to.equal(true));"),
        Caso("✅ Gestor consulta os logs (comportamento atual, ver SEC-018)", "GET", "/logs", auth="token_gestor", sucesso=True),
        Caso("⚠️ Filtro de data inválido é ignorado (comportamento atual, ver SEC-020)", "GET", "/logs", auth="token_admin", query={"de": "ontem"}, sucesso=True,
             descricao="Hoje a data inválida é descartada sem aviso. O SEC-020 propõe responder 422."),
        Caso("❌ Locatário não consulta os logs → 403", "GET", "/logs", auth="token_locatario_a", status=403),
        Caso("❌ Visualizador não consulta os logs → 403", "GET", "/logs", auth="token_visualizador", status=403),
    ]),
    ("08 Administração (seed)", "Só operações sem efeito. Sem SEED_SECRET configurado na API, as rotas /admin respondem 404.", [
        Caso("❌ Status dos dados sem o segredo → 403 ou 404", "GET", "/admin/data/status", auth="token_admin", status=[403, 404]),
        Caso("✅ Status dos dados com o segredo (exige seed_secret)", "GET", "/admin/data/status", auth="token_admin",
             headers={"X-Seed-Secret": "{{ _.seed_secret }}"}, status=[200, 403, 404],
             testes="if (insomnia.environment.get('seed_secret')) { insomnia.test('HTTP 200 com o segredo', () => insomnia.expect(r.code).to.equal(200)); }"),
        Caso("❌ Seed com segredo mas sem token de admin → 401 ou 403", "POST", "/admin/seed", auth="token_gestor",
             headers={"X-Seed-Secret": "{{ _.seed_secret }}"}, corpo={"mode": "expand"}, status=[401, 403, 404]),
    ]),
    ("09 Encerramento e limpeza", "Encerra o contrato e desativa os usuários criados. Rode por último.", [
        Caso("❌ Excluir imóvel com contrato ativo", "DELETE", "/imoveis/{{ _.imovel_id }}", auth="token_admin", sucesso=False, erro="contrato ativo"),
        Caso("❌ Excluir foto de checklist aceito (trava)", "DELETE", "/checklists/{{ _.checklist_id }}/itens/{{ _.checklist_item_id }}/fotos/{{ _.foto_id }}",
             auth="token_vistoriador", sucesso=False, erro="Não é possível excluir fotos"),
        Caso("❌ Locatário não encerra contrato → 403", "PATCH", "/contratos/{{ _.contrato_id }}/encerrar", auth="token_locatario_a", status=403),
        Caso("✅ Admin encerra o contrato", "PATCH", "/contratos/{{ _.contrato_id }}/encerrar", auth="token_admin", sucesso=True,
             testes="insomnia.test('status encerrado', () => insomnia.expect(b.dados.status).to.equal('encerrado'));"),
        Caso("❌ Encerrar de novo", "PATCH", "/contratos/{{ _.contrato_id }}/encerrar", auth="token_admin", sucesso=False, erro="Não é possível encerrar"),
        Caso("❌ Cancelar contrato encerrado", "PATCH", "/contratos/{{ _.contrato_id }}/cancelar", auth="token_admin", sucesso=False, erro="Não é possível cancelar"),
        Caso("✅ Admin exclui o agendamento", "DELETE", "/agendamentos/{{ _.agendamento_id }}", auth="token_admin", sucesso=True),
        Caso("❌ Excluir o agendamento de novo", "DELETE", "/agendamentos/{{ _.agendamento_id }}", auth="token_admin", sucesso=False, erro="Agendamento não encontrado"),
        Caso("✅ Logout do locatário B", "POST", "/auth/logout", auth="token_locatario_b", corpo={"refresh_token": "{{ _.refresh_locatario_b }}"}, sucesso=True),
        Caso("❌ Refresh depois do logout", "POST", "/auth/refresh", corpo={"refresh_token": "{{ _.refresh_locatario_b }}"}, sucesso=False, erro="Refresh token inválido"),
        Caso("✅ Admin desativa o locatário A", "DELETE", "/usuarios/{{ _.locatario_a_id }}", auth="token_admin", sucesso=True),
        Caso("❌ Token do locatário desativado deixa de valer → 401", "GET", "/usuarios/me", auth="token_locatario_a", status=401),
        Caso("✅ Admin desativa o locatário B", "DELETE", "/usuarios/{{ _.locatario_b_id }}", auth="token_admin", sucesso=True),
        Caso("✅ Admin desativa o visualizador", "DELETE", "/usuarios/{{ _.visualizador_id }}", auth="token_admin", sucesso=True),
    ]),
]


def gerar() -> dict:
    recursos: list[dict] = [{
        "_id": WRK, "_type": "workspace", "parentId": None, "name": "OneCheck API — testes manuais",
        "description": "Suíte de casos de sucesso (✅) e de falha (❌) da OneCheck API. Veja docs/insomnia/README.md.",
        "scope": "collection",
    }]
    base_id = _id("env", "base")
    recursos.append({"_id": base_id, "_type": "environment", "parentId": WRK, "name": "Base Environment",
                     "data": {}, "dataPropertyOrder": None, "color": None, "isPrivate": False, "metaSortKey": 0})
    for i, (nome, url) in enumerate([("Local (docker compose)", "http://localhost:8000/api/v1"), ("Outro servidor", "")]):
        dados = {**VARS_USUARIO, "base_url": url, **{v: "" for v in VARS_AUTO}}
        if url == "":
            dados.update({k: "" for k in ("email_admin", "email_gestor", "email_vistoriador")})
        recursos.append({"_id": _id("env", nome), "_type": "environment", "parentId": base_id, "name": nome, "data": dados,
                         "dataPropertyOrder": {"&": list(dados)}, "color": "#7d69cb" if i == 0 else "#d9534f",
                         "isPrivate": False, "metaSortKey": i + 1})
    for i, (nome, descricao, casos) in enumerate(PASTAS):
        pid = _id("fld", nome)
        recursos.append({"_id": pid, "_type": "request_group", "parentId": WRK, "name": nome, "description": descricao,
                         "environment": {}, "environmentPropertyOrder": None, "metaSortKey": (i + 1) * 1000})
        for j, c in enumerate(casos):
            recursos.append(_requisicao(pid, (i + 1) * 1000 + j + 1, c))
    return {"_type": "export", "__export_format": 4, "__export_date": "2026-11-07T00:00:00.000Z",
            "__export_source": "onecheck-api:gerar_collection.py", "resources": recursos}


if __name__ == "__main__":
    dados = gerar()
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = sum(1 for r in dados["resources"] if r["_type"] == "request")
    print(f"{SAIDA.relative_to(AQUI.parent.parent)}: {n} requisições em {len(PASTAS)} pastas")
