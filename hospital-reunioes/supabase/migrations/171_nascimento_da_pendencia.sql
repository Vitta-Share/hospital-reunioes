-- =====================================================
-- Migration 171: evento de nascimento da Pendencia (ADR 0098, decisao 1; issue #1867)
-- =====================================================
-- A Pendencia nasce no envio da Ata para assinatura, cada uma com o evento de
-- nascimento no Historico. O evento vem de um trigger AFTER INSERT em
-- `pendencias`: fica na mesma transacao do INSERT e vale para todo caminho
-- (envio, Reenviar, reconciliacao das 5h30, aprovacao sem assinatura,
-- lembrete do Nucleo), sem depender de o backend lembrar de gravar.
--
-- 1. O CHECK de `pendencia_historico.comando` ganha 'nascimento'.
-- 2. `registrar_nascimento_da_pendencia`: o trigger.
--
-- Depende da 169 (`pendencia_historico`). Sem tabela nova: o RLS default-deny
-- da 169 continua valendo. Rodar duas vezes e inofensivo. Aplicar a mao no Studio.
-- =====================================================

BEGIN;

-- 1. O comando do nascimento ----------------------------------------------------

ALTER TABLE pendencia_historico DROP CONSTRAINT IF EXISTS pendencia_historico_comando_check;
ALTER TABLE pendencia_historico ADD CONSTRAINT pendencia_historico_comando_check
  CHECK (comando IN (
    'nascimento', 'iniciar', 'anotar', 'concluir', 'repactuar', 'cancelar', 'reabrir', 'migracao'
  ));

-- 2. O trigger ---------------------------------------------------------------------

CREATE OR REPLACE FUNCTION registrar_nascimento_da_pendencia()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO pendencia_historico (
    id_acao, comando, anotacao, autor_id, autor_nome,
    status_antes, status_depois, prazo_antes, prazo_depois, conta_atraso
  ) VALUES (
    NEW.id_acao,
    'nascimento',
    -- Sem citar o envio: a Pendencia com Reuniao tambem nasce no Finalizar
    -- sem assinatura e na validacao da Ata do Nucleo, e o Historico so aceita
    -- insercao (a frase errada nao sai mais de la).
    CASE
      WHEN NEW.id_reuniao IS NOT NULL
        THEN 'Nasceu do quadro da Ata da reuniao ' || NEW.id_reuniao || '.'
      ELSE 'Nasceu do lembrete da Agenda regulatoria.'
    END,
    NULL, 'Sistema',
    NULL, NEW.status, NULL, NEW.prazo, false
  );
  RETURN NULL;
END;
$$;

REVOKE EXECUTE ON FUNCTION registrar_nascimento_da_pendencia()
  FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS pendencia_nasce_com_evento ON pendencias;
CREATE TRIGGER pendencia_nasce_com_evento
  AFTER INSERT ON pendencias
  FOR EACH ROW EXECUTE FUNCTION registrar_nascimento_da_pendencia();

COMMIT;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (171) ON CONFLICT (numero) DO NOTHING;
