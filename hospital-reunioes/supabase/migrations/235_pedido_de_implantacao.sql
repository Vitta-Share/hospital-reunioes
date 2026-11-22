-- =====================================================
-- Migration 235: o Pedido de implantacao, o terceiro tipo do Pedido da Vitta
-- (issue #2207, PRD #2205, ADR 0111, emenda a 0110)
-- =====================================================
-- O que o hospital faz depois que o codigo sobe (teste de aceite,
-- configuracao, abertura, treinamento) vira um Pedido do tipo `implantacao`.
-- Ele tem as mesmas colunas e as mesmas regras do Passo a passo (migration
-- 232): o card, de 2 a 15 passos, os checks e os estados aberta, concluida e
-- cancelada. Muda so o que o app faz com o card (fecha ao nascer, e o webhook
-- nao mexe nele), e isso mora no backend.
--
-- Os tres CHECKs que citam o tipo passam a aceitar `implantacao`. Nenhuma
-- tabela nova, nenhuma policy: a tabela segue com RLS default-deny.
--
-- Aplicar a mao no Studio: o deploy nao aplica SQL. Rodar duas vezes e
-- inofensivo.
-- =====================================================

BEGIN;

-- O tipo (o CHECK inline da 232 tem o nome padrao do Postgres).
ALTER TABLE tecnologia_perguntas DROP CONSTRAINT IF EXISTS tecnologia_perguntas_tipo_check;
ALTER TABLE tecnologia_perguntas ADD CONSTRAINT tecnologia_perguntas_tipo_check
  CHECK (tipo IN ('pergunta', 'passo_a_passo', 'implantacao'));

-- O estado: o Pedido de implantacao usa os do Passo a passo.
ALTER TABLE tecnologia_perguntas DROP CONSTRAINT IF EXISTS tecnologia_perguntas_estado_do_tipo;
ALTER TABLE tecnologia_perguntas ADD CONSTRAINT tecnologia_perguntas_estado_do_tipo CHECK (
  (tipo = 'pergunta' AND estado IN ('aberta', 'respondida', 'resolvida', 'cancelada'))
  OR (tipo IN ('passo_a_passo', 'implantacao') AND estado IN ('aberta', 'concluida', 'cancelada'))
);

-- O card e de 2 a 15 passos, como no Passo a passo.
ALTER TABLE tecnologia_perguntas DROP CONSTRAINT IF EXISTS tecnologia_perguntas_passo_a_passo_completo;
ALTER TABLE tecnologia_perguntas ADD CONSTRAINT tecnologia_perguntas_passo_a_passo_completo CHECK (
  tipo = 'pergunta'
  OR (card_projeto IS NOT NULL AND card_numero IS NOT NULL AND jsonb_array_length(passos) BETWEEN 2 AND 15)
);

COMMENT ON COLUMN tecnologia_perguntas.tipo IS
  'pergunta = se responde e espera a leitura da Vitta; passo_a_passo = se conclui e fecha o card no GitHub (ADR 0110, decisao 5); implantacao = fecha o card ao nascer, se conclui so comentando e nao acompanha o GitHub (ADR 0111).';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (235) ON CONFLICT (numero) DO NOTHING;
