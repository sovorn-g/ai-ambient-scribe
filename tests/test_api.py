"""tests/test_api.py — FastAPI adapter tests through fakes (no model).

Happy path: generate → edit → approve → export.
Gate assertion: no DocumentRef without the approve endpoint.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from scribe.api.app import app, set_scribe
from tests.conftest import build_fake_scribe


@pytest.fixture()
def client():
    scribe, audio_source, _ = build_fake_scribe()
    set_scribe(scribe)
    with TestClient(app) as c:
        yield c


# ── happy path ────────────────────────────────────────────────────────────────

def test_generate_returns_draft(client):
    resp = client.post(
        "/drafts/generate",
        json={"patient_ref": "p-001", "encounter_ref": "enc-001", "audio_path": "fake.wav"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "DRAFT"
    assert body["id"]
    assert "note" in body
    assert "dialogue" in body


def test_get_draft(client):
    gen = client.post(
        "/drafts/generate",
        json={"patient_ref": "p-001", "encounter_ref": "enc-001", "audio_path": "fake.wav"},
    ).json()
    draft_id = gen["id"]

    resp = client.get(f"/drafts/{draft_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == draft_id


def test_edit_draft(client):
    gen = client.post(
        "/drafts/generate",
        json={"patient_ref": "p-001", "encounter_ref": "enc-001", "audio_path": "fake.wav"},
    ).json()
    draft_id = gen["id"]

    edited_note = {
        "subjective": [{"text": "Patient edited subjective.", "citations": []}],
        "objective": [],
        "assessment": [],
        "plan": [],
    }
    resp = client.put(f"/drafts/{draft_id}", json={"note": edited_note})
    assert resp.status_code == 200
    body = resp.json()
    assert body["note"]["subjective"][0]["text"] == "Patient edited subjective."
    assert body["status"] == "DRAFT"


def test_approve_returns_document_ref(client):
    gen = client.post(
        "/drafts/generate",
        json={"patient_ref": "p-001", "encounter_ref": "enc-001", "audio_path": "fake.wav"},
    ).json()
    draft_id = gen["id"]

    resp = client.post(
        f"/drafts/{draft_id}/approve",
        json={"approver_name": "Dr. Smith", "approver_role": "clinician"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "resource" in body
    assert "json_text" in body
    assert body["resource"]["resourceType"] == "DocumentReference"


def test_full_generate_edit_approve_flow(client):
    gen = client.post(
        "/drafts/generate",
        json={"patient_ref": "p-002", "encounter_ref": "enc-002", "audio_path": "fake.wav"},
    ).json()
    draft_id = gen["id"]
    assert gen["status"] == "DRAFT"

    edited_note = {
        "subjective": [{"text": "Edited: sore throat x3 days.", "citations": []}],
        "objective": [{"text": "Tonsils red.", "citations": []}],
        "assessment": [{"text": "Viral pharyngitis.", "citations": []}],
        "plan": [{"text": "Rest, fluids, return if worse.", "citations": []}],
    }
    edit_resp = client.put(f"/drafts/{draft_id}", json={"note": edited_note})
    assert edit_resp.status_code == 200

    approve_resp = client.post(
        f"/drafts/{draft_id}/approve",
        json={"approver_name": "Dr. Jones", "approver_role": "clinician"},
    )
    assert approve_resp.status_code == 200
    doc = approve_resp.json()
    assert doc["resource"]["resourceType"] == "DocumentReference"


# ── gate assertions ───────────────────────────────────────────────────────────

def test_approve_unknown_draft_returns_404(client):
    resp = client.post(
        "/drafts/nonexistent-id/approve",
        json={"approver_name": "Dr. Smith", "approver_role": "clinician"},
    )
    assert resp.status_code == 404


def test_get_unknown_draft_returns_404(client):
    resp = client.get("/drafts/nonexistent-id")
    assert resp.status_code == 404


def test_edit_unknown_draft_returns_404(client):
    resp = client.put(
        "/drafts/nonexistent-id",
        json={"note": {"subjective": [], "objective": [], "assessment": [], "plan": []}},
    )
    assert resp.status_code == 404


def test_no_document_ref_without_approve(client):
    """Generating and editing alone never produces a DocumentRef."""
    gen = client.post(
        "/drafts/generate",
        json={"patient_ref": "p-003", "encounter_ref": "enc-003", "audio_path": "fake.wav"},
    ).json()
    draft_id = gen["id"]

    edit_resp = client.put(
        f"/drafts/{draft_id}",
        json={"note": {"subjective": [], "objective": [], "assessment": [], "plan": []}},
    )
    # edit returns a DraftResponse (still DRAFT), never a DocumentRef
    body = edit_resp.json()
    assert "resourceType" not in str(body)
    assert body["status"] == "DRAFT"
    assert "resource" not in body
