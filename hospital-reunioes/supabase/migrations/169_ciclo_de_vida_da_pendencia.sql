-- =====================================================
-- Migration 169: ciclo de vida da Pendencia (ADR 0098, decisoes 4 e 5; issue #1862)
-- =====================================================
-- O banco passa a guardar quatro estados (PENDENTE, EM_PROGRESSO, CONCLUIDO,
-- CANCELADO). Atrasada e calculada (aberta com prazo vencido) e Repactuada
-- tambem (ha Repactuacao no historico); o job das 6h que gravava ATRASADO sai.
--
-- 1. `pendencias.concluida_em`: o dia em que o responsavel marcou a conclusao.
-- 2. `pendencia_historico`: so de insercao. O trigger recusa UPDATE, DELETE e
--    TRUNCATE para todo mundo, inclusive a service_role do backend (ADR 0002):
--    sem ele, qualquer rota nova poderia editar o passado.
-- 3. `registrar_acao_da_pendencia`: a gravacao. Atualiza a Pendencia e insere
--    o evento na mesma transacao. A regra (quem pode, qual transicao, se conta
--    atraso) fica no Python (`app/services/pendencia_ciclo.py`); aqui so a
--    trava de concorrencia (o estado lido tem de ser o estado atual).
-- 4. As Pendencias antigas ATRASADO ou REPACTUADA ("a repactuar", sem prazo)
--    voltam a PENDENTE com o prazo restaurado pelo quadro da Ata. Onde o
--    quadro nao da o prazo, vale a data da ultima mudanca, com um evento
--    "migracao" no historico.
-- 5. O CHECK de status fica com os quatro estados.
--
-- RLS default-deny: so o backend, com a service_role, le e grava. Nenhuma
-- policy de proposito. Rodar duas vezes e inofensivo. Aplicar a mao no Studio.
-- =====================================================

BEGIN;

-- 1. Data de conclusao ------------------------------------------------------

ALTER TABLE pendencias ADD COLUMN IF NOT EXISTS concluida_em TIMESTAMPTZ NULL;

COMMENT ON COLUMN pendencias.concluida_em IS
  'Quando o responsavel marcou a conclusao (ADR 0098). A Reabertura apaga. Issue #1862.';

-- 2. Historico da Pendencia ---------------------------------------------------

CREATE TABLE IF NOT EXISTS pendencia_historico (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_acao        VARCHAR(10) NOT NULL REFERENCES pendencias(id_acao),
  comando        TEXT NOT NULL CHECK (comando IN (
                   'iniciar', 'anotar', 'concluir', 'repactuar', 'cancelar', 'reabrir', 'migracao'
                 )),
  anotacao       TEXT NOT NULL CHECK (length(btrim(anotacao)) > 0),
  -- Sem FK: o historico nao pode depender de um cadastro que muda.
  autor_id       VARCHAR(10),
  autor_nome     TEXT NOT NULL,
  status_antes   TEXT,
  status_depois  TEXT NOT NULL,
  prazo_antes    DATE,
  prazo_depois   DATE,
  -- Repactuacao ou Reabertura feita com o prazo ja vencido (ranking).
  conta_atraso   BOOLEAN NOT NULL DEFAULT false,
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE pendencia_historico IS
  'Historico da Pendencia (ADR 0098, decisao 5): um evento por acao, com anotacao. So de insercao; o trigger recusa UPDATE, DELETE e TRUNCATE. Issue #1862.';

CREATE INDEX IF NOT EXISTS idx_pendencia_historico_acao
  ON pendencia_historico (id_acao, criado_em);

-- A Repactuada e calculada por este indice.
CREATE INDEX IF NOT EXISTS idx_pendencia_historico_repactuacao
  ON pendencia_historico (id_acao) WHERE comando = 'repactuar';

ALTER TABLE pendencia_historico ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON pendencia_historico FROM anon, authenticated;

CREATE OR REPLACE FUNCTION recusar_mudanca_no_historico_da_pendencia()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'O Historico da Pendencia so aceita insercao: % recusado (ADR 0098).', TG_OP
    USING ERRCODE = 'insufficient_privilege';
END;
$$;

DROP TRIGGER IF EXISTS pendencia_historico_sem_update ON pendencia_historico;
CREATE TRIGGER pendencia_historico_sem_update
  BEFORE UPDATE ON pendencia_historico
  FOR EACH ROW EXECUTE FUNCTION recusar_mudanca_no_historico_da_pendencia();

DROP TRIGGER IF EXISTS pendencia_historico_sem_delete ON pendencia_historico;
CREATE TRIGGER pendencia_historico_sem_delete
  BEFORE DELETE ON pendencia_historico
  FOR EACH ROW EXECUTE FUNCTION recusar_mudanca_no_historico_da_pendencia();

DROP TRIGGER IF EXISTS pendencia_historico_sem_truncate ON pendencia_historico;
CREATE TRIGGER pendencia_historico_sem_truncate
  BEFORE TRUNCATE ON pendencia_historico
  FOR EACH STATEMENT EXECUTE FUNCTION recusar_mudanca_no_historico_da_pendencia();

-- 3. A gravacao de uma acao ----------------------------------------------------
-- PT404 e PT409 viram 404 e 409 no PostgREST.

CREATE OR REPLACE FUNCTION registrar_acao_da_pendencia(
  p_id_acao          VARCHAR,
  p_comando          TEXT,
  p_anotacao         TEXT,
  p_autor_id         VARCHAR,
  p_autor_nome       TEXT,
  p_status_esperado  TEXT,
  p_status_novo      TEXT,
  p_prazo_novo       DATE,
  p_concluida        BOOLEAN,
  p_conta_atraso     BOOLEAN
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
  v_atual   pendencias%ROWTYPE;
  v_evento  BIGINT;
BEGIN
  SELECT * INTO v_atual
    FROM pendencias
   WHERE id_acao = p_id_acao AND deleted_at IS NULL
   FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Pendencia % nao encontrada.', p_id_acao USING ERRCODE = 'PT404';
  END IF;
  IF v_atual.status IS DISTINCT FROM p_status_esperado THEN
    RAISE EXCEPTION 'A pendencia mudou enquanto a acao era feita. Recarregue e tente de novo.'
      USING ERRCODE = 'PT409';
  END IF;

  UPDATE pendencias
     SET status = p_status_novo,
         prazo = COALESCE(p_prazo_novo, prazo),
         concluida_em = CASE
           WHEN p_concluida IS TRUE THEN now()
           WHEN p_concluida IS FALSE THEN NULL
           ELSE concluida_em
         END
   WHERE id_acao = p_id_acao;

  INSERT INTO pendencia_historico (
    id_acao, comando, anotacao, autor_id, autor_nome,
    status_antes, status_depois, prazo_antes, prazo_depois, conta_atraso
  ) VALUES (
    p_id_acao, p_comando, p_anotacao, p_autor_id, p_autor_nome,
    v_atual.status, p_status_novo, v_atual.prazo, COALESCE(p_prazo_novo, v_atual.prazo),
    COALESCE(p_conta_atraso, false)
  )
  RETURNING id INTO v_evento;

  IF v_atual.id_reuniao IS NOT NULL THEN
    IF p_status_novo = 'CONCLUIDO' AND v_atual.status <> 'CONCLUIDO' THEN
      UPDATE reunioes SET acoes_concluidas = COALESCE(acoes_concluidas, 0) + 1
       WHERE id_reuniao = v_atual.id_reuniao;
    ELSIF v_atual.status = 'CONCLUIDO' AND p_status_novo <> 'CONCLUIDO' THEN
      UPDATE reunioes SET acoes_concluidas = GREATEST(COALESCE(acoes_concluidas, 0) - 1, 0)
       WHERE id_reuniao = v_atual.id_reuniao;
    END IF;
  END IF;

  RETURN v_evento;
END;
$$;

REVOKE EXECUTE ON FUNCTION registrar_acao_da_pendencia(VARCHAR, TEXT, TEXT, VARCHAR, TEXT, TEXT, TEXT, DATE, BOOLEAN, BOOLEAN)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION registrar_acao_da_pendencia(VARCHAR, TEXT, TEXT, VARCHAR, TEXT, TEXT, TEXT, DATE, BOOLEAN, BOOLEAN)
  TO service_role;

REVOKE EXECUTE ON FUNCTION recusar_mudanca_no_historico_da_pendencia()
  FROM PUBLIC, anon, authenticated;

-- 4. As Pendencias antigas ATRASADO e REPACTUADA ------------------------------
-- O prazo vem da linha do quadro da Ata: pela posicao (`quadro_pos`) e, na
-- Pendencia de antes da posicao, pelo texto da acao, se so uma linha casa.
-- Formatos aceitos: AAAA-MM-DD e DD/MM/AAAA (os de `_normalizar_prazo`).

DO $$
DECLARE
  r              RECORD;
  v_quadro       JSONB;
  v_linha        JSONB;
  v_bruto        TEXT;
  v_partes       TEXT[];
  v_prazo        DATE;
  v_pela_mudanca BOOLEAN;
BEGIN
  FOR r IN
    SELECT p.id_acao, p.status, p.prazo, p.quadro_pos, p.descricao_acao, p.updated_at, re.json_ata
      FROM pendencias p
      LEFT JOIN reunioes re ON re.id_reuniao = p.id_reuniao
     WHERE p.status IN ('ATRASADO', 'REPACTUADA')
  LOOP
    v_prazo := r.prazo;
    v_pela_mudanca := false;

    IF v_prazo IS NULL THEN
      v_quadro := COALESCE(
        NULLIF(r.json_ata -> 'quadro_atribuicoes', 'null'::jsonb),
        NULLIF(r.json_ata -> 'atribuicoes', 'null'::jsonb),
        NULLIF(r.json_ata -> 'acoes', 'null'::jsonb)
      );
      v_linha := NULL;
      IF jsonb_typeof(v_quadro) = 'array' THEN
        IF r.quadro_pos IS NOT NULL THEN
          v_linha := v_quadro -> r.quadro_pos;
        ELSE
          SELECT CASE WHEN count(*) = 1 THEN min(elem::text)::jsonb END INTO v_linha
            FROM jsonb_array_elements(v_quadro) AS elem
           WHERE btrim(COALESCE(elem ->> 'acao', elem ->> 'descricao_acao', '')) = btrim(r.descricao_acao);
        END IF;
      END IF;

      v_bruto := btrim(COALESCE(v_linha ->> 'prazo', ''));
      BEGIN
        IF v_bruto ~ '^\d{4}-\d{2}-\d{2}$' THEN
          v_prazo := v_bruto::date;
        ELSIF v_bruto ~ '^\d{1,2}[/-]\d{1,2}[/-]\d{4}$' THEN
          v_partes := regexp_match(v_bruto, '^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$');
          v_prazo := make_date(v_partes[3]::int, v_partes[2]::int, v_partes[1]::int);
        END IF;
      EXCEPTION WHEN others THEN
        v_prazo := NULL;
      END;

      IF v_prazo IS NULL THEN
        v_prazo := (COALESCE(r.updated_at, now()) AT TIME ZONE 'America/Sao_Paulo')::date;
        v_pela_mudanca := true;
      END IF;
    END IF;

    UPDATE pendencias SET status = 'PENDENTE', prazo = v_prazo WHERE id_acao = r.id_acao;

    IF v_pela_mudanca THEN
      INSERT INTO pendencia_historico (
        id_acao, comando, anotacao, autor_id, autor_nome,
        status_antes, status_depois, prazo_antes, prazo_depois, conta_atraso
      ) VALUES (
        r.id_acao, 'migracao',
        'O quadro da Ata nao tinha o prazo desta pendencia. Vale a data da ultima mudanca, '
          || to_char(v_prazo, 'DD/MM/YYYY') || '.',
        NULL, 'Sistema',
        r.status, 'PENDENTE', NULL, v_prazo, false
      );
    END IF;
  END LOOP;
END;
$$;

-- 5. Quatro estados gravados --------------------------------------------------

ALTER TABLE pendencias DROP CONSTRAINT IF EXISTS pendencias_status_check;
ALTER TABLE pendencias ADD CONSTRAINT pendencias_status_check
  CHECK (status IN ('PENDENTE', 'EM_PROGRESSO', 'CONCLUIDO', 'CANCELADO'));

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (169) ON CONFLICT (numero) DO NOTHING;
