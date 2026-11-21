-- =====================================================
-- Migration 182: o alerta de caso grave e a confirmação de recebimento
-- (issue #1989, PRD #1979)
-- =====================================================
-- Os dois e-mails da chegada de uma notificação nascem no registro de e-mail
-- do Núcleo (`nsp_avisos`, migrations 158 e 173), como todo e-mail do módulo:
--
--   1. o marco ganha `caso_grave` (o alerta à Presidência, ao suplente, ao
--      Acesso pleno e à Diretoria, quando quem notificou marcou "grave ou
--      houve morte") e `confirmacao_de_recebimento` (a quem se identificou
--      com e-mail);
--   2. a confirmação vai a quem notificou, que não precisa ter cadastro: o
--      destinatário deixa de ser obrigatório só para ela, e o endereço sai da
--      própria notificação na hora do envio, sem ficar copiado no registro;
--   3. uma confirmação por caso: a chave única da 173 não segura destinatário
--      vazio (NULL não repete), e a confirmação ganha a dela.
--
-- Nenhuma pessoa entra por aqui. A tabela já tem RLS sem política: só o
-- backend, com a service_role, lê e grava. Rodar duas vezes é inofensivo.
-- Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. Os marcos da chegada ----------
ALTER TABLE nsp_avisos DROP CONSTRAINT IF EXISTS nsp_avisos_marco_check;
ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_marco_check
  CHECK (marco IN ('documento_gerado', 'assinatura_3', 'assinatura_7', 'assinatura_14',
                   'vigencia_60', 'vigencia_30', 'fim_da_carencia', 'convocacao',
                   'caso_grave', 'confirmacao_de_recebimento'));

-- ---------- 2. A confirmação vai a quem notificou ----------
ALTER TABLE nsp_avisos ALTER COLUMN destinatario_id DROP NOT NULL;

ALTER TABLE nsp_avisos DROP CONSTRAINT IF EXISTS nsp_avisos_destinatario_check;
ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_destinatario_check
  CHECK (destinatario_id IS NOT NULL OR (marco = 'confirmacao_de_recebimento' AND caso_id IS NOT NULL));

COMMENT ON COLUMN nsp_avisos.destinatario_id IS
  'Quem recebe o e-mail. Vazio só na confirmação de recebimento: o endereço sai da notificação (caso_id) na hora do envio.';

-- ---------- 3. Uma confirmação por caso ----------
CREATE UNIQUE INDEX IF NOT EXISTS uq_nsp_avisos_confirmacao
  ON nsp_avisos (caso_id, marco, referencia)
  WHERE destinatario_id IS NULL;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (182) ON CONFLICT (numero) DO NOTHING;
