-- =====================================================
-- Migration 200: Canal de Conduta, o agente de triagem
-- (issue #1827, PRD #1786, ADR 0097, decisões 6, 7 e 15; especificação,
-- seções 6.1 e 11 e Anexo A)
-- =====================================================
-- O que entra:
--   1. a leitura do agente, uma por caso: a sugestão cifrada, ou o motivo de
--      o caso ter ficado para triagem manual (desligado, fora do ar, teto do
--      dia ou resposta fora do formato);
--   2. a resposta da coordenação a cada item da sugestão: confirmo ou
--      discordo, e o motivo da discordância, cifrado. Uma resposta por item;
--   3. a cota diária do agente do Canal, à parte da Ouvidoria e do Núcleo:
--      `conduta_agente_reservar_chamada` soma uma chamada ao dia corrente
--      (fuso do hospital) só se ainda houver vaga, num comando só.
--
-- RLS default-deny em toda tabela nova: só o backend, com a service_role, lê
-- e grava. Nenhuma policy de propósito. A função da cota só pode ser chamada
-- pela service_role. Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. A leitura do agente ----------
CREATE TABLE IF NOT EXISTS conduta_sugestoes (
  caso_id           UUID PRIMARY KEY REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  situacao          TEXT NOT NULL CHECK (situacao IN ('sugerida', 'manual')),
  motivo_manual     TEXT CHECK (motivo_manual IN ('desligado', 'agente_fora', 'teto', 'validacao')),
  sugestao_cifrada  TEXT CHECK (sugestao_cifrada IS NULL OR sugestao_cifrada LIKE 'v1:%'),
  modelo            TEXT NOT NULL,
  prompt_versao     TEXT NOT NULL,
  criada_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT conduta_sugestoes_leitura_check CHECK (
    (situacao = 'sugerida' AND sugestao_cifrada IS NOT NULL AND motivo_manual IS NULL)
    OR (situacao = 'manual' AND sugestao_cifrada IS NULL AND motivo_manual IS NOT NULL)
  )
);

COMMENT ON TABLE conduta_sugestoes IS
  'A leitura do agente de triagem do Canal de Conduta, uma por caso (ADR 0097, decisão 6). A sugestão é cifrada pela aplicação. Issue #1827.';
COMMENT ON COLUMN conduta_sugestoes.motivo_manual IS
  'Por que o caso ficou sem sugestão: desligado, agente_fora, teto (cota do dia) ou validacao (resposta fora do formato).';

ALTER TABLE conduta_sugestoes ENABLE ROW LEVEL SECURITY;

-- ---------- 2. A resposta da coordenação, item a item ----------
CREATE TABLE IF NOT EXISTS conduta_sugestao_respostas (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id          UUID NOT NULL REFERENCES conduta_sugestoes(caso_id) ON DELETE RESTRICT,
  item             TEXT NOT NULL CHECK (item IN (
                     'escopo', 'categoria', 'rito', 'especial', 'risco_imediato', 'assunto_para_lista',
                     'resumo', 'lacunas', 'perguntas_ao_denunciante', 'casos_parecidos',
                     'relatos_repetidos_improcedentes', 'sinalizar_nsp', 'confianca')),
  resposta         TEXT NOT NULL CHECK (resposta IN ('confirmo', 'discordo')),
  motivo_cifrado   TEXT CHECK (motivo_cifrado IS NULL OR motivo_cifrado LIKE 'v1:%'),
  autor_id         VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  respondida_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, item),
  CONSTRAINT conduta_sugestao_respostas_motivo_check CHECK (resposta = 'confirmo' OR motivo_cifrado IS NOT NULL)
);

COMMENT ON TABLE conduta_sugestao_respostas IS
  'A coordenação confirma ou discorda de cada item da sugestão do agente; a discordância leva o motivo, cifrado (especificação, seções 6.1 e 11). Issue #1827.';

CREATE INDEX IF NOT EXISTS idx_conduta_sugestao_respostas_autor ON conduta_sugestao_respostas (autor_id);

ALTER TABLE conduta_sugestao_respostas ENABLE ROW LEVEL SECURITY;

-- ---------- 3. A cota diária do agente do Canal ----------
CREATE TABLE IF NOT EXISTS conduta_agente_cota (
  dia       DATE PRIMARY KEY,
  chamadas  INTEGER NOT NULL DEFAULT 0 CHECK (chamadas >= 0)
);

ALTER TABLE conduta_agente_cota ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE conduta_agente_cota IS
  'Quantas leituras o agente de triagem do Canal de Conduta fez em cada dia, à parte da Ouvidoria e do Núcleo (ADR 0097, decisão 6). Só o backend lê e escreve.';

CREATE OR REPLACE FUNCTION conduta_agente_reservar_chamada(p_teto INTEGER)
RETURNS TABLE (reservada BOOLEAN)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_dia DATE := (now() AT TIME ZONE 'America/Sao_Paulo')::date;
BEGIN
  INSERT INTO conduta_agente_cota AS cota (dia, chamadas)
  VALUES (v_dia, 1)
  ON CONFLICT (dia) DO UPDATE
    SET chamadas = cota.chamadas + 1
    WHERE cota.chamadas < p_teto;
  -- FOUND é falso quando o WHERE do ON CONFLICT barrou a soma: o teto do dia.
  reservada := FOUND AND p_teto > 0;
  RETURN NEXT;
END;
$$;

REVOKE EXECUTE ON FUNCTION conduta_agente_reservar_chamada(INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION conduta_agente_reservar_chamada(INTEGER) TO service_role;

COMMENT ON FUNCTION conduta_agente_reservar_chamada(INTEGER) IS
  'Reserva uma leitura do agente de triagem do Canal de Conduta no dia corrente, se a cota do dia ainda tem vaga. Devolve reservada = false no teto.';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (200) ON CONFLICT (numero) DO NOTHING;
