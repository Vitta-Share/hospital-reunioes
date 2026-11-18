-- Os 17 temas mínimos de capacitação dos membros do Núcleo, do caderno nº 6
-- da ANVISA (3ª ed., 2025, item 2.5.2.3), enviados pela Diretoria em
-- 18/11/2026 (issue #1782). A lista nasceu vazia na migration 155; aqui ela é
-- carregada. Tema que a Presidência já tenha incluído com o mesmo nome fica
-- como está (índice único em lower(btrim(nome))), e a Presidência continua
-- podendo renomear e desativar pela tela.

INSERT INTO nsp_temas_minimos (nome) VALUES
  ('Qualidade e Segurança do Paciente'),
  ('Práticas de Segurança do Paciente'),
  ('Regulamentações sobre Qualidade e Segurança do Paciente'),
  ('Princípios Básicos em Segurança do Paciente'),
  ('Tipos de Eventos Adversos Relacionados à Assistência à Saúde'),
  ('Protocolos de Segurança do Paciente'),
  ('Indicadores de Segurança do Paciente'),
  ('Estratégias para a Melhoria da Qualidade e Segurança'),
  ('Cultura de Segurança do Paciente'),
  ('Núcleo de Segurança do Paciente'),
  ('Plano de Segurança do Paciente'),
  ('Gestão de Riscos'),
  ('Sistema de Notificação de Incidentes'),
  ('Investigação do Incidente'),
  ('Análise de Causa-Raiz'),
  ('Análise dos Modos de Falha (FMEA)'),
  ('Engajamento dos Pacientes e Familiares na Assistência Prestada')
ON CONFLICT ((lower(btrim(nome)))) DO NOTHING;


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (162) ON CONFLICT (numero) DO NOTHING;
