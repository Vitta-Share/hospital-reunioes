-- =====================================================
-- Migration 228: Segurança do Paciente, a formação do instrutor na capacitação
-- (issue #1927, PRD #1764, ADR 0095)
-- =====================================================
-- O caderno nº 6 da ANVISA (3ª ed., 2025, item 2.5.2.3) pede que o
-- comprovante de capacitação traga o nome e a formação do instrutor. A
-- capacitação guardava só o nome (migration 155).
--
-- A coluna nova é nula: as capacitações já cadastradas ficam como estão e a
-- tela mostra "Formação não informada". Quem exige a formação na capacitação
-- nova é o backend. Preenchida, vai de 1 a 200 caracteres, como o nome do
-- instrutor.
--
-- Nenhuma linha existente muda. A tabela já tem RLS ligado e nenhuma policy
-- (migration 155); a coluna nova herda isso.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

ALTER TABLE nsp_capacitacoes
  ADD COLUMN IF NOT EXISTS instrutor_formacao TEXT
    CHECK (instrutor_formacao IS NULL OR char_length(btrim(instrutor_formacao)) BETWEEN 1 AND 200);

COMMENT ON COLUMN nsp_capacitacoes.instrutor_formacao IS
  'Formação de quem deu a capacitação (issue #1927). Nula nas capacitações cadastradas antes da migration 228.';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (228) ON CONFLICT (numero) DO NOTHING;
