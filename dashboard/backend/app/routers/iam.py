"""IAM convenience endpoints (admin-only).

Reveal and rotate the client secrets of the seeded M2M clients so the operator
does not have to shell into the host. The file .testbed.secrets stays the
single source: reveal only reads it, rotate writes it FIRST and then converges
Keycloak (and the gateway pod for camara-gateway) to it. Every reveal and
every rotation is audit-logged. See docs/security/iam.md.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.services.audit import write_audit
from app.services.iam_service import CLIENTS, IamService
from app.services.k8s_service import K8sService, get_k8s_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/iam", tags=["iam"])


@router.get("/master-admin-password")
def master_admin_password() -> dict[str, Any]:
    """Reveal the Keycloak MASTER admin password (read from .testbed.secrets).

    Read-only: this credential is auto-generated and owned by the automation
    (bootstrap + phase 08 + client-secret operations authenticate with it).
    Surfaced here only so an operator can read it to log into the master admin
    console without opening the host file; it is not editable from the UI.
    Audit-logged. See docs/security/iam.md.
    """
    value = IamService.read_secret("KEYCLOAK_ADMIN_PASSWORD")
    write_audit("iam.master_admin_reveal", {"found": value is not None})
    from app.config import settings
    if value is None:
        return {"found": False, "username": settings.keycloak_admin_user}
    return {"found": True, "username": settings.keycloak_admin_user, "secret": value}


@router.get("/client-secret/{client_id}")
def client_secret(client_id: str) -> dict[str, Any]:
    meta = CLIENTS.get(client_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"No revealable secret for client '{client_id}'")
    value = IamService.read_secret(meta["env_key"])
    write_audit("iam.client_secret_reveal", {"client": client_id, "found": value is not None})
    if value is None:
        # Absent from the file means the realm was imported with the changeme-*
        # default for this client. Saying so beats guessing a value.
        return {"client_id": client_id, "found": False, "env_key": meta["env_key"]}
    return {"client_id": client_id, "found": True, "env_key": meta["env_key"], "secret": value}


@router.post("/client-secret/{client_id}/rotate")
def rotate_client_secret(
    client_id: str,
    k8s: K8sService = Depends(get_k8s_service),
) -> dict[str, Any]:
    if client_id not in CLIENTS:
        raise HTTPException(status_code=404, detail=f"No rotatable secret for client '{client_id}'")
    try:
        result = IamService(k8s=k8s).rotate(client_id)
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator with the recovery path
        log.exception("client secret rotation failed for %s", client_id)
        write_audit("iam.client_secret_rotate", {"client": client_id, "ok": False, "error": str(exc)})
        raise HTTPException(
            status_code=502,
            detail=(
                f"Rotation did not complete: {exc}. The new value is (or may be) in "
                ".testbed.secrets already; run `kelt run-phase 08-iam` or rotate again "
                "to converge Keycloak to the file."
            ),
        ) from exc
    write_audit("iam.client_secret_rotate", {"client": client_id, "ok": True, "pod_synced": result["pod_synced"]})
    return result
