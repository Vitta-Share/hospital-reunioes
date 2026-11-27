-- =====================================================
-- Migration 236: um Pedido de implantacao espera outro
-- (issue #2208, PRD #2205, ADR 0111, decisao 8)
-- =====================================================
-- O Pedido ganha a referencia opcional ao Pedido que ele espera. O Concluir
-- so libera com o esperado concluido, e isso mora no backend, como a regra
-- de que o esperado e da mesma Demanda e tambem e de implantacao (o CHECK
-- nao le outra linha).
--
-- Aqui ficam as regras de uma linha so: so o Pedido de implantacao espera,
-- e nunca a si mesmo. O esperado precisa existir; se ele for apagado, a
-- espera some com ele (ON DELETE SET NULL).
--
-- Nenhuma tabela nova, nenhuma policy: a tabela segue com RLS default-deny.
--
-- Aplicar a mao no Studio: o deploy nao aplica SQL. Rodar duas vezes e
-- inofensivo.
-- =====================================================

BEGIN;

ALTER TABLE tecnologia_perguntas
  ADD COLUMN IF NOT EXISTS espera_pedido_id uuid REFERENCES tecnologia_perguntas(id) ON DELETE SET NULL;

ALTER TABLE tecnologia_perguntas DROP CONSTRAINT IF EXISTS tecnologia_perguntas_espera_so_na_implantacao;
ALTER TABLE tecnologia_perguntas ADD CONSTRAINT tecnologia_perguntas_espera_so_na_implantacao CHECK (
  espera_pedido_id IS NULL OR (tipo = 'implantacao' AND espera_pedido_id <> id)
);

-- A chave estrangeira sem indice varre a tabela ao apagar um Pedido.
CREATE INDEX IF NOT EXISTS tecnologia_perguntas_espera_pedido_id_idx
  ON tecnologia_perguntas (espera_pedido_id) WHERE espera_pedido_id IS NOT NULL;

COMMENT ON COLUMN tecnologia_perguntas.espera_pedido_id IS
  'O Pedido de implantacao que este espera: o Concluir so libera com ele concluido (ADR 0111, decisao 8).';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (236) ON CONFLICT (numero) DO NOTHING;
