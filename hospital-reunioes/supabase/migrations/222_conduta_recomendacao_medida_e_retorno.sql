-- =====================================================
-- Migration 222: Canal de Conduta, a Recomendação do Comitê, a decisão da
-- medida e o retorno (issue #1835, PRD #1786, ADR 0097; especificação, 6.8,
-- 6.9 e 6.10)
-- =====================================================
-- O que entra:
--   1. os dois perfis nominais da Direção no cadastro da pessoa: o Presidente,
--      que só lê a Recomendação do Comitê, e a diretoria executiva, que lê e
--      registra a decisão do Presidente sobre a medida;
--   2. no caso, "ENVIAR À DIREÇÃO": quem enviou e quando. Só sai caso da fila
--      comum, na etapa Ata, com resultado procedente ou parcialmente
--      procedente. Improcedente e inconclusivo nunca saem do Comitê;
--   3. a decisão da medida, uma por caso: Aplicada, Aplicada com ajuste ou
--      Não aplicada, com a data da decisão e, nas duas últimas, a
--      justificativa cifrada. Só na etapa Medida, e não muda;
--   4. a cópia da comunicação da medida, cifrada no bucket do Canal, em
--      versões que não mudam, depois de uma decisão que aplica a medida;
--   5. o retorno: a resposta a quem relatou e a comunicação ao acusado, em
--      versões cifradas (a do agente e as da coordenação), e no caso a versão
--      aprovada, quem aprovou e quando. Aprovado, não muda;
--   6. a correção de processo: as sugestões do agente, em versões cifradas,
--      e a correção escolhida pelo Comitê, com responsável e prazo. Só em caso
--      procedente ou parcialmente procedente;
--   7. o desfecho `concluido`, o encerramento depois do retorno aprovado.
--
-- RLS default-deny em toda tabela nova: só o backend, com a service_role, lê
-- e grava. Nenhuma policy de propósito. Nenhum dado de pessoa em claro.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. Os perfis da Direção ----------
ALTER TABLE participantes DROP CONSTRAINT IF EXISTS participantes_perfil_conduta_check;
ALTER TABLE participantes
  ADD CONSTRAINT participantes_perfil_conduta_check
  CHECK (perfil_conduta IS NULL OR perfil_conduta IN ('cadastro_de_membros', 'presidente', 'diretoria_executiva'));

COMMENT ON COLUMN participantes.perfil_conduta IS
  'Canal de Conduta (ADR 0097, decisão 3; issue #1835): cadastro_de_membros = cadastra membros do Comitê, a pedido dele; presidente = só lê a Recomendação do Comitê; diretoria_executiva = lê a Recomendação e registra a decisão da medida. Nenhum abre caso. Super admin não herda.';

-- ---------- 7. O desfecho do caso concluído ----------
ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_desfecho_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_desfecho_check
  CHECK (desfecho IS NULL OR desfecho IN ('encaminhado', 'parecer_entregue', 'concluido'));

-- A recusa de UPDATE e DELETE das tabelas guardadas desta migration.
CREATE OR REPLACE FUNCTION conduta_retorno_imutavel() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'O registro da medida e do retorno fica guardado: % não é permitido', TG_OP
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

-- ---------- 5. O retorno, em versões ----------
CREATE TABLE IF NOT EXISTS conduta_retornos (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id              UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  versao               INTEGER NOT NULL CHECK (versao >= 1),
  denunciante_cifrado  TEXT NOT NULL CHECK (denunciante_cifrado LIKE 'v1:%'),
  acusado_cifrado      TEXT NOT NULL CHECK (acusado_cifrado LIKE 'v1:%'),
  origem               TEXT NOT NULL CHECK (origem IN ('agente', 'coordenacao')),
  autor_id             VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  criado_em            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, versao)
);

COMMENT ON TABLE conduta_retornos IS
  'Retorno do caso do Canal de Conduta (issue #1835): a resposta a quem relatou e a comunicação ao acusado, cifradas. Só saem com a versão aprovada pela coordenação. Imutável: editar é versão nova.';

CREATE INDEX IF NOT EXISTS idx_conduta_retornos_autor ON conduta_retornos (autor_id);

ALTER TABLE conduta_retornos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_retornos FROM anon, authenticated;

DROP TRIGGER IF EXISTS trg_conduta_retornos_imutaveis ON conduta_retornos;
CREATE TRIGGER trg_conduta_retornos_imutaveis
  BEFORE UPDATE OR DELETE ON conduta_retornos
  FOR EACH ROW EXECUTE FUNCTION conduta_retorno_imutavel();

