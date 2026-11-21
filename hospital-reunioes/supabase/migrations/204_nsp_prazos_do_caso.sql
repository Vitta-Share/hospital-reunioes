-- Escreva a migration acima do recibo.


-- recibo: a subida espera este número no /api/health (issue #969)
INSERT INTO migracoes_aplicadas (numero) VALUES (204) ON CONFLICT (numero) DO NOTHING;
