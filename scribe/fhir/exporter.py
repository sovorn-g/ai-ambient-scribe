"""FhirExporter — deep-ish, pure (design.md §3).

Hides R5 ``DocumentReference`` construction + validation. Returns a
``DocumentRef`` (resource + serialized JSON), writes nothing — side-effect-free.
The only writer is ``Scribe.approveAndExport``, behind the approval gate.

HYPOTHETICAL seam (R5 only); one adapter, no swappability theatre.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

from scribe.domain.types import (
    ApprovedNote,
    DocumentRef,
    PatientContext,
    SOAPNote,
)


class FhirExporter:
    """ApprovedNote + PatientContext → validated FHIR R5 DocumentReference."""

    def toDocumentReference(
        self,
        approved: ApprovedNote,
        ctx: PatientContext,
    ) -> DocumentRef:
        # Lazy import so importing this module never requires fhir.resources.
        from fhir.resources.documentreference import DocumentReference

        note_text = _serialize_soap(approved.note)
        attachment_data = base64.b64encode(note_text.encode("utf-8")).decode("ascii")

        resource_dict: dict[str, Any] = {
            "resourceType": "DocumentReference",
            "status": "current",
            "docStatus": "final",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11506-3",
                        "display": "Progress note",
                    }
                ],
                "text": "SOAP progress note",
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "LP173421-1",
                            "display": "Clinical note",
                        }
                    ]
                }
            ],
            "subject": {"reference": f"Patient/{ctx.patient_ref}"},
            "context": [
                {"reference": f"Encounter/{ctx.encounter_ref}"},
            ],
            "author": [{"display": approved.approver.name}],
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "data": attachment_data,
                        "title": "SOAP note (clinician-approved)",
                    }
                }
            ],
        }

        # Validate by constructing the R5 resource; raises on schema violation.
        resource = DocumentReference.model_validate(resource_dict)
        # Round-trip through the validated model to get canonical JSON.
        canonical = resource.model_dump(mode="json", exclude_none=True)
        return DocumentRef(resource=canonical, json_text=json.dumps(canonical, indent=2))


def _serialize_soap(note: SOAPNote) -> str:
    lines = ["SOAP Note", "========", ""]
    for section in ("subjective", "objective", "assessment", "plan"):
        lines.append(f"== {section.upper()} ==")
        for i, claim in enumerate(getattr(note, section), 1):
            lines.append(f"{i}. {claim.text}")
        lines.append("")
    return "\n".join(lines)
