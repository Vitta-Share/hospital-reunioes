-- =====================================================
-- Migration 231: Canal de Conduta, dois itens novos nas configurações
-- (issue #1846, PRD #1786, especificação seção 4.3)
-- =====================================================
-- A página "Como este canal protege você" ganha dois blocos que a
-- coordenação edita na tela Configurações, com versão como os outros:
--
-- - `contato_encarregado`: o contato do encarregado de dados do hospital
--   (LGPD, art. 41). O valor é do hospital e não entra no código nem aqui.
-- - `protecao_ia`: o bloco da inteligência artificial (decisão 38 do diretor).
--
-- Só troca a lista do CHECK da migration 186, que é a mesma de
-- `app/services/conduta/configuracoes.py`. Nenhuma linha é tocada. A tabela
-- continua com RLS ligada e sem policy, e as versões continuam imutáveis.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio, depois da 186.
-- =====================================================

BEGIN;

ALTER TABLE conduta_configuracoes DROP CONSTRAINT IF EXISTS conduta_configuracoes_chave_check;
ALTER TABLE conduta_configuracoes
  ADD CONSTRAINT conduta_configuracoes_chave_check CHECK (chave IN (
    'contato_dp',
    'orientacao_nsp',
    'contato_encarregado',
    'aviso_p1_anonimato',
    'aviso_p1_protocolo',
    'aviso_p1_boa_fe',
    'protecao_abertura',
    'protecao_quem_relata',
    'protecao_quem_e_citado',
    'protecao_quem_le',
    'protecao_ia',
    'protecao_direcao',
    'protecao_prazos',
    'protecao_nao_garante',
    'consentimento_gravacao',
    'local_guarda_envelopes'
  ));

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (231) ON CONFLICT (numero) DO NOTHING;
