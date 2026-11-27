"""A skill /pareamento, parte das ações: bloqueio no texto, volta do diretor, ações por card,
passagem ao diretor e o painel local que abre as sessões no Claude Agents."""

from __future__ import annotations

import json
from datetime import date

from test_pareamento import DIR, EU, SKILL, carregar, estado_exemplo, issue, montar, projeto

coletar = carregar("coletar")
acoes = carregar("acoes")
passagem = carregar("passagem")
painel = carregar("painel")


def test_bloqueio_no_texto_acha_o_que_o_nativo_nao_tem():
    corpo = "Pai: #1786\nBloqueada por: #2330\n\nSaiu do #1852.\n1. Espere o #9 fechar. Depende do #2330 e #44."
    abertos = {1786, 2330, 1852, 9, 44, 50}
    assert coletar.bloqueio_no_texto(corpo, [], abertos, 50) == [9, 44, 2330]
    # O que já é nativo, o próprio card e card fechado ficam de fora; "Pai" e "Saiu do" não são bloqueio.
    assert coletar.bloqueio_no_texto(corpo, [2330, 9], abertos - {44}, 50) == []
    assert coletar.bloqueio_no_texto("depende do #50", [], {50}, 50) == []


def test_bloqueio_no_texto_entra_no_card_e_nao_le_corpo_de_fora():
    issues = [issue(60, quem=[EU], corpo="Bloqueada por: #61"), issue(61, quem=[EU]),
              {**issue(62, quem=[EU], corpo="Bloqueada por: #61"), "author_association": "NONE"}]
    cards = coletar.montar_cards([projeto(issues)], EU, {DIR}, {})
    assert cards["Hospital#60"]["no_texto"] == ["Hospital#61"]
    assert cards["Hospital#60"]["livre"]  # o selo continua o do GitHub; a página mostra o alerta
    assert cards["Hospital#62"]["no_texto"] == []


def coment(login, assoc="MEMBER"):
    return {"user": {"login": login}, "author_association": assoc, "body": "x"}


def test_voltou_do_diretor():
    assert coletar.voltou_do_diretor("eu", ["needs-info"], [coment(EU), coment(DIR)], {DIR})
    # A última palavra é de quem perguntou: ainda espera o diretor.
    assert not coletar.voltou_do_diretor("eu", ["needs-info"], [coment(DIR), coment(EU)], {DIR})
    # Comentário de fora do time não conta.
    assert coletar.voltou_do_diretor("eu", ["needs-info"], [coment(DIR), coment("x", "NONE")], {DIR})
    assert not coletar.voltou_do_diretor("eu", ["ready-for-human"], [coment(DIR)], {DIR})
    assert not coletar.voltou_do_diretor("diretor", ["needs-info"], [coment(DIR)], {DIR})


def c_acao(dono="eu", livre=True, **extra):
    return {"chave": "Hospital#7", "numero": 7, "projeto": "Hospital", "dono": dono, "livre": livre, **extra}


def test_acoes_de_cada_card():
    assert acoes.acoes_do_card(c_acao("diretor")) == []
    assert acoes.acoes_do_card(c_acao("outro")) == []
    assert acoes.acoes_do_card(c_acao(livre=False)) == []
    assert acoes.acoes_do_card(c_acao("agente", rodando=True)) == []
    assert acoes.acoes_do_card(c_acao("agente")) == ["agente"]
    assert acoes.acoes_do_card(c_acao(voltou=True)) == ["voltou", "tocar"]
    assert acoes.acoes_do_card(c_acao(), {"proximo": "diretor"})[0] == "diretor"
    assert acoes.acoes_do_card(c_acao(), {"proximo": "esperar"}) == ["tocar", "decidir", "diretor", "agente"]


