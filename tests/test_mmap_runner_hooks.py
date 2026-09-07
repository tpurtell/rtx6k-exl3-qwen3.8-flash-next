# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project
from types import SimpleNamespace
from typing import Any
import pytest
import torch
import vllm.v1.worker.gpu.model_runner as model_runner_module
from vllm.config import CompilationConfig, ParallelConfig
from vllm.config.compilation import CUDAGraphMode
from vllm.v1.worker.gpu.input_batch import InputBatch
from vllm.v1.worker.gpu.model_runner import GPUModelRunner
from vllm.v1.worker.gpu.model_states.mamba_hybrid import MambaHybridModelState


def test_execute_model_dummy_run_uses_prepare_runtime_dummy_inputs_not_prepare_inputs(
    monkeypatch,
):
    """A runtime (profile/DP-empty) dummy run must build its model_inputs via
    ``ModelState.prepare_runtime_dummy_inputs``, never ``prepare_inputs`` --
    the latter is the real path that would reach a table's hash/gather/pin
    methods (e.g. Qwen4Exp's mmap-staged PLE rows), which a dummy/profile
    run must never touch."""

    class _RecordingModelState:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def prepare_runtime_dummy_inputs(self, input_batch, req_states):
            self.calls.append("prepare_runtime_dummy_inputs")
            return {}

        def prepare_inputs(self, input_batch, req_states):
            pytest.fail(
                "execute_model's dummy-run branch must not call prepare_inputs "
                "-- it is the real path that reaches a table's hash/gather/pin"
            )

    class _StopAtModelCall(Exception):
        pass

    captured: dict[str, Any] = {}

    def _fake_model(**kwargs):
        captured.update(kwargs)
        raise _StopAtModelCall

    num_tokens = 4
    fake_input_batch = SimpleNamespace(
        input_ids=torch.zeros(num_tokens, dtype=torch.long),
        positions=torch.arange(num_tokens),
        num_tokens=num_tokens,
        num_tokens_after_padding=num_tokens,
        is_padding=None,
    )
    fake_batch_desc = SimpleNamespace(
        num_tokens=num_tokens,
        num_reqs=1,
        max_query_len=num_tokens,
        cg_mode=CUDAGraphMode.NONE,
        num_active_loras=0,
    )

    runner: Any = GPUModelRunner.__new__(GPUModelRunner)
    runner.lora_config = None
    runner.is_encoder_decoder = False
    runner.cudagraph_manager = None
    runner.dp_size = 1
    runner.dp_rank = 0
    runner.input_buffers = None
    runner.uses_inputs_embeds = False
    runner.supports_mm_inputs = False
    runner.is_encoder_only = False
    runner._ple_offload_connector = None
    runner.is_first_pp_rank = True
    runner.model_state = _RecordingModelState()
    runner.req_states = None
    runner.eplb = SimpleNamespace(prepare_forward=lambda *a, **kw: None)
    runner.step_timing = SimpleNamespace(
        record_batch=lambda *a, **kw: None, forward_start=lambda: None
    )
    runner.model_config = None
    runner.vllm_config = SimpleNamespace(
        parallel_config=ParallelConfig(), compilation_config=CompilationConfig()
    )
    runner.kv_connector = SimpleNamespace(pre_forward=lambda scheduler_output: None)
    runner.model = _fake_model

    monkeypatch.setattr(
        model_runner_module,
        "dispatch_cg_and_sync_dp",
        lambda *args, **kwargs: (fake_batch_desc, None),
    )
    monkeypatch.setattr(
        InputBatch, "make_dummy", classmethod(lambda cls, *a, **kw: fake_input_batch)
    )

    scheduler_output = SimpleNamespace(
        num_scheduled_tokens={"dummy": num_tokens},
        total_num_scheduled_tokens=num_tokens,
    )

    with pytest.raises(_StopAtModelCall):
        runner.execute_model(
            scheduler_output, dummy_run=True, skip_attn_for_dummy_run=True
        )

    assert runner.model_state.calls == ["prepare_runtime_dummy_inputs"]
    assert captured["input_ids"] is fake_input_batch.input_ids


def test_prepare_runtime_dummy_inputs_default_delegates_to_prepare_inputs() -> None:
    """The ``ModelState`` base's default body -- inherited unchanged by every
    model state that has no field needing separate dummy-batch handling,
    e.g. ``MambaHybridModelState`` -- must delegate to ``prepare_inputs``
    with the same (input_batch, req_states) and return its result as-is."""
    state = object.__new__(MambaHybridModelState)
    input_batch = object()
    req_states = object()
    sentinel = {"input_ids": "sentinel"}
    calls = []

    def _prepare_inputs(ib: object, rs: object) -> dict:
        calls.append((ib, rs))
        return sentinel

    state.prepare_inputs = _prepare_inputs

    result = state.prepare_runtime_dummy_inputs(input_batch, req_states)

    assert result is sentinel
    assert calls == [(input_batch, req_states)]
