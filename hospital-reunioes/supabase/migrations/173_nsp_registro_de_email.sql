-- =====================================================
-- Migration 173: o registro de e-mail do Núcleo, com retentativa
-- (issue #1985, PRD #1979, ADR 0107 decisão 8)
-- =====================================================
-- O registro dos avisos da Fase 1 (`nsp_avisos`, migration 158) vira o
-- registro único de e-mail do Núcleo. Todo e-mail nasce aqui antes de sair,
-- com a mensagem guardada (assunto, texto, modelo do HTML e o que o modelo
-- precisa), e um job de 10 em 10 minutos entrega o que já pode sair.
--
-- O que muda na tabela:
-- - `caso_id`: o caso do Núcleo, opcional. A chave estrangeira entra com a
--   tabela de casos (issue #1987); até lá a coluna fica vazia.
-- - `participacao_id` deixa de ser obrigatória: o e-mail de um caso não tem
--   Participação. Uma das duas tem de existir.
-- - `urgente`: sai na hora, fora da janela comercial. Os demais esperam a
--   abertura do expediente em `enviar_a_partir_de`.
-- - `tentativas` e `enviar_a_partir_de`: a falha do provedor devolve a linha à
--   fila com espera crescente; na terceira, a linha vira `falhou`.
-- - a situação ganha `enviando`: o job reivindica a linha antes de chamar o
--   provedor, e a rodada que cruza com outra não manda o mesmo e-mail.
-- - o marco ganha `convocacao` (a convocação das reuniões do Núcleo).
--
-- As linhas da Fase 1 continuam valendo como guarda do marco já avisado: sem
-- `enviar_a_partir_de`, nenhuma delas entra na fila.
--
-- Nenhuma pessoa entra por aqui. A tabela já tem RLS sem política: só o
-- backend, com a service_role, lê e grava. Rodar duas vezes é inofensivo.
-- Aplicar à mão no Studio.
-- =====================================================

BEGIN;

ALTER TABLE nsp_avisos ALTER COLUMN participacao_id DROP NOT NULL;

ALTER TABLE nsp_avisos
  ADD COLUMN IF NOT EXISTS caso_id            UUID,
  ADD COLUMN IF NOT EXISTS urgente            BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS tentativas         SMALLINT NOT NULL DEFAULT 0 CHECK (tentativas >= 0),
  ADD COLUMN IF NOT EXISTS enviar_a_partir_de TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS assunto            TEXT CHECK (assunto IS NULL OR char_length(assunto) <= 300),
  ADD COLUMN IF NOT EXISTS texto              TEXT CHECK (texto IS NULL OR char_length(texto) <= 10000),
  ADD COLUMN IF NOT EXISTS modelo             TEXT CHECK (modelo IS NULL OR modelo ~ '^email_nsp_[a-z_]+\.html$'),
  ADD COLUMN IF NOT EXISTS contexto           JSONB;

ALTER TABLE nsp_avisos DROP CONSTRAINT IF EXISTS nsp_avisos_participacao_ou_caso_check;
ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_participacao_ou_caso_check
  CHECK (participacao_id IS NOT NULL OR caso_id IS NOT NULL);

ALTER TABLE nsp_avisos DROP CONSTRAINT IF EXISTS nsp_avisos_situacao_check;
ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_situacao_check
  CHECK (situacao IN ('pendente', 'enviando', 'enviado', 'falhou'));

ALTER TABLE nsp_avisos DROP CONSTRAINT IF EXISTS nsp_avisos_marco_check;
ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_marco_check
  CHECK (marco IN ('documento_gerado', 'assinatura_3', 'assinatura_7', 'assinatura_14',
                   'vigencia_60', 'vigencia_30', 'fim_da_carencia', 'convocacao'));

-- A chave única da 158 não segura linha sem Participação (NULL não repete):
-- o e-mail de caso ganha a dele.
CREATE UNIQUE INDEX IF NOT EXISTS uq_nsp_avisos_caso
  ON nsp_avisos (caso_id, marco, referencia, destinatario_id)
  WHERE participacao_id IS NULL;

-- A fila que o job lê de 10 em 10 minutos.
CREATE INDEX IF NOT EXISTS idx_nsp_avisos_fila
  ON nsp_avisos (enviar_a_partir_de)
  WHERE situacao = 'pendente';

-- Os convocados da pauta: a convocação enviada de cada reunião, lida a cada
-- abertura (marco, referência e situação). Sem predicado parcial: o PostgREST
-- manda a situação como parâmetro, e o plano genérico não casaria com ele.
CREATE INDEX IF NOT EXISTS idx_nsp_avisos_marco_referencia
  ON nsp_avisos (marco, referencia, situacao);

COMMENT ON TABLE nsp_avisos IS
  'O registro único de e-mail do Núcleo: todo e-mail nasce aqui antes de sair, com retentativa e janela comercial. Issues #1770 e #1985.';
COMMENT ON COLUMN nsp_avisos.caso_id IS
  'O caso do Núcleo a que o e-mail se refere, quando houver. A chave estrangeira entra com a tabela de casos.';
COMMENT ON COLUMN nsp_avisos.enviar_a_partir_de IS
  'Quando a linha pode sair: a abertura do expediente para o que não é urgente, ou a próxima tentativa depois de uma falha.';
COMMENT ON COLUMN nsp_avisos.erro IS
  'Por que o último envio não saiu (sem e-mail no cadastro, recusa do provedor).';

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (173) ON CONFLICT (numero) DO NOTHING;
