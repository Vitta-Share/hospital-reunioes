-- =====================================================
-- Migration 167: o Registro de acesso
-- (issue #1941, PRD #1932, ADR 0104, decisao 10)
-- =====================================================
-- A marca de que a pessoa abriu o Inicio num dia: uma linha por pessoa por
-- dia, sem trilha de cliques. O backend grava ao montar o Inicio da propria
-- pessoa (a segunda abertura do dia bate na chave e nao grava nada) e o job
-- das 06:00 (marcar_atrasadas) apaga o que tem mais de 90 dias.
--
-- Nesta fatia ninguem le a tabela: quem le e o bloco Quem responde a voce,
-- em outra fatia, so para quem ja ve os itens da pessoa.
--
-- RLS default-deny: so o backend, com a service_role, le e grava. Nenhuma
-- policy de proposito.
-- Rodar duas vezes e inofensivo. Aplicar a mao no Studio.
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS registro_de_acesso (
  participante_id  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE CASCADE,
  dia              DATE NOT NULL,
  PRIMARY KEY (participante_id, dia)
);

COMMENT ON TABLE registro_de_acesso IS
  'Registro de acesso (ADR 0104, decisao 10): o dia em que a pessoa abriu o Inicio. Uma linha por pessoa por dia, guardada por 90 dias. Issue #1941.';
COMMENT ON COLUMN registro_de_acesso.dia IS
  'O dia da abertura no fuso de Brasilia.';

-- A retencao apaga por dia; a chave primaria comeca pela pessoa e nao serve.
CREATE INDEX IF NOT EXISTS idx_registro_de_acesso_dia
  ON registro_de_acesso (dia);

ALTER TABLE registro_de_acesso ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (167) ON CONFLICT (numero) DO NOTHING;
