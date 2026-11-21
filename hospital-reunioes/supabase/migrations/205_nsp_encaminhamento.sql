-- =====================================================
-- Migration 205: encaminhar da tela de triagem do Núcleo
-- (issue #1995, PRD #1979, ADR 0095 decisão 11 e ADR 0107 decisão 8)
-- =====================================================
-- O que entra:
--   1. `nsp_encaminhamentos`: cada encaminhamento que a Presidência faz na
--      triagem, com os destinos (Núcleo, Ouvidoria, Canal de Conduta, fora
--      de escopo), o motivo em uma frase e, no fora de escopo, a orientação
--      que quem notificou vê na página de acompanhamento. O protocolo do caso
--      não muda: o encaminhamento aponta para a notificação;
--   2. o registro de e-mail do Núcleo (`nsp_avisos`) ganha o marco
--      `encaminhamento_ouvidoria`: o e-mail ao ouvidor, com protocolo, motivo
--      e relato. O marco entra somado aos que o banco já aceita, lidos da
--      própria constraint, para não desfazer o marco que outra migration da
--      mesma leva tenha somado antes.
--
-- Nada do caso vai para o Canal de Conduta: a tela só orienta.
--
-- Nenhuma pessoa entra por aqui. RLS ligado e sem política na tabela nova:
-- só o backend, com a service_role, lê e grava. Rodar duas vezes é
-- inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. Os encaminhamentos ----------
CREATE TABLE IF NOT EXISTS nsp_encaminhamentos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  notificacao_id  UUID NOT NULL REFERENCES nsp_notificacoes(id) ON DELETE RESTRICT,
  destinos        TEXT[] NOT NULL CHECK (
                    cardinality(destinos) >= 1
                    AND destinos <@ ARRAY['nucleo', 'ouvidoria', 'canal_de_conduta', 'fora_de_escopo']::TEXT[]
                    AND (NOT ('fora_de_escopo' = ANY (destinos)) OR cardinality(destinos) = 1)
                  ),
  motivo          TEXT NOT NULL CHECK (char_length(btrim(motivo)) BETWEEN 1 AND 300),
  orientacao      TEXT CHECK (orientacao IS NULL OR char_length(btrim(orientacao)) BETWEEN 1 AND 300),
  autor_id        VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (('fora_de_escopo' = ANY (destinos)) = (orientacao IS NOT NULL))
);

COMMENT ON TABLE nsp_encaminhamentos IS
  'Os encaminhamentos da triagem do Núcleo: destinos, motivo em uma frase e, no fora de escopo, a orientação a quem notificou. Issue #1995.';
COMMENT ON COLUMN nsp_encaminhamentos.orientacao IS
  'Só no fora de escopo: a frase que quem notificou vê na página de acompanhamento. O motivo fica no Núcleo.';

CREATE INDEX IF NOT EXISTS idx_nsp_encaminhamentos_notificacao ON nsp_encaminhamentos (notificacao_id, criado_em);
CREATE INDEX IF NOT EXISTS idx_nsp_encaminhamentos_autor ON nsp_encaminhamentos (autor_id);

ALTER TABLE nsp_encaminhamentos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nsp_encaminhamentos FROM anon, authenticated;

-- ---------- 2. O marco do e-mail ao ouvidor ----------
DO $$
DECLARE
  definicao TEXT;
BEGIN
  SELECT pg_get_constraintdef(oid) INTO definicao
    FROM pg_constraint
   WHERE conrelid = 'nsp_avisos'::regclass AND conname = 'nsp_avisos_marco_check';
  IF definicao IS NULL THEN
    RAISE EXCEPTION 'nsp_avisos_marco_check não existe: rode antes a migration 182.';
  END IF;
  IF position('''encaminhamento_ouvidoria''' IN definicao) = 0 THEN
    EXECUTE 'ALTER TABLE nsp_avisos DROP CONSTRAINT nsp_avisos_marco_check';
    EXECUTE 'ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_marco_check '
      || replace(definicao, 'ARRAY[', 'ARRAY[''encaminhamento_ouvidoria''::text, ');
  END IF;
END
$$;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (205) ON CONFLICT (numero) DO NOTHING;
