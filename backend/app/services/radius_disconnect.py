import ipaddress
import logging
import os
from pathlib import Path

from pyrad import packet
from pyrad.client import Client, Timeout
from pyrad.dictionary import Dictionary
from sqlalchemy.orm import Session

from app.models.core import Card, RadiusSession, Router
from app.services.router_secrets import decrypt_router_secret

logger = logging.getLogger(__name__)

_DICTIONARY_PATH = (
    Path(__file__).resolve().parents[1] / "dictionaries" / "radius_disconnect.dict"
)


def coa_enabled() -> bool:
    return os.getenv("RADIUS_COA_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _destination(router: Router) -> str:
    # A single NAS source address is also the best CoA destination. If the
    # configured value is a subnet, use the management host instead.
    if router.radius_client_address:
        try:
            network = ipaddress.ip_network(router.radius_client_address, strict=False)
            if network.prefixlen == network.max_prefixlen:
                return str(network.network_address)
        except ValueError:
            pass
    return router.management_host


def send_disconnect_for_session(db: Session, session: RadiusSession) -> bool | None:
    """Send RFC 5176 Disconnect-Request to RouterOS.

    Returns None when CoA is disabled, True for Disconnect-ACK, and False
    when the NAS rejects the request or cannot be reached.
    """
    if not coa_enabled():
        return None
    if session.stopped_at is not None:
        return False

    router = db.get(Router, session.router_id)
    card = db.get(Card, session.card_id)
    if router is None or card is None:
        return False

    try:
        secret = decrypt_router_secret(router.radius_secret_encrypted)
        client = Client(
            server=_destination(router),
            coaport=int(os.getenv("RADIUS_COA_PORT", "1700")),
            secret=secret.encode("utf-8"),
            dict=Dictionary(str(_DICTIONARY_PATH)),
        )
        client.timeout = float(os.getenv("RADIUS_COA_TIMEOUT_SECONDS", "2"))
        client.retries = 1

        attributes = {
            "User_Name": card.username,
            "Acct_Session_Id": session.acct_session_id,
            "NAS_Identifier": router.nas_identifier,
        }
        if session.calling_station_id:
            attributes["Calling_Station_Id"] = session.calling_station_id
        if session.framed_ip_address:
            address = ipaddress.ip_address(session.framed_ip_address)
            if address.version == 4:
                attributes["Framed_IP_Address"] = str(address)
            else:
                attributes["Framed_IPv6_Address"] = str(address)

        request = client.CreateCoAPacket(
            code=packet.DisconnectRequest,
            message_authenticator=True,
            **attributes,
        )
        reply = client.SendPacket(request)
        return reply.code == packet.DisconnectACK
    except Timeout:
        logger.warning(
            "RADIUS Disconnect-Request timed out for router_id=%s session_id=%s",
            router.id,
            session.acct_session_id,
        )
    except Exception as exc:
        logger.warning(
            "RADIUS Disconnect-Request failed for router_id=%s session_id=%s error=%s",
            router.id,
            session.acct_session_id,
            type(exc).__name__,
        )
    return False
