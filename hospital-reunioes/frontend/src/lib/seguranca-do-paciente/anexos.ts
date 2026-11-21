/**
 * Os anexos da notificação no navegador (issue #1988, ADR 0107 decisão 6).
 *
 * Até três fotos ou PDFs, somando menos de 9 MB, abaixo do corte de 10 MB do
 * proxy. A foto grande é reduzida aqui, antes do envio, para caber. O servidor
 * confere tudo de novo (`app/services/seguranca_do_paciente/anexos.py`); a
 * conferência daqui só poupa a pessoa de esperar o envio para saber.
 */

export const MAXIMO_DE_ARQUIVOS = 3;
export const LIMITE_DA_SOMA = 9 * 1024 * 1024;
export const EXTENSOES_ACEITAS = [".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf"];
/** O `accept` do campo: a câmera e a galeria no celular, e o PDF. */
export const ACEITOS_NO_CAMPO = "image/*,application/pdf";

/** A partir daqui a foto é reduzida antes do envio. */
const FOTO_GRANDE = 1024 * 1024;
const LADO_MAXIMO = 1600;
const QUALIDADE = 0.8;
const FOTOS_QUE_O_NAVEGADOR_REDUZ = [".jpg", ".jpeg", ".png", ".webp", ".heic"];

function extensao(nome: string): string {
  const ponto = nome.lastIndexOf(".");
  return ponto < 0 ? "" : nome.slice(ponto).toLowerCase();
}

function emMB(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(1).replace(".", ",");
}

/** O tamanho na tela: KB abaixo de 1 MB, MB com uma casa acima. */
export function tamanhoLegivel(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${emMB(bytes)} MB`;
}

/** A recusa, com a mensagem para a tela, ou `null` quando está tudo certo. */
export function conferirArquivos(arquivos: File[]): string | null {
  if (arquivos.length > MAXIMO_DE_ARQUIVOS) return `Você pode anexar até ${MAXIMO_DE_ARQUIVOS} arquivos.`;
  for (const arquivo of arquivos) {
    if (!EXTENSOES_ACEITAS.includes(extensao(arquivo.name))) {
      return `O arquivo ${arquivo.name} não é aceito. Envie foto (JPG, PNG, WEBP ou HEIC) ou PDF.`;
    }
    if (arquivo.size === 0) return `O arquivo ${arquivo.name} está vazio.`;
  }
  const soma = arquivos.reduce((total, arquivo) => total + arquivo.size, 0);
  if (soma >= LIMITE_DA_SOMA) {
    return `Os arquivos somam ${emMB(soma)} MB e precisam somar menos de 9 MB. Tire um arquivo ou envie um menor.`;
  }
  return null;
}

/**
 * A foto grande vira um JPEG de no máximo 1600 px no lado maior. PDF, foto
 * pequena e foto que o navegador não consegue abrir (HEIC fora do Safari)
 * seguem como vieram: a conferência da soma diz se ainda cabem.
 */
export async function reduzirFoto(arquivo: File): Promise<File> {
  if (!FOTOS_QUE_O_NAVEGADOR_REDUZ.includes(extensao(arquivo.name)) || arquivo.size <= FOTO_GRANDE) {
    return arquivo;
  }
  try {
    const imagem = await createImageBitmap(arquivo);
    const escala = Math.min(1, LADO_MAXIMO / Math.max(imagem.width, imagem.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(imagem.width * escala);
    canvas.height = Math.round(imagem.height * escala);
    const contexto = canvas.getContext("2d");
    if (!contexto) return arquivo;
    contexto.drawImage(imagem, 0, 0, canvas.width, canvas.height);
    imagem.close?.();
    const blob = await new Promise<Blob | null>((resolver) => canvas.toBlob(resolver, "image/jpeg", QUALIDADE));
    if (!blob || blob.size >= arquivo.size) return arquivo;
    const nome = arquivo.name.slice(0, arquivo.name.lastIndexOf(".")) + ".jpg";
    return new File([blob], nome, { type: "image/jpeg" });
  } catch {
    return arquivo;
  }
}
