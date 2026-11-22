-- =====================================================
-- Migration 232: o Pedido da Vitta, Pergunta ou Passo a passo
-- (issue #2176, ADR 0110, emenda a 0109)
-- =====================================================
-- O registro da Pergunta da Vitta (migration 211) passa a ser o Pedido da
-- Vitta, com dois tipos: Pergunta (como hoje) e Passo a passo (o card humano
-- que pede para fazer alguma coisa). A tabela continua a mesma, e ganha:
--
--   - `tipo` (pergunta | passo_a_passo); as linhas que existem ficam Pergunta;
--   - o card do Passo a passo (Projeto e numero da issue), que o app fecha no
--     GitHub quando o Passo a passo e concluido (decisao 5);
--   - os passos, uma lista ordenada de textos; o ultimo e o "Como saber que
--     acabou" (decisao 4);
--   - o estado `concluida`, so do Passo a passo, que usa aberta, concluida e
--     cancelada; a Pergunta segue com os quatro estados de antes;
--   - quem concluiu, em nome de quem, quando e como (pelo app ou pelo GitHub,
--     decisoes 6 e 7). A anotacao opcional da conclusao fica em
--     `resposta_texto`, o campo de resposta do cartao;
--   - o fechamento no GitHub (pendente, fechado, falhou) e o motivo da falha
--     (decisao 8).
--
-- Nasce `tecnologia_checks_do_pedido`, o historico dos checks: cada marcar ou
-- desmarcar e uma linha nova, com quem e em nome de quem (decisao 4). So
-- cresce: o gatilho recusa UPDATE e DELETE direto; o Pedido apagado leva o
-- historico junto (cascata).
--
-- RLS default-deny nas duas (padrao da casa): quem le e escreve e o backend
-- com a service_role. Nenhuma policy de proposito.
--
-- Aplicar a mao no Studio: o deploy nao aplica SQL. Rodar duas vezes e
-- inofensivo.
-- =====================================================

BEGIN;

-- ---------- 1. O Pedido da Vitta ----------
ALTER TABLE tecnologia_perguntas
  ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'pergunta'
    CHECK (tipo IN ('pergunta', 'passo_a_passo')),
  ADD COLUMN IF NOT EXISTS card_projeto TEXT
    CHECK (card_projeto IS NULL OR card_projeto ~ '^[a-z0-9][a-z0-9-]{0,39}$'),
  ADD COLUMN IF NOT EXISTS card_numero INTEGER
    CHECK (card_numero IS NULL OR card_numero > 0),
  ADD COLUMN IF NOT EXISTS passos JSONB NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(passos) = 'array'),
  ADD COLUMN IF NOT EXISTS concluida_por VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS concluida_em_nome_de VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS concluida_em TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS concluida_como TEXT
    CHECK (concluida_como IS NULL OR concluida_como IN ('app', 'github')),
  ADD COLUMN IF NOT EXISTS fechamento_github TEXT
    CHECK (fechamento_github IS NULL OR fechamento_github IN ('pendente', 'fechado', 'falhou')),
  ADD COLUMN IF NOT EXISTS fechamento_motivo TEXT
    CHECK (fechamento_motivo IS NULL OR char_length(fechamento_motivo) <= 500);

-- O estado: o CHECK da 211 sai e entra o dos dois tipos.
ALTER TABLE tecnologia_perguntas DROP CONSTRAINT IF EXISTS tecnologia_perguntas_estado_check;
ALTER TABLE tecnologia_perguntas DROP CONSTRAINT IF EXISTS tecnologia_perguntas_estado_do_tipo;
ALTER TABLE tecnologia_perguntas ADD CONSTRAINT tecnologia_perguntas_estado_do_tipo CHECK (
  (tipo = 'pergunta' AND estado IN ('aberta', 'respondida', 'resolvida', 'cancelada'))
  OR (tipo = 'passo_a_passo' AND estado IN ('aberta', 'concluida', 'cancelada'))
);

