import { useEffect, useState } from "react";
import { api } from "./client";

/**
 * Descarga un recurso protegido (requiere el token de acceso) y devuelve una URL local (blob:).
 * Las etiquetas <img> no pueden enviar la cabecera Authorization.
 */
export function useAuthedObjectUrl(path: string | null): { url: string | undefined; error: boolean } {
  const [url, setUrl] = useState<string | undefined>();
  const [error, setError] = useState(false);

  useEffect(() => {
    setUrl(undefined);
    setError(false);
    if (!path) return;
    let objectUrl: string | undefined;
    let active = true;
    api<Blob>(path, { raw: true })
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => active && setError(true));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  return { url, error };
}
