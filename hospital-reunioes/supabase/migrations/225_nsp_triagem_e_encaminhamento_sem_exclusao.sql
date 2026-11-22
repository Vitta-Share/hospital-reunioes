-- =====================================================
-- Migration 225: a triagem e o encaminhamento não se apagam
-- (issue #2153, PRD #1979)
-- =====================================================
-- O PRD promete que nenhum perfil exclui notificação, triagem nem
-- encaminhamento, e que um trigger bloqueia o DELETE. Só `nsp_notificacoes`
-- tinha o trigger (migration 174). `nsp_triagens` (188) e
-- `nsp_encaminhamentos` (209) têm RLS e REVOKE para anon e authenticated, mas
-- a service role apagava sem barreira. Aqui as duas ganham o mesmo trigger da
-- notificação: uma função e um trigger por tabela, BEFORE DELETE FOR EACH ROW.
--
-- Fora daqui: UPDATE e TRUNCATE nessas tabelas.
-- Nenhum código do backend apaga linha dessas tabelas, então nada quebra.
-- =====================================================

BEGIN;

-- ---------- 1. A triagem não se apaga ----------
CREATE OR REPLACE FUNCTION nsp_triagens_sem_exclusao() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Triagem de incidente não se apaga: ela fica no histórico da notificação'
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_triagens_sem_exclusao ON nsp_triagens;
CREATE TRIGGER trg_nsp_triagens_sem_exclusao
  BEFORE DELETE ON nsp_triagens
  FOR EACH ROW EXECUTE FUNCTION nsp_triagens_sem_exclusao();

-- ---------- 2. O encaminhamento não se apaga ----------
CREATE OR REPLACE FUNCTION nsp_encaminhamentos_sem_exclusao() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Encaminhamento de incidente não se apaga: ele fica no histórico da notificação'
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_encaminhamentos_sem_exclusao ON nsp_encaminhamentos;
CREATE TRIGGER trg_nsp_encaminhamentos_sem_exclusao
  BEFORE DELETE ON nsp_encaminhamentos
  FOR EACH ROW EXECUTE FUNCTION nsp_encaminhamentos_sem_exclusao();

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (225) ON CONFLICT (numero) DO NOTHING;