-- O Passo a passo sempre tem o card e de 2 a 15 passos (o ultimo e o criterio).
ALTER TABLE tecnologia_perguntas DROP CONSTRAINT IF EXISTS tecnologia_perguntas_passo_a_passo_completo;
ALTER TABLE tecnologia_perguntas ADD CONSTRAINT tecnologia_perguntas_passo_a_passo_completo CHECK (
  tipo = 'pergunta'
  OR (card_projeto IS NOT NULL AND card_numero IS NOT NULL AND jsonb_array_length(passos) BETWEEN 2 AND 15)
);

-- O webhook do GitHub acha o Passo a passo pelo card (decisao 7).
CREATE INDEX IF NOT EXISTS idx_tecnologia_perguntas_card
  ON tecnologia_perguntas (card_projeto, card_numero) WHERE tipo = 'passo_a_passo';

COMMENT ON TABLE tecnologia_perguntas IS
  'Pedido da Vitta (ADR 0110): o que a Vitta pede a uma pessoa e que segura trabalho ate ela agir. Dois tipos: Pergunta (ADR 0109) e Passo a passo. Nunca se chama Pendencia (Pendencia e a Acao da Ata).';
COMMENT ON COLUMN tecnologia_perguntas.tipo IS
  'pergunta = se responde e espera a leitura da Vitta; passo_a_passo = se conclui e fecha o card no GitHub (ADR 0110, decisao 5).';
COMMENT ON COLUMN tecnologia_perguntas.passos IS
  'Os passos do Passo a passo, na ordem: lista de textos. O ultimo e o "Como saber que acabou". Vazia na Pergunta.';
COMMENT ON COLUMN tecnologia_perguntas.concluida_como IS
  'app = concluido no cartao; github = o card foi fechado como feito por fora (ADR 0110, decisao 7).';
COMMENT ON COLUMN tecnologia_perguntas.fechamento_github IS
  'O fechamento do card pelo app: pendente, fechado ou falhou (com o motivo). Nunca ha reenvio automatico (decisao 8).';
COMMENT ON COLUMN tecnologia_perguntas.resposta_texto IS
  'Na Pergunta, o texto livre da resposta; no Passo a passo, a anotacao opcional da conclusao (fica so no app).';

-- ---------- 2. O historico dos checks ----------
CREATE TABLE IF NOT EXISTS tecnologia_checks_do_pedido (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pedido_id   UUID NOT NULL REFERENCES tecnologia_perguntas(id) ON DELETE CASCADE,
  passo       SMALLINT NOT NULL CHECK (passo BETWEEN 0 AND 14),
  marcado     BOOLEAN NOT NULL,
  por         VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  em_nome_de  VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tecnologia_checks_do_pedido_pedido
  ON tecnologia_checks_do_pedido (pedido_id, criado_em);

COMMENT ON TABLE tecnologia_checks_do_pedido IS
  'Os checks do Passo a passo da Vitta (ADR 0110, decisao 4): cada marcar ou desmarcar e uma linha, com quem e quando. So cresce; o estado de um passo e a ultima linha dele. Sem `por` = o app zerou os checks na reabertura do card.';
COMMENT ON COLUMN tecnologia_checks_do_pedido.passo IS
  'O indice do passo na lista `passos` do Pedido, a partir de 0.';
COMMENT ON COLUMN tecnologia_checks_do_pedido.em_nome_de IS
  'O Destinatario, quando um Desenvolvedor marcou no lugar dele (decisao 6).';

-- So cresce: UPDATE e DELETE direto sao recusados. A cascata do Pedido e o
-- SET NULL das pessoas chegam por gatilho de chave estrangeira
-- (pg_trigger_depth() > 1) e passam.
CREATE OR REPLACE FUNCTION tecnologia_checks_do_pedido_so_cresce()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  IF pg_trigger_depth() = 1 THEN
    RAISE EXCEPTION 'O historico dos checks so cresce: % recusado.', TG_OP;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tecnologia_checks_do_pedido_so_cresce ON tecnologia_checks_do_pedido;
CREATE TRIGGER tecnologia_checks_do_pedido_so_cresce
  BEFORE UPDATE OR DELETE ON tecnologia_checks_do_pedido
  FOR EACH ROW EXECUTE FUNCTION tecnologia_checks_do_pedido_so_cresce();

ALTER TABLE tecnologia_checks_do_pedido ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (232) ON CONFLICT (numero) DO NOTHING;