-- O retorno é da etapa Retorno, ou da Ata quando o resultado não leva medida,
-- e não ganha versão depois de aprovado.
CREATE OR REPLACE FUNCTION conduta_retorno_em_aberto() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM conduta_casos
        WHERE id = NEW.caso_id AND encerrado_em IS NULL AND retorno_aprovado_id IS NULL
          AND (etapa = 'retorno' OR (etapa = 'ata' AND resultado IN ('improcedente', 'inconclusivo')))
     ) THEN
    RAISE EXCEPTION 'O retorno é da etapa Retorno e não muda depois de aprovado'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_retornos_em_aberto ON conduta_retornos;
CREATE TRIGGER trg_conduta_retornos_em_aberto
  BEFORE INSERT ON conduta_retornos
  FOR EACH ROW EXECUTE FUNCTION conduta_retorno_em_aberto();

-- ---------- 2 e 5. No caso: o envio à Direção e o retorno aprovado ----------
ALTER TABLE conduta_casos
  ADD COLUMN IF NOT EXISTS enviado_a_direcao_em   TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS enviado_a_direcao_por  VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS retorno_aprovado_id    UUID REFERENCES conduta_retornos(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS retorno_aprovado_em    TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS retorno_aprovado_por   VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT;

COMMENT ON COLUMN conduta_casos.enviado_a_direcao_em IS
  'ENVIAR À DIREÇÃO (issue #1835): libera a Recomendação do Comitê ao Presidente e à diretoria executiva. Só procedente ou parcialmente procedente, da fila comum. Gravado, não muda.';
COMMENT ON COLUMN conduta_casos.retorno_aprovado_id IS
  'A versão do retorno aprovada pela coordenação (issue #1835). Só ela sai: a resposta vai à página de acompanhamento, e a comunicação ao acusado é entregue. Gravada, não muda.';

CREATE INDEX IF NOT EXISTS idx_conduta_casos_enviado_a_direcao_por ON conduta_casos (enviado_a_direcao_por);
CREATE INDEX IF NOT EXISTS idx_conduta_casos_retorno_aprovado_id ON conduta_casos (retorno_aprovado_id);
CREATE INDEX IF NOT EXISTS idx_conduta_casos_retorno_aprovado_por ON conduta_casos (retorno_aprovado_por);

-- ---------- 3. A decisão da medida ----------
CREATE TABLE IF NOT EXISTS conduta_decisoes_da_medida (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id                UUID NOT NULL UNIQUE REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  decisao                TEXT NOT NULL CHECK (decisao IN ('aplicada', 'aplicada_com_ajuste', 'nao_aplicada')),
  justificativa_cifrada  TEXT CHECK (justificativa_cifrada IS NULL OR justificativa_cifrada LIKE 'v1:%'),
  decidida_em            DATE NOT NULL,
  registrada_por         VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  registrada_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT conduta_decisoes_da_medida_justificativa CHECK (decisao = 'aplicada' OR justificativa_cifrada IS NOT NULL)
);

COMMENT ON TABLE conduta_decisoes_da_medida IS
  'A decisão do Presidente sobre a medida recomendada, registrada pela diretoria executiva (issue #1835; especificação, 6.8). Com ajuste e não aplicada levam justificativa cifrada. Uma por caso. Imutável.';

CREATE INDEX IF NOT EXISTS idx_conduta_decisoes_da_medida_registrada_por ON conduta_decisoes_da_medida (registrada_por);

ALTER TABLE conduta_decisoes_da_medida ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_decisoes_da_medida FROM anon, authenticated;

DROP TRIGGER IF EXISTS trg_conduta_decisoes_da_medida_imutaveis ON conduta_decisoes_da_medida;
CREATE TRIGGER trg_conduta_decisoes_da_medida_imutaveis
  BEFORE UPDATE OR DELETE ON conduta_decisoes_da_medida
  FOR EACH ROW EXECUTE FUNCTION conduta_retorno_imutavel();

CREATE OR REPLACE FUNCTION conduta_decisao_na_etapa_medida() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM conduta_casos
        WHERE id = NEW.caso_id AND etapa = 'medida' AND enviado_a_direcao_em IS NOT NULL
     ) THEN
    RAISE EXCEPTION 'A decisão da medida é da etapa Medida, depois do envio à Direção'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_decisoes_da_medida_na_etapa ON conduta_decisoes_da_medida;
CREATE TRIGGER trg_conduta_decisoes_da_medida_na_etapa
  BEFORE INSERT ON conduta_decisoes_da_medida
  FOR EACH ROW EXECUTE FUNCTION conduta_decisao_na_etapa_medida();

