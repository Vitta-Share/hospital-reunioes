-- =====================================================
-- Migration 174: a Notificação de incidente do Núcleo
-- (issue #1987, PRD #1979, ADR 0107 decisões 3 e 6)
-- =====================================================
-- O que entra:
--   1. o contador do protocolo, uma linha por ano. O protocolo NSP-AAAA-NNNN
--      sai do banco, no insert, e a sequência recomeça a cada ano;
--   2. a notificação: relato, onde e quando, se chegou ao paciente, quem
--      notificou (ou o hash do código de acompanhamento, na anônima) e a origem
--      pelo ponto de entrada. Nenhuma coluna guarda IP ou identificador do
--      aparelho;
--   3. a notificação não se apaga: o banco recusa DELETE;
--   4. a trilha de cada edição: campo, de, para, quem e quando. Quem editou
--      vem da própria edição, na coluna `editado_por`, que o trigger consome;
--      a trilha só cresce;
--   5. o e-mail de caso (`nsp_avisos.caso_id`, migration 173) ganha a chave
--      estrangeira para a notificação.
--
-- Nenhuma pessoa entra por aqui. RLS ligado e sem política nas tabelas novas:
-- só o backend, com a service_role, lê e grava. Rodar duas vezes é inofensivo.
-- Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. O contador do protocolo ----------
CREATE TABLE IF NOT EXISTS nsp_protocolos (
  ano     SMALLINT PRIMARY KEY,
  ultimo  INTEGER NOT NULL CHECK (ultimo > 0)
);

COMMENT ON TABLE nsp_protocolos IS
  'O último número de protocolo do Núcleo em cada ano (NSP-AAAA-NNNN). Issue #1987.';

ALTER TABLE nsp_protocolos ENABLE ROW LEVEL SECURITY;

-- ---------- 2. A notificação ----------
CREATE TABLE IF NOT EXISTS nsp_notificacoes (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  protocolo                   TEXT NOT NULL UNIQUE,
  ano                         SMALLINT NOT NULL,
  numero                      INTEGER NOT NULL,
  origem                      TEXT NOT NULL CHECK (origem IN ('qr', 'endereco', 'modulo', 'ouvidoria', 'busca_ativa', 'ronda', 'reuniao_rapida', 'auditoria', 'outra')),
  estado                      TEXT NOT NULL DEFAULT 'recebida' CHECK (estado IN ('recebida', 'em_triagem', 'classificada', 'encaminhada', 'fora_de_escopo', 'em_analise_agregada')),
  relato                      TEXT NOT NULL CHECK (char_length(btrim(relato)) BETWEEN 1 AND 10000),
  leito_ou_atendimento        TEXT CHECK (leito_ou_atendimento IS NULL OR char_length(leito_ou_atendimento) <= 60),
  setor_id                    UUID REFERENCES setores(id) ON DELETE RESTRICT,
  data_ocorrencia             DATE NOT NULL,
  turno                       TEXT CHECK (turno IN ('manha', 'tarde', 'noite')),
  hora_aproximada             TIME,
  chegou_ao_paciente          TEXT CHECK (chegou_ao_paciente IN ('nao', 'sem_dano', 'com_dano', 'nao_sei')),
  grave_ou_morte              BOOLEAN,
  percebido_ou_reclamacao     TEXT CHECK (percebido_ou_reclamacao IN ('sim', 'nao', 'nao_sei')),
  anonimo                     BOOLEAN NOT NULL,
  notificante_id              VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  notificante_nome            TEXT CHECK (notificante_nome IS NULL OR char_length(notificante_nome) <= 200),
  notificante_contato         TEXT CHECK (notificante_contato IS NULL OR char_length(notificante_contato) <= 200),
  codigo_acompanhamento_hash  TEXT,
  editado_por                 VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  criado_em                   TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em               TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ano, numero),
  CHECK (NOT anonimo OR (notificante_id IS NULL AND notificante_nome IS NULL AND notificante_contato IS NULL AND codigo_acompanhamento_hash IS NOT NULL)),
  CHECK (anonimo OR codigo_acompanhamento_hash IS NULL)
);

COMMENT ON TABLE nsp_notificacoes IS
  'A Notificação de incidente do Núcleo de Segurança do Paciente. Não guarda IP nem identificador do aparelho; não se apaga; cada edição vai para nsp_notificacoes_trilha. Issue #1987.';
COMMENT ON COLUMN nsp_notificacoes.origem IS
  'Por onde a notificação chegou: qr (/notificar/qr), endereco (/notificar), modulo (botão Notificar incidente) ou as portas das outras fatias.';
COMMENT ON COLUMN nsp_notificacoes.codigo_acompanhamento_hash IS
  'Só na anônima: o hash do código mostrado uma vez a quem notificou. O código não é guardado.';
COMMENT ON COLUMN nsp_notificacoes.editado_por IS
  'Quem faz a edição em curso. O trigger grava na trilha e limpa a coluna: cada edição diz o seu autor.';

