import { Alert, Box, Typography } from "@mui/material";

export default function ForbiddenPage() {
  return (
    <Box sx={{ maxWidth: 560 }}>
      <Typography variant="h1" gutterBottom>
        Acceso restringido
      </Typography>
      <Alert severity="warning">
        Su rol no tiene permiso para ver este módulo. Si cree que es un error, contacte al administrador.
      </Alert>
    </Box>
  );
}
