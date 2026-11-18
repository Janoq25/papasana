import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { FakeAuth, fakeUser } from "../../test/fakeAuth";
import LoginPage from "./LoginPage";

function renderLogin(login: (e: string, p: string) => Promise<ReturnType<typeof fakeUser>>) {
  return render(
    <FakeAuth login={login}>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/bitacora" element={<p>Página de bitácora</p>} />
          <Route path="/dashboard" element={<p>Página de dashboard</p>} />
        </Routes>
      </MemoryRouter>
    </FakeAuth>,
  );
}

describe("LoginPage", () => {
  it("envía las credenciales y redirige a la primera página permitida del rol", async () => {
    const login = vi.fn().mockResolvedValue(fakeUser(["bitacora:ver", "reportes:ver"]));
    renderLogin(login);
    await userEvent.type(screen.getByLabelText(/correo electrónico/i), "auditor@demo.papasana.pe ");
    await userEvent.type(screen.getByLabelText(/contraseña/i), "Secreta-2026");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(login).toHaveBeenCalledWith("auditor@demo.papasana.pe", "Secreta-2026");
    expect(await screen.findByText("Página de bitácora")).toBeInTheDocument();
  });

  it("desde la Fase 3, un rol con dashboard entra al dashboard", async () => {
    const login = vi.fn().mockResolvedValue(fakeUser(["dashboard:ver", "parcelas:ver", "reportes:ver"]));
    renderLogin(login);
    await userEvent.type(screen.getByLabelText(/correo electrónico/i), "tecnico@demo.papasana.pe");
    await userEvent.type(screen.getByLabelText(/contraseña/i), "Secreta-2026");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(await screen.findByText("Página de dashboard")).toBeInTheDocument();
  });

  it("muestra el mensaje del servidor si las credenciales son incorrectas", async () => {
    const login = vi.fn().mockRejectedValue(new ApiError(401, "credenciales_invalidas", "Correo o contraseña incorrectos."));
    renderLogin(login);
    await userEvent.type(screen.getByLabelText(/correo electrónico/i), "x@demo.papasana.pe");
    await userEvent.type(screen.getByLabelText(/contraseña/i), "mala");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Correo o contraseña incorrectos.");
  });

  it("deshabilita el botón hasta completar los campos", () => {
    renderLogin(vi.fn());
    expect(screen.getByRole("button", { name: "Ingresar" })).toBeDisabled();
  });
});
