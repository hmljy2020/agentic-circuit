"""Thin ctypes control plane for a generated Agentic Circuit model library."""

from __future__ import annotations

import ctypes
from pathlib import Path


class ModelRuntime:
    """Own one generated model and advance it in complete simulation ticks."""

    def __init__(self, library: str | Path) -> None:
        self._lib = ctypes.CDLL(str(library))
        handle = ctypes.c_void_p
        self._lib.ac_model_abi_version.restype = ctypes.c_uint32
        if self._lib.ac_model_abi_version() != 3:
            raise RuntimeError("unsupported generated model ABI (requires ABI 3)")
        self._lib.ac_model_create.restype = handle
        self._lib.ac_model_destroy.argtypes = [handle]
        self._lib.ac_model_host_input_count.argtypes = [handle]
        self._lib.ac_model_host_input_count.restype = ctypes.c_size_t
        self._lib.ac_model_host_input_name.argtypes = [handle, ctypes.c_size_t]
        self._lib.ac_model_host_input_name.restype = ctypes.c_char_p
        self._lib.ac_model_host_input_size.argtypes = [handle, ctypes.c_size_t]
        self._lib.ac_model_host_input_size.restype = ctypes.c_size_t
        self._lib.ac_model_host_input_ready.argtypes = [handle, ctypes.c_size_t]
        self._lib.ac_model_host_input_ready.restype = ctypes.c_int
        self._lib.ac_model_offer.argtypes = [handle, ctypes.c_size_t, ctypes.c_int32]
        self._lib.ac_model_offer.restype = ctypes.c_int
        self._lib.ac_model_offer_bytes.argtypes = [
            handle,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
        ]
        self._lib.ac_model_offer_bytes.restype = ctypes.c_int
        self._lib.ac_model_host_output_count.argtypes = [handle]
        self._lib.ac_model_host_output_count.restype = ctypes.c_size_t
        self._lib.ac_model_host_output_name.argtypes = [handle, ctypes.c_size_t]
        self._lib.ac_model_host_output_name.restype = ctypes.c_char_p
        self._lib.ac_model_host_output_size.argtypes = [handle, ctypes.c_size_t]
        self._lib.ac_model_host_output_size.restype = ctypes.c_size_t
        self._lib.ac_model_host_output_ready.argtypes = [handle, ctypes.c_size_t]
        self._lib.ac_model_host_output_ready.restype = ctypes.c_int
        self._lib.ac_model_take_bytes.argtypes = [
            handle,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
        ]
        self._lib.ac_model_take_bytes.restype = ctypes.c_int
        self._lib.ac_model_step_tick.argtypes = [handle]
        self._lib.ac_model_step_tick.restype = ctypes.c_int
        self._lib.ac_model_tick.argtypes = [handle]
        self._lib.ac_model_tick.restype = ctypes.c_uint64
        self._lib.ac_model_reset.argtypes = [handle]
        self._lib.ac_model_stat_count.argtypes = [handle]
        self._lib.ac_model_stat_count.restype = ctypes.c_size_t
        for field in ("name", "path"):
            function = getattr(self._lib, f"ac_model_stat_{field}")
            function.argtypes = [handle, ctypes.c_size_t]
            function.restype = ctypes.c_char_p
        self._lib.ac_model_stat_value.argtypes = [handle, ctypes.c_size_t]
        self._lib.ac_model_stat_value.restype = ctypes.c_uint64
        self._lib.ac_model_last_error.argtypes = [handle]
        self._lib.ac_model_last_error.restype = ctypes.c_char_p
        self._handle = self._lib.ac_model_create()
        if not self._handle:
            raise RuntimeError("generated model construction failed")
        self.inputs = tuple(
            self._decode(self._lib.ac_model_host_input_name(self._handle, index))
            for index in range(self._lib.ac_model_host_input_count(self._handle))
        )
        self._indices = {name: index for index, name in enumerate(self.inputs)}
        self.input_sizes = {
            name: int(self._lib.ac_model_host_input_size(self._handle, index))
            for index, name in enumerate(self.inputs)
        }
        self.outputs = tuple(
            self._decode(self._lib.ac_model_host_output_name(self._handle, index))
            for index in range(self._lib.ac_model_host_output_count(self._handle))
        )
        self._output_indices = {name: index for index, name in enumerate(self.outputs)}
        self.output_sizes = {
            name: int(self._lib.ac_model_host_output_size(self._handle, index))
            for index, name in enumerate(self.outputs)
        }

    @staticmethod
    def _decode(value: bytes | None) -> str:
        return value.decode("utf-8") if value else ""

    def close(self) -> None:
        if self._handle:
            self._lib.ac_model_destroy(self._handle)
            self._handle = None

    def __enter__(self) -> ModelRuntime:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @property
    def tick(self) -> int:
        return int(self._lib.ac_model_tick(self._handle))

    def ready(self, ingress: str) -> bool:
        return bool(self._lib.ac_model_host_input_ready(self._handle, self._indices[ingress]))

    def offer(self, ingress: str, value: int) -> bool:
        result = self._lib.ac_model_offer(self._handle, self._indices[ingress], value)
        if result < 0:
            raise RuntimeError("invalid host offer")
        return bool(result)

    def offer_bytes(self, ingress: str, value: bytes | bytearray | memoryview) -> bool:
        raw = bytes(value)
        expected = self.input_sizes[ingress]
        if len(raw) != expected:
            raise ValueError(f"host input {ingress!r} requires exactly {expected} bytes")
        buffer = (ctypes.c_uint8 * len(raw)).from_buffer_copy(raw)
        result = self._lib.ac_model_offer_bytes(
            self._handle, self._indices[ingress], buffer, len(raw)
        )
        if result < 0:
            raise RuntimeError("invalid host byte offer")
        return bool(result)

    def output_ready(self, output: str) -> bool:
        return bool(
            self._lib.ac_model_host_output_ready(
                self._handle, self._output_indices[output]
            )
        )

    def take_bytes(self, output: str) -> bytes | None:
        index = self._output_indices[output]
        size = self.output_sizes[output]
        buffer = (ctypes.c_uint8 * size)()
        result = self._lib.ac_model_take_bytes(self._handle, index, buffer, size)
        if result < 0:
            raise RuntimeError("invalid host byte take")
        return bytes(buffer) if result else None

    def step(self) -> None:
        if self._lib.ac_model_step_tick(self._handle) != 1:
            error = self._decode(self._lib.ac_model_last_error(self._handle))
            raise RuntimeError(error or "generated model stopped")

    def reset(self) -> None:
        self._lib.ac_model_reset(self._handle)

    def statistics(self) -> dict[tuple[str, str], int]:
        count = self._lib.ac_model_stat_count(self._handle)
        return {
            (
                self._decode(self._lib.ac_model_stat_path(self._handle, index)),
                self._decode(self._lib.ac_model_stat_name(self._handle, index)),
            ): int(self._lib.ac_model_stat_value(self._handle, index))
            for index in range(count)
        }
