---
status: accepted
amends: 0095
---

# Núcleo de Segurança do Paciente: o Responsável técnico assina os documentos do Núcleo

Decisão do Pedro no grill de 25/11/2026, sobre o pedido da Diretoria Executiva no primeiro dia de uso do módulo. A especificação (seção 6.2) dizia que a Diretoria Executiva assina o Ato de designação, o Regimento e o Plano de Segurança do Paciente, e a Fase 1 (PRD #1764) resolveu esse signatário como quem tem o Acesso pleno ao NSP. A gerência de enfermagem corrigiu: pela regra sanitária, o que é do Núcleo é assinado pelo responsável técnico do hospital, o Diretor Técnico, e não pelo Diretor Executivo.

## Decisões

1. **O Responsável técnico é uma marca no cadastro do usuário.** Uma caixa "Responsável técnico" ao lado de "Acesso pleno ao NSP", com uma pessoa só por vez: marcar outra desmarca a anterior. Quem marca é quem já edita o cadastro de usuários (Super admin), com registro no `audit_log`. Nenhuma pessoa entra pela migration (decisão 12 da Fase 1). É papel do hospital, e não do Núcleo, porque é quem responde à vigilância sanitária.

2. **O Responsável técnico entra no lugar da Diretoria Executiva nos três documentos.** Ato de designação: só ele. Regimento e Plano de Segurança do Paciente: ele e a Presidência vigente do Núcleo, como antes. Termo de Adesão (cada membro) e Ata (os presentes) não mudam. O Acesso pleno ao NSP continua como permissão de ver e editar tudo, sem relação com quem assina.

3. **Sem Responsável técnico marcado, o envio trava.** A mensagem diz que não há Responsável técnico marcado no cadastro, como já acontece quando falta a Presidência. Não há volta para a Diretoria Executiva: mandar para a pessoa errada foi o problema que motivou esta decisão.

4. **Troca de Responsável técnico não mexe em envelope aberto.** O envelope em andamento segue com quem estava nele, e a tela mostra quem está assinando. A versão já vigente continua valendo. Só o próximo envio, ou um "Reenviar para assinatura", vai para a pessoa nova. Os envelopes que saíram para o Diretor Executivo antes da mudança se corrigem do mesmo jeito: Reenviar cancela o antigo na ClickSign e manda o novo.

## Alternativas descartadas

- **Fixar o Diretor Técnico pelo e-mail no código**: quebra a decisão 12 e obriga deploy a cada troca.
- **Escolher a pessoa na Configuração do Núcleo**: prende ao módulo um papel que é do hospital.
- **Cair na Diretoria Executiva quando ninguém está marcado**: repete o erro em silêncio.
- **Cancelar e reenviar sozinho na subida ou na troca**: o botão Reenviar já existe e já foi testado; o caminho automático na produção só serve uma vez.
