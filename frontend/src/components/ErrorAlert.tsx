import { Alert } from "@mui/material";
import { ApiError } from "../api/client";

export default function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof ApiError ? error.message : "Ocurrió un error inesperado.";
  const details = error instanceof ApiError ? error.details : [];
  return (
    <Alert severity="error" sx={{ mb: 2 }} role="alert">
      {message}
      {details.length > 0 && (
        <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
          {details.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      )}
    </Alert>
  );
}