def test_pedido_da_sessao_sai_do_servidor_e_recusa_acao_que_o_card_nao_tem():
    p = acoes.pedido("agente", c_acao("agente"), "Vitta-Share/hospital-reunioes", {"para_que_serve": "Serve."})
    assert "/pegar-issue 7" in p and "--repo Vitta-Share/hospital-reunioes" in p and "Serve." in p
    assert "/grill-with-docs #7" in acoes.pedido("decidir", c_acao(), "r/x", {})
    assert "ready-for-agent" in acoes.pedido("voltou", c_acao(voltou=True), "r/x", {})
    assert "passagem.md" in acoes.pedido("diretor", c_acao(), "r/x", {})
    for tipo, card in [("voltou", c_acao()), ("tocar", c_acao("diretor")), ("x", c_acao())]:
        try:
            acoes.pedido(tipo, card, "r/x", {})
        except ValueError:
            continue
        raise AssertionError(tipo)
    nome = acoes.nome_da_sessao("tocar", "Hospital#2135")
    assert nome == "par-hosp-2135-tocar" and acoes.NOME_OK.match(nome)


RASCUNHO = {"tipo": "needs-info", "por_que": "Parou na regra.", "preciso": "Escolher a 1 ou a 2.",
            "opcoes": ["Uma", "Outra"], "recomendacao": "A 1.", "devolver": "Responda e devolva ao Pedro."}


def test_rascunho_da_passagem_confere_o_que_falta():
    assert passagem.conferir(RASCUNHO)["opcoes"] == ["Uma", "Outra"]
    for ruim in [{**RASCUNHO, "tipo": "ready-for-agent"}, {**RASCUNHO, "preciso": " "},
                 {**RASCUNHO, "recomendacao": ""}, {**RASCUNHO, "por_que": "Parou " + chr(0x2014) + " na regra."}]:
        try:
            passagem.conferir(ruim)
        except ValueError:
            continue
        raise AssertionError(ruim)
    # Coisa a fazer não pede recomendação.
    assert passagem.conferir({**RASCUNHO, "tipo": "ready-for-human", "recomendacao": ""})


def test_secao_vai_para_o_comeco_e_troca_a_anterior():
    nova = passagem.secao(passagem.conferir(RASCUNHO), "Pedro", date(2026, 11, 27))
    assert nova.startswith("## 🔁 Por que este card passou para você")
    assert "**De:** Pedro, em 27/11/2026." in nova and "1. Uma\n2. Outra" in nova
    assert "**Minha recomendação:** A 1." in nova
    antigo = "## 🔁 Por que este card passou para você\n\n**Por quê:** velho.\n\n---\n\n## 👔 Para o diretor\n\nTexto."
    corpo = passagem.corpo_novo(antigo, nova)
    assert corpo.count("🔁") == 1 and "velho" not in corpo and corpo.endswith("## 👔 Para o diretor\n\nTexto.")
    assert passagem.corpo_novo("Só o corpo.", nova) == nova + "\n---\n\nSó o corpo."


def test_passar_escreve_o_corpo_comenta_e_troca_dono_e_label():
    chamadas = []

    def gh(*args):
        chamadas.append(args)
        if args[:2] == ("api", "user"):
            return json.dumps({"login": EU})
        if args[0] == "api":
            return json.dumps({"state": "open", "body": "Corpo.", "html_url": "u",
                               "labels": [{"name": "ready-for-agent"}, {"name": "fatia:P"}]})
        return ""

    gente = [{"login": EU, "nome": "Pedro", "papel": "socio"}, {"login": DIR, "nome": "Felipe", "papel": "diretor"}]
    r = passagem.passar("o/r", 5, RASCUNHO, gh=gh, pessoas=gente)
    assert r["diretor"] == DIR
    edicoes = [c for c in chamadas if c[:2] == ("issue", "edit")]
    assert "--body-file" in edicoes[0]
    assert any(c[:2] == ("issue", "comment") for c in chamadas)
    # A ordem importa: a seção já está no corpo quando o diretor recebe o aviso.
    assert chamadas.index(edicoes[1]) > max(i for i, c in enumerate(chamadas) if c[:2] == ("issue", "comment"))
    troca = edicoes[1]
    assert troca[troca.index("--add-assignee") + 1] == DIR and troca[troca.index("--remove-assignee") + 1] == EU
    assert troca[troca.index("--add-label") + 1] == "needs-info"
    assert "ready-for-agent" in troca and "fatia:P" not in troca
    assert f"@{DIR}" in passagem.comentario(DIR, 5) and passagem.comentario(DIR, 5).startswith("<!-- automacao -->")


