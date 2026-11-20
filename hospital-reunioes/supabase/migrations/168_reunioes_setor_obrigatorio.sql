-- =====================================================
-- Migration 168: o setor da Reunião aponta para a tabela de setores
--
-- A coluna TEXT `reunioes.setor` existe desde a 002 e nenhum código grava
-- nela. Esta migration dá à Reunião o mesmo par que o Colaborador ganhou na
-- 028: `setor_id` como FK para `setores`, com a TEXT mantida em sincronia.
-- O agendamento passa a exigir o setor (a API recusa sem ele); por isso a
-- coluna fica NULA no banco: as Reuniões antigas sem setor continuam válidas,
-- e o Super admin as acerta pela tela de acertos.
--
-- Backfill: a Reunião antiga que por acaso tem a TEXT preenchida ganha o
-- `setor_id` casando por `lower(trim(nome))`, como a 028 fez com o Colaborador.
--
-- RLS: nenhuma tabela nova; `reunioes` e `setores` já têm RLS (tudo passa pelo
-- backend com service_role).
--
-- Reversível via: DROP INDEX idx_reunioes_setor_id; ALTER TABLE reunioes
-- DROP COLUMN setor_id. A TEXT preserva o nome.
-- =====================================================

ALTER TABLE reunioes
  ADD COLUMN IF NOT EXISTS setor_id UUID REFERENCES setores(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_reunioes_setor_id ON reunioes(setor_id);

UPDATE reunioes r
SET setor_id = s.id
FROM setores s
WHERE r.setor IS NOT NULL
  AND lower(trim(r.setor)) = lower(s.nome)
  AND r.setor_id IS NULL;

COMMENT ON COLUMN reunioes.setor_id IS
  'FK para setores.id, obrigatório no agendamento e nulo nas Reuniões antigas. Mantido em sincronia com a coluna TEXT setor.';


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (168) ON CONFLICT (numero) DO NOTHING;
