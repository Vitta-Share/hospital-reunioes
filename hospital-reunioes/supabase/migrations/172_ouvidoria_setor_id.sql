-- =====================================================
-- Migration 172: o setor da manifestação aponta para a tabela de setores
-- (issue #1983, ADR 0095 decisão 2)
--
-- A manifestação da Ouvidoria guarda o setor só em texto desde a 063. O
-- Núcleo de Segurança do Paciente conta por setor do cadastro, então o caso
-- que a Ouvidoria manda a ele precisa do mesmo setor. A manifestação ganha o
-- par que a Reunião ganhou na 168: `setor_id` como FK para `setores`, com a
-- TEXT mantida como está. Toda porta que grava o setor passa a gravar o id
-- junto (registro manual, canal aberto, Ana, conversão de avaliação,
-- validação, ciência do elogio e reacionamento).
--
-- Backfill: os casos existentes ganham o id casando por `lower(trim(nome))`,
-- sem diferença de maiúscula, contra todos os setores, ativos ou não: o caso
-- antigo de um setor desativado continua sendo daquele setor. O `lower` roda
-- na colação ICU neutra para "RECEPÇÃO" virar "recepção" em qualquer locale
-- do banco: na colação C ele só baixa as letras sem acento.
--
-- Relatório: o bloco DO do fim lista, por RAISE NOTICE, cada nome que não
-- casou com nenhum setor e os protocolos dele. Esses casos ficam com o id
-- vazio e nada quebra. O marcador "A definir" (caso ainda sem área, do canal
-- aberto, da Ana ou da avaliação) não é erro: entra só como contagem.
--
-- RLS: nenhuma tabela nova; `ouvidoria_protocolos` e `setores` já têm RLS
-- (tudo passa pelo backend com service_role).
--
-- Reversível via: DROP INDEX idx_ouvidoria_protocolos_setor_id; ALTER TABLE
-- ouvidoria_protocolos DROP COLUMN setor_id. A TEXT preserva o nome.
-- =====================================================

ALTER TABLE ouvidoria_protocolos
  ADD COLUMN IF NOT EXISTS setor_id UUID REFERENCES setores(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_ouvidoria_protocolos_setor_id ON ouvidoria_protocolos(setor_id);

UPDATE ouvidoria_protocolos m
SET setor_id = s.id
FROM setores s
WHERE lower(trim(m.setor) COLLATE "und-x-icu") = lower(trim(s.nome) COLLATE "und-x-icu")
  AND m.setor_id IS NULL;

COMMENT ON COLUMN ouvidoria_protocolos.setor_id IS
  'FK para setores.id, gravada junto com a TEXT setor por toda porta que grava a área. Nula no caso sem área (A definir) e no caso antigo cujo nome não casou com nenhum setor.';

-- ---------- Relatório do backfill ----------
DO $$
DECLARE
  sem_setor RECORD;
  orfaos INT;
  pendentes INT;
BEGIN
  SELECT count(*) INTO orfaos
  FROM ouvidoria_protocolos
  WHERE setor_id IS NULL AND trim(setor) <> 'A definir';

  SELECT count(*) INTO pendentes
  FROM ouvidoria_protocolos
  WHERE setor_id IS NULL AND trim(setor) = 'A definir';

  RAISE NOTICE 'Migration 172: % caso(s) sem setor do cadastro, % caso(s) ainda A definir', orfaos, pendentes;

  FOR sem_setor IN
    SELECT setor, string_agg(coalesce(protocolo, id::text), ', ' ORDER BY protocolo) AS protocolos
    FROM ouvidoria_protocolos
    WHERE setor_id IS NULL AND trim(setor) <> 'A definir'
    GROUP BY setor
    ORDER BY setor
  LOOP
    RAISE NOTICE 'Migration 172: setor "%" não casa com nenhum setor: %', sem_setor.setor, sem_setor.protocolos;
  END LOOP;
END $$;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (172) ON CONFLICT (numero) DO NOTHING;
