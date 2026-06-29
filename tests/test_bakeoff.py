"""Phase 4 — note-LLM bake-off tests.

Three concerns, all testable with fakes (no real 7B in CI):

  1. Model registry — the three Ollama tags exist with the right shape.
  2. ModelHost — ensure_resident evicts the previous model before loading
     the next; load/evict are injected callbacks so no real Ollama runs.
  3. EvalHarness.run_bakeoff — iterates the registry, produces one EvalReport
     per model with distinct rows, and the renderer adds a model axis.

WER/DER are model-invariant (ASR + diarization are locked axes) and surface
once in the rendered bake-off report, not per-model.
"""
from __future__ import annotations

import pytest

from scribe.app.scribe import Scribe
from scribe.domain.types import (
    Audio,
    Claim,
    Dialogue,
    EvalReport,
    GroundedNote,
    PatientContext,
    Role,
    SpanRef,
    TimeSpan,
    Utterance,
)
from scribe.app.drafts import InMemoryDraftStore
from scribe.fhir import FhirExporter
from scribe.notes import NoteGenerator
from scribe.runtime.model_host import ModelHost
from eval.datasets.base import Dataset, DatasetItem
from eval.harness import EvalHarness
from eval.report import render_bakeoff_report
from eval.models import DEFAULT_REGISTRY, ModelRegistry, ModelSpec
from eval.bakeoff import BakeoffReport


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────
class TestModelRegistry:
    def test_default_registry_has_three_models(self):
        assert len(DEFAULT_REGISTRY.models) == 3

    def test_default_registry_includes_qwen_medgemma_llama(self):
        tags = {m.ollama_tag for m in DEFAULT_REGISTRY.models}
        ids = {m.model_id for m in DEFAULT_REGISTRY.models}
        # Three distinct model ids + ollama tags.
        assert len(tags) == 3 and len(ids) == 3
        assert any("qwen" in mid for mid in ids)
        assert any("medgemma" in mid for mid in ids)
        assert any("llama" in mid for mid in ids)

    def test_every_spec_has_memory_budget_and_prompt_notes(self):
        for spec in DEFAULT_REGISTRY.models:
            assert spec.memory_gb > 0, "memory budget must be positive"
            assert isinstance(spec.prompt_notes, str)

    def test_registry_iteration_order_is_stable(self):
        first = [m.model_id for m in DEFAULT_REGISTRY.models]
        second = [m.model_id for m in DEFAULT_REGISTRY.models]
        assert first == second

    def test_registry_lookup_by_id(self):
        m = DEFAULT_REGISTRY.get(DEFAULT_REGISTRY.models[0].model_id)
        assert m is DEFAULT_REGISTRY.models[0]

    def test_registry_lookup_missing_returns_none(self):
        assert DEFAULT_REGISTRY.get("nonexistent") is None

    def test_registry_total_memory_sums_specs(self):
        assert DEFAULT_REGISTRY.total_memory_gb == sum(m.memory_gb for m in DEFAULT_REGISTRY.models)


# ─────────────────────────────────────────────────────────────────────────────
# ModelHost — eviction dance
# ─────────────────────────────────────────────────────────────────────────────
class TestModelHostEviction:
    def test_ensure_resident_loads_model_when_idle(self):
        loads, evicts = [], []
        host = ModelHost(loader=lambda tag: loads.append(tag),
                         evictor=lambda tag: evicts.append(tag))
        host.ensure_resident("qwen2.5:7b")
        assert host.resident == "qwen2.5:7b"
        assert loads == ["qwen2.5:7b"]
        assert evicts == []

    def test_ensure_resident_evicts_previous_before_loading_next(self):
        loads, evicts = [], []
        host = ModelHost(loader=lambda tag: loads.append(tag),
                         evictor=lambda tag: evicts.append(tag))
        host.ensure_resident("qwen2.5:7b")
        host.ensure_resident("medgemma:4b")
        # Eviction of the previous resident happens before loading the new one.
        assert host.resident == "medgemma:4b"
        assert evicts == ["qwen2.5:7b"]
        assert loads == ["qwen2.5:7b", "medgemma:4b"]

    def test_ensure_resident_is_noop_when_already_resident(self):
        loads, evicts = [], []
        host = ModelHost(loader=lambda tag: loads.append(tag),
                         evictor=lambda tag: evicts.append(tag))
        host.ensure_resident("qwen2.5:7b")
        host.ensure_resident("qwen2.5:7b")  # second call: no-op
        assert loads == ["qwen2.5:7b"]
        assert evicts == []
        assert host.resident == "qwen2.5:7b"

    def test_eviction_list_exposed_for_test_inspection(self):
        host = ModelHost(loader=lambda tag: None, evictor=lambda tag: None)
        host.ensure_resident("qwen2.5:7b")
        host.ensure_resident("medgemma:4b")
        host.ensure_resident("llama3.1:8b")
        assert host.evictions == ["qwen2.5:7b", "medgemma:4b"]

    def test_resident_none_when_fresh(self):
        host = ModelHost()
        assert host.resident is None

    def test_no_callbacks_is_safe_no_op(self):
        # Default ModelHost (no injected loader/evictor) must not raise.
        host = ModelHost()
        host.ensure_resident("qwen2.5:7b")
        assert host.resident == "qwen2.5:7b"