def test_passar_recusa_card_rodando():
    def gh(*args):
        return json.dumps({"state": "open", "body": "", "labels": [{"name": "in-progress"}]})

    try:
        passagem.passar("o/r", 5, RASCUNHO, gh=gh, pessoas=[])
    except ValueError as e:
        assert "rodando" in str(e)
    else:
        raise AssertionError


def test_guarda_do_painel():
    host_ok, autorizado = painel.guarda(4479, "t" * 48)
    bom = {"Host": "127.0.0.1:4479", "x-pareamento-token": "t" * 48}
    assert autorizado(bom)
    assert autorizado({**bom, "Origin": "http://localhost:4479", "Host": "localhost:4479"})
    assert not autorizado({**bom, "Host": "evil.com:4479"})  # DNS rebinding
    assert not autorizado({**bom, "Origin": "https://claude.ai"})
    assert not autorizado({**bom, "x-pareamento-token": "x" * 48})
    assert not autorizado({"Host": "127.0.0.1:4479"})
    assert host_ok({"Host": "localhost:4479"}) and not host_ok({"Host": "127.0.0.1:80"})


def test_painel_abre_sessao_so_do_que_o_card_aceita(tmp_path):
    estado = {"projetos": [{"nome": "Hospital", "repo": "o/r"}],
              "cards": {"Hospital#7": c_acao("agente"), "Hospital#8": {**c_acao("diretor"), "chave": "Hospital#8", "numero": 8}}}
    (tmp_path / "estado.json").write_text(json.dumps(estado), encoding="utf-8")
    lancadas = []

    def lancador(projeto, nome, prompt):
        lancadas.append((projeto, nome, prompt))
        return {"ok": True, "id": "abc"}

    pedidos = [{"tipo": "agente", "chave": "Hospital#7"}, {"tipo": "tocar", "chave": "Hospital#8"},
               {"tipo": "agente", "chave": "Hospital#99"}, {"tipo": "onda", "projeto": "Hospital"},
               {"tipo": "onda", "projeto": "../x"}]
    r = painel.abrir_sessoes(pedidos, tmp_path, lancador=lancador, vivas=set)
    assert [x.get("ok") for x in r] == [True, None, None, True, None]
    assert lancadas[0][1] == "par-hosp-7-agente" and "/pegar-issue 7" in lancadas[0][2]
    assert "/montar-ondas-enxutas" in lancadas[1][2]
    # Sessão viva com o mesmo nome não abre outra.
    r = painel.abrir_sessoes([{"tipo": "agente", "chave": "Hospital#7"}], tmp_path, lancador=lancador,
                             vivas=lambda: {"par-hosp-7-agente"})
    assert r[0]["viva"] and len(lancadas) == 2


def test_painel_poe_o_token_na_pagina_e_o_artifact_fica_sem(tmp_path):
    dados, _ = montar.dados_da_pagina(estado_exemplo(), {})
    html = montar.html(dados)
    assert "const PAINEL = /*PAINEL*/null;" in html
    (tmp_path / "pareamento.html").write_text(html, encoding="utf-8")
    servida = painel.pagina(tmp_path, "segredo123").decode()
    assert '"token": "segredo123"' in servida and "/*PAINEL*/null" not in servida


def test_rascunho_so_vale_para_a_versao_de_agora_do_card():
    estado = estado_exemplo()
    k = next(iter(estado["cards"]))
    estado["cards"][k].update({"dono": "eu", "livre": True, "versao": "v1"})
    dados, _ = montar.dados_da_pagina(estado, {}, {k: {**RASCUNHO, "versao": "v1"}, "Hospital#404": RASCUNHO})
    assert set(dados["passagens"]) == {k} and "versao" not in dados["passagens"][k]
    dados, _ = montar.dados_da_pagina(estado, {}, {k: {**RASCUNHO, "versao": "velha"}})
    assert dados["passagens"] == {}
    assert "acoes" in dados["cards"][k]


def test_textos_novos_sem_travessao():
    for nome in ["references/passagem.md", "scripts/acoes.py", "scripts/passagem.py", "scripts/painel.py"]:
        texto = (SKILL / nome).read_text(encoding="utf-8")
        assert chr(0x2014) not in texto and chr(0x2013) not in texto, nome
