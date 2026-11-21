-- =====================================================
-- Migration 175: Canal de Conduta, a fundação do sigilo
-- (issue #1820, PRD #1786, ADR 0097, decisões 1, 3, 4, 8, 9 e 10)
-- =====================================================
-- O que entra:
--   1. o Comitê de Conduta como o segundo Colegiado, sem nenhuma pessoa, e o
--      papel `coordenacao` na Participação;
--   2. o perfil do módulo no cadastro da pessoa (`perfil_conduta`): quem
--      cadastra membros. Não dá acesso a caso nenhum;
--   3. o caso: o conteúdo (relato) cifrado pela aplicação, os metadados de
--      lista e prazo em claro, o protocolo aleatório (sem sequência: a
--      numeração da Ouvidoria não é tocada) e o código de acompanhamento só
--      como hash;
--   4. a atribuição de pessoas a um caso (suplente convocado, apurador, CIPA,
--      grupo da Rota Especial) e o impedimento, e o Citado do caso;
--   5. a trilha do caso, em cadeia: cada linha carrega o código da anterior,
--      o banco recusa a linha que não aponta para a última do caso e recusa
--      UPDATE, DELETE e TRUNCATE;
--   6. o bucket privado dos arquivos do Canal, sem policy: o arquivo sai
--      cifrado e só pelo backend (decisão 2);
--   7. o Produto "Canal de Conduta" na aba Tecnologia.
--
-- RLS default-deny em toda tabela nova: só o backend, com a service_role, lê
-- e grava. Nenhuma policy de propósito.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. O Comitê e o papel da coordenação ----------
INSERT INTO colegiados (slug, nome) VALUES ('conduta', 'Comitê de Conduta')
ON CONFLICT (slug) DO NOTHING;

ALTER TABLE participacoes DROP CONSTRAINT IF EXISTS participacoes_papel_check;
ALTER TABLE participacoes
  ADD CONSTRAINT participacoes_papel_check
  CHECK (papel IN ('presidencia', 'suplente', 'membro', 'coordenacao'));

-- ---------- 2. O perfil do módulo ----------
ALTER TABLE participantes
  ADD COLUMN IF NOT EXISTS perfil_conduta TEXT;

ALTER TABLE participantes DROP CONSTRAINT IF EXISTS participantes_perfil_conduta_check;
ALTER TABLE participantes
  ADD CONSTRAINT participantes_perfil_conduta_check
  CHECK (perfil_conduta IS NULL OR perfil_conduta IN ('cadastro_de_membros'));

COMMENT ON COLUMN participantes.perfil_conduta IS
  'Canal de Conduta (ADR 0097, decisão 3): cadastro_de_membros = cadastra membros do Comitê, a pedido dele. Não abre caso. Super admin não herda.';

-- ---------- 3. O caso ----------
CREATE TABLE IF NOT EXISTS conduta_casos (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- Aleatório, gerado pelo backend. Sem DEFAULT de sequência de propósito.
  protocolo          TEXT NOT NULL UNIQUE CHECK (protocolo ~ '^CC-[A-Z0-9]{4}-[A-Z0-9]{4}$'),
  codigo_hash        TEXT NOT NULL,
  rota               TEXT NOT NULL DEFAULT 'comum' CHECK (rota IN ('comum', 'especial')),
  etapa              TEXT NOT NULL DEFAULT 'triagem',
  categoria          TEXT,
  recebido_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
  prazo_em           DATE,
  relato_cifrado     TEXT NOT NULL CHECK (relato_cifrado LIKE 'v1:%'),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE conduta_casos IS
  'Caso do Canal de Conduta (ADR 0097). O relato é cifrado pela aplicação; rota, etapa, categoria e datas ficam em claro para lista e prazo. Issue #1820.';
COMMENT ON COLUMN conduta_casos.protocolo IS
  'Protocolo aleatório, sem ordem nem contagem (ADR 0097, decisão 8).';
COMMENT ON COLUMN conduta_casos.codigo_hash IS
  'Hash com sal do código de acompanhamento, mostrado uma vez só a quem relatou.';

CREATE INDEX IF NOT EXISTS idx_conduta_casos_rota_etapa
  ON conduta_casos (rota, etapa, recebido_em DESC);

ALTER TABLE conduta_casos ENABLE ROW LEVEL SECURITY;

-- ---------- 4. Atribuição e Citado ----------
-- A Participação vigente (coordenação e membro, com Termo assinado) já é a
-- atribuição dos casos da fila comum. Aqui ficam as outras, caso a caso, e o
-- impedimento, que barra a pessoa naquele caso em qualquer perfil.
CREATE TABLE IF NOT EXISTS conduta_atribuicoes (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id            UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  participante_id    VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  motivo             TEXT NOT NULL CHECK (motivo IN ('membro_do_comite', 'suplente_convocado', 'apurador', 'cipa', 'grupo_especial')),
  termo_assinado_em  TIMESTAMPTZ,
  impedido_em        TIMESTAMPTZ,
  revogada_em        TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE conduta_atribuicoes IS
  'Quem foi designado num caso do Canal de Conduta, e o impedimento (ADR 0097, decisão 4). Issue #1820.';

CREATE INDEX IF NOT EXISTS idx_conduta_atribuicoes_pessoa
  ON conduta_atribuicoes (participante_id, caso_id);
CREATE INDEX IF NOT EXISTS idx_conduta_atribuicoes_caso
  ON conduta_atribuicoes (caso_id);

ALTER TABLE conduta_atribuicoes ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS conduta_citados (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id          UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  participante_id  VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  nome_cifrado     TEXT CHECK (nome_cifrado IS NULL OR nome_cifrado LIKE 'v1:%'),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT conduta_citados_quem_check CHECK (participante_id IS NOT NULL OR nome_cifrado IS NOT NULL)
);

COMMENT ON TABLE conduta_citados IS
  'Pessoa citada como envolvida num caso (ADR 0097, decisão 5). Ligada ao cadastro, o portão a barra em qualquer perfil. Issue #1820.';

CREATE INDEX IF NOT EXISTS idx_conduta_citados_pessoa
  ON conduta_citados (participante_id, caso_id);
CREATE INDEX IF NOT EXISTS idx_conduta_citados_caso
  ON conduta_citados (caso_id);

ALTER TABLE conduta_citados ENABLE ROW LEVEL SECURITY;

-- ---------- 5. A trilha em cadeia ----------
CREATE TABLE IF NOT EXISTS conduta_trilha (
  seq              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  caso_id          UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  -- Nulo quando quem age é a pessoa que relatou, que não tem login.
  autor_id         VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  acao             TEXT NOT NULL CHECK (btrim(acao) <> ''),
  detalhe          TEXT NOT NULL DEFAULT '',
  registrado_em    TIMESTAMPTZ NOT NULL,
  codigo_anterior  TEXT,
  codigo           TEXT NOT NULL UNIQUE CHECK (codigo ~ '^[0-9a-f]{64}$')
);

COMMENT ON TABLE conduta_trilha IS
  'Trilha do caso do Canal de Conduta (ADR 0097, decisão 9): quem, quando e o quê. Cada linha carrega o código da anterior do mesmo caso. Imutável. Issue #1820.';

CREATE INDEX IF NOT EXISTS idx_conduta_trilha_caso
  ON conduta_trilha (caso_id, seq DESC);
CREATE INDEX IF NOT EXISTS idx_conduta_trilha_autor
  ON conduta_trilha (autor_id);

ALTER TABLE conduta_trilha ENABLE ROW LEVEL SECURITY;

-- A linha nova tem que apontar para a última do caso. A trava por caso
-- enfileira duas gravações simultâneas: a segunda espera, vê a primeira e é
-- recusada, e o backend refaz com o código certo.
CREATE OR REPLACE FUNCTION conduta_trilha_encadeada() RETURNS TRIGGER AS $$
DECLARE
  ultimo TEXT;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.caso_id::text, 1820));
  SELECT codigo INTO ultimo
    FROM conduta_trilha
   WHERE caso_id = NEW.caso_id
   ORDER BY seq DESC
   LIMIT 1;
  IF NEW.codigo_anterior IS DISTINCT FROM ultimo THEN
    RAISE EXCEPTION 'A trilha do caso é uma cadeia: a linha nova não aponta para a última'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_trilha_encadeada ON conduta_trilha;
CREATE TRIGGER trg_conduta_trilha_encadeada
  BEFORE INSERT ON conduta_trilha
  FOR EACH ROW EXECUTE FUNCTION conduta_trilha_encadeada();

CREATE OR REPLACE FUNCTION conduta_trilha_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'A trilha do caso é imutável: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_trilha_imutavel ON conduta_trilha;
CREATE TRIGGER trg_conduta_trilha_imutavel
  BEFORE UPDATE OR DELETE ON conduta_trilha
  FOR EACH ROW EXECUTE FUNCTION conduta_trilha_imutavel();

DROP TRIGGER IF EXISTS trg_conduta_trilha_sem_truncate ON conduta_trilha;
CREATE TRIGGER trg_conduta_trilha_sem_truncate
  BEFORE TRUNCATE ON conduta_trilha
  FOR EACH STATEMENT EXECUTE FUNCTION conduta_trilha_imutavel();

-- ---------- 6. O bucket privado ----------
-- Sem policy para `authenticated` e sem URL assinada: o backend confere o
-- acesso, decifra e entrega. 300 MB cabem um depoimento de duas horas.
INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('conduta-arquivos', 'conduta-arquivos', false, 314572800)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Authenticated Access conduta-arquivos" ON storage.objects;

-- ---------- 7. O Produto na aba Tecnologia ----------
INSERT INTO tecnologia_produtos (nome, ordem) VALUES
  ('Canal de Conduta', (SELECT COALESCE(MAX(ordem), 0) + 1 FROM tecnologia_produtos))
ON CONFLICT DO NOTHING;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (175) ON CONFLICT (numero) DO NOTHING;
