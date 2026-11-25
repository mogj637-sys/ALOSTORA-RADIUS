from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.cards import _ensure_card_operation_scope


def _search_user():
    return SimpleNamespace(roles=[], card_visibility="search_any", point_of_sales=[])


def _card():
    return SimpleNamespace(
        username="Voucher-42",
        serial_number="SN-42",
        assigned_pos_id=None,
        batch_id=None,
    )


@pytest.mark.parametrize("identifier", [None, "", "Voucher", "SN-4"])
def test_search_any_scope_rejects_missing_or_partial_identifiers(identifier):
    with pytest.raises(HTTPException) as exc_info:
        _ensure_card_operation_scope(_card(), _search_user(), None, exact_identifier=identifier)
    assert exc_info.value.status_code == 404


@pytest.mark.parametrize("identifier", ["Voucher-42", "voucher-42", "SN-42", "sn-42"])
def test_search_any_scope_accepts_exact_username_or_serial(identifier):
    _ensure_card_operation_scope(_card(), _search_user(), None, exact_identifier=identifier)
