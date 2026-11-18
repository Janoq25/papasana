import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Can, RequirePermission } from "./RequirePermission";
import { FakeAuth } from "../test/fakeAuth";

describe("RequirePermission", () => {
  it("muestra el contenido cuando el rol tiene el permiso", () => {
    render(
      <FakeAuth permissions={["bitacora:ver"]}>
        <RequirePermission permission="bitacora:ver">contenido protegido</RequirePermission>
      </FakeAuth>,
    );
    expect(screen.getByText("contenido protegido")).toBeInTheDocument();
  });

  it("muestra 'Acceso restringido' cuando falta el permiso", () => {
    render(
      <FakeAuth permissions={["reportes:ver"]}>
        <RequirePermission permission="bitacora:ver">contenido protegido</RequirePermission>
      </FakeAuth>,
    );
    expect(screen.queryByText("contenido protegido")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Acceso restringido" })).toBeInTheDocument();
  });

  it("Can oculta los botones sin permiso", () => {
    render(
      <FakeAuth permissions={["usuarios:ver"]}>
        <Can permission="usuarios:crear">
          <button>Nuevo usuario</button>
        </Can>
        <Can permission="usuarios:ver">
          <button>Ver usuarios</button>
        </Can>
      </FakeAuth>,
    );
    expect(screen.queryByRole("button", { name: "Nuevo usuario" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ver usuarios" })).toBeInTheDocument();
  });
});
