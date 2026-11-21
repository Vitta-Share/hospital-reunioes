-- =====================================================
-- Migration 174: Contestacao do item da Ata (PRD #1757; issue #1870)
-- =====================================================
-- O responsavel contesta o item dele enquanto a Ata esta em assinatura, e o
-- Facilitador (ou o Super admin) ajusta ou recusa, sempre com anotacao. Os
-- tres gravam evento no Historico pela mesma funcao das outras acoes
-- (`registrar_acao_da_pendencia`, migration 169). A regra (quem pode, quando)
-- fica no Python (`app/services/pendencia_ciclo.py`).
--
-- 1. O CHECK de `pendencia_historico.comando` ganha 'contestar', 'ajustar' e
--    'recusar', sem tirar nenhum dos de antes (171).
-- 2. Indice parcial para achar a Contestacao aberta (o ultimo evento da
--    Contestacao de cada Pendencia), lido toda vez que o Inicio abre.
--
-- Depende da 169 e da 171. Sem tabela nova: o RLS default-deny da 169
-- continua valendo, sem policy. Rodar duas vezes e inofensivo. Aplicar a mao
-- no Studio.
-- =====================================================

BEGIN;

-- 1. Os comandos da Contestacao ---------------------------------------------------

ALTER TABLE pendencia_historico DROP CONSTRAINT IF EXISTS pendencia_historico_comando_check;
ALTER TABLE pendencia_historico ADD CONSTRAINT pendencia_historico_comando_check
  CHECK (comando IN (
    'nascimento', 'iniciar', 'anotar', 'concluir', 'repactuar', 'cancelar', 'reabrir', 'migracao',
    'contestar', 'ajustar', 'recusar'
  ));

-- 2. A Contestacao aberta ---------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_pendencia_historico_contestacao
  ON pendencia_historico (id_acao, criado_em)
  WHERE comando IN ('contestar', 'ajustar', 'recusar');

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (174) ON CONFLICT (numero) DO NOTHING;
