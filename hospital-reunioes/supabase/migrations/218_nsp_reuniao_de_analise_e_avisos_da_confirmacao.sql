-- =====================================================
-- Migration 218: a reunião de análise e os avisos da confirmação da triagem
-- (issue #1994, PRD #1979, ADR 0107 decisão 1)
-- =====================================================
-- O que entra:
--   1. o registro de e-mail do Núcleo (`nsp_avisos`) ganha dois marcos:
--      `comunicacao_a_direcao` (o aviso urgente à Diretoria nas faixas A e
--      B) e `caso_em_analise` (o aviso a quem notificou e se identificou com
--      e-mail). Os marcos entram somados aos que o banco já aceita, lidos da
--      própria constraint, para não desfazer o marco que outra migration da
--      mesma leva tenha somado antes;
--   2. o aviso de caso em análise vai a quem notificou, que não precisa ter
--      cadastro: como a confirmação de recebimento, fica sem destinatário e
--      com o caso. A chave única de uma confirmação por caso (182) passa a
--      valer para ele também;
--   3. `reunioes.nsp_caso_id`: a reunião de análise de evento que nasce da
--      confirmação aponta para o caso, uma por caso. A confirmação repetida
--      encontra a reunião que já existe e não cria outra.
--
-- Nenhuma tabela nova: as duas já têm RLS ligado. Rodar duas vezes é
-- inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. Os marcos da confirmação ----------
DO $$
DECLARE
  definicao TEXT;
  marco TEXT;
BEGIN
  FOREACH marco IN ARRAY ARRAY['comunicacao_a_direcao', 'caso_em_analise'] LOOP
    SELECT pg_get_constraintdef(oid) INTO definicao
      FROM pg_constraint
     WHERE conrelid = 'nsp_avisos'::regclass AND conname = 'nsp_avisos_marco_check';
    IF definicao IS NULL THEN
      RAISE EXCEPTION 'nsp_avisos_marco_check não existe: rode antes a migration 182.';
    END IF;
    IF position('''' || marco || '''' IN definicao) = 0 THEN
      EXECUTE 'ALTER TABLE nsp_avisos DROP CONSTRAINT nsp_avisos_marco_check';
      EXECUTE 'ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_marco_check '
        || replace(definicao, 'ARRAY[', 'ARRAY[''' || marco || '''::text, ');
    END IF;
  END LOOP;
END
$$;

-- ---------- 2. O aviso de caso em análise vai a quem notificou ----------
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
  IF position('''caso_em_analise''' IN definicao) = 0 THEN
    IF position('ARRAY[' IN definicao) > 0 THEN
      -- Outra migration da leva já trocou a igualdade por uma lista.
      definicao := replace(definicao, 'ARRAY[', 'ARRAY[''caso_em_analise''::text, ');
    ELSIF position('(marco = ''confirmacao_de_recebimento''::text)' IN definicao) > 0 THEN
      definicao := replace(
        definicao,
        '(marco = ''confirmacao_de_recebimento''::text)',
        '(marco = ANY (ARRAY[''caso_em_analise''::text, ''confirmacao_de_recebimento''::text]))'
      );
    ELSE
      RAISE EXCEPTION 'nsp_avisos_destinatario_check em forma inesperada: %', definicao;
    END IF;
    EXECUTE 'ALTER TABLE nsp_avisos DROP CONSTRAINT nsp_avisos_destinatario_check';
    EXECUTE 'ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_destinatario_check ' || definicao;
  END IF;
END
$$;

COMMENT ON COLUMN nsp_avisos.destinatario_id IS
  'Quem recebe o e-mail. Vazio só na confirmação de recebimento e no aviso de caso em análise: o endereço sai da notificação (caso_id) na hora do envio.';

-- ---------- 3. Uma reunião de análise por caso ----------
ALTER TABLE reunioes
  ADD COLUMN IF NOT EXISTS nsp_caso_id UUID REFERENCES nsp_notificacoes(id) ON DELETE RESTRICT;

COMMENT ON COLUMN reunioes.nsp_caso_id IS
  'A reunião de análise de evento do Núcleo que a confirmação da triagem criou para o caso: uma por caso. Issue #1994.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_reunioes_nsp_caso
  ON reunioes (nsp_caso_id) WHERE nsp_caso_id IS NOT NULL;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (218) ON CONFLICT (numero) DO NOTHING;
