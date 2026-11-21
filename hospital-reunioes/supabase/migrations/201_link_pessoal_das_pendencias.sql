-- =====================================================
-- Migration 201: Link pessoal das Pendencias (PRD #1757; issue #1878; ADR 0098 decisao 8)
-- =====================================================
-- Quem nunca entrou no app recebe, no e-mail de segunda, um link com token
-- para atualizar as proprias Pendencias sem senha, no padrao do portal do
-- setor da Ouvidoria (migrations 069 e 106): o token em claro vive so no
-- e-mail, o banco guarda o hash SHA-256, o link vence e pode ser revogado.
--
-- Diferencas deliberadas em relacao ao portal do setor:
--   - sem `usado_em`: o link nao e de uso unico. A pessoa inicia hoje, anota
--     amanha e conclui depois, em varias Pendencias, pelo mesmo link. O que o
--     prende e o dono (`participante_id`): ele so alcanca as Pendencias em
--     que essa pessoa e responsavel ou co-responsavel.
--   - validade de 14 dias: o e-mail de segunda traz um link novo por semana,
--     e o da semana anterior ainda vale ate o seguinte chegar.
--   - a emissao nao revoga os links anteriores: o envio que falha tenta de
--     novo na hora seguinte, e o e-mail da tentativa anterior pode ter chegado.
--   - `revogado_em` e gravado quando a pessoa e desligada do hospital.
--
-- So o backend (service_role) le e grava: RLS default-deny, sem policy.
-- Rodar duas vezes e inofensivo. Aplicar a mao no Studio.
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS pendencias_links_pessoais (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  participante_id  VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE CASCADE,
  token_hash       TEXT        NOT NULL,
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
  expira_em        TIMESTAMPTZ NOT NULL DEFAULT now() + interval '14 days',
  revogado_em      TIMESTAMPTZ
);

-- A pagina publica acha o link pelo hash.
CREATE UNIQUE INDEX IF NOT EXISTS idx_pendencias_links_pessoais_hash
  ON pendencias_links_pessoais (token_hash);

-- O desligamento revoga os links vivos da pessoa.
CREATE INDEX IF NOT EXISTS idx_pendencias_links_pessoais_vivos
  ON pendencias_links_pessoais (participante_id)
  WHERE revogado_em IS NULL;

COMMENT ON TABLE pendencias_links_pessoais IS
  'Link pessoal de quem nunca entrou no app (ADR 0098, decisao 8). So o hash fica no banco: vazar a tabela nao vaza o link do e-mail.';
COMMENT ON COLUMN pendencias_links_pessoais.revogado_em IS
  'Quando o link foi cancelado (pessoa desligada). NULL = link vivo, ate expira_em.';

ALTER TABLE pendencias_links_pessoais ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON pendencias_links_pessoais FROM anon, authenticated;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (201) ON CONFLICT (numero) DO NOTHING;
