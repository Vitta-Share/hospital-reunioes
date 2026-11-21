-- =====================================================
-- Migration 203: Canal de Conduta, a nota do Comitê ao Núcleo de Segurança
-- do Paciente (issue #1850, PRD #1786, ADR 0097, decisão 14)
-- =====================================================
-- Quando um caso descreve um risco ao paciente, um membro do Comitê escreve
-- uma nota e a coordenação a envia. O Núcleo recebe só a nota: sem protocolo,
-- sem relato, sem anexo e sem quem relatou.
--
-- Duas tabelas, uma de cada lado:
--   1. conduta_notas_nsp, do lado do Comitê: a nota do caso, cifrada como
--      todo conteúdo do módulo, com quem escreveu e quem enviou. Uma nota
--      esperando o envio por caso;
--   2. nsp_notas_do_comite, do lado do Núcleo: só o texto e a data do envio.
--      Nenhuma coluna aponta para o caso nem para quem agiu, e o lado do
--      Comitê não guarda o id desta linha: nada liga uma à outra.
--
-- RLS default-deny nas duas: só o backend, com a service_role, lê e grava.
-- Nenhuma policy de propósito. Rodar duas vezes é inofensivo. Aplicar à mão
-- no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. O lado do Comitê ----------
CREATE TABLE IF NOT EXISTS conduta_notas_nsp (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id        UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  texto_cifrado  TEXT NOT NULL CHECK (texto_cifrado LIKE 'v1:%'),
  escrita_por    VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  escrita_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
  enviada_por    VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  enviada_em     TIMESTAMPTZ,
  CONSTRAINT conduta_notas_nsp_envio_check CHECK ((enviada_por IS NULL) = (enviada_em IS NULL))
);

COMMENT ON TABLE conduta_notas_nsp IS
  'Sinalizar ao NSP (issue #1850): a nota do Comitê no caso. O Núcleo recebe só o texto, em nsp_notas_do_comite.';

-- Uma nota esperando a coordenação por caso: escrever de novo troca o texto.
CREATE UNIQUE INDEX IF NOT EXISTS uq_conduta_notas_nsp_pendente
  ON conduta_notas_nsp (caso_id) WHERE enviada_em IS NULL;
CREATE INDEX IF NOT EXISTS idx_conduta_notas_nsp_caso ON conduta_notas_nsp (caso_id);
CREATE INDEX IF NOT EXISTS idx_conduta_notas_nsp_escrita_por ON conduta_notas_nsp (escrita_por);
CREATE INDEX IF NOT EXISTS idx_conduta_notas_nsp_enviada_por ON conduta_notas_nsp (enviada_por);

ALTER TABLE conduta_notas_nsp ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_notas_nsp FROM anon, authenticated;

-- ---------- 2. O lado do Núcleo ----------
CREATE TABLE IF NOT EXISTS nsp_notas_do_comite (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  texto       TEXT NOT NULL CHECK (btrim(texto) <> '' AND char_length(texto) <= 2000),
  enviada_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE nsp_notas_do_comite IS
  'Notas do Comitê de Conduta ao Núcleo (issue #1850). Só o texto e a data: nada aponta para o caso do Canal.';

CREATE INDEX IF NOT EXISTS idx_nsp_notas_do_comite_enviada_em ON nsp_notas_do_comite (enviada_em DESC);

ALTER TABLE nsp_notas_do_comite ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nsp_notas_do_comite FROM anon, authenticated;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (203) ON CONFLICT (numero) DO NOTHING;