-- ---------- 4. A cópia da comunicação da medida ----------
CREATE TABLE IF NOT EXISTS conduta_comunicacoes_da_medida (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id        UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  versao         INTEGER NOT NULL CHECK (versao >= 1),
  storage_path   TEXT NOT NULL CHECK (btrim(storage_path) <> ''),
  content_type   TEXT NOT NULL,
  tamanho_bytes  BIGINT NOT NULL CHECK (tamanho_bytes > 0),
  enviado_por    VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  enviado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, versao)
);

COMMENT ON TABLE conduta_comunicacoes_da_medida IS
  'Cópia da comunicação da medida que o DP fez fora do aplicativo (issue #1835; especificação, 6.8). Arquivo cifrado no bucket do Canal. Imutável: correção é versão nova.';

CREATE INDEX IF NOT EXISTS idx_conduta_comunicacoes_da_medida_enviado_por ON conduta_comunicacoes_da_medida (enviado_por);

ALTER TABLE conduta_comunicacoes_da_medida ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_comunicacoes_da_medida FROM anon, authenticated;

DROP TRIGGER IF EXISTS trg_conduta_comunicacoes_da_medida_imutaveis ON conduta_comunicacoes_da_medida;
CREATE TRIGGER trg_conduta_comunicacoes_da_medida_imutaveis
  BEFORE UPDATE OR DELETE ON conduta_comunicacoes_da_medida
  FOR EACH ROW EXECUTE FUNCTION conduta_retorno_imutavel();

CREATE OR REPLACE FUNCTION conduta_comunicacao_com_medida_aplicada() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM conduta_decisoes_da_medida
        WHERE caso_id = NEW.caso_id AND decisao IN ('aplicada', 'aplicada_com_ajuste')
     ) THEN
    RAISE EXCEPTION 'A comunicação da medida vem depois da decisão que aplica a medida'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_comunicacoes_da_medida_aplicada ON conduta_comunicacoes_da_medida;
CREATE TRIGGER trg_conduta_comunicacoes_da_medida_aplicada
  BEFORE INSERT ON conduta_comunicacoes_da_medida
  FOR EACH ROW EXECUTE FUNCTION conduta_comunicacao_com_medida_aplicada();

-- ---------- 6. A correção de processo ----------
CREATE TABLE IF NOT EXISTS conduta_correcoes_sugeridas (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id        UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  versao         INTEGER NOT NULL CHECK (versao >= 1),
  itens_cifrado  TEXT NOT NULL CHECK (itens_cifrado LIKE 'v1:%'),
  autor_id       VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (caso_id, versao)
);

COMMENT ON TABLE conduta_correcoes_sugeridas IS
  'De uma a três correções de processo sugeridas pelo agente, depois do clique de um membro (issue #1835; especificação, 6.10). Sugestão, cifrada. Imutável.';

CREATE INDEX IF NOT EXISTS idx_conduta_correcoes_sugeridas_autor ON conduta_correcoes_sugeridas (autor_id);

ALTER TABLE conduta_correcoes_sugeridas ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_correcoes_sugeridas FROM anon, authenticated;

CREATE TABLE IF NOT EXISTS conduta_correcoes (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id              UUID NOT NULL REFERENCES conduta_casos(id) ON DELETE RESTRICT,
  texto_cifrado        TEXT NOT NULL CHECK (texto_cifrado LIKE 'v1:%'),
  responsavel_cifrado  TEXT NOT NULL CHECK (responsavel_cifrado LIKE 'v1:%'),
  prazo_em             DATE NOT NULL,
  escolhida_por        VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  escolhida_em         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE conduta_correcoes IS
  'A correção de processo escolhida pelo Comitê, com responsável e prazo (issue #1835; especificação, 6.10). Cifrada. Imutável.';

CREATE INDEX IF NOT EXISTS idx_conduta_correcoes_caso ON conduta_correcoes (caso_id);
CREATE INDEX IF NOT EXISTS idx_conduta_correcoes_escolhida_por ON conduta_correcoes (escolhida_por);

ALTER TABLE conduta_correcoes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON conduta_correcoes FROM anon, authenticated;

DROP TRIGGER IF EXISTS trg_conduta_correcoes_sugeridas_imutaveis ON conduta_correcoes_sugeridas;
CREATE TRIGGER trg_conduta_correcoes_sugeridas_imutaveis
  BEFORE UPDATE OR DELETE ON conduta_correcoes_sugeridas
  FOR EACH ROW EXECUTE FUNCTION conduta_retorno_imutavel();

DROP TRIGGER IF EXISTS trg_conduta_correcoes_imutaveis ON conduta_correcoes;
CREATE TRIGGER trg_conduta_correcoes_imutaveis
  BEFORE UPDATE OR DELETE ON conduta_correcoes
  FOR EACH ROW EXECUTE FUNCTION conduta_retorno_imutavel();

CREATE OR REPLACE FUNCTION conduta_correcao_do_procedente() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM conduta_casos
        WHERE id = NEW.caso_id AND encerrado_em IS NULL
          AND resultado IN ('procedente', 'parcialmente_procedente')
     ) THEN
    RAISE EXCEPTION 'A correção de processo é do caso procedente, antes do encerramento'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_correcoes_sugeridas_do_procedente ON conduta_correcoes_sugeridas;
