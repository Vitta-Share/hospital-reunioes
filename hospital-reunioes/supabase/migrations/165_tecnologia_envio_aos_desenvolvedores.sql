-- =====================================================
-- Migration 165: o Envio aos desenvolvedores pela Conversa da Demanda
-- (issue #2011, PRD #2007, ADR 0108, decisoes 3 a 5)
-- =====================================================
-- O diretor escreve na Conversa da Demanda e, no fim, aperta "Enviar para os
-- desenvolvedores". O agente interpreta as mensagens dele desde o ultimo
-- envio ("Entendi assim:"), e so com o "Enviar" nasce o Ajuste do plano no
-- GitHub. Tres mudancas:
--
--   1. `tecnologia_envios_aos_desenvolvedores`: cada envio, da interpretacao
--      ao Ajuste. Guarda a Demanda, quem enviou, quando, os topicos
--      aprovados, o que muda em cada card, o numero do Ajuste e o instante da
--      ultima mensagem coberta (`ate_mensagem_em`), que diz de onde comeca o
--      proximo envio. A trava contra o duplo clique segue a porta de envio do
--      card (migration 128): estado, motivo e instante. O indice unico parcial
--      e a rede de baixo: duas interpretacoes das mesmas mensagens nao viram
--      dois Ajustes. A fala do diretor nao entra aqui: ela ja mora na
--      Conversa, e o GitHub so recebe a interpretacao (ADR 0083, decisao 8).
--
--   2. O passo `envio` no CHECK de `tecnologia_chamadas_ia` (migration 123):
--      o custo do modelo do Envio fica gravado como o das outras conversas.
--
--   3. A origem `sistema` no CHECK da Conversa da Demanda (migration 161): a
--      linha "Enviado aos desenvolvedores em <data>, as <hora>" com os
--      topicos. Ela nao conta como mensagem do diretor no proximo envio.
--
-- RLS default-deny (padrao da casa): quem le e escreve e o backend com a
-- service_role. Nenhuma policy de proposito.
--
-- Aplicar a mao no Studio: o deploy nao aplica SQL. Rodar duas vezes e
-- inofensivo.
-- =====================================================

BEGIN;

-- ---------- 1. O envio ----------
CREATE TABLE IF NOT EXISTS tecnologia_envios_aos_desenvolvedores (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demanda_id       UUID NOT NULL REFERENCES tecnologia_demandas(id) ON DELETE CASCADE,
  enviado_por      VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  topicos          JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(topicos) = 'array'),
  cards            JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(cards) = 'array'),
  ate_mensagem_em  TIMESTAMPTZ NOT NULL,
  ajuste_numero    INTEGER CHECK (ajuste_numero IS NULL OR ajuste_numero > 0),
  estado           TEXT NOT NULL DEFAULT 'interpretado'
                   CHECK (estado IN ('interpretado', 'enviando', 'enviado', 'falhou')),
  motivo           TEXT,
  estado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
  enviado_em       TIMESTAMPTZ,
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tecnologia_envios_aos_desenvolvedores_demanda
  ON tecnologia_envios_aos_desenvolvedores (demanda_id, ate_mensagem_em);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tecnologia_envios_aos_desenvolvedores_um_ajuste
  ON tecnologia_envios_aos_desenvolvedores (demanda_id, ate_mensagem_em)
  WHERE estado IN ('enviando', 'enviado');

COMMENT ON TABLE tecnologia_envios_aos_desenvolvedores IS
  'Envio aos desenvolvedores (ADR 0108, decisoes 3 a 5): a interpretacao das mensagens do diretor na Conversa da Demanda desde o ultimo envio e o Ajuste do plano que ela abriu. Nunca guarda a fala do diretor.';
COMMENT ON COLUMN tecnologia_envios_aos_desenvolvedores.topicos IS
  'O "Entendi assim:" que o diretor aprovou, em topicos (lista de textos).';
COMMENT ON COLUMN tecnologia_envios_aos_desenvolvedores.cards IS
  'O que muda em cada card, com o numero: lista de {numero, muda}.';
COMMENT ON COLUMN tecnologia_envios_aos_desenvolvedores.ate_mensagem_em IS
  'O instante da ultima mensagem do diretor coberta por este envio. O proximo envio comeca depois dele.';
COMMENT ON COLUMN tecnologia_envios_aos_desenvolvedores.estado IS
  'interpretado = o "Entendi assim:" esperando o Enviar; enviando = a vez de abrir o Ajuste (trava do duplo clique); enviado = o Ajuste nasceu; falhou = o GitHub nao abriu, com o motivo.';

ALTER TABLE tecnologia_envios_aos_desenvolvedores ENABLE ROW LEVEL SECURITY;

-- ---------- 2. O passo do custo ----------
ALTER TABLE tecnologia_chamadas_ia DROP CONSTRAINT IF EXISTS tecnologia_chamadas_ia_passo_check;
ALTER TABLE tecnologia_chamadas_ia
  ADD CONSTRAINT tecnologia_chamadas_ia_passo_check
  CHECK (passo IN ('pergunta', 'resumo', 'envio'));

COMMENT ON COLUMN tecnologia_chamadas_ia.passo IS
  'pergunta = um turno do planejamento; resumo = o Fechar e resumir (#1347); envio = a interpretacao do Envio aos desenvolvedores (#2011).';

-- ---------- 3. A linha do sistema na Conversa ----------
ALTER TABLE tecnologia_conversa_da_demanda DROP CONSTRAINT IF EXISTS tecnologia_conversa_da_demanda_origem_check;
ALTER TABLE tecnologia_conversa_da_demanda
  ADD CONSTRAINT tecnologia_conversa_da_demanda_origem_check
  CHECK (origem IN ('app', 'terminal', 'sistema'));

COMMENT ON COLUMN tecnologia_conversa_da_demanda.origem IS
  'De onde veio a mensagem: app (a aba Tecnologia), terminal (a ponte de automacao, ADR 0096) ou sistema (a linha do Envio aos desenvolvedores, ADR 0108). A tela mostra so a do sistema de outro jeito.';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (165) ON CONFLICT (numero) DO NOTHING;