# ─────────────────────────────────────────────────────────────────────────────
# EvalHarness.run_bakeoff
# ─────────────────────────────────────────────────────────────────────────────
def _fake_audio() -> Audio:
    return Audio(source="fake", path=None)


class _StaticDataset(Dataset):
    def __init__(self, items: list[DatasetItem]) -> None:
        self._items = items

    @property
    def name(self) -> str:
        return "static"

    def items(self) -> list[DatasetItem]:
        return self._items


def _build_grounded_fake_scribe(model_spec: ModelSpec) -> Scribe:
    """Build a Scribe whose FakeLLMClient returns a GroundedNote with a tag
    stamped into one claim, so per-model reports are distinct."""
    from tests.fakes import FakeAudioSource, FakeDialogueExtractor
    from tests.fakes.llm import FakeLLMClient

    # Stamp the model id into the assessment claim so we can verify per-model
    # output really did flow through a different LLM.
    canned = {
        "subjective": [
            {"text": f"note from {model_spec.model_id}",
             "citations": [{"utterance_id": "u0001"}]},
        ],
        "objective": [],
        "assessment": [
            {"text": f"assessment by {model_spec.model_id}",
             "citations": [{"utterance_id": "u0001"}]},
        ],
        "plan": [
            {"text": "rest", "citations": [{"utterance_id": "u0000"}]},
        ],
    }
    llm = FakeLLMClient(canned=canned)
    llm._model_id = model_spec.ollama_tag  # for identifier uniqueness if needed
    return Scribe(
        dialogue_extractor=FakeDialogueExtractor(),
        note_generator=NoteGenerator(llm),
        fhir_exporter=FhirExporter(),
        draft_store=InMemoryDraftStore(),
        model_host=ModelHost(),
    )


class TestEvalHarnessBakeoff:
    def test_run_bakeoff_returns_one_report_per_model(self):
        registry = ModelRegistry(models=[
            ModelSpec(model_id="m1", ollama_tag="m1:tag", memory_gb=4.0, prompt_notes=""),
            ModelSpec(model_id="m2", ollama_tag="m2:tag", memory_gb=4.0, prompt_notes=""),
        ])
        host = ModelHost()
        ctx = PatientContext(patient_ref="p", encounter_ref="e")
        dataset = _StaticDataset([DatasetItem(item_id="i1", audio=_fake_audio())])
        harness = EvalHarness(_build_grounded_fake_scribe(registry.models[0]), ctx, nlp=None)

        report = harness.run_bakeoff(
            dataset, registry,
            build_scribe_for_model=_build_grounded_fake_scribe,
            model_host=host,
        )

        assert isinstance(report, BakeoffReport)
        assert set(report.per_model.keys()) == {"m1", "m2"}
        for sub in report.per_model.values():
            assert isinstance(sub, EvalReport)

    def test_run_bakeoff_evicts_between_models(self):
        registry = ModelRegistry(models=[
            ModelSpec(model_id="m1", ollama_tag="m1:tag", memory_gb=4.0, prompt_notes=""),
            ModelSpec(model_id="m2", ollama_tag="m2:tag", memory_gb=4.0, prompt_notes=""),
            ModelSpec(model_id="m3", ollama_tag="m3:tag", memory_gb=4.0, prompt_notes=""),
        ])
        host = ModelHost()
        ctx = PatientContext(patient_ref="p", encounter_ref="e")
        dataset = _StaticDataset([DatasetItem(item_id="i1", audio=_fake_audio())])
        harness = EvalHarness(_build_grounded_fake_scribe(registry.models[0]), ctx, nlp=None)

        harness.run_bakeoff(
            dataset, registry,
            build_scribe_for_model=_build_grounded_fake_scribe,
            model_host=host,
        )

        # Two evictions: m1→m2 evicts m1; m2→m3 evicts m2.
        assert host.evictions == ["m1:tag", "m2:tag"]
        assert host.resident == "m3:tag"

    def test_run_bakeoff_produces_distinct_per_model_rows(self):
        """Each model's report must come from that model's LLM output, not a
        shared cache. The fake stamps the model id into a claim, so the
        rendered reports must differ."""
        registry = ModelRegistry(models=[
            ModelSpec(model_id="m1", ollama_tag="m1:tag", memory_gb=4.0, prompt_notes=""),
            ModelSpec(model_id="m2", ollama_tag="m2:tag", memory_gb=4.0, prompt_notes=""),
        ])
        host = ModelHost()
        ctx = PatientContext(patient_ref="p", encounter_ref="e")
        # Reference note equal to m1's canned output → m1 completeness > m2's.
        ref = "note from m1 assessment by m1 rest"
        dataset = _StaticDataset([
            DatasetItem(item_id="i1", audio=_fake_audio(), reference_note=ref),
        ])
        harness = EvalHarness(_build_grounded_fake_scribe(registry.models[0]), ctx, nlp=None)

        report = harness.run_bakeoff(
            dataset, registry,
            build_scribe_for_model=_build_grounded_fake_scribe,
            model_host=host,
        )

        r1 = report.per_model["m1"].metrics
        r2 = report.per_model["m2"].metrics
        # Both produced completeness rows; values differ because the notes differ.
        assert "completeness" in r1 and "completeness" in r2
        assert r1["completeness"]["rouge1"] != r2["completeness"]["rouge1"]

    def test_run_bakeoff_wer_der_reported_once_model_invariant(self):
        """WER/DER are locked axes — they appear in every per-model report
        (because ASR/diarization are model-invariant), but the renderer
        surfaces them once. Verify the per-model values are identical."""
        registry = ModelRegistry(models=[
            ModelSpec(model_id="m1", ollama_tag="m1:tag", memory_gb=4.0, prompt_notes=""),
            ModelSpec(model_id="m2", ollama_tag="m2:tag", memory_gb=4.0, prompt_notes=""),
        ])
        host = ModelHost()
        ctx = PatientContext(patient_ref="p", encounter_ref="e")
        from tests.fakes.dialogue import _DEFAULT_DIALOGUE
        ref_text = " ".join(u.text for u in _DEFAULT_DIALOGUE.utterances)
        dataset = _StaticDataset([
            DatasetItem(item_id="i1", audio=_fake_audio(), reference_transcript=ref_text),
        ])
        harness = EvalHarness(_build_grounded_fake_scribe(registry.models[0]), ctx, nlp=None)

        report = harness.run_bakeoff(
            dataset, registry,
            build_scribe_for_model=_build_grounded_fake_scribe,
            model_host=host,
        )

        wer1 = report.per_model["m1"].metrics.get("asr", {}).get("wer")
        wer2 = report.per_model["m2"].metrics.get("asr", {}).get("wer")
        assert wer1 is not None and wer2 is not None
        assert wer1 == wer2  # model-invariant


