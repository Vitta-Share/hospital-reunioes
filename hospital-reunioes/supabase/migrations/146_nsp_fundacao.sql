-- =====================================================
-- Migration 146: Segurança do Paciente, a fundação
-- (issue #1765, PRD #1764, ADR 0095, decisões 3, 4 e 12)
-- =====================================================
-- O que entra:
--   1. o perfil do módulo no cadastro da pessoa (`perfil_nsp`): o Acesso
--      pleno ao NSP, nominal, do Diretor Executivo. O super admin do app NÃO
--      herda (decisão 4): sem este perfil, ele só alcança a configuração
--      técnica;
--   2. o registro profissional no cadastro de pessoas: conselho, número e UF;
--   3. o Colegiado e a Participação, genéricos, com vigência (decisão 3);
--   4. o Núcleo como o primeiro Colegiado, SEM nenhuma pessoa (decisão 12: a
--      carga dos membros é feita pela tela, nunca por migration ou seed);
--   5. o Produto "Segurança do Paciente" na aba Tecnologia.
--
-- RLS default-deny nas tabelas novas (padrão da casa): quem lê e escreve é o
-- backend com a service_role. Nenhuma policy de propósito.
--
-- Tudo com IF NOT EXISTS / DROP antes de ADD / ON CONFLICT: rodar duas vezes
-- é inofensivo. Aplicar à mão no Studio: o deploy não aplica SQL.
-- =====================================================

BEGIN;

-- ---------- 1. O perfil do módulo ----------
ALTER TABLE participantes
  ADD COLUMN IF NOT EXISTS perfil_nsp TEXT;

ALTER TABLE participantes DROP CONSTRAINT IF EXISTS participantes_perfil_nsp_check;
ALTER TABLE participantes
  ADD CONSTRAINT participantes_perfil_nsp_check
  CHECK (perfil_nsp IS NULL OR perfil_nsp IN ('acesso_pleno'));

COMMENT ON COLUMN participantes.perfil_nsp IS
  'Segurança do Paciente (ADR 0095, decisão 4): acesso_pleno = vê e edita tudo no módulo. Nulo = o que a Participação vigente e o cargo dão. Super admin não herda.';

-- ---------- 2. O registro profissional ----------
ALTER TABLE participantes ADD COLUMN IF NOT EXISTS conselho_profissional TEXT;
ALTER TABLE participantes ADD COLUMN IF NOT EXISTS registro_profissional TEXT;
ALTER TABLE participantes ADD COLUMN IF NOT EXISTS registro_uf TEXT;

ALTER TABLE participantes DROP CONSTRAINT IF EXISTS participantes_conselho_profissional_check;
ALTER TABLE participantes
  ADD CONSTRAINT participantes_conselho_profissional_check
  CHECK (conselho_profissional IS NULL OR char_length(btrim(conselho_profissional)) BETWEEN 1 AND 20);

ALTER TABLE participantes DROP CONSTRAINT IF EXISTS participantes_registro_profissional_check;
ALTER TABLE participantes
  ADD CONSTRAINT participantes_registro_profissional_check
  CHECK (registro_profissional IS NULL OR char_length(btrim(registro_profissional)) BETWEEN 1 AND 30);

ALTER TABLE participantes DROP CONSTRAINT IF EXISTS participantes_registro_uf_check;
ALTER TABLE participantes
  ADD CONSTRAINT participantes_registro_uf_check
  CHECK (registro_uf IS NULL OR registro_uf ~ '^[A-Z]{2}$');

COMMENT ON COLUMN participantes.conselho_profissional IS
  'Sigla do conselho profissional (COREN, CRM, CRF...). Issue #1765.';
COMMENT ON COLUMN participantes.registro_profissional IS
  'Número do registro no conselho. Issue #1765.';
COMMENT ON COLUMN participantes.registro_uf IS
  'UF do registro profissional, duas letras maiúsculas. Issue #1765.';

-- ---------- 3. Colegiado e Participação ----------
-- O Colegiado aponta para o setor canônico do Admin por id (ADR 0095,
-- decisão 2), opcional: o Núcleo pode ainda não estar na tabela de setores.
CREATE TABLE IF NOT EXISTS colegiados (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug       TEXT NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9_]+$'),
  nome       TEXT NOT NULL CHECK (btrim(nome) <> ''),
  setor_id   UUID REFERENCES setores(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE colegiados IS
  'Grupo formal do hospital com regimento, composição e reuniões próprias (ADR 0095, decisão 3). O Núcleo de Segurança do Paciente é o primeiro (slug nsp).';

ALTER TABLE colegiados ENABLE ROW LEVEL SECURITY;

-- A Participação nunca é apagada: encerrar é mudar o fim da vigência, e o
-- histórico responde quem compunha o Colegiado em qualquer data.
CREATE TABLE IF NOT EXISTS participacoes (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  colegiado_id      UUID NOT NULL REFERENCES colegiados(id) ON DELETE RESTRICT,
  participante_id   VARCHAR(10) NOT NULL REFERENCES participantes(id) ON DELETE RESTRICT,
  papel             TEXT NOT NULL CHECK (papel IN ('presidencia', 'suplente', 'membro')),
  vigencia_inicio   DATE NOT NULL,
  vigencia_fim      DATE NOT NULL,
  termo_assinado_em TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT participacoes_vigencia_check CHECK (vigencia_fim >= vigencia_inicio)
);

COMMENT ON TABLE participacoes IS
  'O papel de uma pessoa num Colegiado, sempre com vigência (ADR 0095, decisão 3). Participação vencida não dá acesso nem conta para quórum.';
COMMENT ON COLUMN participacoes.termo_assinado_em IS
  'Quando o Termo de Adesão desta Participação foi assinado. Nulo = sem Termo válido: só painel, calendário e agenda.';

CREATE INDEX IF NOT EXISTS idx_participacoes_participante
  ON participacoes(participante_id, colegiado_id);
CREATE INDEX IF NOT EXISTS idx_participacoes_colegiado_vigencia
  ON participacoes(colegiado_id, vigencia_inicio, vigencia_fim);

ALTER TABLE participacoes ENABLE ROW LEVEL SECURITY;

-- ---------- 4. O Núcleo, sem nenhuma pessoa ----------
INSERT INTO colegiados (slug, nome, setor_id) VALUES (
  'nsp',
  'Núcleo de Segurança do Paciente',
  (SELECT id FROM setores WHERE lower(nome) = lower('Núcleo de Segurança do Paciente') LIMIT 1)
)
ON CONFLICT (slug) DO NOTHING;

-- ---------- 5. O Produto na aba Tecnologia ----------
-- Molde da 116: o módulo ganha Produto próprio, com texto no Kit de
-- conhecimento do Assistente de Tecnologia.
INSERT INTO tecnologia_produtos (nome, ordem) VALUES
  ('Segurança do Paciente', (SELECT COALESCE(MAX(ordem), 0) + 1 FROM tecnologia_produtos))
ON CONFLICT DO NOTHING;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (146) ON CONFLICT (numero) DO NOTHING;
