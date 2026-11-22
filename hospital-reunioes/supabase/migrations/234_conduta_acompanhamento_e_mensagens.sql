-- =====================================================
-- Migration 234: Canal de Conduta, a página de acompanhamento e as Mensagens
-- do caso (issue #1845, PRD #1786, ADR 0097, decisões 1 e 10;
-- especificação, P7 e 6.1)
-- =====================================================
-- O que entra:
--   1. as mensagens do caso: as perguntas da coordenação a quem relatou e o
--      complemento que chega pela página de acompanhamento, com o texto
--      cifrado pela aplicação. Gravada, a mensagem não muda nem se apaga.
--      O complemento não tem autor: quem relatou não tem login, e nada de
--      IP, aparelho ou localização entra aqui;
--   2. o desfecho `arquivado`: pedido de complemento sem resposta em 15 dias
--      permite arquivar por falta de elementos, e a etapa em que o caso
--      estava fica guardada para a reabertura.
--
-- RLS default-deny na tabela nova: só o backend, com a service_role, lê e
-- grava. Nenhuma policy de propósito.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. As mensagens do caso ----------
CREATE TABLE IF NOT EXISTS conduta_mensagens (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id        UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  tipo           TEXT NOT NULL CHECK (tipo IN ('pergunta', 'complemento')),
  -- Quem da coordenação perguntou; nulo no complemento de quem relatou.
  autor_id       VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  texto_cifrado  TEXT NOT NULL CHECK (texto_cifrado LIKE 'v1:%'),
  enviada_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT conduta_mensagens_autor_check CHECK ((tipo = 'complemento') = (autor_id IS NULL))
);

COMMENT ON TABLE conduta_mensagens IS
  'Conversa do Comitê com quem relatou, pela página de acompanhamento do Canal de Conduta (issue #1845): perguntas da coordenação e complementos, com o texto cifrado. Imutável.';

CREATE INDEX IF NOT EXISTS idx_conduta_mensagens_caso
  ON conduta_mensagens (caso_id, enviada_em);
CREATE INDEX IF NOT EXISTS idx_conduta_mensagens_autor
  ON conduta_mensagens (autor_id);

ALTER TABLE conduta_mensagens ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_mensagens FROM anon, authenticated;

CREATE OR REPLACE FUNCTION conduta_mensagem_imutavel() RETURNS TRIGGER
SET search_path = public
AS $$
BEGIN
  RAISE EXCEPTION 'A mensagem do caso fica como foi enviada: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_mensagem_imutavel ON conduta_mensagens;
CREATE TRIGGER trg_conduta_mensagem_imutavel
  BEFORE UPDATE OR DELETE ON conduta_mensagens
  FOR EACH ROW EXECUTE FUNCTION conduta_mensagem_imutavel();

-- ---------- 2. O arquivamento por falta de elementos ----------
ALTER TABLE conduta_casos
  ADD COLUMN IF NOT EXISTS etapa_ao_arquivar TEXT;

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_desfecho_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_desfecho_check
  CHECK (desfecho IS NULL OR desfecho IN ('encaminhado', 'parecer_entregue', 'concluido', 'arquivado'));

-- O arquivado guarda a etapa para reabrir; os outros não guardam nada.
ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_arquivado_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_arquivado_check
  CHECK ((desfecho IS NOT DISTINCT FROM 'arquivado') = (etapa_ao_arquivar IS NOT NULL AND encerrado_em IS NOT NULL));

COMMENT ON COLUMN conduta_casos.etapa_ao_arquivar IS
  'A etapa em que o caso estava quando foi arquivado por falta de elementos (pedido de complemento sem resposta em 15 dias). A reabertura volta a ela. Issue #1845.';

COMMIT;

-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (234) ON CONFLICT (numero) DO NOTHING;
