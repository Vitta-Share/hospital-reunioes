-- =====================================================
-- Migration 164: o atalho Ver o plano no card
-- (issue #2010, PRD #2007, ADR 0108 decisao 2)
-- =====================================================
-- A sincronizacao com o GitHub le na issue-raiz o marcador
-- `<!-- apresentacao: <url> -->` que o `apresentar.py publicar` grava, e a
-- label `validado:diretor`. Duas colunas novas na tabela que ja existe:
--
--   1. `apresentacao_url`: o link da Apresentacao do PRD. Nulo sem marcador.
--      So a pagina dos planos (https://planos-hsm.vercel.app/), a mesma
--      guarda do backend.
--
--   2. `plano_validado`: se a issue-raiz tem a label `validado:diretor`.
--      Default false, o que toda Demanda de hoje ja e para a tela.
--
-- `apresentacao_url` nula sem default e `plano_validado` com default
-- constante: o Postgres nao reescreve a tabela. Sem policy nova: a tabela ja
-- esta com RLS e o backend escreve com a service role (migration 102).
--
-- Aplicar a mao no Studio: o deploy nao aplica SQL. Rodar duas vezes e
-- inofensivo.
-- =====================================================

BEGIN;

ALTER TABLE tecnologia_demandas ADD COLUMN IF NOT EXISTS apresentacao_url TEXT;
ALTER TABLE tecnologia_demandas ADD COLUMN IF NOT EXISTS plano_validado BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE tecnologia_demandas DROP CONSTRAINT IF EXISTS tecnologia_demandas_apresentacao_url_check;
ALTER TABLE tecnologia_demandas
  ADD CONSTRAINT tecnologia_demandas_apresentacao_url_check
  CHECK (apresentacao_url IS NULL OR apresentacao_url LIKE 'https://planos-hsm.vercel.app/%');

COMMENT ON COLUMN tecnologia_demandas.apresentacao_url IS
  'O link da Apresentacao do PRD, lido do marcador <!-- apresentacao: <url> --> da issue-raiz (ADR 0108, decisao 2). So https://planos-hsm.vercel.app/.';
COMMENT ON COLUMN tecnologia_demandas.plano_validado IS
  'Se a issue-raiz tem a label validado:diretor (ADR 0108, decisao 2). Volta a false quando a label sai.';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (164) ON CONFLICT (numero) DO NOTHING;
