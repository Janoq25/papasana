import { createTheme } from "@mui/material/styles";
import { esES } from "@mui/material/locale";

// Paleta con contraste AA sobre fondo claro (texto primario #1b2a16 sobre #f6f8f4 ≈ 14:1).
export const theme = createTheme(
  {
    palette: {
      mode: "light",
      primary: { main: "#2e5e1f", contrastText: "#ffffff" },
      secondary: { main: "#7a4b12", contrastText: "#ffffff" },
      error: { main: "#b3261e" },
      warning: { main: "#8a5300" },
      success: { main: "#2e6b30" },
      background: { default: "#f6f8f4", paper: "#ffffff" },
      text: { primary: "#1b2a16", secondary: "#45523f" },
    },
    shape: { borderRadius: 10 },
    typography: {
      fontFamily: '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      h1: { fontSize: "1.75rem", fontWeight: 600 },
      h2: { fontSize: "1.4rem", fontWeight: 600 },
      h3: { fontSize: "1.15rem", fontWeight: 600 },
    },
    components: {
      MuiButton: { defaultProps: { disableElevation: true } },
      MuiTextField: { defaultProps: { size: "small", fullWidth: true } },
      MuiTableCell: { styleOverrides: { head: { fontWeight: 600 } } },
    },
  },
  esES,
);
