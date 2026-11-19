-- =====================================================
-- Migration 166: a observacao do Validar fica no app
-- (issue #2013, PRD #2007, ADR 0108, decisao 5)
-- =====================================================
-- O botao Validar da Apresentacao do PRD (a funcao `validar.js` da Vercel)
-- deixa de copiar a observacao do diretor para o GitHub. A funcao manda o
-- texto a ponte de automacao, o app guarda o original junto da Demanda do PRD
-- e devolve so a interpretacao, que e o que vai para o comentario e o Ajuste.
--
-- O original mora na tabela do Envio aos desenvolvedores (migration 165), com
-- duas colunas novas:
--
--   1. `origem`: de onde veio o envio. `conversa` (o default, todo envio de
--      hoje) ou `validacao` (a observacao do Validar). A linha da validacao
--      nao e envio da Conversa: nao marca de onde comeca o proximo.
--
--   2. `texto_original`: a observacao como o diretor escreveu, so na origem
--      `validacao`. Fica no app; nunca vai para o GitHub (ADR 0083, decisao 8).
--
-- A tabela ja nasceu com RLS default-deny (migration 165): quem le e escreve
-- e o backend com a service_role. Nenhuma policy de proposito.
--
-- Aplicar a mao no Studio: o deploy nao aplica SQL. Rodar duas vezes e
-- inofensivo.
-- =====================================================

BEGIN;

ALTER TABLE tecnologia_envios_aos_desenvolvedores
  ADD COLUMN IF NOT EXISTS origem TEXT NOT NULL DEFAULT 'conversa';

ALTER TABLE tecnologia_envios_aos_desenvolvedores
  DROP CONSTRAINT IF EXISTS tecnologia_envios_aos_desenvolvedores_origem_check;
ALTER TABLE tecnologia_envios_aos_desenvolvedores
  ADD CONSTRAINT tecnologia_envios_aos_desenvolvedores_origem_check
  CHECK (origem IN ('conversa', 'validacao'));

ALTER TABLE tecnologia_envios_aos_desenvolvedores
  ADD COLUMN IF NOT EXISTS texto_original TEXT;

COMMENT ON TABLE tecnologia_envios_aos_desenvolvedores IS
  'Envio aos desenvolvedores (ADR 0108, decisoes 3 a 5): a interpretacao das mensagens do diretor na Conversa da Demanda desde o ultimo envio e o Ajuste do plano que ela abriu. Desde a migration 166 guarda tambem a observacao do Validar da Apresentacao do PRD (origem validacao), com o texto original, que nunca vai para o GitHub.';
COMMENT ON COLUMN tecnologia_envios_aos_desenvolvedores.origem IS
  'conversa = o Envio pela Conversa da Demanda; validacao = a observacao do Validar da Apresentacao do PRD (issue #2013). A validacao nao conta como envio da Conversa.';
COMMENT ON COLUMN tecnologia_envios_aos_desenvolvedores.texto_original IS
  'A observacao do Validar como o diretor escreveu (so na origem validacao). Fica no app; o GitHub recebe so os topicos.';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (166) ON CONFLICT (numero) DO NOTHING;
