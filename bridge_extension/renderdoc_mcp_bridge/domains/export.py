"""Debug and export-oriented services."""

import os
import tempfile
import hashlib

import renderdoc as rd


class ExportServiceMixin:
    def export_texture_raw(self, params):
        """Export native replay bytes for one explicit subresource; no image remap."""
        result = {"schema_version": 1, "path": None, "error": None}

        def collect(controller):
            temporary = None
            try:
                if params.get("eid") is None or not params.get("dest"):
                    raise ValueError("eid and explicit dest are required")
                eid = int(params["eid"])
                controller.SetFrameEvent(eid, True)
                texture = next((t for t in controller.GetTextures() if str(t.resourceId) == str(params.get("rid"))), None)
                if texture is None:
                    raise ValueError("Texture not found")
                mip, layer, sample = (int(params.get(k, 0)) for k in ("mip", "slice", "sample"))
                if not 0 <= mip < int(texture.mips) or not 0 <= layer < int(texture.arraysize) or not 0 <= sample < max(1, int(texture.msSamp)):
                    raise ValueError("Subresource outside texture bounds")
                if int(texture.dimension) == 3 and layer != 0:
                    raise ValueError("3D exports contain the whole mip volume; slice must be zero")
                sub = rd.Subresource()
                sub.mip, sub.slice, sub.sample = mip, layer, sample
                data = bytes(controller.GetTextureData(texture.resourceId, sub))
                if not data:
                    raise ValueError("Replay returned no texture bytes")
                path = os.path.abspath(str(params["dest"]))
                if os.path.isdir(path) or (os.path.exists(path) and not params.get("overwrite")):
                    raise ValueError("Destination exists or is not a file")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                descriptor, temporary = tempfile.mkstemp(prefix=".texture-raw-", dir=os.path.dirname(path))
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
                os.replace(temporary, path)
                temporary = None
                result.update(path=path, eid=eid, rid=str(texture.resourceId), mip=mip, slice=layer, sample=sample,
                              width=max(1, int(texture.width) >> mip), height=max(1, int(texture.height) >> mip),
                              depth=max(1, int(texture.depth) >> mip), format=texture.format.Name(),
                              bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), complete=True)
            except Exception as exc:
                result["error"] = str(exc)
            finally:
                if temporary is not None and os.path.exists(temporary):
                    os.unlink(temporary)
        self.ctx.Replay().BlockInvoke(collect)
        return {"ok": result["path"] is not None, "mode": "summary", "data": result,
                "err": None if result["path"] else {"code": "texture_raw_export_failed", "msg": result["error"]},
                "meta": {"cap": "active", "truncated": False}}

    def export_buffer(self, params):
        """Write an exact buffer range locally without putting its bytes in RPC JSON."""
        result = {"path": None, "error": None}

        def collect(controller):
            temporary = None
            try:
                rid = params.get("rid")
                dest = params.get("dest")
                if rid is None or not dest:
                    raise ValueError("rid and dest are required")
                offset = int(params.get("offset", 0) or 0)
                length = int(params.get("length", 0) or 0)
                if offset < 0 or length < 0:
                    raise ValueError("Buffer range must be nonnegative")
                eid = params.get("eid")
                if eid is not None:
                    controller.SetFrameEvent(int(eid), True)
                resolved = self._resolve_buffer_rid(controller, rid)
                if resolved is None:
                    raise ValueError("Buffer resource not found in current capture")
                size = int((self._resource_meta(resolved) or {}).get("size", 0) or 0)
                if length == 0:
                    length = size - offset
                if offset > size or length < 0 or offset + length > size:
                    raise ValueError("Requested buffer range exceeds the resource")
                overwrite = bool(params.get("overwrite"))
                path = os.path.abspath(str(dest))
                if os.path.isdir(path) or str(dest).endswith(("/", "\\")):
                    raise ValueError("Buffer dest must be an explicit file path")
                if os.path.exists(path) and not overwrite:
                    raise ValueError("Export destination already exists")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                descriptor, temporary = tempfile.mkstemp(prefix=".buffer-export-", suffix=".partial", dir=os.path.dirname(path))
                digest = hashlib.sha256()
                written = 0
                with os.fdopen(descriptor, "wb") as stream:
                    for position in range(0, length, 8 * 1024 * 1024):
                        requested = min(8 * 1024 * 1024, length - position)
                        data = self._byte_list(controller.GetBufferData(resolved, offset + position, requested))
                        if len(data) != requested:
                            raise ValueError("Replay returned an incomplete buffer range")
                        stream.write(data)
                        digest.update(data)
                        written += len(data)
                if written != length:
                    raise ValueError("Buffer export extent mismatch")
                if not overwrite and os.path.exists(path):
                    raise ValueError("Export destination already exists")
                os.replace(temporary, path)
                temporary = None
                result.update({"path": path, "rid": str(resolved), "eid": eid,
                               "offset": offset, "bytes": written, "resource_bytes": size,
                               "sha256": digest.hexdigest(), "complete": True})
            except Exception as exc:
                result["error"] = str(exc)
            finally:
                if temporary is not None and os.path.exists(temporary):
                    os.unlink(temporary)

        self.ctx.Replay().BlockInvoke(collect)
        return {"ok": result["path"] is not None, "mode": "summary", "data": result,
                "err": None if result["path"] else {"code": "buffer_export_failed", "msg": result["error"]},
                "meta": {"cap": "active", "truncated": False}}

    @staticmethod
    def _overlay_enum(name):
        overlay_map = {
            "drawcall": rd.DebugOverlay.Drawcall,
            "highlight_drawcall": rd.DebugOverlay.Drawcall,
            "wireframe": rd.DebugOverlay.Wireframe,
            "depth": rd.DebugOverlay.Depth,
            "stencil": rd.DebugOverlay.Stencil,
            "backface_cull": rd.DebugOverlay.BackfaceCull,
            "viewport_scissor": rd.DebugOverlay.ViewportScissor,
            "clear_before_draw": rd.DebugOverlay.ClearBeforeDraw,
            "clear_before_pass": rd.DebugOverlay.ClearBeforePass,
            "triangle_size_draw": rd.DebugOverlay.TriangleSizeDraw,
            "triangle_size_pass": rd.DebugOverlay.TriangleSizePass,
            "quad_overdraw_draw": rd.DebugOverlay.QuadOverdrawDraw,
            "quad_overdraw_pass": rd.DebugOverlay.QuadOverdrawPass,
        }
        return overlay_map.get(str(name or "").lower())

    def debug_resource_ctx(self, params):
        rid = params.get("rid")
        eid = params.get("eid")
        if rid is None or eid is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "rid and eid are required"},
                "meta": {"cap": "active", "truncated": False},
            }

        ctx = self._binding_context_for_event(rid, int(eid))
        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "rid": str(rid),
                "eid": int(eid),
                "ctx": ctx,
            },
            "err": None,
            "meta": {"cap": "active", "truncated": False},
        }

    def debug_resource_info(self, params):
        rid = params.get("rid")
        if rid is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "rid is required"},
                "meta": {"cap": "active", "truncated": False},
            }

        target = None
        resources = self.ctx.GetResources()
        for res in resources:
            if str(res.resourceId) == str(rid):
                target = res
                break

        if target is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "not_found", "msg": "resource not found"},
                "meta": {"cap": "active", "truncated": False},
            }

        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "rid": str(target.resourceId),
                "name": target.name,
                "type": str(target.type).split(".")[-1],
                "autogen": bool(target.autogeneratedName),
                "parents": [str(x) for x in target.parentResources],
                "derived": [str(x) for x in target.derivedResources],
            },
            "err": None,
            "meta": {"cap": "active", "truncated": False},
        }

    def debug_save_texture(self, params):
        rid = params.get("rid")
        eid = params.get("eid")
        if rid is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "rid is required"},
                "meta": {"cap": "active", "truncated": False},
            }

        dest, dest_path = self._resolve_texture_dest(params)
        result = {
            "path": None,
            "error": None,
            "format": dest,
            "requested_dest": dest_path,
            "rid": str(rid),
        }

        def collect(controller):
            if eid is not None:
                controller.SetFrameEvent(int(eid), True)
            saved = self._save_texture_resource(
                controller,
                rid,
                dest,
                dest_path,
                eid,
                bool(params.get("overwrite")),
                prefix="texture",
                type_cast=params.get("type_cast"),
            )
            result.update(saved)

        self.ctx.Replay().BlockInvoke(collect)

        return {
            "ok": result["path"] is not None,
            "mode": "summary",
            "data": result,
            "err": None if result["path"] else {"code": "save_failed", "msg": result["error"]},
            "meta": {"cap": "active", "truncated": False},
        }

    def save_event_output_texture(self, params):
        eid = params.get("eid")
        if eid is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "eid is required"},
                "meta": {"cap": "active", "truncated": False},
            }

        output_index = max(0, int(params.get("output_index", 0) or 0))
        include_depth = bool(params.get("depth"))
        dest, dest_path = self._resolve_texture_dest(params)
        result = {
            "path": None,
            "error": None,
            "format": dest,
            "requested_dest": dest_path,
            "eid": int(eid),
            "output_index": output_index,
            "depth": include_depth,
            "rid": None,
            "name": None,
        }

        def collect(controller):
            resolved_rid = self._resolve_event_output_rid(controller, int(eid), output_index, include_depth)
            if resolved_rid is None:
                result["error"] = "Requested event output target was not found"
                return

            result["rid"] = str(resolved_rid)
            try:
                result["name"] = self.ctx.GetResourceName(resolved_rid)
            except Exception as exc:
                self._warn_swallow("export.save_event_output_texture.resource_name", exc)

            saved = self._save_texture_resource(
                controller,
                resolved_rid,
                dest,
                dest_path,
                int(eid),
                bool(params.get("overwrite")),
                prefix="event_output",
            )
            result.update(saved)

        self.ctx.Replay().BlockInvoke(collect)

        return {
            "ok": result["path"] is not None,
            "mode": "summary",
            "data": result,
            "err": None if result["path"] else {"code": "save_failed", "msg": result["error"]},
            "meta": {"cap": "active", "truncated": False},
        }

    def debug_save_overlay(self, params):
        eid = params.get("eid")
        overlay_name = params.get("overlay", "drawcall")
        rid = params.get("rid")
        dest = str(params.get("dest", "PNG")).upper()

        if eid is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "eid is required"},
                "meta": {"cap": "active", "truncated": False},
            }

        overlay_enum = self._overlay_enum(overlay_name)
        if overlay_enum is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "bad_overlay", "msg": "unsupported overlay: {}".format(overlay_name)},
                "meta": {"cap": "active", "truncated": False},
            }

        out_dir = os.path.join(tempfile.gettempdir(), "renderdoc_mcp_exports")
        os.makedirs(out_dir, exist_ok=True)
        result = {"path": None, "error": None, "target_rid": None, "overlay_rid": None}

        def collect(controller):
            controller.SetFrameEvent(int(eid), True)
            pipe = controller.GetPipelineState()

            target_rid = None
            if rid is not None:
                target_rid = str(rid)
            else:
                try:
                    for out in pipe.GetOutputTargets():
                        res = getattr(out, "resource", None)
                        res_str = str(res)
                        if res_str and "Null" not in res_str and res_str != "ResourceId::0":
                            target_rid = res_str
                            break
                except Exception as exc:
                    self._warn_swallow("export.debug_save_overlay.output_targets", exc)
                    target_rid = None

            if target_rid is None:
                result["error"] = "No output render target found for overlay export"
                return

            tex_details = None
            resolved = None
            for tex in controller.GetTextures():
                if str(tex.resourceId) == target_rid:
                    tex_details = tex
                    resolved = tex.resourceId
                    break

            if resolved is None:
                result["error"] = "Target texture resource not found in current capture"
                return

            width = int(getattr(tex_details, "width", 256) or 256)
            height = int(getattr(tex_details, "height", 256) or 256)
            result["target_rid"] = target_rid

            out = None
            try:
                out = controller.CreateOutput(
                    rd.CreateHeadlessWindowingData(width, height),
                    rd.ReplayOutputType.Texture,
                )
                tex_display = rd.TextureDisplay()
                tex_display.resourceId = resolved
                tex_display.overlay = overlay_enum
                tex_display.subresource.mip = 0
                tex_display.subresource.slice = 0
                tex_display.subresource.sample = 0
                out.SetTextureDisplay(tex_display)
                out.Display()
                overlay_rid = out.GetDebugOverlayTexID()
                overlay_rid_str = str(overlay_rid)
                result["overlay_rid"] = overlay_rid_str

                if not overlay_rid_str or "Null" in overlay_rid_str or overlay_rid_str == "ResourceId::0":
                    result["error"] = "Overlay texture was not generated"
                    return

                save = rd.TextureSave()
                save.resourceId = overlay_rid
                ext = "png"
                if dest == "HDR":
                    save.destType = rd.FileType.HDR
                    ext = "hdr"
                elif dest == "DDS":
                    save.destType = rd.FileType.DDS
                    ext = "dds"
                    save.mip = -1
                    save.slice.sliceIndex = -1
                else:
                    save.destType = rd.FileType.PNG
                save.alpha = rd.AlphaMapping.Preserve
                if dest != "DDS":
                    save.mip = 0
                    save.slice.sliceIndex = 0

                out_path = os.path.join(
                    out_dir,
                    "overlay_{}_{}_{}.{}".format(
                        str(overlay_name).lower(),
                        str(eid),
                        target_rid.replace("::", "_"),
                        ext,
                    ),
                )
                save_res = controller.SaveTexture(save, out_path)
                result["path"] = out_path if os.path.exists(out_path) else None
                result["error"] = None if result["path"] else str(save_res)
            except Exception as exc:
                result["error"] = str(exc)
            finally:
                if out is not None:
                    try:
                        controller.ShutdownOutput(out)
                    except Exception as exc:
                        self._warn_swallow("export.debug_save_overlay.shutdown_output", exc)

        self.ctx.Replay().BlockInvoke(collect)

        return {
            "ok": result["path"] is not None,
            "mode": "summary",
            "data": result,
            "err": None if result["path"] else {"code": "save_failed", "msg": result["error"]},
            "meta": {"cap": "active", "truncated": False},
        }

    @staticmethod
    def _resolve_export_path(dest_path, prefix, rid, eid, ext, overwrite):
        safe_rid = str(rid).replace("::", "_").replace(":", "_").replace("\\", "_").replace("/", "_")
        eid_part = "_eid{}".format(eid) if eid is not None else ""
        filename = "{}_{}{}.{}".format(prefix, safe_rid, eid_part, ext)

        if dest_path:
            path = os.path.abspath(str(dest_path))
            root, suffix = os.path.splitext(path)
            is_dir = (
                os.path.isdir(path)
                or str(dest_path).endswith(("\\", "/"))
                or suffix.lower() not in (".png", ".hdr", ".dds")
            )
            out_path = os.path.join(path, filename) if is_dir else path
        else:
            out_dir = os.path.join(tempfile.gettempdir(), "renderdoc_mcp_exports")
            out_path = os.path.join(out_dir, filename)

        out_dir = os.path.dirname(out_path)
        os.makedirs(out_dir, exist_ok=True)

        if overwrite or not os.path.exists(out_path):
            return out_path

        root, suffix = os.path.splitext(out_path)
        for idx in range(1, 10000):
            candidate = "{}_{:03d}{}".format(root, idx, suffix)
            if not os.path.exists(candidate):
                return candidate
        raise RuntimeError("Could not find a non-conflicting export path for {}".format(out_path))

    @staticmethod
    def _resolve_texture_dest(params):
        dest_value = params.get("dest")
        dest_format = params.get("format") or params.get("type")
        dest_path = params.get("path") or params.get("output")
        if dest_value is not None:
            dest_text = str(dest_value)
            if dest_text.upper() in ("PNG", "HDR", "DDS") and dest_format is None and dest_path is None:
                dest_format = dest_text
            elif dest_path is None:
                dest_path = dest_text
        if dest_format is None and dest_path is not None:
            suffix = os.path.splitext(str(dest_path))[1].lower().lstrip(".")
            if suffix in ("png", "hdr", "dds"):
                dest_format = suffix
        return str(dest_format or "PNG").upper(), dest_path

    @staticmethod
    def _valid_resource_id(rid):
        rid_str = str(rid)
        return bool(rid_str) and "Null" not in rid_str and rid_str != "ResourceId::0"

    def _resolve_event_output_rid(self, controller, eid, output_index, include_depth):
        # Action metadata identifies the resource, but its contents still require replay.
        controller.SetFrameEvent(int(eid), True)
        action = self.ctx.GetAction(int(eid))
        if action is not None:
            if include_depth:
                rid = getattr(action, "depthOut", None)
                if self._valid_resource_id(rid):
                    return rid
            else:
                try:
                    outputs = list(getattr(action, "outputs", []) or [])
                except Exception:
                    outputs = []
                if 0 <= output_index < len(outputs):
                    rid = outputs[output_index]
                    if self._valid_resource_id(rid):
                        return rid

        pipe = controller.GetPipelineState()

        if include_depth:
            try:
                depth_target = pipe.GetDepthTarget()
                rid = getattr(depth_target, "resource", None)
                if self._valid_resource_id(rid):
                    return rid
            except Exception as exc:
                self._warn_swallow("export.resolve_event_output_rid.depth_target", exc)
            return None

        try:
            outputs = list(pipe.GetOutputTargets() or [])
        except Exception as exc:
            self._warn_swallow("export.resolve_event_output_rid.output_targets", exc)
            outputs = []
        if 0 <= output_index < len(outputs):
            rid = getattr(outputs[output_index], "resource", None)
            if self._valid_resource_id(rid):
                return rid
        return None

    def _save_texture_resource(self, controller, rid, dest, dest_path, eid, overwrite, prefix, type_cast=None):
        result = {"schema_version": 2, "path": None, "error": None}
        casts = {name.lower(): name for name in ("Typeless", "Float", "UNorm", "SNorm", "UInt", "SInt", "Depth", "Double", "UScaled", "SScaled")}
        requested_cast = "typeless" if type_cast is None else str(type_cast).strip().lower()
        if requested_cast not in casts:
            result["error"] = "Unsupported texture type_cast: " + str(type_cast)
            return result
        cast_name = casts[requested_cast]
        result["type_cast"] = cast_name
        save = rd.TextureSave()
        save.typeCast = getattr(rd.CompType, cast_name)
        resolved = None
        for tex in controller.GetTextures():
            if str(tex.resourceId) == str(rid):
                resolved = tex.resourceId
                break
        if resolved is None:
            result["error"] = "Texture resource not found in current capture"
            return result

        save.resourceId = resolved
        ext = "png"
        if dest == "HDR":
            save.destType = rd.FileType.HDR
            ext = "hdr"
        elif dest == "DDS":
            save.destType = rd.FileType.DDS
            ext = "dds"
            save.mip = -1
            save.slice.sliceIndex = -1
        else:
            save.destType = rd.FileType.PNG
        save.alpha = rd.AlphaMapping.Preserve
        if dest != "DDS":
            save.mip = 0
            save.slice.sliceIndex = 0

        try:
            out_path = self._resolve_export_path(dest_path, prefix, rid, eid, ext, overwrite)
        except Exception as exc:
            result["error"] = str(exc)
            return result

        try:
            save_result = controller.SaveTexture(save, out_path)
            result["path"] = out_path if os.path.exists(out_path) else None
            result["error"] = None if result["path"] else str(save_result)
        except Exception as exc:
            result["error"] = str(exc)
        return result
