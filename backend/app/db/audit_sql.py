"""SQL de la bitácora inmutable: hash encadenado, bloqueo de UPDATE/DELETE/TRUNCATE y verificación.

El hash se calcula en la base de datos (trigger BEFORE INSERT), de modo que ninguna ruta de código
puede insertar un registro sin encadenarlo. La verificación usa la misma función de carga útil.
"""

GENESIS_HASH = "0" * 64

PAYLOAD_FUNCTION = r"""
CREATE OR REPLACE FUNCTION auditoria.fn_audit_payload(r auditoria.audit_log)
RETURNS text
LANGUAGE sql IMMUTABLE AS $$
  SELECT jsonb_build_object(
    'id', r.id,
    'seq', r.seq,
    'occurred_at', to_char(r.occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'user_id', r.user_id::text,
    'user_email', r.user_email,
    'role_code', r.role_code,
    'session_id', r.session_id::text,
    'event_type', r.event_type,
    'module_code', r.module_code,
    'action', r.action,
    'http_method', r.http_method,
    'endpoint', r.endpoint,
    'entity_type', r.entity_type,
    'entity_id', r.entity_id,
    'before', r.before,
    'after', r.after,
    'ip', host(r.ip),
    'user_agent', r.user_agent,
    'result', r.result,
    'error_detail', r.error_detail,
    'related_event_id', r.related_event_id,
    'duration_ms', r.duration_ms
  )::text
$$;
"""

CHAIN_TRIGGER = rf"""
CREATE OR REPLACE FUNCTION auditoria.fn_audit_chain()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_prev_hash text;
  v_prev_seq bigint;
BEGIN
  -- Serializa las inserciones para que la cadena no se bifurque.
  PERFORM pg_advisory_xact_lock(hashtext('auditoria.audit_log'));
  SELECT a.hash, a.seq INTO v_prev_hash, v_prev_seq
    FROM auditoria.audit_log a ORDER BY a.seq DESC LIMIT 1;
  NEW.seq := COALESCE(v_prev_seq, 0) + 1;
  NEW.prev_hash := COALESCE(v_prev_hash, '{GENESIS_HASH}');
  NEW.hash := encode(sha256(convert_to(NEW.prev_hash || auditoria.fn_audit_payload(NEW), 'UTF8')), 'hex');
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_audit_chain
  BEFORE INSERT ON auditoria.audit_log
  FOR EACH ROW EXECUTE FUNCTION auditoria.fn_audit_chain();
"""

IMMUTABLE_TRIGGERS = r"""
CREATE OR REPLACE FUNCTION auditoria.fn_audit_immutable()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'La bitácora de auditoría es inmutable: % no está permitido', TG_OP
    USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER trg_audit_no_update_delete
  BEFORE UPDATE OR DELETE ON auditoria.audit_log
  FOR EACH ROW EXECUTE FUNCTION auditoria.fn_audit_immutable();

CREATE TRIGGER trg_audit_no_truncate
  BEFORE TRUNCATE ON auditoria.audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION auditoria.fn_audit_immutable();
"""

DROP_ALL = r"""
DROP TRIGGER IF EXISTS trg_audit_no_truncate ON auditoria.audit_log;
DROP TRIGGER IF EXISTS trg_audit_no_update_delete ON auditoria.audit_log;
DROP TRIGGER IF EXISTS trg_audit_chain ON auditoria.audit_log;
DROP FUNCTION IF EXISTS auditoria.fn_audit_immutable();
DROP FUNCTION IF EXISTS auditoria.fn_audit_chain();
DROP FUNCTION IF EXISTS auditoria.fn_audit_payload(auditoria.audit_log);
"""

# Devuelve el primer registro cuya cadena no cuadra (o ninguna fila si la cadena es íntegra).
VERIFY_QUERY = rf"""
WITH chain AS (
  SELECT a.seq, a.id, a.hash, a.prev_hash,
         LAG(a.hash) OVER (ORDER BY a.seq) AS expected_prev,
         encode(sha256(convert_to(a.prev_hash || auditoria.fn_audit_payload(a), 'UTF8')), 'hex') AS recomputed
    FROM auditoria.audit_log a
)
SELECT seq, id,
       CASE WHEN hash <> recomputed THEN 'contenido_alterado' ELSE 'cadena_rota' END AS motivo
  FROM chain
 WHERE hash <> recomputed OR prev_hash <> COALESCE(expected_prev, '{GENESIS_HASH}')
 ORDER BY seq
 LIMIT 1
"""
