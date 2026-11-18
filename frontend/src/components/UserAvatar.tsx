import { useEffect, useState } from "react";
import { Avatar, type SxProps } from "@mui/material";
import { api } from "../api/client";

/** La foto requiere el token de acceso: se descarga como blob y se muestra con una URL local. */
export default function UserAvatar({
  userId,
  name,
  hasPhoto,
  version = 0,
  sx,
}: {
  userId: string;
  name: string;
  hasPhoto: boolean;
  version?: number;
  sx?: SxProps;
}) {
  const [src, setSrc] = useState<string | undefined>();

  useEffect(() => {
    if (!hasPhoto) {
      setSrc(undefined);
      return;
    }
    let url: string | undefined;
    let active = true;
    api<Blob>(`/users/${userId}/photo`, { raw: true })
      .then((blob) => {
        if (!active) return;
        url = URL.createObjectURL(blob);
        setSrc(url);
      })
      .catch(() => setSrc(undefined));
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [userId, hasPhoto, version]);

  const initials = name
    .split(" ")
    .filter(Boolean)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <Avatar src={src} alt={name} sx={{ bgcolor: "primary.main", ...sx }}>
      {initials}
    </Avatar>
  );
}
