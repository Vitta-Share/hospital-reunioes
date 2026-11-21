-- =====================================================
-- Migration 172: nada apaga Pendencia (ADR 0098, decisao 6; issue #1864)
-- =====================================================
-- A FK pendencias.id_reuniao -> reunioes era ON DELETE CASCADE (migration 003):
-- excluir a Reuniao levava as Pendencias junto. Agora a FK recusa. Excluir
-- Reuniao com qualquer Pendencia, aberta ou cancelada, da erro; o caminho para
-- tirar uma Pendencia da cobranca e cancelar com anotacao.
--
-- O nome da FK veio do default do Postgres na 003, mas o bloco abaixo derruba
-- toda FK de pendencias para reunioes, seja qual for o nome, para nao sobrar
-- uma CASCADE ao lado da nova. Rodar duas vezes e inofensivo. Aplicar a mao no
-- Studio.
-- =====================================================

BEGIN;

DO $$
DECLARE
  fk record;
BEGIN
  FOR fk IN
    SELECT conname
    FROM pg_constraint
    WHERE contype = 'f'
      AND conrelid = 'public.pendencias'::regclass
      AND confrelid = 'public.reunioes'::regclass
  LOOP
    EXECUTE format('ALTER TABLE public.pendencias DROP CONSTRAINT %I', fk.conname);
  END LOOP;
END
$$;

ALTER TABLE pendencias
  ADD CONSTRAINT pendencias_id_reuniao_fkey FOREIGN KEY (id_reuniao)
  REFERENCES reunioes (id_reuniao) ON DELETE RESTRICT;

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (172) ON CONFLICT (numero) DO NOTHING;
