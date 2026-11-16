-- =====================================================
-- Migration 160: a ata do Núcleo assinada nos Documentos
-- (issue #1776, PRD #1764, ADR 0095)
-- =====================================================
-- O que entra:
--   1. a coluna `nsp_documentos.reuniao_id`: na ata encerrada, a reunião de
--      onde ela veio. Única, para o job do encerramento, rodando de novo,
--      não guardar a mesma ata duas vezes.
--
-- O envio para assinatura e o encerramento ficam no `json_ata` da reunião, e
-- o PDF assinado vai para o bucket privado `nsp-documentos` (migration 151).
-- Nenhum documento nem pessoa entra por aqui.
--
-- RLS: `nsp_documentos` já nasceu com RLS e sem policy (migration 147).
--
-- Tudo com IF NOT EXISTS: rodar duas vezes é inofensivo. Aplicar à mão no
-- Studio: o deploy não aplica SQL.
-- =====================================================

BEGIN;

ALTER TABLE nsp_documentos
  ADD COLUMN IF NOT EXISTS reuniao_id VARCHAR(20) UNIQUE REFERENCES reunioes(id_reuniao) ON DELETE RESTRICT;

COMMENT ON COLUMN nsp_documentos.reuniao_id IS
  'Na ata do Núcleo assinada: a reunião de onde ela veio. Única, para o encerramento repetido não duplicar o documento. Issue #1776.';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (160) ON CONFLICT (numero) DO NOTHING;
