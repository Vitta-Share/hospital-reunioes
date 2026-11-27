-- =====================================================
-- Migration 242: Canal de Conduta, o papel original, a guarda, o congelamento
-- e a eliminação do caso (issue #1838, PRD #1786, ADR 0097; especificação,
-- seções 9.3 e 9.4 e Anexo E.2)
-- =====================================================
-- O que entra:
--   1. o lacre do envelope com os originais em papel: quem lacrou, a data e o
--      local de guarda. Só depois do encerramento, e gravado não muda;
--   2. o congelamento do caso pela coordenação (processo judicial ou
--      administrativo): caso congelado não é eliminado;
--   3. a eliminação do conteúdo ao fim da guarda (cinco anos do encerramento;
--      um ano para o encaminhado), pela função
--      `conduta_eliminar_conteudo_do_caso`, a única porta. Ela confere o prazo
--      pelo relógio do banco, recusa o caso congelado e apaga tudo o que é
--      conteúdo do caso: relato, nome de quem relatou, anexos do relato,
--      mensagens, depoimentos, termos, votos, atas, relatórios, retornos,
--      verificações de retaliação, assinaturas, notas, os nomes dos Citados.
--      Ficam os metadados
--      (protocolo, rito, datas), a trilha, as atribuições, os prazos vencidos
--      e os avisos. Os arquivos do bucket saem pelo backend antes;
--   4. a marca do aviso de vencimento da guarda do papel, mandado uma vez só à
--      coordenação.
--
-- As tabelas do conteúdo recusam UPDATE e DELETE por gatilho. A função
-- desliga os gatilhos de usuário só dentro da própria transação (ALTER TABLE
-- é transacional) e os religa antes de terminar; as chaves estrangeiras
-- continuam valendo. Só a service_role executa a função.
-- Nenhuma tabela nova e nenhuma policy nova: RLS segue default-deny.
-- Rodar duas vezes é inofensivo. Aplicar à mão no Studio.
-- =====================================================

BEGIN;

