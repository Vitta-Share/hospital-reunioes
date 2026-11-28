/* Novidades do Hospital Reuniões: protótipo navegável da tela inicial.
   Tudo aqui é demonstração: pessoas, reuniões e prazos são inventados, e as datas
   andam junto com o dia de hoje para a tela nunca ficar velha. */
(function () {
  'use strict';

  // ------------------------------------------------------------------ datas
  const HOJE = new Date(); HOJE.setHours(0, 0, 0, 0);
  const SEMANA = ['domingo', 'segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado'];
  const SEM_CURTA = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
  const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
  const dia = (off) => { const d = new Date(HOJE); d.setDate(d.getDate() + off); return d; };
  const dd = (n) => String(n).padStart(2, '0');
  const fmt = (d) => `${dd(d.getDate())}/${dd(d.getMonth() + 1)}/${d.getFullYear()}`;
  const curto = (d) => `${dd(d.getDate())}/${dd(d.getMonth() + 1)}`;
  const longo = (d) => { const s = `${SEMANA[d.getDay()]}, ${d.getDate()} de ${MESES[d.getMonth()]} de ${d.getFullYear()}`; return s[0].toUpperCase() + s.slice(1); };
  const iso = (d) => `${d.getFullYear()}-${dd(d.getMonth() + 1)}-${dd(d.getDate())}`;
  const deIso = (s) => { const [a, m, d] = s.split('-').map(Number); return new Date(a, m - 1, d); };
  const difDias = (d) => Math.round((d - HOJE) / 86400000);
  const quando = (d) => { const n = difDias(d); return n === 0 ? 'hoje' : n === 1 ? 'amanhã' : n === -1 ? 'ontem' : `${SEM_CURTA[d.getDay()]}, ${curto(d)}`; };
  const EXT = ['nenhum', 'um', 'dois', 'três', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove', 'dez'];
  const ext = (n) => EXT[n] || String(n);
  const cap = (s) => s[0].toUpperCase() + s.slice(1);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ------------------------------------------------------------------ dados de demonstração
  const EU = { nome: 'Renata Alves', primeiro: 'Renata', cargo: 'Diretora Assistencial', setor: 'Diretoria Assistencial' };

  const reunioes = [
    { id: 'r0', off: -7, hora: '10:00', titulo: 'Reunião da Diretoria Assistencial', papel: 'facilitador', ata: 'Assinada por todos',
      participantes: ['Renata Alves', 'Carla Nogueira', 'Rodrigo Sales', 'Paulo Mendes', 'Juliana Prado'], pauta: ['Escalas de dezembro', 'EPIs do Centro Cirúrgico', 'Indicadores de outubro'] },
    { id: 'rm1', off: -16, hora: '15:00', titulo: 'Comissão de Controle de Infecção', papel: 'participante', ata: 'Aguardando a sua assinatura',
      participantes: ['Fernanda Lima', 'Renata Alves', 'Carla Nogueira', 'Rodrigo Sales'], pauta: ['Taxa de infecção de corrente sanguínea', 'Campanha de higienização das mãos'] },
    { id: 'r1', off: 0, hora: '14:00', titulo: 'Reunião da Diretoria Assistencial', papel: 'facilitador', ata: 'A Reunião ainda não aconteceu',
      participantes: ['Renata Alves', 'Carla Nogueira', 'Rodrigo Sales', 'Paulo Mendes', 'Juliana Prado', 'Fernanda Lima'], pauta: ['Plano de ação da auditoria de prontuários', 'Escala de enfermagem do 3º andar', 'Casos da Ouvidoria da semana'] },
    { id: 'r2', off: 1, hora: '09:30', titulo: 'Comissão de Controle de Infecção', papel: 'participante', ata: 'A Reunião ainda não aconteceu',
      participantes: ['Fernanda Lima', 'Renata Alves', 'Carla Nogueira'], pauta: ['Resultado da ronda de higienização', 'Protocolo de isolamento'] },
    { id: 'r3', off: 2, hora: '16:00', titulo: 'Qualidade e Acreditação', papel: 'facilitador', ata: 'A Reunião ainda não aconteceu',
      participantes: ['Renata Alves', 'Juliana Prado', 'Fernanda Lima', 'Paulo Mendes'], pauta: ['Preparação para a visita da acreditadora', 'Protocolo de sepse'] },
    { id: 'r4', off: 6, hora: '08:00', titulo: 'Reunião do Núcleo de Segurança do Paciente', papel: 'participante', ata: 'A Reunião ainda não aconteceu',
      participantes: ['Fernanda Lima', 'Renata Alves', 'Carla Nogueira', 'Rodrigo Sales'], pauta: ['Indicadores de queda', 'Notificações do mês'] },
    { id: 'r5', off: 13, hora: '10:00', titulo: 'Reunião da Diretoria Assistencial', papel: 'facilitador', ata: 'A Reunião ainda não aconteceu',
      participantes: ['Renata Alves', 'Carla Nogueira', 'Rodrigo Sales', 'Paulo Mendes', 'Juliana Prado'], pauta: ['Fechamento do mês'] }
  ].map((r) => ({ ...r, data: iso(dia(r.off)) }));

  // Cada item que pede alguma coisa da Renata. "off" é o prazo em dias a partir de hoje; null = sem prazo.
  const itens = [
    { id: 'p1', area: 'Reunião', tipo: 'pendencia', off: -12, titulo: 'Revisar a escala de enfermagem do 3º andar', origem: 'Pendência · Reunião da Diretoria Assistencial', reuniao: 'r0', detalhe: 'Refazer a escala de dezembro do 3º andar com as duas novas técnicas. A Carla mandou a proposta por e-mail em 10/11.' },
    { id: 'p2', area: 'Reunião', tipo: 'ata', off: -6, titulo: 'Assinar a Ata da Comissão de Controle de Infecção', origem: 'Ata a assinar · Reunião de ' + curto(dia(-16)), reuniao: 'rm1', detalhe: 'A Ata foi revisada pela Fernanda Lima e só falta a sua assinatura para seguir.' },
    { id: 'p3', area: 'Reunião', tipo: 'contestacao', off: -3, titulo: 'Responder a contestação de Paulo Mendes', origem: 'Contestação · Pendência dos EPIs do Centro Cirúrgico', reuniao: 'r0', detalhe: 'O Paulo pede mais 15 dias porque o fornecedor atrasou a entrega dos aventais.' },
    { id: 'p4', area: 'Reunião', tipo: 'pendencia', off: 0, titulo: 'Enviar o plano de ação da auditoria de prontuários', origem: 'Pendência · Qualidade e Acreditação', reuniao: 'r3', detalhe: 'Plano com responsáveis e prazos para as 6 não conformidades da auditoria de outubro.' },
    { id: 'p5', area: 'Rotina', tipo: 'rotina', off: 0, titulo: 'Ronda de higienização das mãos', origem: 'Verificação · Rotina semanal', detalhe: 'Percorrer as 4 alas, observar 10 oportunidades em cada e registrar a adesão.' },
    { id: 'p6', area: 'Ouvidoria', tipo: 'ouvidoria', off: 1, titulo: 'Demora no atendimento da recepção da Emergência', origem: 'Caso 482 · Ouvidoria do setor', detalhe: 'Acompanhante relata espera de 2 horas para a primeira avaliação no domingo à noite.' },
    { id: 'p7', area: 'Reunião', tipo: 'pendencia', off: 2, titulo: 'Enviar os indicadores de queda ao NSP', origem: 'Pendência · Reunião do Núcleo', reuniao: 'r4', detalhe: 'Quedas por 1.000 pacientes-dia dos últimos 3 meses, por ala.' },
    { id: 'p13', area: 'NSP', tipo: 'capacitacao', off: 1, titulo: 'Capacitação: comunicação de evento adverso', origem: 'Capacitação do Núcleo · 15:00, auditório', detalhe: 'Capacitação obrigatória para membros do Núcleo, com 1 hora de duração.' },
    { id: 'p8', area: 'POP', tipo: 'pop', off: 5, titulo: 'Revisar o POP de identificação do paciente', origem: 'POP · a versão 3 aguarda a sua revisão', detalhe: 'Mudanças: pulseira com QR code e dupla checagem antes de hemocomponentes.' },
    { id: 'p9', area: 'POP', tipo: 'pop', off: null, titulo: 'Validar o POP de coleta de hemocultura', origem: 'POP · aguarda a sua validação', detalhe: 'Revisado pela CCIH. Falta a validação da Diretoria Assistencial.' },
    { id: 'p10', area: 'Reunião', tipo: 'pendencia', off: 12, titulo: 'Atualizar o protocolo de sepse', origem: 'Pendência · Qualidade e Acreditação', reuniao: 'r3', detalhe: 'Incluir o novo fluxo de coleta de lactato na primeira hora.' },
    { id: 'p11', area: 'Ouvidoria', tipo: 'ouvidoria', off: 9, titulo: 'Elogio à equipe da UTI adulto', origem: 'Caso 477 · Ouvidoria do setor', detalhe: 'Família agradece o cuidado da equipe da noite. Pede que o elogio chegue a todos.' },
    { id: 'p14', area: 'Reunião', tipo: 'pendencia', off: 3, titulo: 'Atualizar a lista de presença da Diretoria Assistencial', origem: 'Pendência · Reunião da Diretoria Assistencial', reuniao: 'r0', detalhe: 'Conferir quem assinou a presença das 3 últimas Reuniões e corrigir as faltas.' },
    { id: 'p15', area: 'Rotina', tipo: 'rotina', off: 4, titulo: 'Conferência dos psicotrópicos', origem: 'Verificação · Rotina semanal', detalhe: 'Contar o estoque de psicotrópicos da farmácia satélite e bater com o livro.' },
    { id: 'p16', area: 'Reunião', tipo: 'ata', off: 2, titulo: 'Assinar a Ata da Reunião de Hotelaria', origem: 'Ata a assinar · Reunião de ' + curto(dia(-4)), detalhe: 'A Ata foi revisada pela Juliana Prado e falta a sua assinatura.' },
    { id: 'p12', area: 'Rotina', tipo: 'rotina', off: 9, titulo: 'Checagem do carrinho de emergência', origem: 'Verificação · Rotina quinzenal', detalhe: 'Conferir lacre, validade dos medicamentos e o desfibrilador de cada carrinho.' }
  ];
  const concluidos = [
    { titulo: 'Relatório de eventos adversos de outubro', quando: dia(-3), noPrazo: true, area: 'Reunião' },
    { titulo: 'Assinar a Ata da Reunião de Qualidade', quando: dia(-6), noPrazo: true, area: 'Reunião' },
    { titulo: 'Conferência do carrinho de emergência', quando: dia(-8), noPrazo: true, area: 'Rotina' },
    { titulo: 'Resposta ao caso 470 da Ouvidoria', quando: dia(-10), noPrazo: false, area: 'Ouvidoria' }
  ];
  const pessoas = [
    { id: 'rs', nome: 'Rodrigo Sales', setor: 'Farmácia', cargo: 'Farmacêutico responsável', vencidos: [['Inventário dos medicamentos controlados', 9], ['Plano de contingência de estoque', 5], ['Treinamento de dupla checagem', 2]], abertos: 5, np: 14, fp: 4, acesso: 'há 11 dias' },
    { id: 'cn', nome: 'Carla Nogueira', setor: 'Enfermagem', cargo: 'Coordenadora de Enfermagem', vencidos: [['Escala de dezembro da UTI', 4], ['Checklist de passagem de plantão', 1]], abertos: 4, np: 18, fp: 3, acesso: 'hoje' },
    { id: 'pm', nome: 'Paulo Mendes', setor: 'Suprimentos', cargo: 'Supervisor de Suprimentos', vencidos: [['Cotação de EPIs do Centro Cirúrgico', 3]], abertos: 2, np: 9, fp: 2, acesso: 'ontem' },
    { id: 'fl', nome: 'Fernanda Lima', setor: 'CCIH', cargo: 'Enfermeira da CCIH', vencidos: [], abertos: 3, np: 21, fp: 0, acesso: 'hoje' },
    { id: 'jp', nome: 'Juliana Prado', setor: 'Hotelaria', cargo: 'Coordenadora de Hotelaria', vencidos: [], abertos: 1, np: 7, fp: 1, acesso: 'há 2 dias' }
  ];
  const pops = [
    { id: 'pop1', titulo: 'Identificação do paciente', versao: 3, status: 'Em revisão', item: 'p8' },
    { id: 'pop2', titulo: 'Coleta de hemocultura', versao: 2, status: 'Em validação', item: 'p9' },
    { id: 'pop3', titulo: 'Higienização das mãos', versao: 5, status: 'Vigente' },
    { id: 'pop4', titulo: 'Prevenção de quedas', versao: 4, status: 'Vigente' },
    { id: 'pop5', titulo: 'Passagem de plantão', versao: 2, status: 'Vigente' },
    { id: 'pop6', titulo: 'Administração de hemocomponentes', versao: 1, status: 'Em elaboração' }
  ];
  const notificacoes = [
    { texto: 'Paulo Mendes contestou uma Pendência', sub: 'EPIs do Centro Cirúrgico · há 3 dias', href: '#item-p3' },
    { texto: 'Você foi marcada na Ata da Comissão de Controle de Infecção', sub: 'Assinatura pendente · há 6 dias', href: '#item-p2' },
    { texto: 'Novo caso da Ouvidoria no seu setor', sub: 'Caso 482 · ontem', href: '#item-p6' }
  ];

  // ------------------------------------------------------------------ estado
  const MODELOS = ['atual', '2b', '2c', '2c-escuro'];
  const est = {
    modelo: '2b', aba: 'tudo', area: 'todas', ordem: 'urgente', pop: null,
    feitos: {}, naoRealizada: {}, lidas: false, menu: false, sino: false,
    pendAba: 'abertas', pendBusca: '', popBusca: '', notifEnviada: null, pessoaAberta: null,
    grupos: {}, secoes: {}, jaEntrou: false, recolhido: false, porPagina: 10, pagina: 1, busca: null
  };
  try {
    const q = new URLSearchParams(location.search).get('modelo');
    const guardado = localStorage.getItem('novidades-modelo');
    if (MODELOS.includes(q)) est.modelo = q; else if (MODELOS.includes(guardado)) est.modelo = guardado;
    est.recolhido = localStorage.getItem('novidades-recolhido') === '1';
  } catch (e) { /* sem armazenamento: fica no 2B */ }

  const grupo = (it) => it.off === null ? 'sem' : it.off < 0 ? 'venc' : it.off === 0 ? 'hoje' : it.off <= 7 ? 'prox' : 'depois';
  const abertos = () => itens.filter((i) => !est.feitos[i.id]);
  const fila = () => abertos().filter((i) => grupo(i) !== 'depois');
  const ESTADO = { venc: ['e-venc', 'Atrasada'], hoje: ['e-hoje', 'Hoje'], prox: ['e-prox', 'Próxima'], sem: ['e-sem', 'Sem prazo'], depois: ['e-prox', 'Próxima'] };
  const ACAO = { pendencia: 'Resolver', ata: 'Assinar', contestacao: 'Responder', rotina: 'Resolver', ouvidoria: 'Responder', pop: 'Revisar', capacitacao: 'Confirmar' };
  const reuniao = (id) => reunioes.find((r) => r.id === id);
  const proximas = () => reunioes.filter((r) => difDias(deIso(r.data)) >= 0).sort((a, b) => (a.data + a.hora).localeCompare(b.data + b.hora));

  // ------------------------------------------------------------------ ícones
  const I = {
    inicio: '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3l9 8h-2.5v9h-5v-6h-3v6h-5v-9H3z"/></svg>',
    reunioes: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4"/></svg>',
    dashboard: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M5 20V11M10 20V5M15 20v-7M20 20V8"/></svg>',
    calendario: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4M8 14h2M14 14h2"/></svg>',
    pendencias: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM9 13l2 2 4-4"/></svg>',
    rotinas: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 12a8 8 0 0 1 14-5l2 2M20 12a8 8 0 0 1-14 5l-2-2M20 4v5h-5M4 20v-5h5"/></svg>',
    pops: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 6c-2-1.5-5-2-8-1.5v13c3-.5 6 0 8 1.5 2-1.5 5-2 8-1.5v-13C17 4 14 4.5 12 6zM12 6v13"/></svg>',
    ouvidoria: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 5h16v11H10l-5 4v-4H4z"/></svg>',
    notificar: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 4l9 16H3zM12 10v4M12 17v.5"/></svg>',
    nsp: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6zM9 12l2 2 4-4"/></svg>',
    seta: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M4 12h15M13 6l6 6-6 6"/></svg>',
    voltar: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M20 12H5M11 6l-6 6 6 6"/></svg>',
    baixo: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" aria-hidden="true"><path d="M5 9l7 7 7-7"/></svg>',
    cal: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4M8 14h2M12 14h2"/></svg>',
    tres: '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>',
    info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/></svg>',
    lista: '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M9 2h6v2h4v18H5V4h4zm-1 8v2h8v-2zm0 4v2h8v-2z"/></svg>',
    alerta: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5v.5"/></svg>',
    relogio: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    agenda: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4"/></svg>',
    certo: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>',
    agendar: '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 2h2v2h6V2h2v2h3v17H4V4h3zm-1 8v9h12v-9zm5 1.5h2V14h2.5v2H13v2.5h-2V16H8.5v-2H11z"/></svg>',
    calCheio: '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 2h2v2h6V2h2v2h3v17H4V4h3zm-1 8v9h12v-9zm2 2h3v3H8z"/></svg>',
    pendCheio: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM9 11h6M9 15h6"/></svg>',
    popCheio: '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3 5c3-.6 6 0 8 1.5v13c-2-1.5-5-2-8-1.5zm18 0c-3-.6-6 0-8 1.5v13c2-1.5 5-2 8-1.5z"/></svg>',
    notifCheio: '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3l10 18H2zm-1 6v6h2V9zm0 7.5v2h2v-2z"/></svg>',
    processos: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M8 3h9l3 3v15H8zM4 7v14h12M11 9h6M11 13h6"/></svg>',
    lista2: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M9 6h11M9 12h11M9 18h11M4 6h1M4 12h1M4 18h1"/></svg>',
    kanban: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/></svg>',
    pessoas: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="9" cy="8" r="3.5"/><path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6M16 4a3.5 3.5 0 0 1 0 7M18 14c2 .7 3 2.8 3 6"/></svg>',
    doc: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6"/></svg>',
    capacitacao: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M2 9l10-5 10 5-10 5zM6 11v5c3 2 9 2 12 0v-5"/></svg>',
    agenda2: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4M12 13v3l2 1"/></svg>',
    auditoria: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM9 14l2 2 4-4"/></svg>',
    risco: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6zM12 8v5M12 16v.5"/></svg>',
    comissao: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 21h18M5 21V10M19 21V10M9 21V10M15 21V10M2 10l10-6 10 6z"/></svg>',
    ouvCheio: '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3 4h18v13H11l-6 4v-4H3z"/></svg>'
  };

  const MENU = [
    ['inicio', 'Início', I.inicio], ['reunioes', 'Reuniões e metas', I.reunioes], ['dashboard', 'Dashboard', I.dashboard],
    ['calendario', 'Calendário', I.calendario], ['pendencias', 'Pendências', I.pendencias], ['rotinas', 'Rotinas', I.rotinas],
    ['pops', 'POPs', I.pops], ['ouvidoria', 'Ouvidoria', I.ouvidoria], ['notificar', 'Notificar incidente', I.notificar], ['nsp', 'NSP', I.nsp]
  ];
  // O menu de hoje (components/layout/Sidebar.tsx, itensDoMenu) para o perfil da Renata.
  // Contas médicas, Comitê de Conduta e Admin só aparecem para quem tem esse acesso.
  const ARVORE = [
    { k: 'inicio', t: 'Início', ic: 'inicio' },
    { g: 'reunioes', t: 'Reuniões e metas', ic: 'reunioes', filhos: [
      { k: 'dashboard', t: 'Dashboard', ic: 'dashboard' }, { k: 'calendario', t: 'Calendário', ic: 'calendario' },
      { k: 'fora-processos', t: 'Definições de processo', ic: 'processos' },
      { g: 'pendencias', t: 'Pendências', ic: 'pendencias', filhos: [{ k: 'pendencias', t: 'Lista', ic: 'lista2' }, { k: 'fora-kanban', t: 'Kanban', ic: 'kanban' }] },
      { k: 'rotinas', t: 'Rotinas', ic: 'rotinas' }] },
    { k: 'ouvidoria', t: 'Ouvidoria', ic: 'ouvidoria' },
    { k: 'pops', t: 'POPs', ic: 'pops' },
    { g: 'nsp', t: 'NSP', ic: 'nsp', nome: 'Núcleo de Segurança do Paciente', filhos: [
      { k: 'notificar', t: 'Notificar incidente', ic: 'notificar' }, { k: 'nsp', t: 'Visão geral', ic: 'inicio' },
      { k: 'fora-reunioes-do-nucleo', t: 'Reuniões', ic: 'calendario' },
      { g: 'nucleo', t: 'Núcleo', ic: 'pessoas', filhos: [
        { k: 'fora-membros', t: 'Membros', ic: 'pessoas' }, { k: 'fora-documentos', t: 'Documentos', ic: 'doc' },
        { k: 'fora-capacitacoes', t: 'Capacitações', ic: 'capacitacao' }, { k: 'fora-agenda', t: 'Agenda regulatória', ic: 'agenda2' }] },
      { breve: 'Auditorias de adesão', ic: 'auditoria', dica: 'Em breve: auditorias rápidas pelo celular, que alimentam os indicadores dos protocolos sem digitação.' },
      { breve: 'Gestão de riscos', ic: 'risco', dica: 'Em breve: mapa de riscos por setor e análise preventiva de processos críticos.' },
      { breve: 'Comissões', ic: 'comissao', dica: 'Em breve: as demais comissões do hospital com membros, documentos, reuniões e atas.' }] }
  ];
  const temAtivo = (n, ativo) => n.k === ativo || (n.filhos || []).some((f) => temAtivo(f, ativo));
  function menuArvore(nos, ativo, nivel) {
    return nos.map((n) => {
      const ic = I[n.ic] || '';
      if (n.breve) return `<li><span class="breve-m" title="${esc(n.dica)}">${ic}<span class="txt-m">${n.breve}</span><span class="selo-m">Em breve</span></span></li>`;
      if (n.g) {
        const aberto = est.grupos[n.g] !== undefined ? est.grupos[n.g] : (temAtivo(n, ativo) || n.g === 'reunioes');
        return `<li><button type="button" class="grupo-m${temAtivo(n, ativo) ? ' com-ativo' : ''}" data-grupo="${n.g}" aria-expanded="${aberto}"${n.nome ? ` aria-label="${n.nome}" title="${n.nome}"` : ''}>${ic}<span class="txt-m">${n.t}</span><svg class="chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></button>${aberto ? `<ul class="sub-m">${menuArvore(n.filhos, ativo, nivel + 1)}</ul>` : ''}</li>`;
      }
      const on = n.k === ativo;
      return `<li><a href="#${n.k}" class="${on ? 'on' : ''}"${on ? ' aria-current="page"' : ''}>${ic}<span class="txt-m">${n.t}</span></a></li>`;
    }).join('');
  }

  const TRILHA = { inicio: 'Início', reunioes: 'Reuniões e metas', reuniao: 'Reuniões e metas', dashboard: 'Dashboard', calendario: 'Calendário',
    pendencias: 'Pendências', item: 'Pendências', rotinas: 'Rotinas', pops: 'POPs', ouvidoria: 'Ouvidoria', notificar: 'Notificar incidente', nsp: 'NSP', pessoas: 'Quem responde a você', pessoa: 'Quem responde a você', fora: 'Fora do protótipo' };
  const MENU_ATIVO = { reuniao: 'reunioes', item: 'pendencias', pessoas: 'inicio', pessoa: 'inicio' };

  // ------------------------------------------------------------------ rota
  function rota() {
    const h = (location.hash || '#inicio').slice(1);
    const [pag, ...resto] = h.split('-');
    return { pag: TRILHA[pag] ? pag : 'inicio', id: resto.join('-') };
  }

  // ------------------------------------------------------------------ peças
  function linhaFila(it) {
    const [cls, rot] = ESTADO[grupo(it)];
    const data = it.off === null ? 'Sem prazo' : fmt(dia(it.off));
    const r = it.reuniao ? reuniao(it.reuniao) : null;
    const aberto = est.pop === 'mais-' + it.id;
    return `<li class="linha ${aberto ? 'com-menu' : 'entra'}">
      <span class="estado ${cls}"><i aria-hidden="true"></i>${rot}</span>
      <span class="t">${esc(it.titulo)}<small>${esc(it.origem)}</small></span>
      <span class="pill">${it.area}</span>
      <span class="data x-data">${I.cal}<span class="num">${data}</span></span>
      <a class="btn" href="#item-${it.id}" aria-label="${ACAO[it.tipo]}: ${esc(it.titulo)}">${ACAO[it.tipo]}</a>
      <span class="mais-wrap"><button type="button" class="mais" data-pop="mais-${it.id}" aria-expanded="${aberto}" aria-label="Mais opções: ${esc(it.titulo)}">${I.tres}</button>
        ${aberto ? `<div class="pop" role="menu">
          <a role="menuitem" href="#item-${it.id}">Abrir</a>
          ${r ? `<a role="menuitem" href="#reuniao-${r.id}">Ver a Reunião de origem</a>` : ''}
          <a role="menuitem" href="#${it.area === 'POP' ? 'pops' : it.area === 'Ouvidoria' ? 'ouvidoria' : it.area === 'Rotina' ? 'rotinas' : it.area === 'NSP' ? 'nsp' : 'pendencias'}">Ir para ${it.area === 'Reunião' ? 'Pendências' : it.area === 'Rotina' ? 'Rotinas' : it.area === 'POP' ? 'POPs' : it.area}</a>
        </div>` : ''}</span>
    </li>`;
  }

  function popMenu(nome, opcoes, atual) {
    return `<div class="pop" role="menu">${opcoes.map(([v, t]) => `<button type="button" role="menuitemradio" aria-checked="${v === atual}" data-escolha="${nome}" data-valor="${v}">${t}</button>`).join('')}</div>`;
  }

  // ------------------------------------------------------------------ páginas
  function pInicio() {
    const f = fila();
    const conta = (g) => f.filter((i) => grupo(i) === g).length;
    const venc = f.filter((i) => grupo(i) === 'venc');
    const hora = new Date().getHours();
    const saudacao = hora < 12 ? 'Bom dia' : hora < 18 ? 'Boa tarde' : 'Boa noite';
    let frase;
    if (venc.length) {
      const max = Math.max(...venc.map((i) => -i.off));
      frase = venc.length === 1 ? `Um prazo seu venceu. Ele espera há ${max} ${max === 1 ? 'dia' : 'dias'}.` : `${cap(ext(venc.length))} prazos seus venceram. O mais antigo espera há ${max} dias.`;
    } else if (conta('hoje')) frase = `Nada atrasado. ${conta('hoje') === 1 ? 'Um prazo vence' : cap(ext(conta('hoje'))) + ' prazos vencem'} hoje.`;
    else frase = 'Você está em dia. Bom trabalho.';

    const prox = proximas()[0];
    const ABAS = [['tudo', 'Todas'], ['venc', 'Atrasadas'], ['hoje', 'Hoje'], ['prox', 'Próximas'], ['sem', 'Sem prazo']];
    let lista = f.filter((i) => est.aba === 'tudo' || grupo(i) === est.aba).filter((i) => est.area === 'todas' || i.area === est.area);
    const peso = (i) => i.off === null ? 999 : i.off;
    lista.sort((a, b) => est.ordem === 'urgente' ? peso(a) - peso(b) : peso(b) - peso(a));
    const paginas = Math.max(1, Math.ceil(lista.length / est.porPagina));
    if (est.pagina > paginas) est.pagina = paginas;
    const ini = (est.pagina - 1) * est.porPagina;
    const pagina = lista.slice(ini, ini + est.porPagina);
    const AREAS = [['todas', 'Todas as áreas'], ['Reunião', 'Reunião'], ['Rotina', 'Rotina'], ['POP', 'POP'], ['Ouvidoria', 'Ouvidoria'], ['NSP', 'NSP']];
    const ORDENS = [['urgente', 'Mais urgente primeiro'], ['distante', 'Prazo mais distante primeiro']];
    const pessoasComVenc = [...pessoas].sort((a, b) => b.vencidos.length - a.vencidos.length).slice(0, 4);
    const t90 = 41 + 6;

    return `
    <section class="heroi" aria-label="Abertura">
      <img src="assets/quarto-hsm.jpg" alt="Quarto do Hospital São Matheus">
      <div class="veu-foto" aria-hidden="true"></div>
      <div class="dentro">
        <div style="flex:1 1 380px;min-width:0">
          <h1>${saudacao}, ${EU.primeiro}!</h1>
          <p class="frase">${frase}</p>
          <div class="risco" aria-hidden="true"></div>
        </div>
        ${prox ? `<section class="prox-reuniao" aria-label="Próxima Reunião">
          <h2>Próxima Reunião · ${quando(deIso(prox.data))}, ${prox.hora}</h2>
          <p class="nome">${esc(prox.titulo)}</p>
          <p class="papel">${prox.papel === 'facilitador' ? 'Você conduz esta Reunião' : 'Você participa desta Reunião'}</p>
          <a href="#reuniao-${prox.id}">Abrir a Reunião</a>
        </section>` : ''}
      </div>
    </section>
    <div class="inicio-corpo">
      <section class="resumo" aria-label="Resumo">
        <a href="#inicio" class="cartao stat" data-ir-aba="venc"><span><span class="rot">Prazos vencidos</span><span class="valor num ${conta('venc') ? 'verm' : ''}">${dd(conta('venc'))}</span></span><span class="ic ${conta('venc') ? 'verm' : ''}">${I.alerta}</span></a>
        <a href="#inicio" class="cartao stat" data-ir-aba="hoje"><span><span class="rot">Vencem hoje</span><span class="valor num">${dd(conta('hoje'))}</span></span><span class="ic">${I.relogio}</span></a>
        <a href="#inicio" class="cartao stat" data-ir-aba="prox"><span><span class="rot">Próximos 7 dias</span><span class="valor num">${dd(conta('prox'))}</span></span><span class="ic">${I.agenda}</span></a>
        <a href="#dashboard" class="cartao stat"><span><span class="rot">No prazo em 90 dias</span><span class="valor num">${Math.round(41 / t90 * 100)}%</span></span><span class="ic">${I.certo}</span></a>
      </section>

      <div class="duas" style="margin-top:14px">
        <section class="cartao bloco larga" id="minhas-pendencias" aria-label="Minhas pendências">
          <div class="cab">
            <h2>${I.lista}Minhas pendências</h2>
            <div class="filtros">
              <div class="filtro"><button type="button" data-pop="area" aria-expanded="${est.pop === 'area'}" aria-haspopup="menu">${est.area === 'todas' ? 'Todas' : est.area}${I.baixo}</button>${est.pop === 'area' ? popMenu('area', AREAS, est.area) : ''}</div>
              <div class="filtro"><button type="button" data-pop="ordem" aria-expanded="${est.pop === 'ordem'}" aria-haspopup="menu">Prioridade${I.baixo}</button>${est.pop === 'ordem' ? popMenu('ordem', ORDENS, est.ordem) : ''}</div>
              <a href="#pendencias" class="filtro-link">Ver todas${I.seta}</a>
            </div>
          </div>
          <div class="abas" role="tablist" aria-label="Filtrar as pendências">
            ${ABAS.map(([k, t]) => `<button type="button" role="tab" aria-selected="${est.aba === k}" data-aba="${k}">${t} (${k === 'tudo' ? f.length : conta(k)})</button>`).join('')}
          </div>
          <ul class="linhas" role="tabpanel">${pagina.map(linhaFila).join('')}</ul>
          ${lista.length ? `<div class="paginador">
            <div class="pp"><label for="por-pagina">Mostrar</label><select id="por-pagina">${[5, 10, 20, 50].map((n) => `<option value="${n}"${n === est.porPagina ? ' selected' : ''}>${n}</option>`).join('')}</select><span>por página</span><span class="pp-total num">· ${lista.length} ${lista.length === 1 ? "pendência" : "pendências"}</span></div>
            <div class="pg"><span class="num" aria-live="polite">Página ${est.pagina} de ${paginas}</span>
              <button type="button" class="pg-btn" data-pagina="anterior" aria-label="Página anterior"${est.pagina <= 1 ? ' disabled' : ''}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg></button>
              <button type="button" class="pg-btn" data-pagina="proxima" aria-label="Próxima página"${est.pagina >= paginas ? ' disabled' : ''}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></button>
            </div>
          </div>` : ''}
          ${lista.length ? '' : `<p class="vazio">${est.aba === 'tudo' ? 'Nenhuma pendência aberta. Você está em dia.' : 'Nenhuma pendência nesta aba.'}</p>`}
          <p class="aviso">${I.info}${venc.length ? `Você possui ${venc.length} ${venc.length === 1 ? 'pendência atrasada' : 'pendências atrasadas'}. Recomendamos regularizar o quanto antes.` : 'Nenhuma pendência atrasada. Continue assim.'}</p>
        </section>

        <aside class="estreita">
          <section class="cartao bloco" aria-label="Ações rápidas">
            <h2 class="titulo-bloco" style="margin-bottom:12px">Ações rápidas</h2>
            <div class="tiles">
              <button type="button" class="tile" data-acao="agendar">${I.agendar}Agendar Reunião</button>
              <a class="tile" href="#calendario">${I.calCheio}Calendário</a>
              <a class="tile" href="#pendencias">${I.pendCheio}Pendências</a>
              <a class="tile" href="#pops">${I.popCheio}POPs</a>
              <a class="tile" href="#notificar">${I.notifCheio}Notificar incidente</a>
              <a class="tile" href="#ouvidoria">${I.ouvCheio}Ouvidoria</a>
            </div>
          </section>
          <section class="cartao bloco" aria-label="Quem responde a você">
            <div class="cab"><h2 style="font-size:16.5px">Quem responde a você</h2><a class="link" href="#pessoas">Ver todas</a></div>
            ${pessoasComVenc.map((p) => `<a class="pessoa" href="#pessoa-${p.id}"><span class="ini" aria-hidden="true">${p.nome.split(' ').map((x) => x[0]).join('')}</span><span><span class="pn">${p.nome}</span><span class="ps">${p.setor}</span></span><span class="tag ${p.vencidos.length ? 'verm' : ''}">${p.vencidos.length ? p.vencidos.length + (p.vencidos.length === 1 ? ' atrasada' : ' atrasadas') : 'Em dia'}</span></a>`).join('')}
          </section>
        </aside>
      </div>
      <p class="demo">Dados de demonstração. O dia em que você abre o Início fica registrado.</p>
    </div>`;
  }

  function pItem(id) {
    const it = itens.find((i) => i.id === id);
    if (!it) return pNaoAchou();
    const r = it.reuniao ? reuniao(it.reuniao) : null;
    const feito = est.feitos[it.id];
    const [cls, rot] = feito ? ['e-ok', 'Concluída'] : ESTADO[grupo(it)];
    const prazo = it.off === null ? 'Sem prazo' : `${fmt(dia(it.off))}${it.off < 0 ? ` (${-it.off} ${-it.off === 1 ? 'dia' : 'dias'} de atraso)` : ''}`;
    let acoes = '';
    if (!feito) {
      if (it.tipo === 'pendencia') acoes = `<div class="campo"><label for="anot">Anotação da conclusão</label><textarea id="anot" placeholder="O que foi feito, em poucas linhas"></textarea></div><div class="acoes-item"><button class="btn grande" data-concluir="${it.id}" data-msg="Pendência concluída.">Concluir a Pendência</button><button class="btn contorno grande" data-acao="anotar">Só registrar a anotação</button></div>`;
      if (it.tipo === 'ata') acoes = `<div class="acoes-item"><button class="btn grande" data-concluir="${it.id}" data-msg="Ata assinada. A assinatura seguiu para a ClickSign.">Assinar a Ata</button><button class="btn contorno grande" data-acao="demo" data-msg="No sistema, abre o PDF da Ata.">Ler a Ata</button></div>`;
      if (it.tipo === 'contestacao') acoes = `<div class="campo"><label for="anot">Resposta ao Paulo</label><textarea id="anot" placeholder="Explique a decisão"></textarea></div><div class="acoes-item"><button class="btn grande" data-concluir="${it.id}" data-msg="Contestação aceita. O novo prazo foi aplicado.">Aceitar o novo prazo</button><button class="btn contorno grande" data-concluir="${it.id}" data-msg="Contestação recusada. O prazo original continua.">Recusar</button></div>`;
      if (it.tipo === 'rotina') acoes = `<div class="acoes-item"><button class="btn grande" data-concluir="${it.id}" data-msg="Verificação marcada como Realizada.">Realizada</button><button class="btn contorno grande" data-nao="${it.id}">Não realizada</button></div>${est.naoRealizada[it.id] ? '<div class="campo" style="margin-top:14px"><label for="motivo">Por que não foi realizada?</label><textarea id="motivo"></textarea><button class="btn" style="align-self:flex-start;margin-top:8px" data-concluir="' + it.id + '" data-msg="Verificação marcada como Não realizada, com a anotação.">Registrar</button></div>' : ''}`;
      if (it.tipo === 'ouvidoria') acoes = `<div class="campo"><label for="anot">Resposta do setor</label><textarea id="anot" placeholder="O que o setor apurou e o que vai mudar"></textarea></div><div class="acoes-item"><button class="btn grande" data-concluir="${it.id}" data-msg="Resposta enviada à Ouvidoria.">Enviar a resposta</button></div>`;
      if (it.tipo === 'pop') acoes = `<div class="acoes-item"><button class="btn grande" data-concluir="${it.id}" data-msg="${it.titulo.startsWith('Validar') ? 'POP validado.' : 'Revisão concluída. O POP seguiu para validação.'}">${it.titulo.startsWith('Validar') ? 'Validar o POP' : 'Concluir a revisão'}</button><button class="btn contorno grande" data-acao="demo" data-msg="No sistema, abre a versão do POP lado a lado com a anterior.">Comparar versões</button></div>`;
      if (it.tipo === 'capacitacao') acoes = `<div class="acoes-item"><button class="btn grande" data-concluir="${it.id}" data-msg="Presença confirmada na Capacitação.">Confirmar presença</button></div>`;
    } else acoes = `<p class="aviso">${I.info}Este item já foi resolvido.</p>`;
    return `<div class="pagina">
      <a class="voltar" href="#inicio">${I.voltar}Voltar ao Início</a>
      <div class="cartao bloco" style="padding:24px">
        <div class="cab"><span class="estado ${cls}"><i aria-hidden="true"></i>${rot}</span><span class="pill">${it.area}</span></div>
        <h1 class="pagina-titulo" style="margin-top:12px">${esc(it.titulo)}</h1>
        <p class="pagina-sub">${esc(it.origem)}</p>
        <dl class="ficha">
          <div><dt>Prazo</dt><dd class="num">${prazo}</dd></div>
          <div><dt>Responsável</dt><dd>${EU.nome}</dd></div>
          ${r ? `<div><dt>Reunião de origem</dt><dd><a href="#reuniao-${r.id}">${esc(r.titulo)}, ${curto(deIso(r.data))}</a></dd></div>` : ''}
        </dl>
        <h2 class="titulo-bloco" style="margin-top:22px">O que precisa ser feito</h2>
        <p style="max-width:70ch">${esc(it.detalhe)}</p>
        <div class="form-item" style="display:flex;flex-direction:column;gap:14px;margin-top:16px;max-width:720px">${acoes}</div>
      </div>
    </div>`;
  }

  function pReunioes() {
    const futuras = proximas();
    const passadas = reunioes.filter((r) => difDias(deIso(r.data)) < 0).sort((a, b) => b.data.localeCompare(a.data));
    const tab = (lista) => `<div class="tabela-rola"><table class="tab"><thead><tr><th>Data</th><th>Reunião</th><th>Seu papel</th><th>Ata</th></tr></thead><tbody>${lista.map((r) => `<tr><td class="num">${fmt(deIso(r.data))}, ${r.hora}</td><td><a href="#reuniao-${r.id}">${esc(r.titulo)}</a></td><td>${r.papel === 'facilitador' ? 'Conduz' : 'Participa'}</td><td>${r.ata}</td></tr>`).join('')}</tbody></table></div>`;
    return `<div class="pagina">
      <div class="cab"><div><h1 class="pagina-titulo">Reuniões e metas</h1><p class="pagina-sub">As Reuniões em que você conduz ou participa.</p></div><button class="btn grande" data-acao="agendar">Agendar Reunião</button></div>
      <section class="cartao bloco" style="margin-top:18px"><h2 class="titulo-bloco" style="margin-bottom:8px">Próximas</h2>${tab(futuras)}</section>
      <section class="cartao bloco" style="margin-top:14px"><h2 class="titulo-bloco" style="margin-bottom:8px">Já aconteceram</h2>${tab(passadas)}</section>
    </div>`;
  }

  function pReuniao(id) {
    const r = reuniao(id);
    if (!r) return pNaoAchou();
    const d = deIso(r.data), futura = difDias(d) >= 0;
    const geradas = itens.filter((i) => i.reuniao === r.id);
    return `<div class="pagina">
      <a class="voltar" href="#reunioes">${I.voltar}Voltar às Reuniões</a>
      <div class="cartao bloco" style="padding:24px">
        <span class="pill">${futura ? 'Programada' : 'Realizada'}</span>
        <h1 class="pagina-titulo" style="margin-top:12px">${esc(r.titulo)}</h1>
        <p class="pagina-sub">${longo(d)}, ${r.hora} · ${r.papel === 'facilitador' ? 'Você conduz esta Reunião' : 'Você participa desta Reunião'}</p>
        <dl class="ficha">
          <div><dt>Participantes</dt><dd>${r.participantes.length} pessoas</dd></div>
          <div><dt>Ata</dt><dd>${r.ata}</dd></div>
          <div><dt>Pendências geradas</dt><dd>${geradas.length}</dd></div>
        </dl>
        <div class="duas" style="margin-top:20px">
          <div class="larga">
            <h2 class="titulo-bloco">Pauta</h2>
            <ol style="margin:10px 0 0;padding-left:20px;display:flex;flex-direction:column;gap:6px">${r.pauta.map((p) => `<li>${esc(p)}</li>`).join('')}</ol>
            ${geradas.length ? `<h2 class="titulo-bloco" style="margin-top:22px">Pendências desta Reunião</h2><ul class="linhas">${geradas.map((it) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto auto"><span class="t">${esc(it.titulo)}<small>${it.off === null ? 'Sem prazo' : 'Prazo ' + fmt(dia(it.off))}</small></span><span class="estado ${est.feitos[it.id] ? 'e-ok' : ESTADO[grupo(it)][0]}"><i aria-hidden="true"></i>${est.feitos[it.id] ? 'Concluída' : ESTADO[grupo(it)][1]}</span><a class="btn" href="#item-${it.id}">Abrir</a></li>`).join('')}</ul>` : ''}
          </div>
          <div class="estreita">
            <h2 class="titulo-bloco">Participantes</h2>
            <ul style="list-style:none;margin:6px 0 0;padding:0">${r.participantes.map((n) => `<li style="padding:8px 0;border-bottom:1px solid var(--linha)">${n}${n === EU.nome ? ' (você)' : ''}</li>`).join('')}</ul>
            ${futura && r.papel === 'facilitador' ? `<button class="btn grande" style="margin-top:16px" data-acao="demo" data-msg="No sistema, começa a gravação para a Ata guiada.">Gravar a Reunião</button>` : ''}
            ${!futura ? `<button class="btn contorno grande" style="margin-top:16px" data-acao="demo" data-msg="No sistema, abre o PDF da Ata.">Abrir a Ata</button>` : ''}
          </div>
        </div>
      </div>
    </div>`;
  }

  function pCalendario() {
    const ano = HOJE.getFullYear(), mes = HOJE.getMonth();
    const primeiro = new Date(ano, mes, 1);
    const inicio = new Date(primeiro); inicio.setDate(1 - ((primeiro.getDay() + 6) % 7));
    const dias = [];
    for (let i = 0; i < 42; i++) { const d = new Date(inicio); d.setDate(inicio.getDate() + i); dias.push(d); }
    const ultimaSemanaUsada = dias.slice(35).some((d) => d.getMonth() === mes) ? 42 : 35;
    return `<div class="pagina">
      <div class="cab"><div><h1 class="pagina-titulo">${cap(MESES[mes])} de ${ano}</h1><p class="pagina-sub">Clique numa Reunião para abrir, ou num dia livre para agendar.</p></div><button class="btn grande" data-acao="agendar">Agendar Reunião</button></div>
      <div class="cartao bloco" style="margin-top:18px">
        <div class="cal">
          ${['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'].map((s) => `<div class="dsem">${s}</div>`).join('')}
          ${dias.slice(0, ultimaSemanaUsada).map((d) => {
            const evs = reunioes.filter((r) => r.data === iso(d)).sort((a, b) => a.hora.localeCompare(b.hora));
            return `<div class="dia ${d.getMonth() !== mes ? 'fora' : ''} ${iso(d) === iso(HOJE) ? 'hoje' : ''}">
              <button type="button" class="dia-num" data-acao="agendar" data-dia="${iso(d)}" aria-label="Agendar em ${fmt(d)}"><b class="num">${d.getDate()}</b></button>
              ${evs.map((r) => `<a class="ev" href="#reuniao-${r.id}" title="${esc(r.titulo)}">${r.hora} ${esc(r.titulo)}</a>`).join('')}
            </div>`;
          }).join('')}
        </div>
      </div>
    </div>`;
  }

  function pPendencias() {
    const termo = est.pendBusca.trim().toLowerCase();
    const lista = abertos().filter((i) => !termo || (i.titulo + ' ' + i.origem).toLowerCase().includes(termo)).sort((a, b) => (a.off ?? 999) - (b.off ?? 999));
    const feitosAgora = itens.filter((i) => est.feitos[i.id]).map((i) => ({ titulo: i.titulo, quando: HOJE, noPrazo: i.off === null || i.off >= 0, area: i.area }));
    const conc = [...feitosAgora, ...concluidos];
    return `<div class="pagina">
      <div class="cab"><div><h1 class="pagina-titulo">Pendências</h1><p class="pagina-sub">Tudo o que está no seu nome, de todas as áreas.</p></div>
        <div class="modelos" role="group" aria-label="Forma de ver"><button type="button" aria-pressed="true">Lista</button><button type="button" aria-pressed="false" data-vista="kanban">Kanban</button></div></div>
      <div class="cartao bloco" style="margin-top:18px">
        <div class="cab">
          <div class="abas" role="tablist" style="margin:0;border:0">
            <button type="button" role="tab" aria-selected="${est.pendAba === 'abertas'}" data-pend-aba="abertas">Abertas (${abertos().length})</button>
            <button type="button" role="tab" aria-selected="${est.pendAba === 'concluidas'}" data-pend-aba="concluidas">Concluídas (${conc.length})</button>
          </div>
          <div class="campo" style="flex:0 1 320px"><label for="busca-pend" class="sr">Buscar pendência</label><input id="busca-pend" type="search" placeholder="Buscar pendência" value="${esc(est.pendBusca)}"></div>
        </div>
        <div class="tabela-rola" style="margin-top:10px">
        ${est.pendAba === 'abertas' ? `<table class="tab"><thead><tr><th>Situação</th><th>Pendência</th><th>Área</th><th>Prazo</th><th></th></tr></thead><tbody>
          ${lista.map((i) => `<tr><td><span class="estado ${ESTADO[grupo(i)][0]}"><i aria-hidden="true"></i>${ESTADO[grupo(i)][1]}</span></td><td><a href="#item-${i.id}">${esc(i.titulo)}</a><div style="font-size:12.5px;color:var(--texto2)">${esc(i.origem)}</div></td><td><span class="pill">${i.area}</span></td><td class="num">${i.off === null ? 'Sem prazo' : fmt(dia(i.off))}</td><td><a class="btn" href="#item-${i.id}">${ACAO[i.tipo]}</a></td></tr>`).join('')}
          </tbody></table>${lista.length ? '' : '<p class="vazio">Nada encontrado com esse texto.</p>'}`
        : `<table class="tab"><thead><tr><th>Pendência</th><th>Área</th><th>Concluída em</th><th>Prazo</th></tr></thead><tbody>${conc.map((c) => `<tr><td>${esc(c.titulo)}</td><td><span class="pill">${c.area}</span></td><td class="num">${fmt(c.quando)}</td><td><span class="estado ${c.noPrazo ? 'e-ok' : 'e-venc'}"><i aria-hidden="true"></i>${c.noPrazo ? 'No prazo' : 'Fora do prazo'}</span></td></tr>`).join('')}</tbody></table>`}
        </div>
      </div>
    </div>`;
  }

  function pRotinas() {
    const rot = itens.filter((i) => i.area === 'Rotina');
    const extra = [{ titulo: 'Checagem de validade dos medicamentos da farmácia satélite', ciclo: 'Mensal', ate: dia(4), feita: 'Realizada' }];
    return `<div class="pagina">
      <h1 class="pagina-titulo">Rotinas</h1><p class="pagina-sub">As Rotinas em que você é responsável, com a Verificação do ciclo atual.</p>
      <div class="cartao bloco" style="margin-top:18px"><div class="tabela-rola"><table class="tab"><thead><tr><th>Rotina</th><th>Ciclo</th><th>Verificar até</th><th>Verificação</th><th></th></tr></thead><tbody>
        ${rot.map((i) => `<tr><td><a href="#item-${i.id}">${esc(i.titulo)}</a></td><td>${i.origem.includes('quinzenal') ? 'Quinzenal' : 'Semanal'}</td><td class="num">${fmt(dia(i.off))}</td><td>${est.feitos[i.id] ? '<span class="estado e-ok"><i aria-hidden="true"></i>Marcada</span>' : `<span class="estado ${ESTADO[grupo(i)][0]}"><i aria-hidden="true"></i>Falta marcar</span>`}</td><td>${est.feitos[i.id] ? '' : `<button class="btn" data-concluir="${i.id}" data-msg="Verificação marcada como Realizada." data-ficar="1">Realizada</button>`}</td></tr>`).join('')}
        ${extra.map((e) => `<tr><td>${e.titulo}</td><td>${e.ciclo}</td><td class="num">${fmt(e.ate)}</td><td><span class="estado e-ok"><i aria-hidden="true"></i>${e.feita}</span></td><td></td></tr>`).join('')}
      </tbody></table></div></div>
    </div>`;
  }

  function pPops() {
    const t = est.popBusca.trim().toLowerCase();
    const lista = pops.filter((p) => !t || p.titulo.toLowerCase().includes(t));
    return `<div class="pagina">
      <h1 class="pagina-titulo">POPs</h1><p class="pagina-sub">Procedimentos Operacionais Padrão da Diretoria Assistencial.</p>
      <div class="cartao bloco" style="margin-top:18px">
        <div class="campo" style="max-width:360px"><label for="busca-pop" class="sr">Buscar POP</label><input id="busca-pop" type="search" placeholder="Buscar POP" value="${esc(est.popBusca)}"></div>
        <div class="tabela-rola" style="margin-top:10px"><table class="tab"><thead><tr><th>POP</th><th>Versão</th><th>Situação</th><th></th></tr></thead><tbody>
        ${lista.map((p) => { const it = p.item && itens.find((i) => i.id === p.item); const pend = it && !est.feitos[it.id];
          return `<tr><td>${p.titulo}</td><td class="num">v${p.versao}</td><td>${pend ? `<span class="estado e-hoje"><i aria-hidden="true"></i>${p.status}, com você</span>` : `<span class="pill">${it ? 'Seguiu adiante' : p.status}</span>`}</td><td>${pend ? `<a class="btn" href="#item-${it.id}">${ACAO.pop}</a>` : `<button class="btn contorno" data-acao="demo" data-msg="No sistema, abre o POP vigente na Biblioteca.">Ler</button>`}</td></tr>`; }).join('')}
        </tbody></table></div>
      </div>
    </div>`;
  }

  function pOuvidoria() {
    const casos = itens.filter((i) => i.area === 'Ouvidoria');
    return `<div class="pagina">
      <h1 class="pagina-titulo">Ouvidoria do setor</h1><p class="pagina-sub">Manifestações enviadas à Diretoria Assistencial, com o prazo de resposta.</p>
      <div class="cartao bloco" style="margin-top:18px"><div class="tabela-rola"><table class="tab"><thead><tr><th>Caso</th><th>Manifestação</th><th>Responder até</th><th>Situação</th><th></th></tr></thead><tbody>
        ${casos.map((c) => `<tr><td class="num">${c.origem.match(/\d+/)[0]}</td><td><a href="#item-${c.id}">${esc(c.titulo)}</a></td><td class="num">${fmt(dia(c.off))}</td><td>${est.feitos[c.id] ? '<span class="estado e-ok"><i aria-hidden="true"></i>Respondido</span>' : `<span class="estado ${ESTADO[grupo(c)][0]}"><i aria-hidden="true"></i>Aguardando resposta</span>`}</td><td>${est.feitos[c.id] ? '' : `<a class="btn" href="#item-${c.id}">Responder</a>`}</td></tr>`).join('')}
        <tr><td class="num">470</td><td>Barulho no corredor da maternidade à noite</td><td class="num">${fmt(dia(-12))}</td><td><span class="estado e-ok"><i aria-hidden="true"></i>Respondido</span></td><td></td></tr>
      </tbody></table></div></div>
    </div>`;
  }

  function pNotificar() {
    if (est.notifEnviada) return `<div class="pagina"><div class="cartao bloco entra" style="padding:28px;max-width:720px">
      <span class="estado e-ok"><i aria-hidden="true"></i>Notificação recebida</span>
      <h1 class="pagina-titulo" style="margin-top:10px">Obrigado por notificar.</h1>
      <p class="pagina-sub">O Núcleo de Segurança do Paciente recebeu o relato e vai analisar. Guarde o protocolo para acompanhar.</p>
      <p style="font-size:28px;font-weight:700;color:var(--titulo);margin:18px 0 0" class="num">${est.notifEnviada}</p>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:20px"><a class="btn grande" href="#inicio">Voltar ao Início</a><button class="btn contorno grande" data-acao="nova-notif">Notificar outro incidente</button></div>
    </div></div>`;
    return `<div class="pagina">
      <h1 class="pagina-titulo">Notificar incidente</h1><p class="pagina-sub">Qualquer pessoa do hospital pode notificar. A notificação vai para o Núcleo de Segurança do Paciente e pode ser anônima.</p>
      <form class="cartao bloco" id="form-notif" style="margin-top:18px;padding:24px;display:flex;flex-direction:column;gap:16px;max-width:860px">
        <div class="grade-form">
          <div class="campo"><label for="n-tipo">Tipo de incidente</label><select id="n-tipo" required><option value="">Escolha</option><option>Queda</option><option>Erro de medicação</option><option>Identificação do paciente</option><option>Lesão por pressão</option><option>Outro</option></select></div>
          <div class="campo"><label for="n-local">Onde aconteceu</label><input id="n-local" required placeholder="Ex.: 3º andar, leito 12"></div>
          <div class="campo"><label for="n-data">Quando</label><input id="n-data" type="date" required value="${iso(HOJE)}"></div>
        </div>
        <div class="campo"><label for="n-desc">O que aconteceu</label><textarea id="n-desc" required placeholder="Descreva o que você viu, sem nomes de pacientes"></textarea></div>
        <label style="display:flex;align-items:center;gap:10px;font-size:15px"><input type="checkbox" id="n-anon" style="width:20px;height:20px"> Enviar sem me identificar</label>
        <div><button class="btn grande" type="submit">Enviar a notificação</button></div>
      </form>
    </div>`;
  }

  function pNsp() {
    const cap = itens.find((i) => i.id === 'p13');
    const r4 = reuniao('r4');
    const card = (t, v, d, href, btn) => `<div class="cartao bloco"><span class="rot" style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--texto2)">${t}</span><p style="margin:8px 0 0;font-size:24px;font-weight:700;color:var(--titulo)">${v}</p><p style="margin:4px 0 0;color:var(--texto2);font-size:14px">${d}</p>${href ? `<a class="btn" style="margin-top:14px" href="${href}">${btn}</a>` : ''}</div>`;
    return `<div class="pagina">
      <h1 class="pagina-titulo">Núcleo de Segurança do Paciente</h1><p class="pagina-sub">Visão geral do que é seu no Núcleo.</p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-top:18px">
        ${card('Termo de Adesão', 'Assinado', 'Válido até dezembro de 2027')}
        ${card('Capacitação', est.feitos.p13 ? 'Presença confirmada' : 'Confirme a presença', `${esc(cap.titulo.replace('Capacitação: ', ''))}, ${quando(dia(cap.off))} às 15:00`, est.feitos.p13 ? '' : '#item-p13', 'Confirmar presença')}
        ${card('Próxima Reunião do Núcleo', `${quando(deIso(r4.data))}, ${r4.hora}`, esc(r4.titulo), '#reuniao-r4', 'Abrir a Reunião')}
        ${card('Documentos', '3 documentos', '1 publicado esta semana: regimento interno, versão 2', '#nsp', 'Ver os documentos')}
      </div>
      <div class="cartao bloco" style="margin-top:14px;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px"><div><h2 class="titulo-bloco">Viu um incidente?</h2><p class="pagina-sub" style="margin-top:4px">A notificação pode ser anônima e leva menos de 2 minutos.</p></div><a class="btn grande" href="#notificar">Notificar incidente</a></div>
    </div>`;
  }

  function pDashboard() {
    const meses = [[MESES[(HOJE.getMonth() + 10) % 12], 12, 3], [MESES[(HOJE.getMonth() + 11) % 12], 15, 2], [MESES[HOJE.getMonth()], 14, 1]];
    const max = Math.max(...meses.map((m) => m[1] + m[2]));
    const areas = [['Reuniões', 26, 4], ['Rotinas', 9, 1], ['POPs', 4, 0], ['Ouvidoria', 2, 1]];
    return `<div class="pagina">
      <h1 class="pagina-titulo">Dashboard</h1><p class="pagina-sub">As suas entregas dos últimos 90 dias.</p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-top:18px">
        <div class="cartao bloco"><span class="rot" style="font-size:13.5px;color:var(--texto2)">No prazo</span><p class="num" style="margin:6px 0 0;font-size:32px;font-weight:700;color:var(--titulo)">87%</p></div>
        <div class="cartao bloco"><span class="rot" style="font-size:13.5px;color:var(--texto2)">Entregas no prazo</span><p class="num" style="margin:6px 0 0;font-size:32px;font-weight:700;color:var(--titulo)">41</p></div>
        <div class="cartao bloco"><span class="rot" style="font-size:13.5px;color:var(--texto2)">Entregas fora do prazo</span><p class="num" style="margin:6px 0 0;font-size:32px;font-weight:700;color:var(--verm)">6</p></div>
      </div>
      <div class="duas" style="margin-top:14px">
        <section class="cartao bloco larga"><h2 class="titulo-bloco">Entregas por mês</h2>
          <div class="barras" role="img" aria-label="${meses.map((m) => `${m[0]}: ${m[1]} no prazo e ${m[2]} fora`).join('; ')}">
            ${meses.map((m) => `<div class="col"><small class="num">${m[1] + m[2]}</small><div class="pilha" style="height:${(m[1] + m[2]) / max * 140}px"><span class="np" style="height:${m[1] / (m[1] + m[2]) * 100}%"></span><span class="fp" style="height:${m[2] / (m[1] + m[2]) * 100}%"></span></div><small>${m[0]}</small></div>`).join('')}
          </div>
          <div class="legenda"><span><i style="background:var(--btn-fundo)"></i>No prazo</span><span><i style="background:var(--ponto-verm)"></i>Fora do prazo</span></div>
        </section>
        <section class="cartao bloco estreita"><h2 class="titulo-bloco">Por área</h2>
          ${areas.map((a) => `<div style="margin-top:12px"><div style="display:flex;justify-content:space-between;font-size:14px"><span>${a[0]}</span><span class="num" style="color:var(--texto2)">${a[1]} no prazo, ${a[2]} fora</span></div><div style="height:8px;border-radius:999px;background:var(--suave2);margin-top:6px;overflow:hidden"><div style="height:100%;width:${a[1] / 30 * 100}%;background:var(--btn-fundo);border-radius:999px"></div></div></div>`).join('')}
        </section>
      </div>
    </div>`;
  }

  function pPessoas() {
    return `<div class="pagina">
      <a class="voltar" href="#inicio">${I.voltar}Voltar ao Início</a>
      <h1 class="pagina-titulo">Quem responde a você</h1><p class="pagina-sub">As pessoas responsáveis por Pendências das Reuniões que você conduz.</p>
      <div class="cartao bloco" style="margin-top:18px"><div class="tabela-rola"><table class="tab"><thead><tr><th>Pessoa</th><th>Atrasadas</th><th>Em aberto</th><th>Entregas em 90 dias</th><th>Último acesso</th></tr></thead><tbody>
        ${pessoas.map((p) => `<tr><td><a href="#pessoa-${p.id}">${p.nome}</a><div style="font-size:12.5px;color:var(--texto2)">${p.cargo}</div></td><td class="num" style="color:${p.vencidos.length ? 'var(--verm)' : 'var(--texto)'};font-size:18px">${p.vencidos.length}</td><td class="num" style="font-size:18px">${p.abertos}</td><td class="num">${p.np} no prazo, ${p.fp} fora</td><td>${p.acesso}</td></tr>`).join('')}
      </tbody></table></div></div>
    </div>`;
  }

  function pPessoa(id) {
    const p = pessoas.find((x) => x.id === id);
    if (!p) return pNaoAchou();
    return `<div class="pagina">
      <a class="voltar" href="#pessoas">${I.voltar}Voltar a Quem responde a você</a>
      <div class="cartao bloco" style="padding:24px">
        <h1 class="pagina-titulo">${p.nome}</h1><p class="pagina-sub">${p.cargo} · ${p.setor} · último acesso ${p.acesso}</p>
        <dl class="ficha"><div><dt>Atrasadas</dt><dd class="num" style="color:${p.vencidos.length ? 'var(--verm)' : 'inherit'}">${p.vencidos.length}</dd></div><div><dt>Em aberto</dt><dd class="num">${p.abertos}</dd></div><div><dt>Entregas em 90 dias</dt><dd class="num">${p.np} no prazo, ${p.fp} fora</dd></div></dl>
        <h2 class="titulo-bloco" style="margin-top:22px">O que venceu e não foi entregue</h2>
        ${p.vencidos.length ? `<ul class="linhas">${p.vencidos.map(([t, n]) => `<li class="linha" style="grid-template-columns:minmax(0,1fr) auto"><span class="t">${t}</span><span class="estado e-venc"><i aria-hidden="true"></i>há ${n} ${n === 1 ? 'dia' : 'dias'}</span></li>`).join('')}</ul>
          <button class="btn grande" style="margin-top:14px" data-acao="demo" data-msg="Lembrete enviado para ${p.nome.split(' ')[0]}.">Enviar um lembrete</button>` : '<p class="vazio">Nada vencido. Em dia.</p>'}
      </div>
    </div>`;
  }

  function pFora(id) {
    const nome = { manual: 'O Manual', processos: 'As Definições de processo', kanban: 'O Kanban de Pendências', membros: 'Os Membros do Núcleo', documentos: 'Os Documentos do Núcleo', capacitacoes: 'As Capacitações do Núcleo', agenda: 'A Agenda regulatória', 'reunioes-do-nucleo': 'As Reuniões do Núcleo' }[id] || 'Esta tela';
    return `<div class="pagina"><h1 class="pagina-titulo">${nome} fica fora deste protótipo.</h1><p class="pagina-sub">O protótipo cobre o Início e as telas que ele abre. <a href="#inicio">Voltar ao Início</a></p></div>`;
  }

  function pNaoAchou() {
    return `<div class="pagina"><h1 class="pagina-titulo">Não encontramos essa tela.</h1><p class="pagina-sub"><a href="#inicio">Voltar ao Início</a></p></div>`;
  }

  // ------------------------------------------------------------------ desenho
  const $ = (id) => document.getElementById(id);
  function desenhar(foco) {
    const { pag, id } = rota();
    document.documentElement.setAttribute('data-modelo', est.modelo);
    document.querySelectorAll('.modelos button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.modelo === est.modelo)));
    const ativo = MENU_ATIVO[pag] || pag;
    const atual = est.modelo === 'atual';
    const chave = pag === 'fora' ? 'fora-' + id : ativo;
    $('menu-itens').innerHTML = atual ? `<ul>${menuArvore(ARVORE, chave, 0)}</ul>` : window.NOVIDADES.menuNovo(chave);
    $('menu-rodape').innerHTML = atual ? '' : window.NOVIDADES.rodapeNovo(chave);
    document.querySelector('.app').classList.toggle('recolhido', !atual && !!est.recolhido);
    $('trilha').textContent = TRILHA[pag].toUpperCase();
    $('data-hoje').textContent = longo(HOJE);
    const venc = fila().filter((i) => grupo(i) === 'venc').length;
    document.title = (venc ? `(${venc}) ` : '') + TRILHA[pag] + ' | Hospital Reuniões';
    const P = { fora: () => pFora(id), inicio: atual ? window.NOVIDADES.pInicioAtual : pInicio, reunioes: pReunioes, reuniao: () => pReuniao(id), dashboard: pDashboard, calendario: pCalendario, pendencias: pPendencias,
      item: () => pItem(id), rotinas: pRotinas, pops: pPops, ouvidoria: pOuvidoria, notificar: pNotificar, nsp: pNsp, pessoas: pPessoas, pessoa: () => pPessoa(id) };
    $('conteudo').innerHTML = P[pag]();
    if (atual && pag === 'inicio') est.jaEntrou = true;
    $('menu').classList.toggle('aberto', est.menu);
    $('veu').hidden = !est.menu;
    $('abrir-menu').setAttribute('aria-expanded', String(est.menu));
    $('bolinha').hidden = est.lidas;
    $('sino').setAttribute('aria-label', est.lidas ? 'Notificações' : 'Notificações, 3 novas');
    $('sino').setAttribute('aria-expanded', String(est.sino));
    const cs = $('caixa-sino');
    cs.hidden = !est.sino;
    if (est.sino) cs.innerHTML = `<h2>Notificações</h2>${notificacoes.map((n) => `<a href="${n.href}">${n.texto}<span>${n.sub}</span></a>`).join('')}<button type="button" class="btn contorno" style="width:100%;margin-top:6px" data-acao="ler-todas">Marcar todas como lidas</button>`;
    if (foco) { window.scrollTo(0, 0); $('conteudo').focus({ preventScroll: true }); }
  }

  function aviso(msg) {
    const t = $('toast');
    t.textContent = msg; t.hidden = false;
    clearTimeout(aviso.t); aviso.t = setTimeout(() => { t.hidden = true; }, 3400);
  }

  function abrirAgendar(dataIso) {
    const m = $('modal');
    m.hidden = false;
    m.innerHTML = `<form class="modal entra" id="form-agendar" role="dialog" aria-modal="true" aria-labelledby="ag-tit">
      <h2 id="ag-tit">Agendar Reunião</h2>
      <p style="margin:0 0 16px;color:var(--texto2);font-size:14px">Você fica como quem conduz. Os participantes recebem o convite por e-mail.</p>
      <div style="display:flex;flex-direction:column;gap:14px">
        <div class="campo"><label for="ag-titulo">Título</label><input id="ag-titulo" required placeholder="Ex.: Reunião da Diretoria Assistencial"></div>
        <div class="grade-form"><div class="campo"><label for="ag-data">Data</label><input id="ag-data" type="date" required value="${dataIso || iso(dia(1))}"></div><div class="campo"><label for="ag-hora">Hora</label><input id="ag-hora" type="time" required value="10:00"></div></div>
        <div class="campo"><label for="ag-part">Participantes</label><input id="ag-part" placeholder="Nomes separados por vírgula"></div>
        <div class="campo"><label for="ag-pauta">Pauta</label><textarea id="ag-pauta" placeholder="Um assunto por linha"></textarea></div>
      </div>
      <div class="acoes"><button type="button" class="btn contorno grande" data-acao="fechar-modal">Cancelar</button><button type="submit" class="btn grande">Agendar</button></div>
    </form>`;
    setTimeout(() => $('ag-titulo').focus(), 30);
  }
  function abrirBusca() {
    est.busca = ''; est.recolhido = false; est.menu = window.innerWidth <= 900; desenhar();
    const c = $('nv-busca-input'); if (c) c.focus();
  }
  function fecharModal() { $('modal').hidden = true; $('modal').innerHTML = ''; }

  // ------------------------------------------------------------------ eventos
  document.addEventListener('click', (ev) => {
    const linhaPessoa = ev.target.closest('[data-pessoa-at]');
    if (linhaPessoa) { const id = linhaPessoa.dataset.pessoaAt; est.pessoaAberta = est.pessoaAberta === id ? null : id; desenhar(); const v = document.querySelector('[data-pessoa-at="' + id + '"]'); if (v) v.focus(); return; }
    const alvo = ev.target.closest('button, a');
    if (!alvo) { if (est.pop || est.sino) { est.pop = null; est.sino = false; desenhar(); } return; }
    const d = alvo.dataset;
    if (d.modelo && alvo.closest('.modelos')) { est.modelo = d.modelo; try { localStorage.setItem('novidades-modelo', d.modelo); } catch (e) { /* sem armazenamento */ } desenhar(); return; }
    if (d.grupo) { est.grupos[d.grupo] = alvo.getAttribute('aria-expanded') !== 'true'; desenhar(); return; }
    if (d.ancora) { ev.preventDefault(); const el = $(d.ancora); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); return; }
    if (d.pop) { est.pop = est.pop === d.pop ? null : d.pop; est.sino = false; desenhar(); return; }
    if (d.escolha) { est[d.escolha] = d.valor; est.pop = null; est.pagina = 1; desenhar(); return; }
    if (d.aba) { est.aba = d.aba; est.pop = null; est.pagina = 1; desenhar(); return; }
    if (d.pagina) { est.pagina += d.pagina === 'proxima' ? 1 : -1; desenhar(); const el = $('minhas-pendencias'); if (el && el.getBoundingClientRect().top < 0) el.scrollIntoView({ block: 'start' }); return; }
    if (d.secao) { est.secoes[d.secao] = alvo.getAttribute('aria-expanded') !== 'true'; desenhar(); return; }
    if (d.irAba) { ev.preventDefault(); est.aba = d.irAba; if (location.hash !== '#inicio' && location.hash) location.hash = '#inicio'; desenhar(); const el = $('minhas-pendencias'); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); return; }
    if (d.pendAba) { est.pendAba = d.pendAba; desenhar(); return; }
    if (d.concluir) {
      est.feitos[d.concluir] = true; est.naoRealizada[d.concluir] = false; aviso(d.msg);
      if (d.ficar) desenhar(); else location.hash = '#inicio';
      return;
    }
    if (d.nao) { est.naoRealizada[d.nao] = true; desenhar(); setTimeout(() => $('motivo') && $('motivo').focus(), 30); return; }
    if (alvo.id === 'abrir-menu') { est.menu = !est.menu; desenhar(); return; }
    if (alvo.id === 'veu') { est.menu = false; desenhar(); return; }
    if (alvo.id === 'sino') { est.sino = !est.sino; est.pop = null; desenhar(); return; }
    if (d.acao === 'ler-todas') { est.lidas = true; est.sino = false; desenhar(); aviso('Notificações marcadas como lidas.'); return; }
    if (d.acao === 'agendar') { abrirAgendar(d.dia); return; }
    if (d.acao === 'paleta') { abrirBusca(); return; }
    if (d.acao === 'fechar-busca') { est.busca = null; desenhar(); return; }
    if (d.fechaBusca) { est.busca = null; if (location.hash === alvo.getAttribute('href')) desenhar(); return; }
    if (d.acao === 'recolher') { est.recolhido = !est.recolhido; try { localStorage.setItem('novidades-recolhido', est.recolhido ? '1' : '0'); } catch (e) { /* sem armazenamento */ } desenhar(); return; }
    if (d.fechaPaleta) { ev.preventDefault(); const destino = alvo.getAttribute('href'); fecharModal(); if (location.hash === destino) desenhar(true); else location.hash = destino; return; }
    if (d.vista) { aviso('No sistema, abre as Pendências em Kanban, por coluna de situação.'); return; }
    if (d.acao === 'fechar-modal') { fecharModal(); return; }
    if (d.acao === 'demo') { aviso(d.msg); return; }
    if (d.acao === 'anotar') { aviso('Anotação registrada. A Pendência continua aberta.'); return; }
    if (d.acao === 'nova-notif') { est.notifEnviada = null; desenhar(true); return; }
    if (alvo.tagName === 'A' && (est.pop || est.sino || est.menu)) { est.pop = null; est.sino = false; est.menu = false; }
  });
  document.addEventListener('submit', (ev) => {
    ev.preventDefault();
    if (ev.target.id === 'form-agendar') {
      const titulo = $('ag-titulo').value.trim(), data = $('ag-data').value, hora = $('ag-hora').value;
      if (!titulo || !data || !hora) return;
      const part = $('ag-part').value.split(',').map((s) => s.trim()).filter(Boolean);
      const pauta = $('ag-pauta').value.split('\n').map((s) => s.trim()).filter(Boolean);
      const nova = { id: 'n' + Date.now(), titulo, data, hora, papel: 'facilitador', ata: 'A Reunião ainda não aconteceu', participantes: [EU.nome, ...part], pauta: pauta.length ? pauta : ['Pauta a definir'] };
      reunioes.push(nova);
      fecharModal();
      aviso(`Reunião agendada para ${fmt(deIso(data))}, ${hora}.`);
      location.hash = '#reuniao-' + nova.id;
    }
    if (ev.target.id === 'form-notif') {
      est.notifEnviada = 'NSP-' + HOJE.getFullYear() + '-' + String(Math.floor(1000 + Math.random() * 9000));
      desenhar(true);
    }
  });
  document.addEventListener('change', (ev) => {
    if (ev.target.id === 'por-pagina') { est.porPagina = Number(ev.target.value); est.pagina = 1; desenhar(); const s = $('por-pagina'); if (s) s.focus(); }
  });
  document.addEventListener('input', (ev) => {
    if (ev.target.id === 'nv-busca-input') {
      const pos = ev.target.selectionStart; est.busca = ev.target.value; desenhar();
      const c = $('nv-busca-input'); c.focus(); c.setSelectionRange(pos, pos); return;
    }
    if (ev.target.id === 'busca-pend' || ev.target.id === 'busca-pop') {
      const campo = ev.target.id, pos = ev.target.selectionStart;
      if (campo === 'busca-pend') est.pendBusca = ev.target.value; else est.popBusca = ev.target.value;
      desenhar();
      const novo = $(campo); novo.focus(); novo.setSelectionRange(pos, pos);
    }
  });
  document.addEventListener('keydown', (ev) => {
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k' && est.modelo !== 'atual') { ev.preventDefault(); abrirBusca(); return; }
    if (ev.target.id === 'nv-busca-input' && ev.key === 'Enter') { ev.preventDefault(); const a = document.querySelector('.nv-res'); if (a) a.click(); return; }
    if (ev.target.id === 'nv-busca-input' && ev.key === 'Escape') { est.busca = null; desenhar(); const b = document.querySelector('.nv-busca'); if (b) b.focus(); return; }
    if (ev.key === 'Enter' && ev.target.dataset && ev.target.dataset.pessoaAt) { ev.preventDefault(); ev.target.click(); return; }
    if (ev.key !== 'Escape') return;
    if (!$('modal').hidden) { fecharModal(); return; }
    if (est.pop || est.sino || est.menu) { est.pop = null; est.sino = false; est.menu = false; desenhar(); }
  });
  $('modal').addEventListener('click', (ev) => { if (ev.target.id === 'modal') fecharModal(); });
  window.addEventListener('hashchange', () => { est.busca = null; est.pop = null; est.sino = false; est.menu = false; desenhar(true); });

  window.NOVIDADES = { itens, reunioes, pessoas, est, dia, deIso, difDias, curto, longo, esc, ext, cap, EU, HOJE, I };
  document.addEventListener('DOMContentLoaded', () => desenhar());
})();
