"""O roteiro dos prints da página de Reuniões e Pendências (issue #1721).

O roteiro refaz todas as imagens da página, a partir de um seed fictício numa
faixa de ids só dele, e recusa o print que mostre dado de fora do seed. Estes
testes rodam sem navegador e sem banco: leem o Markdown da página de verdade e
chamam as guardas do roteiro direto.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prints_manual_reunioes as roteiro  # noqa: E402

PAGINA = (
    Path(__file__).resolve().parent.parent
    / "hospital-reunioes/frontend/public/manual/reunioes-e-pendencias/pagina.md"
)


def imagens_da_pagina() -> list[str]:
    return re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", PAGINA.read_text(encoding="utf-8"))


def test_o_roteiro_refaz_todas_as_imagens_da_pagina():
    citadas = imagens_da_pagina()
    assert len(citadas) >= 6
    assert sorted(f"{nome}.png" for nome in roteiro.PRINTS) == sorted(citadas)


def test_o_print_do_inicio_sai_da_tela_onde_o_endereco_principal_cai(monkeypatch):
    # Issue #1948: o print prova que o app abre no Início. Ele entra pelo
    # endereço principal e espera o app levar ao Início, sem abrir o Início
    # direto.
    monkeypatch.setattr(roteiro, "_rest", lambda *a, **k: [])

    passos = roteiro.PRINTS["inicio"]()

    assert "abrir('/')" in passos
    assert "abrir('/inicio')" not in passos
    assert re.search(r"waitForURL\(.*'/inicio'", passos)


def test_o_print_do_inicio_nao_poe_balao_no_grupo_que_ja_comeca_aberto(monkeypatch):
    # Revisão do PR #2035: o grupo "Reuniões e metas" já começa aberto, e
    # clicar nele esconde o Dashboard. Os balões são Início (1) e Dashboard (2).
    monkeypatch.setattr(roteiro, "_rest", lambda *a, **k: [])

    passos = roteiro.PRINTS["inicio"]()
    baloes = re.findall(r"await balao\(page\.getByRole\('(\w+)', \{ name: '([^']+)'.*?, (\d+)\);", passos)

    assert baloes == [("link", "Início", "1"), ("link", "Dashboard", "2")]


def test_o_roteiro_grava_os_prints_ao_lado_do_markdown():
    assert roteiro.PASTA_DA_PAGINA == PAGINA.parent


def test_o_seed_so_tem_gente_de_exemplo_numa_faixa_propria():
    ids = [pid for pid, *_ in roteiro.PESSOAS]
    emails = [roteiro.email_de(nome) for _, nome, *_ in roteiro.PESSOAS]

    assert all(e.endswith("@exemplo.local") for e in emails)
    assert all(re.fullmatch(r"P1721\d", pid) for pid in ids)
    # As faixas dos outros roteiros de print: P900 a P989 (inclusive a P980 da casca).
    assert not any(re.fullmatch(r"P9[0-8]\d", pid) for pid in ids)
    assert len(set(ids)) == len(ids)


def test_print_com_nome_de_fora_do_seed_nao_sai():
    tela = "Pendências\nCalibrar as bombas\nFábio Guimarães\nMarcos Teixeira Lopes\n"

    with pytest.raises(roteiro.DadoRealNoPrint, match="Marcos Teixeira Lopes"):
        roteiro.exigir_so_dado_de_exemplo(tela, ["Marcos Teixeira Lopes", "Ana"], "pendencias")


def test_print_com_nome_de_fora_em_caixa_alta_nao_sai():
    # O CSS põe botão, cabeçalho e etiqueta em caixa alta, e o innerText
    # devolve o texto já transformado.
    tela = "PENDÊNCIAS\nMARCOS TEIXEIRA LOPES\nCOMISSÃO DE ÉTICA MÉDICA\n"

    with pytest.raises(roteiro.DadoRealNoPrint, match="Marcos Teixeira Lopes"):
        roteiro.exigir_so_dado_de_exemplo(tela, ["Marcos Teixeira Lopes"], "pendencias")
    with pytest.raises(roteiro.DadoRealNoPrint, match="Comissão de Ética Médica"):
        roteiro.exigir_so_dado_de_exemplo(tela, ["Comissão de Ética Médica"], "pendencias")


def test_a_lista_de_fora_do_seed_le_o_banco_alem_do_teto_do_postgrest(monkeypatch):
    # O PostgREST local corta cada resposta em max_rows = 1000.
    teto = 1000
    participantes = [{"id": f"X{i}", "nome_completo": f"Pessoa Real {i}"} for i in range(2500)]
    reunioes = [{"id_reuniao": f"R{i}", "titulo": f"Reunião Real {i}"} for i in range(1200)]

    def rest_com_teto(caminho, metodo="GET", corpo=None, prefer=None):
        tabela = participantes if caminho.startswith("participantes") else reunioes
        params = dict(p.split("=", 1) for p in caminho.split("?", 1)[1].split("&"))
        inicio = int(params.get("offset", 0))
        limite = min(int(params.get("limit", teto)), teto)
        return tabela[inicio : inicio + limite]

    monkeypatch.setattr(roteiro, "_rest", rest_com_teto)

    de_fora = roteiro.nomes_de_fora_do_seed()

    assert "Pessoa Real 2499" in de_fora
    assert "Reunião Real 1199" in de_fora
    assert len(de_fora) == 3700


def test_print_so_com_dado_de_exemplo_sai():
    tela = "Pendências\nCalibrar as bombas\nFábio Guimarães\nAnalisar o estoque\n"

    roteiro.exigir_so_dado_de_exemplo(tela, ["Marcos Teixeira Lopes", "Ana"], "pendencias")


def test_o_seed_recusa_banco_que_nao_e_o_local(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SUPABASE_URL=https://supabase.hospitalsaomatheus.cloud\nSUPABASE_SERVICE_KEY=x\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="não é o Supabase local"):
        roteiro.credenciais_locais(env)


# --------------------------------------------------------------------------
# O ciclo de vida, o painel e a Rotina (issue #1880)
# --------------------------------------------------------------------------


def test_as_reunioes_do_seed_nao_contam_como_dado_de_fora(monkeypatch):
    # A reunião em assinatura (da Contestação) é do seed: o Calendário e a
    # lista de Pendências mostram o título dela e o print tem de sair.
    reunioes = [{"id_reuniao": r, "titulo": t} for r, t in roteiro.REUNIOES_DO_SEED.items()]
    reunioes.append({"id_reuniao": "R1", "titulo": "Comissão de Ética Médica"})

    def rest(caminho, metodo="GET", corpo=None, prefer=None):
        if caminho.split("&offset=")[1] != "0":
            return []
        return reunioes if caminho.startswith("reunioes") else []

    monkeypatch.setattr(roteiro, "_rest", rest)

    de_fora = roteiro.nomes_de_fora_do_seed()

    assert len(roteiro.REUNIOES_DO_SEED) >= 3
    assert de_fora == ["Comissão de Ética Médica"]


def test_o_seed_novo_fica_na_faixa_da_issue():
    assert all(r.startswith("MRP1721") for r in roteiro.REUNIOES_DO_SEED)
    assert all(pid.startswith("PE1721") for pid, *_ in roteiro.PENDENCIAS)
    assert len({pid for pid, *_ in roteiro.PENDENCIAS}) == len(roteiro.PENDENCIAS)


def test_o_link_pessoal_do_seed_grava_so_o_hash_do_token(monkeypatch):
    # O banco guarda o hash, como o app (`link_pessoal.py`); o token em claro
    # só vive no roteiro, que abre a página por ele.
    gravados = []

    def rest(caminho, metodo="GET", corpo=None, prefer=None):
        if metodo == "POST":
            gravados.append((caminho, corpo))
        return []

    monkeypatch.setattr(roteiro, "_rest", rest)

    roteiro.semear_link_pessoal()

    (tabela, [linha]), *_ = [g for g in gravados if g[0] == "pendencias_links_pessoais"]
    assert tabela == "pendencias_links_pessoais"
    assert linha["token_hash"] == hashlib.sha256(roteiro.TOKEN_DO_LINK.encode()).hexdigest()
    assert roteiro.TOKEN_DO_LINK not in json.dumps(linha)
    assert linha["participante_id"] == roteiro.DONO_DO_LINK


def test_o_ranking_sai_pelo_super_admin_de_exemplo_e_so_com_gente_do_seed(monkeypatch):
    # O ranking com nomes é só do Super admin (issue #2144), e lista o hospital
    # inteiro: o print entra como o Super admin de exemplo e tira da tela as
    # linhas de quem não é do seed antes de a guarda ler o texto.
    monkeypatch.setattr(roteiro, "_rest", lambda *a, **k: [])
    admin = [p for p in roteiro.PESSOAS if p[4] == "super_admin"]

    passos = roteiro.PRINTS["ranking"]()

    assert roteiro.QUEM_TIRA["ranking"] == admin[0][0]
    for _, nome, *_ in roteiro.PESSOAS:
        assert json.dumps(nome, ensure_ascii=False) in passos
    assert ".remove()" in passos


class BancoDasVerificacoes:
    """`rotina_verificacoes` com a chave `id` e o `UNIQUE (rotina_id, ciclo_inicio)` da migration 177."""

    def __init__(self):
        self.linhas: dict[str, dict] = {}

    def rest(self, caminho, metodo="GET", corpo=None, prefer=None):
        if not caminho.startswith("rotina_verificacoes"):
            return []
        if metodo == "DELETE":
            rotina = caminho.split("rotina_id=eq.", 1)[1].split("&", 1)[0]
            self.linhas = {k: v for k, v in self.linhas.items() if v["rotina_id"] != rotina}
            return None
        if metodo == "POST":
            for linha in corpo:
                chave = linha.get("id") or f"novo-{len(self.linhas)}"
                if chave in self.linhas and prefer != "resolution=merge-duplicates":
                    raise SystemExit(f"POST {caminho}: 409 id repetido")
                ciclo = (linha["rotina_id"], linha["ciclo_inicio"])
                if any((v["rotina_id"], v["ciclo_inicio"]) == ciclo for k, v in self.linhas.items() if k != chave):
                    raise SystemExit(f"POST {caminho}: 409 rotina_verificacoes_rotina_id_ciclo_inicio_key")
                self.linhas[chave] = linha
        return []


def test_a_rotina_semeia_de_novo_semanas_depois_sem_bater_no_ciclo_unico(monkeypatch):
    # Revisão do PR #2156: o ciclo anda com a semana de hoje, e a Verificação
    # de id fixo da rodada anterior ainda ocupa o ciclo que a de agora grava.
    banco = BancoDasVerificacoes()
    monkeypatch.setattr(roteiro, "_rest", banco.rest)
    primeira_segunda = roteiro.dt.date(2026, 11, 16)

    for semanas_depois in range(4):
        hoje = primeira_segunda + roteiro.dt.timedelta(days=7 * semanas_depois)
        monkeypatch.setattr(roteiro, "_segunda", lambda n, hoje=hoje: hoje - roteiro.dt.timedelta(days=7 * n))

        roteiro.semear_rotina()

        ciclos = sorted(v["ciclo_inicio"] for v in banco.linhas.values())
        esperados = sorted((hoje - roteiro.dt.timedelta(days=7 * s)).isoformat() for s, *_ in roteiro.VERIFICACOES)
        assert ciclos == esperados


def _historico_falso(eventos):
    gravados = []

    def rest(caminho, metodo="GET", corpo=None, prefer=None):
        if metodo == "POST":
            gravados.extend(corpo)
            return None
        assert caminho.startswith(f"pendencia_historico?id_acao=eq.{roteiro.CONTESTADA}")
        return eventos

    return rest, gravados


def _agora_utc(dias_atras: int = 0) -> str:
    agora = roteiro.dt.datetime.now(roteiro.dt.timezone.utc) - roteiro.dt.timedelta(days=dias_atras)
    return agora.isoformat()


def test_a_contestacao_antiga_entra_de_novo_para_seguir_no_grupo_de_48_horas(monkeypatch):
    # Revisão do PR #2156: o prazo da Contestação é o dia seguinte a ela, e o
    # Histórico não muda. A semeadura de outro dia grava uma Contestação nova,
    # senão o print `minha-fila` não acha o grupo de até 48 horas.
    rest, gravados = _historico_falso([{"comando": "contestar", "criado_em": _agora_utc(dias_atras=2)}])
    monkeypatch.setattr(roteiro, "_rest", rest)

    roteiro.semear_contestacao()

    assert [g["comando"] for g in gravados] == ["contestar"]
    assert gravados[0]["id_acao"] == roteiro.CONTESTADA


def test_a_contestacao_de_hoje_nao_entra_de_novo(monkeypatch):
    rest, gravados = _historico_falso([{"comando": "contestar", "criado_em": _agora_utc()}])
    monkeypatch.setattr(roteiro, "_rest", rest)

    roteiro.semear_contestacao()

    assert gravados == []


def test_a_contestacao_respondida_no_banco_local_e_aberta_de_novo(monkeypatch):
    rest, gravados = _historico_falso([{"comando": "ajustar", "criado_em": _agora_utc()}])
    monkeypatch.setattr(roteiro, "_rest", rest)

    roteiro.semear_contestacao()

    assert [g["comando"] for g in gravados] == ["contestar"]
