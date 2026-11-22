-- =====================================================
-- Migration 219: o alerta do prazo de 72 horas (issue #2000, PRD #1979)
-- =====================================================
-- O e-mail urgente do caso A cuja notificação externa ainda está pendente
-- quando faltam menos de 24 horas para o fim do prazo legal de 72 horas nasce
-- no registro de e-mail do Núcleo (`nsp_avisos`, migrations 158 e 173), como
-- todo e-mail do módulo. O marco `prazo_de_72_horas` entra somado aos que o
-- banco já aceita, lidos da própria constraint, para não desfazer o marco que
-- outra migration da mesma fase acrescentou (o mesmo jeito da 209).
--
-- Uma linha por caso e pessoa: a chave única `uq_nsp_avisos_caso` da 173
-- (caso, marco, referência, destinatário) já segura a repetição.
--
-- Nenhuma tabela nova e nenhuma política: `nsp_avisos` segue com RLS sem
-- política, e só o backend, com a service_role, lê e grava. Rodar duas vezes
-- é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

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
  IF position('''prazo_de_72_horas''' IN definicao) = 0 THEN
    EXECUTE 'ALTER TABLE nsp_avisos DROP CONSTRAINT nsp_avisos_marco_check';
    EXECUTE 'ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_marco_check '
      || replace(definicao, 'ARRAY[', 'ARRAY[''prazo_de_72_horas''::text, ');
  END IF;
END
$$;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (219) ON CONFLICT (numero) DO NOTHING;
