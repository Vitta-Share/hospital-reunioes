-- =====================================================
-- Migration 190: o fluxo continuo antigo vira Rotina (ADR 0098, decisao 9; issue #1877)
-- =====================================================
-- Item 15 do Refino da #1757. A Pendencia aberta (PENDENTE ou EM_PROGRESSO),
-- viva e sem prazo cuja linha no quadro da Ata diz "Fluxo continuo" vira
-- Rotina sem frequencia: o Facilitador escolhe a frequencia na Minha Fila, e
-- ate la nenhuma Verificacao existe. A Pendencia e encerrada (CANCELADO) com
-- um evento "migracao" no Historico que aponta para a Rotina.
--
-- 1. `pendencia_historico.rotina_id`: o evento aponta para a Rotina.
-- 2. A conversao. A linha do quadro vem pela posicao (`quadro_pos`) e, na
--    Pendencia de antes da posicao, pelo texto da acao, se so uma linha casa
--    (a mesma regra da 169). Se a Rotina daquela posicao ja existe (nasceu do
--    envio da Ata), a Pendencia aponta para ela.
--
-- A sem prazo que nao casa continua Pendencia e aparece na tela de acertos
-- do Super admin. Sem tabela nova: o RLS default-deny da 169 e da 177
-- continua valendo. Rodar duas vezes e inofensivo: a Pendencia convertida ja
-- esta encerrada e a Rotina e unica por (id_reuniao, quadro_pos). Aplicar a
-- mao no Studio, depois da 177.
-- =====================================================

BEGIN;

-- 1. O evento aponta para a Rotina ------------------------------------------------

ALTER TABLE pendencia_historico
  ADD COLUMN IF NOT EXISTS rotina_id UUID NULL REFERENCES rotinas(id) ON DELETE RESTRICT;

COMMENT ON COLUMN pendencia_historico.rotina_id IS
  'A Rotina em que a Pendencia de fluxo continuo virou (issue #1877).';

CREATE INDEX IF NOT EXISTS idx_pendencia_historico_rotina
  ON pendencia_historico (rotina_id) WHERE rotina_id IS NOT NULL;

-- 2. A conversao -------------------------------------------------------------------

DO $$
DECLARE
  r         RECORD;
  v_quadro  JSONB;
  v_pos     INTEGER;
  v_prazo   TEXT;
  v_rotina  UUID;
BEGIN
  FOR r IN
    SELECT p.id_acao, p.id_reuniao, p.status, p.quadro_pos, p.descricao_acao,
           p.responsavel_id, COALESCE(NULLIF(btrim(p.responsavel_nome), ''), pa.nome_completo, '') AS responsavel_nome,
           re.json_ata
      FROM pendencias p
      JOIN reunioes re ON re.id_reuniao = p.id_reuniao AND re.deleted_at IS NULL
      LEFT JOIN participantes pa ON pa.id = p.responsavel_id
     WHERE p.deleted_at IS NULL
       AND p.prazo IS NULL
       AND p.status IN ('PENDENTE', 'EM_PROGRESSO')
     ORDER BY p.id_acao
  LOOP
    v_quadro := COALESCE(
      NULLIF(r.json_ata -> 'quadro_atribuicoes', 'null'::jsonb),
      NULLIF(r.json_ata -> 'atribuicoes', 'null'::jsonb),
      NULLIF(r.json_ata -> 'acoes', 'null'::jsonb)
    );
    CONTINUE WHEN jsonb_typeof(v_quadro) IS DISTINCT FROM 'array';

    v_pos := r.quadro_pos;
    IF v_pos IS NULL THEN
      SELECT CASE WHEN count(*) = 1 THEN (min(ordem) - 1)::int END INTO v_pos
        FROM jsonb_array_elements(v_quadro) WITH ORDINALITY AS e(elem, ordem)
       WHERE btrim(COALESCE(elem ->> 'acao', elem ->> 'descricao_acao', '')) = btrim(r.descricao_acao);
    END IF;
    CONTINUE WHEN v_pos IS NULL;

    v_prazo := translate(
      regexp_replace(lower(btrim(COALESCE(v_quadro -> v_pos ->> 'prazo', ''))), '\s+', ' ', 'g'),
      'íúÍÚ', 'iuiu'
    );
    CONTINUE WHEN v_prazo <> 'fluxo continuo';

    INSERT INTO rotinas (
      id_reuniao, quadro_pos, descricao, responsavel_id, responsavel_nome, frequencia, comeca_em, status
    ) VALUES (
      r.id_reuniao, v_pos, COALESCE(NULLIF(btrim(r.descricao_acao), ''), 'Rotina sem descrição'),
      r.responsavel_id, r.responsavel_nome, NULL, NULL, 'ATIVA'
    )
    ON CONFLICT (id_reuniao, quadro_pos) DO NOTHING;

    SELECT id INTO v_rotina FROM rotinas WHERE id_reuniao = r.id_reuniao AND quadro_pos = v_pos;

    UPDATE pendencias SET status = 'CANCELADO' WHERE id_acao = r.id_acao;

    INSERT INTO pendencia_historico (
      id_acao, comando, anotacao, autor_id, autor_nome,
      status_antes, status_depois, prazo_antes, prazo_depois, conta_atraso, rotina_id
    ) VALUES (
      r.id_acao, 'migracao',
      'O fluxo contínuo virou Rotina, na tela das Rotinas. Esta pendência foi encerrada, '
        || 'e o facilitador da reunião escolhe a frequência da Rotina na Minha Fila.',
      NULL, 'Sistema',
      r.status, 'CANCELADO', NULL, NULL, false, v_rotina
    );
  END LOOP;
END;
$$;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (190) ON CONFLICT (numero) DO NOTHING;
