// PROTÓTIPO, descartável (integração Fireflies, ADR 0113 proposta).
// O Código da gravação: letra do módulo e cinco números, o último conferindo os
// outros (dígito de Luhn). No produto ele seria sorteado e guardado no banco;
// aqui sai de um hash do id da Reunião, só para a tela ter um código estável.

function luhn(digitos: string): number {
  let soma = 0;
  for (let i = 0; i < digitos.length; i++) {
    let d = Number(digitos[digitos.length - 1 - i]);
    if (i % 2 === 0) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    soma += d;
  }
  return (10 - (soma % 10)) % 10;
}

export function codigoDaGravacao(idReuniao: string, doNucleo = false): string {
  let h = 0;
  for (const c of idReuniao) h = (h * 31 + c.charCodeAt(0)) % 10000;
  const quatro = String(h).padStart(4, "0");
  return `${doNucleo ? "N" : "R"}-${quatro}${luhn(quatro)}`;
}

export function codigoConfere(codigo: string): boolean {
  const m = /^[RN]-(\d{4})(\d)$/.exec(codigo.trim().toUpperCase());
  return !!m && luhn(m[1]) === Number(m[2]);
}
