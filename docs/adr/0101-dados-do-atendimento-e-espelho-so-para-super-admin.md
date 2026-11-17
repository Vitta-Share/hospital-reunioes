---
status: accepted
amends: 0031, 0038
---

# Dados do Atendimento e o Espelho da Global Health ficam só com o Super admin

Decisão do diretor na Demanda #1907 (bug relatado na aba Tecnologia) e do Pedro no Refino (17/11/2026). Um médico sem super admin clicou em Admin no menu, caiu em Dados do Atendimento e viu os valores particulares que alimentam a Ana. O app fazia o que as ADRs 0031 e 0038 mandavam: todo papel de Reuniões lia a tela. O diretor mudou a regra. Ela entra no código pela issue #1907; até a issue subir, o código segue a regra antiga.

## Decisões

1. **Só o Super admin vê e edita Dados do Atendimento.** As três tabelas de valores (consultas particulares, exames e estimativas de cirurgias) deixam de ser lidas pelo Facilitador e de ser editadas pela Secretária. Emenda a decisão 2 da ADR 0031.

2. **O Espelho da Global Health segue a tela.** Só o Super admin consulta. Emenda a decisão 8 da ADR 0038. O resto da 0038 não muda: o backend continua sendo o único que fala com a Global Health, sempre em homologação, e falha continua aparecendo como falha.

3. **O time da Vitta não ganha permissão própria.** O diretor pediu "super admin e o time de tecnologia da Vitta". O Desenvolvedor já é o Super admin com login do GitHub no cadastro (ADR 0083), então a regra é uma só: Super admin.

4. **O Admin passa a ser área só do Super admin.** Dados do Atendimento era o único módulo do Admin aberto à Secretária e ao Facilitador. Sem ele, o item Admin some do menu dos dois e os endereços do Admin deixam de abrir para eles.

5. **A API da Ana não muda.** Os endpoints `/api/ana/*` continuam lendo as mesmas tabelas com a API key de serviço (ADR 0031, decisão 4), e a edição continua valendo na hora.

## Por que é surpreendente

- A Secretária perde a edição de valores que a ADR 0031 deu a ela e o Espelho que o glossário dizia que ela mantinha. O diretor foi avisado e manteve a decisão.
- "Time da Vitta" está no pedido e não existe como permissão no código: é o Super admin.
- Quem investiga por que a Ana não achou horário passa a ser só o Super admin, porque o Espelho fechou junto.

## Alternativas descartadas

- **Permissão "Super admin ou Desenvolvedor" só para essa tela.** Cobriria exatamente as mesmas pessoas.
- **Fechar a leitura do Facilitador e manter a Secretária.** Contraria o diretor, que disse que os únicos perfis são o Super admin e o time da Vitta.
- **Manter o item Admin com um aviso de acesso restrito.** Seria um menu que leva a lugar nenhum, o mesmo relato do diretor com outra tela.
