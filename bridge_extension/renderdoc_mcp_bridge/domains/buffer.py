"""Buffer read and decode services."""

import re
import struct


class BufferServiceMixin:
    _MAX_BUFFER_READ_BYTES = 64 * 1024
    _MAX_DECODE_ROWS = 256

    @staticmethod
    def _is_null_rid(rid):
        rid_str = str(rid)
        return not rid_str or "Null" in rid_str or rid_str == "ResourceId::0"

    def _resolve_buffer_rid(self, controller, rid):
        if rid is None:
            return None

        rid_str = str(rid)
        try:
            if self.ctx.GetBuffer(rid) is not None:
                return rid
        except Exception:
            pass

        try:
            for buf in controller.GetBuffers():
                buf_rid = getattr(buf, "resourceId", None)
                if str(buf_rid) == rid_str:
                    return buf_rid
        except Exception as exc:
            self._warn_swallow("buffer.resolve.get_buffers", exc)

        try:
            for res in self.ctx.GetResources():
                res_rid = getattr(res, "resourceId", None)
                if str(res_rid) == rid_str and self.ctx.GetBuffer(res_rid) is not None:
                    return res_rid
        except Exception as exc:
            self._warn_swallow("buffer.resolve.get_resources", exc)

        return None

    @staticmethod
    def _byte_list(data):
        try:
            return bytes(data)
        except Exception:
            return bytes(bytearray(data))

    @staticmethod
    def _unpack_row(fmt, data, pos, count):
        size = struct.calcsize(fmt)
        if pos + size > len(data):
            return None
        return list(struct.unpack_from(fmt, data, pos)[:count])

    def _decode_vec4_rows(self, data, base_offset, fmt, max_rows=None):
        max_rows = max_rows or self._MAX_DECODE_ROWS
        spec = {
            "float4": ("<4f", 4),
            "uint4": ("<4I", 4),
            "int4": ("<4i", 4),
        }[fmt]
        row_size = struct.calcsize(spec[0])
        rows = []
        row_count = len(data) // row_size
        for row in range(min(row_count, max_rows)):
            pos = row * row_size
            rows.append(
                {
                    "offset": base_offset + pos,
                    "value": self._unpack_row(spec[0], data, pos, spec[1]),
                }
            )
        return {
            "format": fmt,
            "row_size": row_size,
            "rows": rows,
            "row_count": row_count,
            "truncated": row_count > len(rows),
        }

    def _decode_matrix_rows(self, data, base_offset, fmt, max_rows=None):
        max_rows = max_rows or self._MAX_DECODE_ROWS
        rows_count = 4
        cols_count = 4
        match = re.search(r"([1-4])x([1-4])", fmt)
        if match:
            rows_count = int(match.group(1))
            cols_count = int(match.group(2))

        value_count = rows_count * cols_count
        row_size = value_count * 4
        matrices = []
        matrix_count = len(data) // row_size
        for row in range(min(matrix_count, max_rows)):
            pos = row * row_size
            vals = self._unpack_row("<{}f".format(value_count), data, pos, value_count)
            if vals is None:
                continue
            matrix = [
                vals[idx * cols_count : (idx + 1) * cols_count]
                for idx in range(rows_count)
            ]
            matrices.append({"offset": base_offset + pos, "value": matrix})

        return {
            "format": "matrix{}x{}".format(rows_count, cols_count),
            "row_size": row_size,
            "rows": matrices,
            "row_count": matrix_count,
            "truncated": matrix_count > len(matrices),
        }

    def _decode_raw_rows(self, data, base_offset, max_rows=None):
        max_rows = max_rows or self._MAX_DECODE_ROWS
        rows = []
        row_size = 16
        row_count = (len(data) + row_size - 1) // row_size
        for row in range(min(row_count, max_rows)):
            pos = row * row_size
            chunk = data[pos : pos + row_size]
            item = {
                "offset": base_offset + pos,
                "hex": chunk.hex(),
            }
            if len(chunk) == 16:
                item["float4"] = list(struct.unpack_from("<4f", chunk, 0))
                item["int4"] = list(struct.unpack_from("<4i", chunk, 0))
                item["uint4"] = list(struct.unpack_from("<4I", chunk, 0))
            rows.append(item)
        return {
            "format": "raw16",
            "row_size": row_size,
            "rows": rows,
            "row_count": row_count,
            "truncated": row_count > len(rows),
        }

    @staticmethod
    def _parse_structured_stride(fmt, stride):
        if stride:
            return int(stride)
        match = re.search(r"structured\D+(\d+)", fmt)
        if match:
            return int(match.group(1))
        return None

    def _decode_structured_rows(self, data, base_offset, fmt, stride, max_rows=None):
        max_rows = max_rows or self._MAX_DECODE_ROWS
        stride = self._parse_structured_stride(fmt, stride)
        if not stride or stride <= 0:
            return {
                "format": "structured",
                "error": "structured format requires stride",
                "rows": [],
                "row_count": 0,
                "truncated": False,
            }

        rows = []
        row_count = len(data) // stride
        for row in range(min(row_count, max_rows)):
            pos = row * stride
            chunk = data[pos : pos + stride]
            item = {
                "index": row,
                "offset": base_offset + pos,
                "stride": stride,
                "hex": chunk.hex(),
            }
            float4_rows = []
            int4_rows = []
            uint4_rows = []
            for inner in range(0, len(chunk) // 16):
                inner_pos = inner * 16
                sub = chunk[inner_pos : inner_pos + 16]
                float4_rows.append(
                    {"offset": inner_pos, "value": list(struct.unpack_from("<4f", sub, 0))}
                )
                int4_rows.append(
                    {"offset": inner_pos, "value": list(struct.unpack_from("<4i", sub, 0))}
                )
                uint4_rows.append(
                    {"offset": inner_pos, "value": list(struct.unpack_from("<4I", sub, 0))}
                )
            if float4_rows:
                item["float4"] = float4_rows
                item["int4"] = int4_rows
                item["uint4"] = uint4_rows
            rows.append(item)

        return {
            "format": "structured",
            "stride": stride,
            "rows": rows,
            "row_count": row_count,
            "truncated": row_count > len(rows),
        }

    def _decode_buffer_bytes(self, data, base_offset, fmt=None, stride=None, max_rows=None):
        fmt = str(fmt or "raw").lower()
        if fmt in ("float4", "uint4", "int4"):
            return self._decode_vec4_rows(data, base_offset, fmt, max_rows)
        if fmt in ("matrix", "mat4", "float4x4", "matrix4x4") or re.fullmatch(
            r"(matrix|float)?[1-4]x[1-4]", fmt
        ):
            return self._decode_matrix_rows(data, base_offset, fmt, max_rows)
        if fmt.startswith("structured") or stride:
            return self._decode_structured_rows(data, base_offset, fmt, stride, max_rows)
        return self._decode_raw_rows(data, base_offset, max_rows)

    def read_buffer(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        rid = params.get("rid")
        if rid is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "rid is required"},
                "meta": {"cap": "active", "truncated": False},
            }

        offset = max(0, int(params.get("offset", 0) or 0))
        length = int(params.get("length", 0) or 0)
        fmt = params.get("format", "raw")
        stride = params.get("stride")
        eid = params.get("eid")

        result = {"data": None, "error": None}

        def collect(controller):
            if eid is not None:
                controller.SetFrameEvent(int(eid), True)

            resolved = self._resolve_buffer_rid(controller, rid)
            if resolved is None:
                result["error"] = "Buffer resource not found in current capture"
                return

            meta = self._resource_meta(resolved)
            size = int((meta or {}).get("size", 0) or 0)
            read_length = length
            if read_length <= 0 and size > offset:
                read_length = size - offset
            if read_length < 0:
                read_length = 0
            capped_length = min(read_length, self._MAX_BUFFER_READ_BYTES)

            raw = b""
            if capped_length > 0:
                raw = self._byte_list(controller.GetBufferData(resolved, offset, capped_length))
            decoded = self._decode_buffer_bytes(raw, offset, fmt, stride)
            result["data"] = {
                "rid": str(resolved),
                "name": self.ctx.GetResourceName(resolved),
                "meta": meta,
                "offset": offset,
                "requested_length": length,
                "read_length": len(raw),
                "format": str(fmt or "raw"),
                "decoded": decoded,
                "truncated": read_length > len(raw) or bool(decoded.get("truncated")),
            }

        self.ctx.Replay().BlockInvoke(collect)

        return {
            "ok": result["data"] is not None,
            "mode": "summary",
            "data": result["data"],
            "err": None if result["data"] is not None else {"code": "read_failed", "msg": result["error"]},
            "meta": {
                "cap": "active",
                "truncated": bool((result["data"] or {}).get("truncated", False)),
            },
        }