CREATE INDEX IF NOT EXISTS idx_nsp_notificacoes_criado_em ON nsp_notificacoes (criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_nsp_notificacoes_setor ON nsp_notificacoes (setor_id);
CREATE INDEX IF NOT EXISTS idx_nsp_notificacoes_notificante ON nsp_notificacoes (notificante_id);
CREATE INDEX IF NOT EXISTS idx_nsp_notificacoes_editado_por ON nsp_notificacoes (editado_por);

ALTER TABLE nsp_notificacoes ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION nsp_notificacao_protocolo() RETURNS TRIGGER AS $$
DECLARE
  v_ano    SMALLINT := extract(year FROM (now() AT TIME ZONE 'America/Sao_Paulo'))::smallint;
  v_numero INTEGER;
BEGIN
  INSERT INTO nsp_protocolos (ano, ultimo) VALUES (v_ano, 1)
    ON CONFLICT (ano) DO UPDATE SET ultimo = nsp_protocolos.ultimo + 1
    RETURNING ultimo INTO v_numero;
  NEW.ano := v_ano;
  NEW.numero := v_numero;
  NEW.protocolo := 'NSP-' || v_ano || '-' || lpad(v_numero::text, greatest(4, length(v_numero::text)), '0');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_notificacao_protocolo ON nsp_notificacoes;
CREATE TRIGGER trg_nsp_notificacao_protocolo
  BEFORE INSERT ON nsp_notificacoes
  FOR EACH ROW EXECUTE FUNCTION nsp_notificacao_protocolo();

-- ---------- 3. A notificação não se apaga ----------
CREATE OR REPLACE FUNCTION nsp_notificacoes_sem_exclusao() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Notificação de incidente não se apaga: corrija por edição, que fica na trilha'
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_notificacoes_sem_exclusao ON nsp_notificacoes;
CREATE TRIGGER trg_nsp_notificacoes_sem_exclusao
  BEFORE DELETE ON nsp_notificacoes
  FOR EACH ROW EXECUTE FUNCTION nsp_notificacoes_sem_exclusao();

-- ---------- 4. A trilha de cada edição ----------
CREATE TABLE IF NOT EXISTS nsp_notificacoes_trilha (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  notificacao_id  UUID NOT NULL REFERENCES nsp_notificacoes(id) ON DELETE RESTRICT,
  campo           TEXT NOT NULL,
  de              TEXT,
  para            TEXT,
  autor_id        VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  papel_do_banco  TEXT NOT NULL DEFAULT current_user,
  ocorrido_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE nsp_notificacoes_trilha IS
  'Trilha da Notificação de incidente (issue #1987): campo, de, para, quem e quando. Imutável: o banco recusa UPDATE e DELETE.';
COMMENT ON COLUMN nsp_notificacoes_trilha.papel_do_banco IS
  'O papel do banco que fez a edição: diz quem foi quando a edição não veio do aplicativo e não tem autor.';

CREATE INDEX IF NOT EXISTS idx_nsp_notificacoes_trilha_notificacao
  ON nsp_notificacoes_trilha (notificacao_id, ocorrido_em DESC);
CREATE INDEX IF NOT EXISTS idx_nsp_notificacoes_trilha_autor
  ON nsp_notificacoes_trilha (autor_id);

ALTER TABLE nsp_notificacoes_trilha ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION nsp_notificacoes_editar() RETURNS TRIGGER AS $$
DECLARE
  v_velha JSONB := to_jsonb(OLD);
  v_nova  JSONB := to_jsonb(NEW);
  v_campo TEXT;
BEGIN
  IF NEW.protocolo IS DISTINCT FROM OLD.protocolo
     OR NEW.ano IS DISTINCT FROM OLD.ano
     OR NEW.numero IS DISTINCT FROM OLD.numero
     OR NEW.criado_em IS DISTINCT FROM OLD.criado_em THEN
    RAISE EXCEPTION 'O protocolo e a data de registro da notificação não mudam'
      USING ERRCODE = 'check_violation';
  END IF;

  FOR v_campo IN SELECT jsonb_object_keys(v_nova) LOOP
    IF v_campo NOT IN ('editado_por', 'atualizado_em')
       AND (v_velha -> v_campo) IS DISTINCT FROM (v_nova -> v_campo) THEN
      INSERT INTO nsp_notificacoes_trilha (notificacao_id, campo, de, para, autor_id)
        VALUES (NEW.id, v_campo, v_velha ->> v_campo, v_nova ->> v_campo, NEW.editado_por);
    END IF;
  END LOOP;

  NEW.editado_por := NULL;
  NEW.atualizado_em := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_notificacoes_editar ON nsp_notificacoes;
CREATE TRIGGER trg_nsp_notificacoes_editar
  BEFORE UPDATE ON nsp_notificacoes
  FOR EACH ROW EXECUTE FUNCTION nsp_notificacoes_editar();

CREATE OR REPLACE FUNCTION nsp_notificacoes_trilha_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'A trilha da notificação é imutável: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql SET search_path = public;

DROP TRIGGER IF EXISTS trg_nsp_notificacoes_trilha_imutavel ON nsp_notificacoes_trilha;
CREATE TRIGGER trg_nsp_notificacoes_trilha_imutavel
  BEFORE UPDATE OR DELETE ON nsp_notificacoes_trilha
  FOR EACH ROW EXECUTE FUNCTION nsp_notificacoes_trilha_imutavel();

-- ---------- 5. O e-mail de caso aponta para a notificação ----------
ALTER TABLE nsp_avisos DROP CONSTRAINT IF EXISTS nsp_avisos_caso_id_fkey;
ALTER TABLE nsp_avisos
  ADD CONSTRAINT nsp_avisos_caso_id_fkey
  FOREIGN KEY (caso_id) REFERENCES nsp_notificacoes(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_nsp_avisos_caso ON nsp_avisos (caso_id);

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (174) ON CONFLICT (numero) DO NOTHING;
