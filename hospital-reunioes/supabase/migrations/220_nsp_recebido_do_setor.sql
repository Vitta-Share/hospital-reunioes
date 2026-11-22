-- =====================================================
-- Migration 220: encaminhar à Segurança do Trabalho e à queixa técnica,
-- com o botão "Recebido" (issue #1996, PRD #1979, ADR 0107 decisão 8)
-- =====================================================
-- O que entra:
--   1. `nsp_encaminhamentos` aceita os destinos `seguranca_do_trabalho` e
--      `queixa_tecnica`, ao lado dos da migration 209;
--   2. `nsp_recebimentos`: um envio por destino com Recebido, endereçado ao
--      titular vigente (ou ao gestor) do cadastro de responsáveis da
--      Ouvidoria. Guarda só o HASH do token do link de uso único
--      (`token_hash`), a validade (`expira_em`), quando saiu, o reenvio único
--      e o clique (`recebido_em`). O token em claro só existe no e-mail;
--   3. o registro de e-mail do Núcleo (`nsp_avisos`) ganha os marcos
--      `encaminhamento_setor` (o e-mail ao setor) e
--      `encaminhamento_sem_titular` (o aviso à Presidência quando o setor não
--      tem titular). Somados aos que a constraint já aceita, lidos dela, para
--      não desfazer o marco que outra migration da leva tenha somado;
--   4. o e-mail ao setor não tem `destinatario_id` (o responsável não é um
--      cadastro de pessoa): o endereço sai do recebimento na hora do envio. A
--      regra do destinatário ganha esse caso, somada à que já vale.
--
-- Nenhuma pessoa entra por aqui. RLS ligado e sem política na tabela nova:
-- só o backend, com a service_role, lê e grava. Rodar duas vezes é
-- inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. Os destinos novos do encaminhamento ----------
ALTER TABLE nsp_encaminhamentos DROP CONSTRAINT IF EXISTS nsp_encaminhamentos_destinos_check;
ALTER TABLE nsp_encaminhamentos ADD CONSTRAINT nsp_encaminhamentos_destinos_check CHECK (
  cardinality(destinos) >= 1
  AND destinos <@ ARRAY['nucleo', 'ouvidoria', 'canal_de_conduta', 'seguranca_do_trabalho', 'queixa_tecnica', 'fora_de_escopo']::TEXT[]
  AND (NOT ('fora_de_escopo' = ANY (destinos)) OR cardinality(destinos) = 1)
);

-- ---------- 2. Os envios com Recebido ----------
CREATE TABLE IF NOT EXISTS nsp_recebimentos (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  encaminhamento_id   UUID NOT NULL REFERENCES nsp_encaminhamentos(id) ON DELETE RESTRICT,
  notificacao_id      UUID NOT NULL REFERENCES nsp_notificacoes(id) ON DELETE RESTRICT,
  destino             TEXT NOT NULL CHECK (destino IN ('seguranca_do_trabalho', 'queixa_tecnica')),
  setor               TEXT NOT NULL CHECK (btrim(setor) <> ''),
  destinatario_nome   TEXT NOT NULL CHECK (char_length(destinatario_nome) <= 200),
  destinatario_email  TEXT NOT NULL CHECK (char_length(btrim(destinatario_email)) BETWEEN 3 AND 320),
  papel               TEXT NOT NULL CHECK (papel IN ('titular', 'gestor')),
  token_hash          TEXT UNIQUE CHECK (token_hash IS NULL OR token_hash ~ '^[0-9a-f]{64}$'),
  expira_em           TIMESTAMPTZ,
  enviado_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
  reenviado_em        TIMESTAMPTZ,
  recebido_em         TIMESTAMPTZ,
  criado_em           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (encaminhamento_id, destino)
);

COMMENT ON TABLE nsp_recebimentos IS
  'O encaminhamento do Núcleo à Segurança do Trabalho e à queixa técnica, com o botão Recebido do link de uso único. Issue #1996.';
COMMENT ON COLUMN nsp_recebimentos.token_hash IS
  'SHA-256 do token do link mais recente. O token em claro só existe no e-mail; cada envio troca o hash.';
COMMENT ON COLUMN nsp_recebimentos.recebido_em IS
  'Quando o setor clicou em Recebido. Preenchido uma vez só: depois dele o link recusa.';

CREATE INDEX IF NOT EXISTS idx_nsp_recebimentos_notificacao ON nsp_recebimentos (notificacao_id, enviado_em);
-- Os que ainda esperam o clique, lidos pelo reenvio a cada 10 minutos.
CREATE INDEX IF NOT EXISTS idx_nsp_recebimentos_sem_clique
  ON nsp_recebimentos (enviado_em)
  WHERE recebido_em IS NULL AND reenviado_em IS NULL;

ALTER TABLE nsp_recebimentos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nsp_recebimentos FROM anon, authenticated;

-- ---------- 3. Os marcos do e-mail ao setor e do aviso à Presidência ----------
DO $$
DECLARE
  definicao TEXT;
  marco TEXT;
BEGIN
  FOREACH marco IN ARRAY ARRAY['encaminhamento_setor', 'encaminhamento_sem_titular'] LOOP
    SELECT pg_get_constraintdef(oid) INTO definicao
      FROM pg_constraint
     WHERE conrelid = 'nsp_avisos'::regclass AND conname = 'nsp_avisos_marco_check';
    IF definicao IS NULL THEN
      RAISE EXCEPTION 'nsp_avisos_marco_check não existe: rode antes a migration 182.';
    END IF;
    IF position(quote_literal(marco) IN definicao) = 0 THEN
      EXECUTE 'ALTER TABLE nsp_avisos DROP CONSTRAINT nsp_avisos_marco_check';
      EXECUTE 'ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_marco_check '
        || replace(definicao, 'ARRAY[', 'ARRAY[' || quote_literal(marco) || '::text, ');
    END IF;
  END LOOP;
END
$$;

-- ---------- 4. O e-mail ao setor sai sem destinatario_id ----------
DO $$
DECLARE
  definicao TEXT;
BEGIN
  SELECT pg_get_constraintdef(oid) INTO definicao
    FROM pg_constraint
   WHERE conrelid = 'nsp_avisos'::regclass AND conname = 'nsp_avisos_destinatario_check';
  IF definicao IS NULL THEN
    RAISE EXCEPTION 'nsp_avisos_destinatario_check não existe: rode antes a migration 182.';
  END IF;
  IF position('''encaminhamento_setor''' IN definicao) = 0 THEN
    EXECUTE 'ALTER TABLE nsp_avisos DROP CONSTRAINT nsp_avisos_destinatario_check';
    -- `definicao` é "CHECK (<regra>)": a regra nova entra somada à antiga.
    EXECUTE 'ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_destinatario_check CHECK ('
      || substr(definicao, 7)
      || ' OR (marco = ''encaminhamento_setor'' AND caso_id IS NOT NULL))';
  END IF;
END
$$;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (220) ON CONFLICT (numero) DO NOTHING;
