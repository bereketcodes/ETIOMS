from io import BytesIO
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from backend.app.models.tender import Tender
from backend.app.routers.admin import get_admin_stats
from backend.app.routers.tenders import MAX_FILE_SIZE, save_upload_safely


class DummyUpload:
    def __init__(self, filename: str, payload: bytes):
        self.filename = filename
        self.file = BytesIO(payload)


@pytest.mark.asyncio
async def test_save_upload_safely_rejects_unsupported_extension():
    with pytest.raises(HTTPException) as exc:
        await save_upload_safely(DummyUpload("bad.exe", b"hello"))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_save_upload_safely_rejects_oversized_upload():
    with pytest.raises(HTTPException) as exc:
        await save_upload_safely(DummyUpload("notice.pdf", b"x" * (MAX_FILE_SIZE + 1)))
    assert exc.value.status_code == 413


def test_get_accessible_tender_blocks_cross_organization_private_access():
    from backend.app.routers.tenders import _get_accessible_tender

    private_tender = Tender(
        title="Private Tender",
        procuring_entity="Agency",
        sector="ICT",
        region="Addis Ababa",
        deadline=None,
        status="Open",
        description="Private notice",
        organization_id=uuid.uuid4(),
    )
    current_user = SimpleNamespace(organization_id=uuid.uuid4())

    with pytest.raises(HTTPException) as exc:
        _get_accessible_tender(db=SimpleNamespace(query=lambda *args, **kwargs: SimpleNamespace(filter=lambda *a, **k: SimpleNamespace(first=lambda: private_tender))), tender_id=uuid.uuid4(), current_user=current_user)

    assert exc.value.status_code == 403


def test_admin_stats_rejects_non_admin_roles():
    current_user = SimpleNamespace(role="Team Member", organization_id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        get_admin_stats(db=SimpleNamespace(), current_user=current_user)
    assert exc.value.status_code == 403
