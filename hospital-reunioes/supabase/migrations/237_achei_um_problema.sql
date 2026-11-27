-- =====================================================
-- Migration 237: o Achei um problema do Pedido de implantacao
-- (issue #2210, PRD #2205, ADR 0111, decisao 9)
-- =====================================================
-- O botao "Achei um problema" do Pedido de implantacao abre o bug no
-- Assistente. Tres referencias opcionais, todas com ON DELETE SET NULL:
--
-- - tecnologia_demandas.pedido_origem_id: o Pedido de que o bug veio,
--   gravado quando a conversa nasce. E por ele que o Criar o card liga as
--   duas pontas.
-- - tecnologia_demandas.demanda_origem_id: a Demanda de origem (a entrega),
--   gravada no Criar o card. Nunca a propria Demanda.
-- - tecnologia_perguntas.espera_demanda_id: a Demanda de bug que o Pedido
--   espera, gravada no Criar o card. Ate ela ficar Entregue o Concluir
--   recusa, e essa regra mora no backend (o CHECK nao le outra linha). So o
--   Pedido de implantacao espera uma Demanda de bug.
--
-- Nenhuma tabela nova, nenhuma policy: as duas tabelas seguem com RLS
-- default-deny. Cada chave estrangeira tem indice parcial, para apagar uma
-- linha nao varrer a outra tabela.
--
-- Aplicar a mao no Studio: o deploy nao aplica SQL. Rodar duas vezes e
-- inofensivo.
-- =====================================================

BEGIN;

ALTER TABLE tecnologia_demandas
  ADD COLUMN IF NOT EXISTS pedido_origem_id uuid REFERENCES tecnologia_perguntas(id) ON DELETE SET NULL;

ALTER TABLE tecnologia_demandas
  ADD COLUMN IF NOT EXISTS demanda_origem_id uuid REFERENCES tecnologia_demandas(id) ON DELETE SET NULL;

ALTER TABLE tecnologia_demandas DROP CONSTRAINT IF EXISTS tecnologia_demandas_origem_nao_e_ela_mesma;
ALTER TABLE tecnologia_demandas ADD CONSTRAINT tecnologia_demandas_origem_nao_e_ela_mesma CHECK (
  demanda_origem_id IS NULL OR demanda_origem_id <> id
);

ALTER TABLE tecnologia_perguntas
  ADD COLUMN IF NOT EXISTS espera_demanda_id uuid REFERENCES tecnologia_demandas(id) ON DELETE SET NULL;

ALTER TABLE tecnologia_perguntas DROP CONSTRAINT IF EXISTS tecnologia_perguntas_espera_demanda_so_na_implantacao;
ALTER TABLE tecnologia_perguntas ADD CONSTRAINT tecnologia_perguntas_espera_demanda_so_na_implantacao CHECK (
  espera_demanda_id IS NULL OR tipo = 'implantacao'
);

CREATE INDEX IF NOT EXISTS tecnologia_demandas_pedido_origem_id_idx
  ON tecnologia_demandas (pedido_origem_id) WHERE pedido_origem_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS tecnologia_demandas_demanda_origem_id_idx
  ON tecnologia_demandas (demanda_origem_id) WHERE demanda_origem_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS tecnologia_perguntas_espera_demanda_id_idx
  ON tecnologia_perguntas (espera_demanda_id) WHERE espera_demanda_id IS NOT NULL;

COMMENT ON COLUMN tecnologia_demandas.pedido_origem_id IS
  'O Pedido de implantacao de que o bug veio pelo Achei um problema (ADR 0111, decisao 9).';
COMMENT ON COLUMN tecnologia_demandas.demanda_origem_id IS
  'A Demanda de origem do bug do Achei um problema, gravada no Criar o card (ADR 0111, decisao 9).';
COMMENT ON COLUMN tecnologia_perguntas.espera_demanda_id IS
  'A Demanda de bug que o Pedido de implantacao espera: o Concluir so libera com ela Entregue (ADR 0111, decisao 9).';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (237) ON CONFLICT (numero) DO NOTHING;
