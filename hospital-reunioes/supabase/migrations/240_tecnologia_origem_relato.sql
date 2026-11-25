-- =====================================================
-- Migration 240: a Origem "Relato no app" da Demanda (issue #2275, PRD #2262, ADR 0113)
-- =====================================================
-- O bug relatado pelo Assistente do app vira Demanda com uma terceira Origem,
-- `relato`, ao lado de `diretor` (o card com `origem:diretor`) e `vitta` (a
-- issue-raiz do app aberta pelo terminal). A tela mostra "Relato no app".
--
-- So troca o CHECK da coluna (migration 130) e o comentario. Nenhuma linha
-- existente muda, e nenhuma tabela, policy ou indice novo. A tabela tem
-- dezenas de linhas: a validacao do CHECK novo e instantanea.
--
-- Rodar duas vezes e inofensivo. Aplicar a mao no Studio: o deploy nao aplica SQL.
-- =====================================================

ALTER TABLE tecnologia_demandas DROP CONSTRAINT IF EXISTS tecnologia_demandas_origem_check;
ALTER TABLE tecnologia_demandas
  ADD CONSTRAINT tecnologia_demandas_origem_check
  CHECK (origem IN ('diretor', 'vitta', 'relato'));

COMMENT ON COLUMN tecnologia_demandas.origem IS
  'Quem abriu o card: diretor (a issue com a label origem:diretor, ADR 0113, decisao 6), vitta (a issue-raiz do app aberta pelo terminal, ADR 0084, decisao 4) ou relato (o bug relatado no Assistente do app, ADR 0113, decisao 8).';


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (240) ON CONFLICT (numero) DO NOTHING;
