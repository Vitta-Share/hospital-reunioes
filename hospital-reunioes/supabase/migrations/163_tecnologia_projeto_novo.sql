-- =====================================================
-- Migration 163: a Demanda de um Projeto novo
-- (issue #1967, PRD #1964)
-- =====================================================
-- A ponte de automacao cria a Demanda do PRD de um Projeto que o app nao
-- conhece (o PedroOS, por exemplo), so com a Conversa da Demanda e o link.
-- Tres mudancas, na tabela que ja existe:
--
--   1. O CHECK do `projeto` (migration 145) deixa de ser a lista Hospital e
--      Ana e passa a ser o formato do nome: minusculas, numeros e hifen, ate
--      40 caracteres. E o mesmo `github_client.FORMATO_DO_PROJETO` da rota da
--      ponte; o teste amarra as duas pontas. As Demandas de hoje (`hospital`
--      e `ana`) cabem no formato e nao mudam.
--
--   2. `projeto_nome`: o nome do Projeto novo como a tela o mostra. Nulo no
--      Hospital e na Ana, cujo nome a tela ja sabe.
--
--   3. `raiz_url`: o link do PRD que a ponte manda. O app nao le o repositorio
--      do Projeto novo e nao tem como montar o link pelo numero. Nulo no
--      Hospital e na Ana. So https, como o link da Demonstracao (migration 130).
--
-- Colunas nulas sem default: o Postgres nao reescreve a tabela. Sem policy
-- nova: a tabela ja esta com RLS e o backend escreve com a service role
-- (migration 102).
--
-- Aplicar a mao no Studio: o deploy nao aplica SQL. Rodar duas vezes e
-- inofensivo.
-- =====================================================

BEGIN;

ALTER TABLE tecnologia_demandas DROP CONSTRAINT IF EXISTS tecnologia_demandas_projeto_check;
ALTER TABLE tecnologia_demandas
  ADD CONSTRAINT tecnologia_demandas_projeto_check
  CHECK (projeto ~ '^[a-z0-9][a-z0-9-]{0,39}$');

ALTER TABLE tecnologia_demandas ADD COLUMN IF NOT EXISTS projeto_nome TEXT;
ALTER TABLE tecnologia_demandas ADD COLUMN IF NOT EXISTS raiz_url TEXT;

ALTER TABLE tecnologia_demandas DROP CONSTRAINT IF EXISTS tecnologia_demandas_raiz_url_check;
ALTER TABLE tecnologia_demandas
  ADD CONSTRAINT tecnologia_demandas_raiz_url_check
  CHECK (raiz_url IS NULL OR raiz_url LIKE 'https://%');

COMMENT ON COLUMN tecnologia_demandas.projeto IS
  'O Projeto da Demanda (ADR 0093, decisao 2; issue #1967): hospital, ana ou um Projeto novo da Vitta que o app nao le, criado pela ponte de automacao. A chave do Vinculo e projeto mais github_issue_numero.';
COMMENT ON COLUMN tecnologia_demandas.projeto_nome IS
  'O nome do Projeto novo como a tela o mostra (issue #1967). Nulo no hospital e na ana.';
COMMENT ON COLUMN tecnologia_demandas.raiz_url IS
  'O link do PRD do Projeto novo, que a ponte manda (issue #1967). Nulo no hospital e na ana, cujo link sai do repositorio configurado.';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (163) ON CONFLICT (numero) DO NOTHING;
