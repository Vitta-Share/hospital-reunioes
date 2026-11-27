"""A skill /pareamento, parte das ações: bloqueio no texto, volta do diretor, ações por card,
passagem ao diretor, aderência à ADR 0113 e o acao.py, a porta da Ala Pareamento do PedroOS."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from test_pareamento import DIR, EU, SKILL, carregar, estado_exemplo, issue, montar, projeto

coletar = carregar("coletar")
acoes = carregar("acoes")
passagem = carregar("passagem")
acao = carregar("acao")
aderencia = carregar("aderencia")


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


def test_explicar_so_aparece_no_card_do_diretor_sem_explicacao():
    sem = c_acao("diretor", corpo="Só o passo a passo.")
    com = c_acao("diretor", corpo="## 🔁 Por que este card passou para você\n...")
    assert acoes.acoes_extra(sem) == ["explicar", "cobrar"]
    assert acoes.acoes_extra(com) == ["cobrar"]
    assert acoes.acoes_extra({**com, "livre": False}) == []
    assert acoes.acoes_extra(c_acao("eu", labels=["com:ti"])) == ["limpar"]
    assert acoes.rotulo("Hospital#2330") == "#2330" and acoes.rotulo("Ana#4") == "Ana #4"


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


def estado_da_ala(tmp_path, cards, gerado="2026-11-27T12:00:00+00:00"):
    estado = {"gerado_em": gerado, "eu": {"login": EU, "nome": "Pedro"}, "diretor": {"login": DIR, "nome": "Felipe"},
              "projetos": [{"nome": "Hospital", "repo": "o/r", "prds": []}], "cards": cards}
    (tmp_path / "estado.json").write_text(json.dumps(estado), encoding="utf-8")
    return estado


def test_acao_sessao_so_do_que_o_card_aceita(tmp_path):
    estado_da_ala(tmp_path, {"Hospital#7": c_acao("agente"),
                             "Hospital#8": {**c_acao("diretor"), "chave": "Hospital#8", "numero": 8}})
    r = acao.sessao(tmp_path, "agente", "Hospital#7")
    assert r["nome"] == "par-hosp-7-agente" and r["projeto"] == "Hospital" and "/pegar-issue 7" in r["prompt"]
    # Card do diretor não abre sessão de esfera, mas aceita as da aderência.
    assert "menciona o diretor" in acao.sessao(tmp_path, "cobrar", "Hospital#8")["prompt"]
    for tipo, chave in [("tocar", "Hospital#8"), ("agente", "Hospital#99")]:
        try:
            acao.sessao(tmp_path, tipo, chave)
        except ValueError:
            continue
        raise AssertionError((tipo, chave))
    assert "/montar-ondas-enxutas" in acao.sessao(tmp_path, "onda", projeto="Hospital")["prompt"]
    assert "/pareamento" in acao.sessao(tmp_path, "atualizar")["prompt"]


def test_acao_cli_devolve_erro_em_json(tmp_path, capsys):
    estado_da_ala(tmp_path, {})
    assert acao.main(["sessao", "--pasta", str(tmp_path), "--tipo", "onda", "--projeto", "../x"]) == 2
    assert json.loads(capsys.readouterr().out)["erro"]
    assert acao.main(["dados", "--pasta", str(tmp_path / "nada")]) == 2


def test_acao_dados_sem_corpo_com_aderencia(tmp_path):
    estado_da_ala(tmp_path, {"Hospital#7": {**c_acao(), "corpo": "SEGREDO", "versao": "v", "espera": [], "segura": [],
                                            "prd": None, "labels": [], "titulo": "t"}})
    d = acao.dados(tmp_path, agora=datetime(2026, 11, 27, 13, tzinfo=timezone.utc))
    assert "SEGREDO" not in json.dumps(d, ensure_ascii=False)
    assert d["cards"]["Hospital#7"]["acoes"] and "extras" in d["cards"]["Hospital#7"]
    assert 0 <= d["aderencia"]["nota"] <= 100 and d["rotulos"]["cobrar"]


def test_acao_passar_so_card_seu_e_marca_feito(tmp_path):
    estado_da_ala(tmp_path, {"Hospital#7": c_acao(), "Hospital#8": {**c_acao("diretor"), "chave": "Hospital#8", "numero": 8}})
    chamado = []
    acao.passar(tmp_path, "Hospital#7", RASCUNHO, executar=lambda *a: chamado.append(a) or {"ok": True})
    assert chamado[0][:2] == ("o/r", 7)
    assert "passado:Hospital#7" in json.loads((tmp_path / "feitos.json").read_text(encoding="utf-8"))
    try:
        acao.passar(tmp_path, "Hospital#8", RASCUNHO, executar=lambda *a: {"ok": True})
    except ValueError:
        pass
    else:
        raise AssertionError


AGORA = datetime(2026, 11, 27, 13, tzinfo=timezone.utc)


def card_ad(k, dono, **extra):
    n = int(k.split("#")[1])
    return {"chave": k, "numero": n, "projeto": "Hospital", "dono": dono, "livre": True, "labels": [], "corpo": "",
            "versao": "v", "atualizado": "2026-11-27T10:00:00Z", **extra}


def regras(r, estado="falta"):
    return sorted((i["regra"], i["chave"]) for i in r["faltam" if estado == "falta" else "justificados"])


def test_aderencia_cem_quando_tudo_segue_a_adr():
    estado = {"gerado_em": "2026-11-27T12:00:00+00:00", "cards": {
        "Hospital#1": card_ad("Hospital#1", "diretor", corpo="## 🔁 Por que este card passou para você"),
        "Hospital#2": card_ad("Hospital#2", "eu"),
        "Hospital#3": card_ad("Hospital#3", "eu", labels=["com:ti"]),
    }}
    desc = {"Hospital#2": {"proximo": "tocar"}, "Hospital#3": {"proximo": "esperar", "proximo_porque": "Segura até 30/11."}}
    r = aderencia.aderencia(estado, desc, {}, {}, AGORA)
    assert r["nota"] == 100 and r["faltam"] == []
    assert regras(r, "justificado") == [("comunicacao", "Hospital#3")]


def test_aderencia_aponta_cada_falta_com_a_acao_que_resolve():
    estado = {"gerado_em": "2026-11-26T12:00:00+00:00", "cards": {
        "Hospital#1": card_ad("Hospital#1", "diretor"),  # sem explicação
        "Hospital#2": card_ad("Hospital#2", "diretor", corpo="👔 Para o diretor", atualizado="2026-11-20T10:00:00Z"),
        "Hospital#3": card_ad("Hospital#3", "eu", voltou=True, labels=["needs-info"]),
        "Hospital#4": card_ad("Hospital#4", "eu", no_texto=["Hospital#9"]),
        "Hospital#5": card_ad("Hospital#5", "eu", labels=["com:rib"]),
        "Hospital#6": card_ad("Hospital#6", "eu"),
    }}
    desc = {"Hospital#4": {"proximo": "esperar", "proximo_porque": "x"}, "Hospital#5": {"proximo": "tocar"},
            "Hospital#6": {"proximo": "diretor"}}
    r = aderencia.aderencia(estado, desc, {}, {}, AGORA)
    assert [i["acao"]["tipo"] for i in r["faltam"]] == ["voltou", "bloqueio", "explicar", "cobrar", "diretor", "limpar", "atualizar"]
    assert r["faltam"][1]["acao"] == {"tipo": "bloqueio", "chave": "Hospital#4", "espera": "Hospital#9"}
    assert "espera o #9," in r["faltam"][1]["motivo"]
    assert 0 < r["nota"] < 100
    # O que já foi feito pela Ala sai da conta, e o rascunho da versão de agora fecha a passagem.
    feitos = {"bloqueio:Hospital#4:Hospital#9": "x"}
    r2 = aderencia.aderencia(estado, desc, {"Hospital#6": {"versao": "v"}}, feitos, AGORA)
    assert ("bloqueio", "Hospital#4") not in regras(r2) and ("passagem", "Hospital#6") not in regras(r2)


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
    for nome in ["references/passagem.md", "scripts/acoes.py", "scripts/passagem.py", "scripts/acao.py", "scripts/aderencia.py"]:
        texto = (SKILL / nome).read_text(encoding="utf-8")
        assert chr(0x2014) not in texto and chr(0x2013) not in texto, nome
