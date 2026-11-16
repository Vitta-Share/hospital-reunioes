-- =====================================================
-- Migration 158: Segurança do Paciente, os avisos do Termo e da vigência
-- (issue #1770, PRD #1764, ADR 0095)
-- =====================================================
-- O que entra: o registro de cada aviso por e-mail do job diário
-- (`nsp_avisos`). Uma linha por (Participação, marco, referência,
-- destinatário), gravada ANTES do envio: a chave única faz a segunda rodada
-- do dia bater na guarda em vez de mandar o e-mail de novo. A referência é o
-- envio do Termo nos marcos de assinatura (o reenvio recomeça a contagem) e o
-- fim da vigência nos outros (a renovação recomeça os avisos). A falha do
-- envio fica na própria linha, com o motivo.
--
-- Nenhuma pessoa entra por aqui (decisão 12).
-- RLS default-deny na tabela nova: só o backend, com a service_role, lê e grava.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS nsp_avisos (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participacao_id  UUID NOT NULL REFERENCES participacoes(id) ON DELETE RESTRICT,
  marco            TEXT NOT NULL
                   CHECK (marco IN ('documento_gerado', 'assinatura_3', 'assinatura_7', 'assinatura_14',
                                    'vigencia_60', 'vigencia_30', 'fim_da_carencia')),
  referencia       TEXT NOT NULL CHECK (char_length(referencia) BETWEEN 1 AND 64),
  destinatario_id  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  situacao         TEXT NOT NULL DEFAULT 'pendente'
                   CHECK (situacao IN ('pendente', 'enviado', 'falhou')),
  erro             TEXT CHECK (erro IS NULL OR char_length(erro) <= 500),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  enviado_em       TIMESTAMPTZ,
  UNIQUE (participacao_id, marco, referencia, destinatario_id)
);

COMMENT ON TABLE nsp_avisos IS
  'Cada aviso por e-mail do Núcleo (Termo sem assinatura, fim da vigência, fim da carência), gravado antes do envio. A chave única impede o mesmo aviso duas vezes. Issue #1770.';
COMMENT ON COLUMN nsp_avisos.referencia IS
  'O id do envio do Termo nos marcos de assinatura; o fim da vigência (AAAA-MM-DD) nos marcos de vigência e de carência.';
COMMENT ON COLUMN nsp_avisos.erro IS
  'Por que o aviso não saiu (sem e-mail no cadastro, recusa do provedor). Só quando a situação é falhou.';

-- A chave única já cobre a busca por Participação; a FK do destinatário
-- ganha o próprio índice.
CREATE INDEX IF NOT EXISTS idx_nsp_avisos_destinatario
  ON nsp_avisos (destinatario_id);

ALTER TABLE nsp_avisos ENABLE ROW LEVEL SECURITY;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (158) ON CONFLICT (numero) DO NOTHING;