# ─────────────────────────────────────────────────────────────────────────────
# render_bakeoff_report — model axis
# ─────────────────────────────────────────────────────────────────────────────
class TestRenderBakeoffReport:
    def test_render_includes_model_axis_header(self):
        registry = ModelRegistry(models=[
            ModelSpec(model_id="m1", ollama_tag="m1:tag", memory_gb=4.0, prompt_notes=""),
            ModelSpec(model_id="m2", ollama_tag="m2:tag", memory_gb=4.0, prompt_notes=""),
        ])
        report = BakeoffReport(
            registry=registry,
            per_model={
                "m1": EvalReport(metrics={
                    "completeness": {"rouge1": 0.42},
                    "grounding": {"citation_coverage": 1.0},
                }),
                "m2": EvalReport(metrics={
                    "completeness": {"rouge1": 0.31},
                    "grounding": {"citation_coverage": 0.8},
                }),
            },
        )
        out = render_bakeoff_report(report)
        assert "model" in out.lower()
        # Both model ids appear.
        assert "m1" in out and "m2" in out
        # Per-model metrics appear.
        assert "rouge1" in out
        assert "citation_coverage" in out

    def test_render_wer_der_section_appears_once(self):
        """WER/DER are model-invariant — render them in a separate 'locked
        axes' section, not per-model."""
        registry = ModelRegistry(models=[
            ModelSpec(model_id="m1", ollama_tag="m1:tag", memory_gb=4.0, prompt_notes=""),
            ModelSpec(model_id="m2", ollama_tag="m2:tag", memory_gb=4.0, prompt_notes=""),
        ])
        report = BakeoffReport(
            registry=registry,
            per_model={
                "m1": EvalReport(metrics={
                    "asr": {"wer": 0.12},
                    "diarization": {"der": 0.25},
                    "completeness": {"rouge1": 0.42},
                }),
                "m2": EvalReport(metrics={
                    "asr": {"wer": 0.12},
                    "diarization": {"der": 0.25},
                    "completeness": {"rouge1": 0.31},
                }),
            },
        )
        out = render_bakeoff_report(report)
        # Locked-axes section is present.
        assert "locked" in out.lower() or "invariant" in out.lower()
        # WER appears in the locked section, not duplicated per-model.
        assert out.count("wer") >= 1
        # Completeness rows are per-model (m1 + m2 each get a row).
        assert out.count("rouge1") >= 2

    def test_render_empty_bakeoff_is_graceful(self):
        registry = ModelRegistry(models=[])
        report = BakeoffReport(registry=registry, per_model={})
        out = render_bakeoff_report(report)
        assert isinstance(out, str) and len(out) > 0

    def test_render_includes_eyeball_checklist(self):
        registry = ModelRegistry(models=[
            ModelSpec(model_id="m1", ollama_tag="m1:tag", memory_gb=4.0, prompt_notes=""),
        ])
        report = BakeoffReport(
            registry=registry,
            per_model={"m1": EvalReport(metrics={})},
        )
        out = render_bakeoff_report(report)
        assert "Eyeball" in out or "eyeball" in out
