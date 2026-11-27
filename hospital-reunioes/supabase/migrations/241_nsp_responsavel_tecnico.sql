-- =====================================================
-- Migration 241: a marca de Responsável técnico no cadastro
-- (issue #2248, PRD #2247, ADR 0112)
-- =====================================================
-- O que entra:
--   1. `participantes.responsavel_tecnico`: quem responde pelo hospital, falso
--      por padrão. O índice único parcial sobre as linhas marcadas deixa o
--      banco garantir uma pessoa só;
--   2. a função `trocar_responsavel_tecnico`, que numa só transação desmarca
--      quem estava e marca a nova pessoa (ou só desmarca). Devolve o id de
--      quem perdeu a marca para outra pessoa, para a auditoria do backend;
--   3. o CHECK da qualidade em `nsp_documentos_signatarios` passa a aceitar
--      `responsavel_tecnico`, mantendo `diretoria_executiva` (as linhas
--      antigas) e `presidencia`.
--
-- Nenhuma pessoa entra por aqui (decisão 12 da Fase 1): o Super admin marca
-- pelo cadastro de usuários. RLS segue como está (tabelas já existentes).
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. A marca ----------
ALTER TABLE participantes
  ADD COLUMN IF NOT EXISTS responsavel_tecnico BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN participantes.responsavel_tecnico IS
  'O Responsável técnico do hospital (issue #2248, ADR 0112): assina pela Direção os documentos do Núcleo de Segurança do Paciente. Uma pessoa só por vez; troca pela função trocar_responsavel_tecnico.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_participantes_responsavel_tecnico
  ON participantes (responsavel_tecnico)
  WHERE responsavel_tecnico;

-- ---------- 2. A troca ----------
-- A trava serializa duas trocas ao mesmo tempo: sem ela, as duas desmarcariam
-- a mesma anterior e a segunda bateria no índice único.
CREATE OR REPLACE FUNCTION trocar_responsavel_tecnico(
  p_participante_id VARCHAR(10),
  p_marcar          BOOLEAN
) RETURNS VARCHAR(10)
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  v_anterior VARCHAR(10);
BEGIN
  PERFORM pg_advisory_xact_lock(hashtext('responsavel_tecnico'));

  IF p_marcar THEN
    UPDATE participantes SET responsavel_tecnico = false
     WHERE responsavel_tecnico AND id <> p_participante_id
    RETURNING id INTO v_anterior;
  END IF;

  UPDATE participantes SET responsavel_tecnico = p_marcar
   WHERE id = p_participante_id;

  RETURN v_anterior;
END;
$$;

-- A troca é do backend, nunca da anon_key do bundle. `PUBLIC` na frente
-- porque o Postgres concede EXECUTE a PUBLIC quando a função nasce.
REVOKE EXECUTE ON FUNCTION trocar_responsavel_tecnico(VARCHAR, BOOLEAN)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION trocar_responsavel_tecnico(VARCHAR, BOOLEAN) TO service_role;

-- ---------- 3. A qualidade de quem assina ----------
ALTER TABLE nsp_documentos_signatarios
  DROP CONSTRAINT IF EXISTS nsp_documentos_signatarios_qualidade_check;
ALTER TABLE nsp_documentos_signatarios
  ADD CONSTRAINT nsp_documentos_signatarios_qualidade_check
  CHECK (qualidade IN ('diretoria_executiva', 'presidencia', 'responsavel_tecnico'));

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (241) ON CONFLICT (numero) DO NOTHING;
