-- =====================================================
-- Migration 211: a Pergunta da Vitta e a conversa do Me explique
-- (issue #2116, PRD #2112, ADR 0109)
-- =====================================================
-- A pergunta que a Vitta manda a alguem do Hospital pela ponte de automacao
-- deixa de ser so uma mensagem da Conversa da Demanda e vira registro do app
-- (ADR 0109, decisao 1). Uma migration so para o PRD inteiro, porque cada
-- migration espera o Pedro aplicar. Duas tabelas:
--
--   1. `tecnologia_perguntas`: a Pergunta, ligada a uma Demanda e a entrada
--      dela na Conversa (`mensagem_id`), com Destinatario, Assunto, o texto,
--      as quatro linhas do cartao, as opcoes com a recomendada e o porque, e o
--      estado (aberta, respondida, resolvida, cancelada). Ja nasce com as
--      colunas das proximas Fatias: a resposta (opcao ou texto, quem
--      registrou e em nome de quem), a resolucao (o que foi decidido e o que
--      destravou), a data de cada passagem e a do lembrete unico de 3 dias;
--
--   2. `tecnologia_conversas_do_me_explique`: a conversa particular do Me
--      explique (decisao 8), uma por Pergunta e por pessoa. So o que a pessoa
--      envia vai para a Conversa da Demanda; esta fica com ela.
--
-- RLS default-deny (padrao da casa): quem le e escreve e o backend com a
-- service_role. Nenhuma policy de proposito.
--
-- Aplicar a mao no Studio: o deploy nao aplica SQL. Rodar duas vezes e
-- inofensivo.
-- =====================================================

BEGIN;

-- ---------- 1. A Pergunta da Vitta ----------
-- ON DELETE CASCADE na Demanda: a Pergunta nao tem sentido sem ela (que, na
-- pratica, nao se apaga; o Apagar e lapide). ON DELETE SET NULL nas pessoas e
-- na entrada da Conversa: a Pergunta fica se a pessoa sai do cadastro.
CREATE TABLE IF NOT EXISTS tecnologia_perguntas (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demanda_id             UUID NOT NULL REFERENCES tecnologia_demandas(id) ON DELETE CASCADE,
  mensagem_id            UUID UNIQUE REFERENCES tecnologia_conversa_da_demanda(id) ON DELETE SET NULL,
  autor_id               VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  destinatario_id        VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  assunto                TEXT NOT NULL CHECK (btrim(assunto) <> '' AND char_length(assunto) <= 120),
  texto                  TEXT NOT NULL CHECK (btrim(texto) <> '' AND char_length(texto) <= 5000),
  por_que_precisa        TEXT NOT NULL CHECK (btrim(por_que_precisa) <> '' AND char_length(por_que_precisa) <= 500),
  o_que_esta_parado      TEXT NOT NULL CHECK (btrim(o_que_esta_parado) <> '' AND char_length(o_que_esta_parado) <= 500),
  o_que_anda_depois      TEXT NOT NULL CHECK (btrim(o_que_anda_depois) <> '' AND char_length(o_que_anda_depois) <= 500),
  ganho                  TEXT NOT NULL CHECK (btrim(ganho) <> '' AND char_length(ganho) <= 500),
  opcoes                 JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(opcoes) = 'array'),
  recomendada            TEXT CHECK (recomendada IS NULL OR recomendada IN ('A', 'B', 'C', 'D')),
  porque_da_recomendada  TEXT CHECK (porque_da_recomendada IS NULL OR char_length(porque_da_recomendada) <= 500),
  estado                 TEXT NOT NULL DEFAULT 'aberta'
                         CHECK (estado IN ('aberta', 'respondida', 'resolvida', 'cancelada')),
  resposta_opcao         TEXT CHECK (resposta_opcao IS NULL OR resposta_opcao IN ('A', 'B', 'C', 'D')),
  resposta_texto         TEXT CHECK (resposta_texto IS NULL OR char_length(resposta_texto) <= 5000),
  respondida_por         VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  respondida_em_nome_de  VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  respondida_em          TIMESTAMPTZ,
  resolucao_decidido     TEXT CHECK (resolucao_decidido IS NULL OR char_length(resolucao_decidido) <= 2000),
  resolucao_destravou    TEXT CHECK (resolucao_destravou IS NULL OR char_length(resolucao_destravou) <= 2000),
  resolvida_em           TIMESTAMPTZ,
  cancelada_em           TIMESTAMPTZ,
  lembrete_enviado_em    TIMESTAMPTZ,
  criado_em              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tecnologia_perguntas_demanda
  ON tecnologia_perguntas (demanda_id, criado_em);

-- A lista Esperando sua resposta e o lembrete de 3 dias leem so as abertas.
CREATE INDEX IF NOT EXISTS idx_tecnologia_perguntas_abertas
  ON tecnologia_perguntas (criado_em) WHERE estado = 'aberta';

CREATE INDEX IF NOT EXISTS idx_tecnologia_perguntas_destinatario
  ON tecnologia_perguntas (destinatario_id);

COMMENT ON TABLE tecnologia_perguntas IS
  'Pergunta da Vitta (ADR 0109): a pergunta que a Vitta manda a alguem do Hospital pela ponte, ligada a uma Demanda e a entrada dela na Conversa. Nunca se chama Pendencia (Pendencia e a Acao da Ata).';
COMMENT ON COLUMN tecnologia_perguntas.mensagem_id IS
  'A entrada da Pergunta na Conversa da Demanda: a tela desenha o cartao no lugar da bolha dela.';
COMMENT ON COLUMN tecnologia_perguntas.opcoes IS
  'As opcoes prontas, na ordem: lista de {letra, texto}, de A a D. Vazia = so o campo livre.';
COMMENT ON COLUMN tecnologia_perguntas.estado IS
  'aberta = espera a resposta; respondida = a pessoa respondeu e a Vitta ainda nao leu; resolvida = a Vitta leu e deu o ok; cancelada = deixou de ser necessaria.';
COMMENT ON COLUMN tecnologia_perguntas.respondida_por IS
  'Quem registrou a resposta: o Destinatario, ou um Desenvolvedor no lugar dele (ADR 0109, decisao 5).';
COMMENT ON COLUMN tecnologia_perguntas.respondida_em_nome_de IS
  'O Destinatario, quando um Desenvolvedor registrou a resposta no lugar dele.';
COMMENT ON COLUMN tecnologia_perguntas.lembrete_enviado_em IS
  'O lembrete unico, depois de 3 dias sem resposta (ADR 0109, decisao 7). Nulo = ainda nao foi.';

ALTER TABLE tecnologia_perguntas ENABLE ROW LEVEL SECURITY;

-- ---------- 2. A conversa do Me explique ----------
-- Uma por Pergunta e por pessoa: o Assistente explica em particular (ADR
-- 0109, decisao 8). `mensagens` segue o JSONB da conversa com o agente.
CREATE TABLE IF NOT EXISTS tecnologia_conversas_do_me_explique (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pergunta_id      UUID NOT NULL REFERENCES tecnologia_perguntas(id) ON DELETE CASCADE,
  participante_id  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE CASCADE,
  mensagens        JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(mensagens) = 'array'),
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (pergunta_id, participante_id)
);

CREATE INDEX IF NOT EXISTS idx_tecnologia_conversas_do_me_explique_participante
  ON tecnologia_conversas_do_me_explique (participante_id);

COMMENT ON TABLE tecnologia_conversas_do_me_explique IS
  'Me explique (ADR 0109, decisao 8): a conversa particular de uma pessoa com o Assistente sobre uma Pergunta da Vitta. Nada daqui vai para a Conversa da Demanda sem a pessoa enviar.';

ALTER TABLE tecnologia_conversas_do_me_explique ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (211) ON CONFLICT (numero) DO NOTHING;