-- ---------- 1. O lacre do envelope ----------
ALTER TABLE conduta_casos
  ADD COLUMN IF NOT EXISTS papel_lacrado_por   VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS papel_lacrado_em    DATE,
  ADD COLUMN IF NOT EXISTS papel_local         TEXT,
  ADD COLUMN IF NOT EXISTS congelado_em        TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS congelado_por       VARCHAR(10) REFERENCES participantes(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS eliminado_em        TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS guarda_avisada_em   TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_conduta_casos_papel_lacrado_por ON conduta_casos (papel_lacrado_por);
CREATE INDEX IF NOT EXISTS idx_conduta_casos_congelado_por ON conduta_casos (congelado_por);

-- O job diário procura os casos encerrados que ainda têm conteúdo.
CREATE INDEX IF NOT EXISTS idx_conduta_casos_em_guarda
  ON conduta_casos (encerrado_em) WHERE encerrado_em IS NOT NULL AND eliminado_em IS NULL;

ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_lacre_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_lacre_check
  CHECK (
    (papel_lacrado_em IS NULL AND papel_lacrado_por IS NULL AND papel_local IS NULL)
    OR (
      papel_lacrado_em IS NOT NULL AND papel_lacrado_por IS NOT NULL
      AND btrim(COALESCE(papel_local, '')) <> '' AND encerrado_em IS NOT NULL
    )
  );

COMMENT ON COLUMN conduta_casos.papel_lacrado_em IS
  'Dia em que o envelope com os originais em papel foi lacrado (issue #1838). Com quem lacrou e o local de guarda. Gravado não muda.';
COMMENT ON COLUMN conduta_casos.papel_local IS
  'Onde o envelope lacrado fica guardado. Sem nome de pessoa (issue #1838).';

CREATE OR REPLACE FUNCTION conduta_lacre_gravado() RETURNS TRIGGER AS $$
BEGIN
  IF OLD.papel_lacrado_em IS NOT NULL AND (
       NEW.papel_lacrado_em IS DISTINCT FROM OLD.papel_lacrado_em
       OR NEW.papel_lacrado_por IS DISTINCT FROM OLD.papel_lacrado_por
       OR NEW.papel_local IS DISTINCT FROM OLD.papel_local
     ) THEN
    RAISE EXCEPTION 'O lacre do envelope, uma vez registrado, não muda'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conduta_lacre_gravado ON conduta_casos;
CREATE TRIGGER trg_conduta_lacre_gravado
  BEFORE UPDATE OF papel_lacrado_em, papel_lacrado_por, papel_local ON conduta_casos
  FOR EACH ROW EXECUTE FUNCTION conduta_lacre_gravado();

-- ---------- 2. O congelamento ----------
-- Congelado não se elimina; eliminado não se congela.
ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_congelado_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_congelado_check
  CHECK (
    (congelado_em IS NULL) = (congelado_por IS NULL)
    AND (congelado_em IS NULL OR eliminado_em IS NULL)
  );

COMMENT ON COLUMN conduta_casos.congelado_em IS
  'Caso congelado pela coordenação, por processo judicial ou administrativo (issue #1838). Suspende a eliminação. Descongelar volta a NULL.';

-- ---------- 3. A eliminação ----------
-- O relato some na eliminação; antes dela, é obrigatório.
ALTER TABLE conduta_casos ALTER COLUMN relato_cifrado DROP NOT NULL;
ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_relato_ou_eliminado_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_relato_ou_eliminado_check
  CHECK (relato_cifrado IS NOT NULL OR eliminado_em IS NOT NULL);

-- A prorrogação continua registrada (a data), sem a justificativa.
ALTER TABLE conduta_casos DROP CONSTRAINT IF EXISTS conduta_casos_prorrogacao_check;
ALTER TABLE conduta_casos
  ADD CONSTRAINT conduta_casos_prorrogacao_check
  CHECK (
    prorrogado_em IS NULL
    OR eliminado_em IS NOT NULL
    OR (
      prorrogacao_cifrada LIKE 'v1:%'
      AND (rito = 'completo' OR (rito = 'especial' AND desviado_em IS NOT NULL))
    )
  );

COMMENT ON COLUMN conduta_casos.eliminado_em IS
  'Quando o conteúdo do caso foi eliminado ao fim da guarda (issue #1838). Só pela função conduta_eliminar_conteudo_do_caso. Os metadados e a trilha ficam.';
COMMENT ON COLUMN conduta_casos.guarda_avisada_em IS
  'Quando a coordenação foi avisada do vencimento da guarda do papel (issue #1838). Uma vez só.';

CREATE OR REPLACE FUNCTION conduta_eliminar_conteudo_do_caso(p_caso_id UUID)
RETURNS TIMESTAMPTZ
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  caso conduta_casos%ROWTYPE;
  hoje DATE := (now() AT TIME ZONE 'America/Sao_Paulo')::date;
  guardar_ate DATE;
  tabela TEXT;
  -- Toda tabela de onde sai conteúdo do caso.
  tabelas TEXT[] := ARRAY[
    'conduta_casos',
    'conduta_assinaturas',
    'conduta_depoimento_arquivos',
    'conduta_depoimento_conferencia',
    'conduta_depoimento_termos',
    'conduta_depoimentos',
    'conduta_contestacao_votos',
    'conduta_contestacoes',
    'conduta_participacao_votos',
    'conduta_contestacoes_de_participacao',
    'conduta_sugestao_respostas',
    'conduta_sugestoes',
    'conduta_afastamentos',
    'conduta_citados',
    'conduta_notas_nsp',
    'conduta_relatorios',
    'conduta_selos',
    'conduta_entregas_do_parecer',
    'conduta_votos',
    'conduta_trava_preenchimentos',
    'conduta_trava_confirmacoes',
    'conduta_ciencias_do_codigo',
    'conduta_atas',
    'conduta_reuniao_transcricoes',
    'conduta_reuniao_conferencia',
    'conduta_retornos',
    'conduta_decisoes_da_medida',
    'conduta_comunicacoes_da_medida',
    'conduta_correcoes_sugeridas',
    'conduta_correcoes',
    'conduta_relato_anexos',
    'conduta_mensagens',
    'conduta_verificacoes_de_retaliacao'
  ];
BEGIN
  SELECT * INTO caso FROM conduta_casos WHERE id = p_caso_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Caso do Canal de Conduta inexistente' USING ERRCODE = 'no_data_found';
  END IF;
  IF caso.eliminado_em IS NOT NULL THEN
    RETURN caso.eliminado_em;
  END IF;
  IF caso.congelado_em IS NOT NULL THEN
    RAISE EXCEPTION 'Caso congelado não é eliminado' USING ERRCODE = 'check_violation';
  END IF;
  IF caso.encerrado_em IS NULL THEN
    RAISE EXCEPTION 'Só o caso encerrado é eliminado' USING ERRCODE = 'check_violation';
  END IF;
  guardar_ate := (
    (caso.encerrado_em AT TIME ZONE 'America/Sao_Paulo')::date
    + CASE WHEN caso.desfecho = 'encaminhado' THEN interval '1 year' ELSE interval '5 years' END
  )::date;
  IF hoje <= guardar_ate THEN
    RAISE EXCEPTION 'A guarda do caso vai até %', guardar_ate USING ERRCODE = 'check_violation';
  END IF;

  FOREACH tabela IN ARRAY tabelas LOOP
    EXECUTE format('ALTER TABLE %I DISABLE TRIGGER USER', tabela);
  END LOOP;

  UPDATE conduta_casos
     SET relato_cifrado = NULL,
         relator_nome_cifrado = NULL,
         prorrogacao_cifrada = NULL,
         orientacao_cifrada = NULL,
         medida_cifrada = NULL,
         retorno_aprovado_id = NULL,
         eliminado_em = now()
   WHERE id = p_caso_id;

  DELETE FROM conduta_assinaturas WHERE caso_id = p_caso_id;
  DELETE FROM conduta_depoimento_arquivos
   WHERE depoimento_id IN (SELECT id FROM conduta_depoimentos WHERE caso_id = p_caso_id);
  DELETE FROM conduta_depoimento_conferencia
   WHERE depoimento_id IN (SELECT id FROM conduta_depoimentos WHERE caso_id = p_caso_id);
  DELETE FROM conduta_depoimento_termos
   WHERE depoimento_id IN (SELECT id FROM conduta_depoimentos WHERE caso_id = p_caso_id);
  DELETE FROM conduta_depoimentos WHERE caso_id = p_caso_id;
  DELETE FROM conduta_contestacao_votos
   WHERE contestacao_id IN (SELECT id FROM conduta_contestacoes WHERE caso_id = p_caso_id);
  DELETE FROM conduta_contestacoes WHERE caso_id = p_caso_id;
  DELETE FROM conduta_participacao_votos
   WHERE contestacao_id IN (SELECT id FROM conduta_contestacoes_de_participacao WHERE caso_id = p_caso_id);
  DELETE FROM conduta_contestacoes_de_participacao WHERE caso_id = p_caso_id;
  DELETE FROM conduta_sugestao_respostas WHERE caso_id = p_caso_id;
  DELETE FROM conduta_sugestoes WHERE caso_id = p_caso_id;
  DELETE FROM conduta_afastamentos WHERE caso_id = p_caso_id;
  -- O Citado ligado ao cadastro continua barrado no caso; o nome some.
  DELETE FROM conduta_citados WHERE caso_id = p_caso_id AND participante_id IS NULL;
  UPDATE conduta_citados SET nome_cifrado = NULL WHERE caso_id = p_caso_id;
  DELETE FROM conduta_notas_nsp WHERE caso_id = p_caso_id;
  DELETE FROM conduta_relatorios WHERE caso_id = p_caso_id;
  DELETE FROM conduta_selos WHERE caso_id = p_caso_id;
  DELETE FROM conduta_entregas_do_parecer WHERE caso_id = p_caso_id;
  DELETE FROM conduta_votos WHERE caso_id = p_caso_id;
  DELETE FROM conduta_trava_preenchimentos WHERE caso_id = p_caso_id;
  DELETE FROM conduta_trava_confirmacoes WHERE caso_id = p_caso_id;
  DELETE FROM conduta_ciencias_do_codigo WHERE caso_id = p_caso_id;
  DELETE FROM conduta_atas WHERE caso_id = p_caso_id;
  DELETE FROM conduta_reuniao_transcricoes WHERE caso_id = p_caso_id;
  DELETE FROM conduta_reuniao_conferencia WHERE caso_id = p_caso_id;
  DELETE FROM conduta_comunicacoes_da_medida WHERE caso_id = p_caso_id;
  DELETE FROM conduta_decisoes_da_medida WHERE caso_id = p_caso_id;
  DELETE FROM conduta_retornos WHERE caso_id = p_caso_id;
  DELETE FROM conduta_correcoes WHERE caso_id = p_caso_id;
  DELETE FROM conduta_correcoes_sugeridas WHERE caso_id = p_caso_id;
  DELETE FROM conduta_relato_anexos WHERE caso_id = p_caso_id;
  DELETE FROM conduta_mensagens WHERE caso_id = p_caso_id;
  DELETE FROM conduta_verificacoes_de_retaliacao WHERE caso_id = p_caso_id;

  FOREACH tabela IN ARRAY tabelas LOOP
    EXECUTE format('ALTER TABLE %I ENABLE TRIGGER USER', tabela);
  END LOOP;

  RETURN now();
END;
$$;

COMMENT ON FUNCTION conduta_eliminar_conteudo_do_caso(UUID) IS
  'Elimina o conteúdo do caso do Canal de Conduta ao fim da guarda (issue #1838): confere o prazo, recusa o congelado, apaga o conteúdo e marca eliminado_em. A trilha fica.';

REVOKE ALL ON FUNCTION conduta_eliminar_conteudo_do_caso(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION conduta_eliminar_conteudo_do_caso(UUID) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION conduta_eliminar_conteudo_do_caso(UUID) TO service_role;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (242) ON CONFLICT (numero) DO NOTHING;
