/**
 * @vitest-environment jsdom
 */

/**
 * O cadastro de pessoas com o registro profissional e o Acesso pleno à
 * Segurança do Paciente (issue #1765, ADR 0095).
 *
 * Conselho, número e UF entram no que se salva, na criação e na edição. O
 * Acesso pleno é escolhido na edição, como os outros acessos de módulo; quem
 * recusa dar a si mesmo é o backend.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UsuarioFormModal } from "./UsuarioFormModal";
import { AdminUsuario, AdminUsuarioPayload } from "./types";

const PESSOA: AdminUsuario = {
  id: "P010",
  nome_completo: "Pessoa de Teste",
  email: "pessoa@x.com",
  cargo: "Enfermeira",
  area: null,
  setor: null,
  role: "coordenador",
  ativo: true,
  is_externo: false,
  is_super_admin: false,
  access_profile: "regular",
  conselho_profissional: null,
  registro_profissional: null,
  registro_uf: null,
  perfil_nsp: null,
};

function montar(initial: AdminUsuario | undefined, mode: "create" | "edit") {
  const enviados: AdminUsuarioPayload[] = [];
  render(
    <UsuarioFormModal
      mode={mode}
      initial={initial}
      roleOptions={["coordenador", "gerente"]}
      onClose={() => {}}
      onSubmit={async (payload) => {
        enviados.push(payload);
        return true;
      }}
    />
  );
  return enviados;
}

function digitar(rotulo: string | RegExp, valor: string) {
  fireEvent.change(screen.getByLabelText(rotulo), { target: { value: valor } });
}

function salvar() {
  fireEvent.click(screen.getByRole("button", { name: /Criar|Salvar/ }));
}

afterEach(() => {
  cleanup();
});

describe("o registro profissional", () => {
  it("conselho, número e UF entram no que se salva", async () => {
    const enviados = montar(PESSOA, "edit");

    digitar("Conselho profissional", "COREN");
    digitar("Número do registro", "000000");
    digitar("UF do registro", "rj");
    salvar();

    await vi.waitFor(() =>
      expect(enviados[0]).toMatchObject({
        conselho_profissional: "COREN",
        registro_profissional: "000000",
        registro_uf: "RJ",
      })
    );
  });

  it("mostra o registro de quem já tem", () => {
    montar({ ...PESSOA, conselho_profissional: "CRM", registro_profissional: "123", registro_uf: "SP" }, "edit");

    expect((screen.getByLabelText("Conselho profissional") as HTMLInputElement).value).toBe("CRM");
    expect((screen.getByLabelText("Número do registro") as HTMLInputElement).value).toBe("123");
    expect((screen.getByLabelText("UF do registro") as HTMLInputElement).value).toBe("SP");
  });

  it("quem não mexeu no registro não manda o registro", async () => {
    const enviados = montar(PESSOA, "edit");

    digitar("Área", "Assistencial");
    salvar();

    await vi.waitFor(() => expect(enviados).toHaveLength(1));
    expect(enviados[0]).not.toHaveProperty("registro_uf");
    expect(enviados[0]).not.toHaveProperty("perfil_nsp");
  });

  it("a pessoa nova já pode nascer com o registro", async () => {
    const enviados = montar(undefined, "create");

    digitar(/Nome completo/, "Pessoa Nova");
    digitar(/^Email/, "nova@x.com");
    digitar(/^Cargo/, "Enfermeira");
    digitar("Conselho profissional", "CRF");
    digitar("Número do registro", "000001");
    digitar("UF do registro", "MG");
    salvar();

    await vi.waitFor(() =>
      expect(enviados[0]).toMatchObject({ conselho_profissional: "CRF", registro_profissional: "000001", registro_uf: "MG" })
    );
  });
});

describe("o Acesso pleno à Segurança do Paciente", () => {
  it("escolher o Acesso pleno manda o perfil do módulo", async () => {
    const enviados = montar(PESSOA, "edit");

    fireEvent.click(screen.getByRole("checkbox", { name: /Acesso pleno à Segurança do Paciente/ }));
    salvar();

    await vi.waitFor(() => expect(enviados[0]?.perfil_nsp).toBe("acesso_pleno"));
  });

  it("tirar o Acesso pleno manda null", async () => {
    const enviados = montar({ ...PESSOA, perfil_nsp: "acesso_pleno" }, "edit");

    const caixa = screen.getByRole("checkbox", { name: /Acesso pleno à Segurança do Paciente/ }) as HTMLInputElement;
    expect(caixa.checked).toBe(true);
    fireEvent.click(caixa);
    salvar();

    await vi.waitFor(() => expect(enviados[0]?.perfil_nsp).toBeNull());
  });
});

describe("o Responsável técnico (issue #2248)", () => {
  const caixa = () => screen.getByRole("checkbox", { name: /Responsável técnico/ }) as HTMLInputElement;

  it("mostra a marca de quem já é o Responsável técnico", () => {
    montar({ ...PESSOA, responsavel_tecnico: true }, "edit");

    expect(caixa().checked).toBe(true);
    expect(screen.getByText("Marcar aqui desmarca quem estava.")).toBeTruthy();
  });

  it("marcar manda a marca", async () => {
    const enviados = montar(PESSOA, "edit");

    expect(caixa().checked).toBe(false);
    fireEvent.click(caixa());
    salvar();

    await vi.waitFor(() => expect(enviados[0]?.responsavel_tecnico).toBe(true));
  });

  it("desmarcar manda false", async () => {
    const enviados = montar({ ...PESSOA, responsavel_tecnico: true }, "edit");

    fireEvent.click(caixa());
    salvar();

    await vi.waitFor(() => expect(enviados[0]?.responsavel_tecnico).toBe(false));
  });

  it("quem não mexeu na marca não manda a marca", async () => {
    const enviados = montar({ ...PESSOA, responsavel_tecnico: true }, "edit");

    digitar("Área", "Assistencial");
    salvar();

    await vi.waitFor(() => expect(enviados).toHaveLength(1));
    expect(enviados[0]).not.toHaveProperty("responsavel_tecnico");
  });
});

describe("o perfil do Canal de Conduta (issues #1822 e #1835)", () => {
  const perfil = () => screen.getByRole("combobox", { name: "Perfil no Canal de Conduta" }) as HTMLSelectElement;

  it.each(["cadastro_de_membros", "presidente", "diretoria_executiva"])(
    "dar o perfil %s manda o perfil do módulo",
    async (valor) => {
      const enviados = montar(PESSOA, "edit");

      fireEvent.change(perfil(), { target: { value: valor } });
      salvar();

      await vi.waitFor(() => expect(enviados[0]?.perfil_conduta).toBe(valor));
    }
  );

  it("tirar o perfil manda null", async () => {
    const enviados = montar({ ...PESSOA, perfil_conduta: "cadastro_de_membros" }, "edit");

    expect(perfil().value).toBe("cadastro_de_membros");
    fireEvent.change(perfil(), { target: { value: "" } });
    salvar();

    await vi.waitFor(() => expect(enviados[0]?.perfil_conduta).toBeNull());
  });

  it("quem não mexeu no perfil não manda o perfil", async () => {
    const enviados = montar(PESSOA, "edit");
    digitar("Área", "Assistencial");
    salvar();

    await vi.waitFor(() => expect(enviados).toHaveLength(1));
    expect(enviados[0]).not.toHaveProperty("perfil_conduta");
  });
});
