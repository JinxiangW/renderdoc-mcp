"""Packet-building services."""

import renderdoc as rd


class PacketServiceMixin:
    def get_frame_packet(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        limit = int(params.get("limit", 20) or 20)
        pass_summary = self.list_passes({"limit": limit})
        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "api": str(self.ctx.APIProps().pipelineType),
                "path": self.ctx.GetCaptureFilename(),
                "passes": pass_summary["data"]["items"],
            },
            "err": None,
            "meta": {
                "cap": "active",
                "truncated": pass_summary["meta"].get("truncated", False),
                "count": pass_summary["data"]["count"],
            },
        }

    def get_pass_packet(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        marker = params.get("marker") or params.get("pass")
        eid = params.get("eid")
        limit = int(params.get("limit", 8) or 8)

        pass_entry = None
        if marker:
            summary = self.list_passes({"marker": marker, "limit": 1})
            items = summary["data"]["items"]
            if items:
                pass_entry = items[0]
        elif eid is not None:
            action = self.ctx.GetAction(int(eid))
            if action is not None:
                name = action.customName or action.GetName(self.ctx.GetStructuredFile())
                pass_entry = self._summarize_marker(name, action.eventId, action.children)

        if pass_entry is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "pass_not_found", "msg": "Pass not found"},
                "meta": {"cap": "active", "truncated": False},
            }

        reps = self._collect_children(pass_entry["eid"], limit)
        pass_io = self._pass_outputs(pass_entry["eid"])
        rep_packet = None
        rep_eid = self._find_representative_eid(pass_entry["eid"])
        if rep_eid is not None:
            rep_packet_res = self.get_draw_packet({"eid": rep_eid})
            if rep_packet_res["ok"]:
                rep_packet = rep_packet_res["data"]
        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "pass": pass_entry,
                "io": pass_io,
                "rep": reps,
                "rep_draw": rep_packet,
            },
            "err": None,
            "meta": {"cap": "active", "truncated": len(reps) >= limit},
        }

    def get_draw_packet(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        eid = params.get("eid")
        if eid is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_event_id", "msg": "eid is required"},
                "meta": {"cap": "active", "truncated": False},
            }

        eid = int(eid)
        action = self.ctx.GetAction(eid)
        if action is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "bad_event", "msg": "Event not found"},
                "meta": {"cap": "active", "truncated": False},
            }

        pipe = self.inspect_pipeline_state({"eid": eid})
        kind = self._action_type(action)
        if kind == "Dispatch":
            shader = self.inspect_shader({"eid": eid, "stage": "cs"})
        else:
            shader = self.inspect_shader({"eid": eid, "stage": "ps"})

        packet = {
            "eid": eid,
            "name": action.customName or action.GetName(self.ctx.GetStructuredFile()),
            "type": kind,
            "counts": {
                "idx": int(getattr(action, "numIndices", 0) or 0),
                "inst": int(getattr(action, "numInstances", 0) or 0),
            },
            "pipe": pipe["data"] if pipe["ok"] else None,
            "shader": shader["data"] if shader and shader["ok"] else None,
            "io": self._event_io_packet(action, kind),
            "state": self._fixed_function_state(eid),
        }

        return {
            "ok": True,
            "mode": "summary",
            "data": packet,
            "err": None,
            "meta": {"cap": "active", "truncated": False},
        }

    def _collect_children(self, eid, limit):
        action = self.ctx.GetAction(eid)
        if action is None:
            return []
        items = []
        for child in action.children:
            if len(items) >= limit:
                break
            name = child.customName or child.GetName(self.ctx.GetStructuredFile())
            items.append(
                {
                    "eid": child.eventId,
                    "name": name,
                    "type": self._action_type(child),
                }
            )
        return items

    def _pass_outputs(self, eid):
        action = self.ctx.GetAction(eid)
        packet = {
            "out_rt": [],
            "out_ds": None,
        }
        if action is None:
            return packet
        terminal_eid = self._max_descendant_eid(action)

        for idx, rid in enumerate(action.outputs):
            rid_str = str(rid)
            if not rid_str or "Null" in rid_str or rid_str == "ResourceId::0":
                continue
            packet["out_rt"].append(
                {
                    "rid": rid_str,
                    "name": self.ctx.GetResourceName(rid),
                    "slot": idx,
                    "meta": self._resource_meta(rid),
                    "producer": self._producer_info(rid, terminal_eid),
                    "last_write": self._last_write_info(rid),
                    "first_read": self._first_read_info(rid, terminal_eid),
                    "first_ps_read": self._first_stage_read_info(rid, terminal_eid, "PS_"),
                    "next": self._first_consumers(rid, terminal_eid, 3),
                }
            )

        rid = action.depthOut
        rid_str = str(rid)
        if rid_str and "Null" not in rid_str and rid_str != "ResourceId::0":
            packet["out_ds"] = {
                "rid": rid_str,
                "name": self.ctx.GetResourceName(rid),
                "meta": self._resource_meta(rid),
                "producer": self._producer_info(rid, terminal_eid),
                "last_write": self._last_write_info(rid),
                "first_read": self._first_read_info(rid, terminal_eid),
                "first_ps_read": self._first_stage_read_info(rid, terminal_eid, "PS_"),
                "next": self._first_consumers(rid, terminal_eid, 3),
            }

        return packet

    def _find_representative_eid(self, eid):
        action = self.ctx.GetAction(eid)
        if action is None:
            return None

        def visit(node):
            for child in node.children:
                kind = self._action_type(child)
                if kind in ("Draw", "Dispatch"):
                    return child.eventId
                if len(child.children) > 0:
                    found = visit(child)
                    if found is not None:
                        return found
            return None

        return visit(action)

    def _event_io_packet(self, action, kind):
        packet = {
            "in_tex": [],
            "out_rt": [],
            "out_uav": [],
            "out_ds": None,
            "out_next": [],
        }
        eid = action.eventId

        def collect(controller):
            controller.SetFrameEvent(eid, True)
            pipe = controller.GetPipelineState()

            if kind == "Dispatch":
                stages = [rd.ShaderStage.Compute]
            else:
                stages = [
                    rd.ShaderStage.Vertex,
                    rd.ShaderStage.Hull,
                    rd.ShaderStage.Domain,
                    rd.ShaderStage.Geometry,
                    rd.ShaderStage.Pixel,
                ]

            seen_inputs = set()
            out_rids = []

            for stage in stages:
                try:
                    for srv in pipe.GetReadOnlyResources(stage, False):
                        rid = srv.descriptor.resource
                        rid_str = str(rid)
                        if not rid_str or "Null" in rid_str or rid_str == "ResourceId::0":
                            continue
                        if rid_str in seen_inputs:
                            continue
                        seen_inputs.add(rid_str)
                        packet["in_tex"].append(
                            {
                                "rid": rid_str,
                                "name": self.ctx.GetResourceName(rid),
                                "slot": srv.access.index,
                            }
                        )
                except Exception:
                    pass

            try:
                if kind != "Dispatch":
                    for idx, rid in enumerate(action.outputs):
                        rid_str = str(rid)
                        if not rid_str or "Null" in rid_str or rid_str == "ResourceId::0":
                            continue
                        out_rids.append((rid, rid_str))
                        packet["out_rt"].append(
                            {
                                "rid": rid_str,
                                "name": self.ctx.GetResourceName(rid),
                                "slot": idx,
                            }
                        )

                    rid = action.depthOut
                    rid_str = str(rid)
                    if rid_str and "Null" not in rid_str and rid_str != "ResourceId::0":
                        packet["out_ds"] = {
                            "rid": rid_str,
                            "name": self.ctx.GetResourceName(rid),
                        }

                    if not packet["out_rt"] and packet["out_ds"] is None:
                        try:
                            outs = pipe.GetOutputTargets()
                            for idx, rt in enumerate(outs):
                                rid = getattr(rt, "resource", None)
                                rid_str = str(rid)
                                if not rid_str or "Null" in rid_str or rid_str == "ResourceId::0":
                                    continue
                                packet["out_rt"].append(
                                    {
                                        "rid": rid_str,
                                        "name": self.ctx.GetResourceName(rid),
                                        "slot": idx,
                                    }
                                )
                        except Exception:
                            pass
            except Exception:
                pass

            uav_stages = [rd.ShaderStage.Compute] if kind == "Dispatch" else [rd.ShaderStage.Pixel]
            seen_uav = set()
            for stage in uav_stages:
                try:
                    for uav in pipe.GetReadWriteResources(stage, False):
                        rid = uav.descriptor.resource
                        rid_str = str(rid)
                        if not rid_str or "Null" in rid_str or rid_str == "ResourceId::0":
                            continue
                        if rid_str in seen_uav:
                            continue
                        seen_uav.add(rid_str)
                        packet["out_uav"].append(
                            {
                                "rid": rid_str,
                                "name": self.ctx.GetResourceName(rid),
                                "slot": uav.access.index,
                            }
                        )
                except Exception:
                    pass

            packet["in_tex"] = packet["in_tex"][:8]
            packet["out_rt"] = packet["out_rt"][:8]
            packet["out_uav"] = packet["out_uav"][:8]

            downstream = []
            for rid, rid_str in out_rids[:2]:
                try:
                    usage_items = controller.GetUsage(rid)
                except Exception:
                    continue
                for use in usage_items:
                    if use.eventId <= eid:
                        continue
                    downstream.append(
                        {
                            "src": rid_str,
                            "eid": use.eventId,
                            "usage": str(use.usage).split(".")[-1],
                        }
                    )
                    if len(downstream) >= 8:
                        break
                if len(downstream) >= 8:
                    break

            packet["out_next"] = downstream

        self.ctx.Replay().BlockInvoke(collect)
        return packet

    def _fixed_function_state(self, eid):
        state = {
            "blend": None,
            "depth": None,
            "rast": None,
        }

        def collect(controller):
            controller.SetFrameEvent(eid, True)
            try:
                d3d11 = controller.GetD3D11PipelineState()
            except Exception:
                return
            if d3d11 is None:
                return

            try:
                om = d3d11.outputMerger
                bs = om.blendState
                state["blend"] = {
                    "alpha_to_coverage": bool(bs.alphaToCoverage),
                    "independent_blend": bool(bs.independentBlend),
                }
            except Exception:
                pass

            try:
                om = d3d11.outputMerger
                ds = om.depthStencilState
                state["depth"] = {
                    "enabled": bool(ds.depthEnable),
                    "func": str(ds.depthFunction).split(".")[-1],
                    "write": bool(ds.depthWrites),
                }
            except Exception:
                pass

            try:
                rast = d3d11.rasterizer.state
                state["rast"] = {
                    "fill": str(rast.fillMode).split(".")[-1],
                    "cull": str(rast.cullMode).split(".")[-1],
                    "front_ccw": bool(rast.frontCCW),
                }
            except Exception:
                pass

        self.ctx.Replay().BlockInvoke(collect)
        return state