CREATE TRIGGER trg_conduta_correcoes_sugeridas_do_procedente
  BEFORE INSERT ON conduta_correcoes_sugeridas
  FOR EACH ROW EXECUTE FUNCTION conduta_correcao_do_procedente();

DROP TRIGGER IF EXISTS trg_conduta_correcoes_do_procedente ON conduta_correcoes;
CREATE TRIGGER trg_conduta_correcoes_do_procedente
  BEFORE INSERT ON conduta_correcoes
  FOR EACH ROW EXECUTE FUNCTION conduta_correcao_do_procedente();

-- ---------- O caminho do caso depois da Ata ----------
-- Só sai do Comitê o procedente da fila comum; a Medida só termina com a
-- decisão registrada; o retorno aprovado é a última versão do caso e, no
-- procedente, vem depois da decisão e de uma correção escolhida.
CREATE OR REPLACE FUNCTION conduta_caminho_depois_da_ata() RETURNS TRIGGER AS $$
BEGIN
  IF OLD.enviado_a_direcao_em IS NOT NULL AND NEW.enviado_a_direcao_em IS DISTINCT FROM OLD.enviado_a_direcao_em THEN
    RAISE EXCEPTION 'O envio à Direção gravado não muda'
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.enviado_a_direcao_em IS NULL AND NEW.enviado_a_direcao_em IS NOT NULL AND (
       OLD.etapa IS DISTINCT FROM 'ata'
       OR NEW.rota IS DISTINCT FROM 'comum'
       OR NEW.resultado IS NULL
       OR NEW.resultado NOT IN ('procedente', 'parcialmente_procedente')
     ) THEN
    RAISE EXCEPTION 'Só o caso procedente da fila comum, na etapa Ata, vai à Direção'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.etapa = 'medida' AND OLD.etapa IS DISTINCT FROM 'medida' AND NEW.enviado_a_direcao_em IS NULL THEN
    RAISE EXCEPTION 'A etapa Medida começa com o envio à Direção'
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.etapa = 'medida' AND NEW.etapa IS DISTINCT FROM 'medida'
     AND NOT EXISTS (SELECT 1 FROM conduta_decisoes_da_medida WHERE caso_id = NEW.id) THEN
    RAISE EXCEPTION 'A etapa Medida termina com a decisão registrada'
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.retorno_aprovado_id IS NOT NULL AND NEW.retorno_aprovado_id IS DISTINCT FROM OLD.retorno_aprovado_id THEN
    RAISE EXCEPTION 'O retorno aprovado não muda'
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.retorno_aprovado_id IS NULL AND NEW.retorno_aprovado_id IS NOT NULL THEN
    IF NEW.retorno_aprovado_id IS DISTINCT FROM (
         SELECT r.id FROM conduta_retornos r WHERE r.caso_id = NEW.id ORDER BY r.versao DESC LIMIT 1
       ) THEN
      RAISE EXCEPTION 'Só a última versão do retorno do caso é aprovada'
        USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.resultado IN ('procedente', 'parcialmente_procedente') AND (
         NOT EXISTS (SELECT 1 FROM conduta_decisoes_da_medida WHERE caso_id = NEW.id)
         OR NOT EXISTS (SELECT 1 FROM conduta_correcoes WHERE caso_id = NEW.id)
       ) THEN
      RAISE EXCEPTION 'No caso procedente, o retorno vem depois da decisão da medida e da correção de processo'
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_caminho_depois_da_ata ON conduta_casos;
CREATE TRIGGER trg_conduta_caminho_depois_da_ata
  BEFORE UPDATE OF enviado_a_direcao_em, etapa, retorno_aprovado_id ON conduta_casos
  FOR EACH ROW EXECUTE FUNCTION conduta_caminho_depois_da_ata();

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (222) ON CONFLICT (numero) DO NOTHING;
