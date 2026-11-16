-- =====================================================
-- Migration 161: a origem da mensagem da Conversa da Demanda (issue #1805,
-- PRD #1803, ADR 0096, decisao 3)
-- =====================================================
-- A Mensagem pelo terminal: a sessao do terminal de um Desenvolvedor escreve
-- na Conversa da Demanda pela ponte de automacao, no perfil dele. A tela nao
-- mostra selo; o banco guarda de onde a mensagem veio:
--
--   `app`      escrita na aba Tecnologia (padrao: toda mensagem que ja existe
--              veio de la);
--   `terminal` escrita pela ponte, depois do "aprovo" de quem roda a sessao.
--
-- So uma coluna nova, com default constante: o Postgres nao reescreve a
-- tabela, e as linhas que ja existem ficam com `app`. A tabela (129) ja tem
-- RLS ligado e nenhuma policy; quem escreve e o backend com a service_role.
--
-- Tudo com IF NOT EXISTS / DROP IF EXISTS / ON CONFLICT: rodar duas vezes e
-- inofensivo. Aplicar a mao no Studio: o deploy nao aplica SQL.
-- =====================================================

ALTER TABLE tecnologia_conversa_da_demanda ADD COLUMN IF NOT EXISTS origem TEXT NOT NULL DEFAULT 'app';

ALTER TABLE tecnologia_conversa_da_demanda DROP CONSTRAINT IF EXISTS tecnologia_conversa_da_demanda_origem_check;
ALTER TABLE tecnologia_conversa_da_demanda
  ADD CONSTRAINT tecnologia_conversa_da_demanda_origem_check
  CHECK (origem IN ('app', 'terminal'));

COMMENT ON COLUMN tecnologia_conversa_da_demanda.origem IS
  'De onde veio a mensagem: app (a aba Tecnologia) ou terminal (a ponte de automacao, ADR 0096). A tela nao mostra.';

-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (161) ON CONFLICT (numero) DO NOTHING;
