-- =====================================================
-- Migration 154: Segurança do Paciente, a reunião rápida de segurança
-- (issue #1777, PRD #1764, ADR 0095)
-- =====================================================
-- O que entra:
--   1. o registro curto da reunião rápida (`nsp_reunioes_rapidas`): data,
--      setor, participantes e um texto de até três linhas. Fica fora da
--      tabela `reunioes` de propósito: nada do pipeline da ata (transcrição,
--      ata, envelope de assinatura, quórum) a alcança;
--   2. o texto com no máximo três linhas e 500 caracteres, a mesma regra que
--      o backend aplica antes de gravar.
--
-- RLS default-deny na tabela nova (padrão da casa): quem lê e escreve é o
-- backend com a service_role, que aplica o sigilo do Núcleo. Nenhuma policy
-- de propósito. Nenhum dado de pessoa entra aqui.
--
-- Tudo com IF NOT EXISTS: rodar duas vezes é inofensivo.
-- Aplicar à mão no Studio: o deploy não aplica SQL.
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS nsp_reunioes_rapidas (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  colegiado_id  UUID NOT NULL REFERENCES colegiados(id) ON DELETE RESTRICT,
  data          DATE NOT NULL,
  setor         TEXT NOT NULL CHECK (char_length(btrim(setor)) BETWEEN 1 AND 120),
  participantes VARCHAR(10)[] NOT NULL CHECK (cardinality(participantes) BETWEEN 1 AND 50),
  texto         TEXT NOT NULL CHECK (
    char_length(btrim(texto)) BETWEEN 1 AND 500
    AND cardinality(string_to_array(texto, E'\n')) <= 3
  ),
  criada_por    VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE nsp_reunioes_rapidas IS
  'Reunião rápida de segurança do Núcleo (issue #1777): registro de três linhas, sem transcrição, ata, assinatura nem quórum. Só o backend lê, com o sigilo do Núcleo.';
COMMENT ON COLUMN nsp_reunioes_rapidas.participantes IS
  'Ids de `participantes` de quem estava na conversa. Não conta quórum.';

CREATE INDEX IF NOT EXISTS idx_nsp_reunioes_rapidas_colegiado_data
  ON nsp_reunioes_rapidas(colegiado_id, data);

ALTER TABLE nsp_reunioes_rapidas ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (154) ON CONFLICT (numero) DO NOTHING;
