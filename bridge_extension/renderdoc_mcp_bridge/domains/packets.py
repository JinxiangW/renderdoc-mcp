"""Packet-building services."""

import renderdoc as rd


class PacketServiceMixin:
    def _action_name(self, action):
        return action.customName or action.GetName(self.ctx.GetStructuredFile())

    @staticmethod
    def _is_marker_action(action):
        return action is not None and len(action.children) > 0

    def _compact_action_ref(self, action):
        if action is None:
            return None
        return {
            "eid": action.eventId,
            "name": self._action_name(action),
            "type": self._action_type(action),
        }

    def _find_action_path(self, actions, eid, path=None):
        path = path or []
        for action in actions:
            current = path + [action]
            if int(action.eventId) == int(eid):
                return current
            if len(action.children) > 0:
                found = self._find_action_path(action.children, eid, current)
                if found:
                    return found
        return None

    def _flatten_non_marker_actions(self, actions):
        items = []
        for action in actions:
            if self._is_marker_action(action):
                items.extend(self._flatten_non_marker_actions(action.children))
            else:
                items.append(action)
        return items

    def _pass_context_for_eid(self, eid):
        path = self._find_action_path(self.ctx.CurRootActions(), int(eid))
        if not path:
            return {
                "marker_path": "",
                "markers": [],
                "parent_pass": None,
                "root_pass": None,
                "position": {
                    "index": None,
                    "count": 0,
                    "draw_dispatch_index": None,
                    "draw_dispatch_count": 0,
                },
                "neighbors": {"prev": None, "next": None},
            }

        markers = [item for item in path[:-1] if self._is_marker_action(item)]
        marker_items = [{"eid": item.eventId, "name": self._action_name(item)} for item in markers]
        parent_marker = markers[-1] if markers else None
        root_marker = markers[0] if markers else None
        owner_actions = parent_marker.children if parent_marker is not None else self.ctx.CurRootActions()
        ordered = self._flatten_non_marker_actions(owner_actions)
        draw_dispatch = [item for item in ordered if self._action_type(item) in ("Draw", "Dispatch")]

        index = None
        prev_item = None
        next_item = None
        for idx, item in enumerate(ordered):
            if int(item.eventId) == int(eid):
                index = idx + 1
                if idx > 0:
                    prev_item = ordered[idx - 1]
                if idx + 1 < len(ordered):
                    next_item = ordered[idx + 1]
                break

        dd_index = None
        for idx, item in enumerate(draw_dispatch):
            if int(item.eventId) == int(eid):
                dd_index = idx + 1
                break

        return {
            "marker_path": " / ".join(item["name"] for item in marker_items if item.get("name")),
            "markers": marker_items,
            "parent_pass": (
                self._summarize_marker(self._action_name(parent_marker), parent_marker.eventId, parent_marker.children)
                if parent_marker is not None
                else None
            ),
            "root_pass": (
                self._summarize_marker(self._action_name(root_marker), root_marker.eventId, root_marker.children)
                if root_marker is not None
                else None
            ),
            "position": {
                "index": index,
                "count": len(ordered),
                "draw_dispatch_index": dd_index,
                "draw_dispatch_count": len(draw_dispatch),
            },
            "neighbors": {
                "prev": self._compact_action_ref(prev_item),
                "next": self._compact_action_ref(next_item),
            },
        }

    def get_frame_packet(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        limit = int(params.get("limit", 20) or 20)
        pass_summary = self._filtered_frame_passes(params, limit)
        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "api": str(self.ctx.APIProps().pipelineType),
                "path": self.ctx.GetCaptureFilename(),
                "passes": pass_summary["items"],
                "filters": pass_summary["filters"],
            },
            "err": None,
            "meta": {
                "cap": "active",
                "truncated": pass_summary["truncated"],
                "count": pass_summary["count"],
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
            "context": self._pass_context_for_eid(eid),
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

    def _filtered_frame_passes(self, params, limit):
        filters = {
            "pass_contains": (
                params.get("pass_name_contains")
                or params.get("pass_contains")
                or params.get("marker")
                or params.get("pass")
                or ""
            ),
            "draw_contains": params.get("draw_name_contains") or params.get("draw_contains") or "",
            "only_writes_to_resource": params.get("only_writes_to_resource"),
            "only_reads_resource": params.get("only_reads_resource"),
            "exclude_editor_only": bool(params.get("exclude_editor_only")),
        }
        pass_filter = str(filters["pass_contains"] or "").lower()
        draw_filter = str(filters["draw_contains"] or "").lower()
        write_events = self._usage_events_for_resource(filters["only_writes_to_resource"], "write")
        read_events = self._usage_events_for_resource(filters["only_reads_resource"], "read")

        matched = []

        def visit(actions, marker_stack):
            for action in actions:
                if len(action.children) > 0:
                    name = self._action_name(action)
                    marker_path = marker_stack + ([name] if name else [])
                    marker_text = " / ".join([item for item in marker_path if item])
                    marker_l = marker_text.lower()
                    if self._frame_pass_matches(
                        action,
                        marker_l,
                        pass_filter,
                        draw_filter,
                        write_events,
                        read_events,
                        filters["exclude_editor_only"],
                    ):
                        item = self._summarize_marker(name, action.eventId, action.children)
                        if marker_text and marker_text != name:
                            item["marker_path"] = marker_text
                        matched.append(item)

                    if visit(action.children, marker_path):
                        return True
            return False

        visit(self.ctx.CurRootActions(), [])
        return {
            "items": matched[:limit],
            "count": len(matched),
            "truncated": len(matched) > limit,
            "filters": {key: value for key, value in filters.items() if value},
        }

    def _frame_pass_matches(
        self,
        action,
        marker_l,
        pass_filter,
        draw_filter,
        write_events,
        read_events,
        exclude_editor_only,
    ):
        if pass_filter and pass_filter not in marker_l:
            return False
        if exclude_editor_only and self._is_editor_only_pass(marker_l):
            return False
        if draw_filter and not self._pass_has_draw_name(action, draw_filter):
            return False
        start, end = self._event_range(action)
        if write_events is not None and not any(start <= eid <= end for eid in write_events):
            return False
        if read_events is not None and not any(start <= eid <= end for eid in read_events):
            return False
        return True

    def _pass_has_draw_name(self, action, draw_filter):
        for child in self._flatten_non_marker_actions(action.children):
            try:
                name = self._action_name(child).lower()
            except Exception:
                name = ""
            if draw_filter in name:
                return True
        return False

    def _usage_events_for_resource(self, rid, kind):
        if not rid:
            return None
        rid_str = str(rid)
        events = []

        def collect(controller):
            target = None
            for tex in controller.GetTextures():
                if str(tex.resourceId) == rid_str:
                    target = tex.resourceId
                    break
            if target is None:
                try:
                    buffers = controller.GetBuffers()
                except Exception as exc:
                    self._warn_swallow("packets.frame_filters.get_buffers", exc)
                    buffers = []
                for buf in buffers:
                    if str(buf.resourceId) == rid_str:
                        target = buf.resourceId
                        break
            if target is None:
                return
            for use in controller.GetUsage(target):
                if self._usage_kind(str(use.usage)) == kind:
                    events.append(int(use.eventId))

        self.ctx.Replay().BlockInvoke(collect)
        return set(events)

    @staticmethod
    def _is_editor_only_pass(marker_l):
        editor_tokens = [
            "editorselectionoutlines",
            "compositeeditorprimitives",
            "gizmomaterial",
            "selectionoutline",
            "editor primitive",
            "editorprimitive",
        ]
        return any(token in marker_l for token in editor_tokens)

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
            "in_tex_meta": {
                "total_bindings": 0,
                "unique_resources": 0,
                "reported_resources": 0,
                "truncated": False,
                "cap": 8,
                "stage_bindings": {},
            },
            "out_rt": [],
            "out_rt_meta": {
                "total_resources": 0,
                "reported_resources": 0,
                "truncated": False,
                "cap": 8,
            },
            "out_uav": [],
            "out_uav_meta": {
                "total_bindings": 0,
                "unique_resources": 0,
                "reported_resources": 0,
                "truncated": False,
                "cap": 8,
                "stage_bindings": {},
            },
            "out_ds": None,
            "out_next": [],
            "out_next_meta": {
                "source_resources_considered": 0,
                "reported_uses": 0,
                "truncated": False,
                "resource_cap": 4,
                "use_cap": 8,
            },
        }
        eid = action.eventId

        def collect(controller):
            controller.SetFrameEvent(eid, True)
            pipe = controller.GetPipelineState()

            if kind == "Dispatch":
                stages = [("CS", rd.ShaderStage.Compute)]
            else:
                stages = [
                    ("VS", rd.ShaderStage.Vertex),
                    ("HS", rd.ShaderStage.Hull),
                    ("DS", rd.ShaderStage.Domain),
                    ("GS", rd.ShaderStage.Geometry),
                    ("PS", rd.ShaderStage.Pixel),
                ]

            input_map = {}
            out_rt_map = {}
            out_uav_map = {}
            out_rids = []

            for stage_name, stage in stages:
                stage_binding_count = 0
                try:
                    for srv in pipe.GetReadOnlyResources(stage, False):
                        stage_binding_count += 1
                        rid = srv.descriptor.resource
                        rid_str = str(rid)
                        if not rid_str or "Null" in rid_str or rid_str == "ResourceId::0":
                            continue
                        slot = int(getattr(srv.access, "index", -1) or -1)
                        entry = input_map.get(rid_str)
                        if entry is None:
                            entry = {
                                "rid": rid_str,
                                "name": self.ctx.GetResourceName(rid),
                                "meta": self._resource_meta(rid),
                                "stages": [],
                                "slots": [],
                            }
                            input_map[rid_str] = entry
                        if stage_name not in entry["stages"]:
                            entry["stages"].append(stage_name)
                        slot_ref = {"stage": stage_name, "slot": slot}
                        if slot_ref not in entry["slots"]:
                            entry["slots"].append(slot_ref)
                except Exception as exc:
                    self._warn_swallow("packets.event_io.read_only_resources", exc)
                packet["in_tex_meta"]["stage_bindings"][stage_name] = stage_binding_count
                packet["in_tex_meta"]["total_bindings"] += stage_binding_count

            try:
                if kind != "Dispatch":
                    for idx, rid in enumerate(action.outputs):
                        rid_str = str(rid)
                        if not rid_str or "Null" in rid_str or rid_str == "ResourceId::0":
                            continue
                        out_rids.append((rid, rid_str))
                        out_rt_map[rid_str] = {
                            "rid": rid_str,
                            "name": self.ctx.GetResourceName(rid),
                            "slot": idx,
                            "meta": self._resource_meta(rid),
                        }

                    rid = action.depthOut
                    rid_str = str(rid)
                    if rid_str and "Null" not in rid_str and rid_str != "ResourceId::0":
                        packet["out_ds"] = {
                            "rid": rid_str,
                            "name": self.ctx.GetResourceName(rid),
                            "meta": self._resource_meta(rid),
                        }

                    if not out_rt_map and packet["out_ds"] is None:
                        try:
                            outs = pipe.GetOutputTargets()
                            for idx, rt in enumerate(outs):
                                rid = getattr(rt, "resource", None)
                                rid_str = str(rid)
                                if not rid_str or "Null" in rid_str or rid_str == "ResourceId::0":
                                    continue
                                out_rt_map[rid_str] = {
                                    "rid": rid_str,
                                    "name": self.ctx.GetResourceName(rid),
                                    "slot": idx,
                                    "meta": self._resource_meta(rid),
                                }
                                out_rids.append((rid, rid_str))
                        except Exception as exc:
                            self._warn_swallow("packets.event_io.output_targets", exc)
            except Exception as exc:
                self._warn_swallow("packets.event_io.outputs", exc)

            uav_stages = [("CS", rd.ShaderStage.Compute)] if kind == "Dispatch" else [("PS", rd.ShaderStage.Pixel)]
            for stage_name, stage in uav_stages:
                stage_binding_count = 0
                try:
                    for uav in pipe.GetReadWriteResources(stage, False):
                        stage_binding_count += 1
                        rid = uav.descriptor.resource
                        rid_str = str(rid)
                        if not rid_str or "Null" in rid_str or rid_str == "ResourceId::0":
                            continue
                        slot = int(getattr(uav.access, "index", -1) or -1)
                        entry = out_uav_map.get(rid_str)
                        if entry is None:
                            entry = {
                                "rid": rid_str,
                                "name": self.ctx.GetResourceName(rid),
                                "meta": self._resource_meta(rid),
                                "stages": [],
                                "slots": [],
                            }
                            out_uav_map[rid_str] = entry
                            out_rids.append((rid, rid_str))
                        if stage_name not in entry["stages"]:
                            entry["stages"].append(stage_name)
                        slot_ref = {"stage": stage_name, "slot": slot}
                        if slot_ref not in entry["slots"]:
                            entry["slots"].append(slot_ref)
                except Exception as exc:
                    self._warn_swallow("packets.event_io.read_write_resources", exc)
                packet["out_uav_meta"]["stage_bindings"][stage_name] = stage_binding_count
                packet["out_uav_meta"]["total_bindings"] += stage_binding_count

            in_items = list(input_map.values())
            out_rt_items = list(out_rt_map.values())
            out_uav_items = list(out_uav_map.values())

            packet["in_tex_meta"]["unique_resources"] = len(in_items)
            packet["in_tex_meta"]["reported_resources"] = min(len(in_items), packet["in_tex_meta"]["cap"])
            packet["in_tex_meta"]["truncated"] = len(in_items) > packet["in_tex_meta"]["cap"]
            packet["out_rt_meta"]["total_resources"] = len(out_rt_items)
            packet["out_rt_meta"]["reported_resources"] = min(len(out_rt_items), packet["out_rt_meta"]["cap"])
            packet["out_rt_meta"]["truncated"] = len(out_rt_items) > packet["out_rt_meta"]["cap"]
            packet["out_uav_meta"]["unique_resources"] = len(out_uav_items)
            packet["out_uav_meta"]["reported_resources"] = min(len(out_uav_items), packet["out_uav_meta"]["cap"])
            packet["out_uav_meta"]["truncated"] = len(out_uav_items) > packet["out_uav_meta"]["cap"]

            packet["in_tex"] = in_items[: packet["in_tex_meta"]["cap"]]
            packet["out_rt"] = out_rt_items[: packet["out_rt_meta"]["cap"]]
            packet["out_uav"] = out_uav_items[: packet["out_uav_meta"]["cap"]]

            downstream = []
            unique_out_rids = []
            seen_out_rids = set()
            for rid, rid_str in out_rids:
                if rid_str in seen_out_rids:
                    continue
                seen_out_rids.add(rid_str)
                unique_out_rids.append((rid, rid_str))
            packet["out_next_meta"]["source_resources_considered"] = min(
                len(unique_out_rids), packet["out_next_meta"]["resource_cap"]
            )
            packet["out_next_meta"]["truncated"] = len(unique_out_rids) > packet["out_next_meta"]["resource_cap"]
            for rid, rid_str in unique_out_rids[: packet["out_next_meta"]["resource_cap"]]:
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
                    if len(downstream) >= packet["out_next_meta"]["use_cap"]:
                        break
                if len(downstream) >= packet["out_next_meta"]["use_cap"]:
                    break

            packet["out_next"] = downstream
            packet["out_next_meta"]["reported_uses"] = len(downstream)
            if len(downstream) >= packet["out_next_meta"]["use_cap"]:
                packet["out_next_meta"]["truncated"] = True

        self.ctx.Replay().BlockInvoke(collect)
        for item in packet["out_next"]:
            use_action = self.ctx.GetAction(int(item.get("eid", 0) or 0))
            if use_action is None:
                continue
            item["name"] = self._action_name(use_action)
            item["type"] = self._action_type(use_action)
            ctx = self._pass_context_for_eid(use_action.eventId)
            root_pass = ctx.get("root_pass") or {}
            parent_pass = ctx.get("parent_pass") or {}
            item["pass"] = root_pass.get("pass") or parent_pass.get("pass") or ctx.get("marker_path") or None
        return packet

    def _fixed_function_state(self, eid):
        state = {
            "api": str(self.ctx.APIProps().pipelineType),
            "source_api": "D3D11",
            "limited_to_source_api": False,
            "blend": None,
            "depth": None,
            "rast": None,
        }

        def collect(controller):
            controller.SetFrameEvent(eid, True)
            if "D3D11" not in state["api"]:
                state["limited_to_source_api"] = True
                return
            try:
                d3d11 = controller.GetD3D11PipelineState()
            except Exception as exc:
                state["limited_to_source_api"] = True
                self._warn_swallow("packets.fixed_function_state.get_d3d11_pipeline_state", exc)
                return
            if d3d11 is None:
                state["limited_to_source_api"] = True
                return

            try:
                om = d3d11.outputMerger
                bs = om.blendState
                targets = []
                try:
                    for idx, blend in enumerate(bs.blends):
                        targets.append(
                            {
                                "slot": idx,
                                "enabled": bool(blend.enabled),
                                "logic_enabled": bool(blend.logicOperationEnabled),
                                "logic_op": str(blend.logicOperation).split(".")[-1],
                                "color": {
                                    "src": str(blend.colorBlend.source).split(".")[-1],
                                    "dst": str(blend.colorBlend.destination).split(".")[-1],
                                    "op": str(blend.colorBlend.operation).split(".")[-1],
                                },
                                "alpha": {
                                    "src": str(blend.alphaBlend.source).split(".")[-1],
                                    "dst": str(blend.alphaBlend.destination).split(".")[-1],
                                    "op": str(blend.alphaBlend.operation).split(".")[-1],
                                },
                                "write_mask": int(getattr(blend, "writeMask", 0) or 0),
                            }
                        )
                except Exception as exc:
                    self._warn_swallow("packets.fixed_function_state.blend_targets", exc)
                    targets = []
                state["blend"] = {
                    "alpha_to_coverage": bool(bs.alphaToCoverage),
                    "independent_blend": bool(bs.independentBlend),
                    "targets": targets,
                }
            except Exception as exc:
                self._warn_swallow("packets.fixed_function_state.blend_state", exc)

            try:
                om = d3d11.outputMerger
                ds = om.depthStencilState
                state["depth"] = {
                    "enabled": bool(ds.depthEnable),
                    "func": str(ds.depthFunction).split(".")[-1],
                    "write": bool(ds.depthWrites),
                }
            except Exception as exc:
                self._warn_swallow("packets.fixed_function_state.depth_state", exc)

            try:
                rast = d3d11.rasterizer.state
                state["rast"] = {
                    "fill": str(rast.fillMode).split(".")[-1],
                    "cull": str(rast.cullMode).split(".")[-1],
                    "front_ccw": bool(rast.frontCCW),
                }
            except Exception as exc:
                self._warn_swallow("packets.fixed_function_state.rasterizer_state", exc)

        self.ctx.Replay().BlockInvoke(collect)
        return state
