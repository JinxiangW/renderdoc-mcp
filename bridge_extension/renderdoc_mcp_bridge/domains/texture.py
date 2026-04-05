"""Texture inspection services."""


class TextureServiceMixin:
    def inspect_texture_usage(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        rid = params.get("rid")
        name_filter = params.get("name")
        limit = int(params.get("limit", 10) or 10)
        result = None

        def collect(controller):
            nonlocal result
            tex = self._select_texture(controller, rid, name_filter)
            if tex is None:
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "texture_not_found", "msg": "Texture not found"},
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            tex_rid = tex.resourceId
            usage_items = controller.GetUsage(tex_rid)
            items = []
            reads = 0
            writes = 0
            producer = None
            first_read = None
            first_ps_read = None
            first_non_compute_read = None
            last_write = None

            def pass_name_for(action):
                return self._parent_pass_name(action) or self._find_top_level_pass_for_eid(action.eventId)

            def make_info(use, action, usage_name):
                return {
                    "eid": use.eventId,
                    "usage": usage_name.split(".")[-1],
                    "name": action.customName or action.GetName(self.ctx.GetStructuredFile()),
                    "pass": pass_name_for(action),
                }

            def ctx_for_event(eid_local):
                contexts = []
                controller.SetFrameEvent(eid_local, True)
                pipe = controller.GetPipelineState()
                rid_str = str(tex_rid)

                def add_ctx(role, stage, slot, name=""):
                    contexts.append({"role": role, "stage": stage, "slot": slot, "name": name})

                stages = self._binding_stages()

                for stage_name, stage_enum in stages:
                    refl = None
                    try:
                        refl = pipe.GetShaderReflection(stage_enum)
                    except Exception:
                        refl = None

                    def bind_name(category, slot):
                        try:
                            if not refl:
                                return ""
                            if category == "SRV":
                                for res in refl.readOnlyResources:
                                    if int(res.fixedBindNumber) == int(slot):
                                        return res.name
                            if category == "UAV":
                                for res in refl.readWriteResources:
                                    if int(res.fixedBindNumber) == int(slot):
                                        return res.name
                        except Exception:
                            pass
                        return ""

                    try:
                        for srv in pipe.GetReadOnlyResources(stage_enum, False):
                            if str(srv.descriptor.resource) == rid_str:
                                add_ctx("SRV", stage_name, int(srv.access.index), bind_name("SRV", int(srv.access.index)))
                    except Exception:
                        pass
                    try:
                        for uav in pipe.GetReadWriteResources(stage_enum, False):
                            if str(uav.descriptor.resource) == rid_str:
                                add_ctx("UAV", stage_name, int(uav.access.index), bind_name("UAV", int(uav.access.index)))
                    except Exception:
                        pass
                try:
                    for idx, out in enumerate(pipe.GetOutputTargets()):
                        res = getattr(out, "resource", None)
                        if str(res) == rid_str:
                            add_ctx("RT", "OM", idx)
                except Exception:
                    pass
                try:
                    ds = pipe.GetDepthTarget()
                    res = getattr(ds, "resource", None)
                    if str(res) == rid_str:
                        add_ctx("DS", "OM", 0)
                except Exception:
                    pass
                return contexts

            for use in usage_items:
                usage_name = str(use.usage)
                rw_type = self._usage_kind(usage_name)
                if rw_type == "read":
                    reads += 1
                elif rw_type == "write":
                    writes += 1

                action = self.ctx.GetAction(use.eventId)
                action_name = ""
                if action is not None:
                    try:
                        action_name = action.customName or action.GetName(self.ctx.GetStructuredFile())
                    except Exception:
                        action_name = action.customName or ""

                items.append(
                    {
                        "eid": use.eventId,
                        "type": rw_type,
                        "usage": usage_name.split(".")[-1],
                        "name": action_name,
                    }
                )

                if action is None:
                    continue

                if rw_type == "write":
                    last_write = make_info(use, action, usage_name)
                    if producer is None:
                        producer = last_write
                elif rw_type == "read":
                    if first_read is None:
                        first_read = make_info(use, action, usage_name)
                    if first_ps_read is None and usage_name.split(".")[-1].startswith("PS_"):
                        first_ps_read = make_info(use, action, usage_name)
                    if first_non_compute_read is None and "Dispatch" not in action_name:
                        first_non_compute_read = make_info(use, action, usage_name)

            items.sort(key=lambda item: item["eid"])
            truncated = len(items) > limit
            items = items[:limit]

            first_read_ctx = ctx_for_event(first_read["eid"]) if first_read else []
            first_ps_read_ctx = ctx_for_event(first_ps_read["eid"]) if first_ps_read else []
            first_non_compute_read_ctx = (
                ctx_for_event(first_non_compute_read["eid"]) if first_non_compute_read else []
            )

            result = {
                "ok": True,
                "mode": "summary",
                "data": {
                    "rid": str(tex_rid),
                    "name": self.ctx.GetResourceName(tex_rid),
                    "meta": self._resource_meta(tex_rid),
                    "producer": producer,
                    "last_write": last_write,
                    "first_read": first_read,
                    "first_ps_read": first_ps_read,
                    "first_read_ctx": first_read_ctx,
                    "first_ps_read_ctx": first_ps_read_ctx,
                    "first_non_compute_read": first_non_compute_read,
                    "first_non_compute_read_ctx": first_non_compute_read_ctx,
                    "uses": {
                        "read": reads,
                        "write": writes,
                    },
                    "items": items,
                },
                "err": None,
                "meta": {
                    "cap": "active",
                    "truncated": truncated,
                    "count": len(usage_items),
                },
            }

        self.ctx.Replay().BlockInvoke(collect)
        return result

    @staticmethod
    def _select_texture(controller, rid, name_filter):
        textures = controller.GetTextures()
        if rid:
            rid_str = str(rid)
            for tex in textures:
                if str(tex.resourceId) == rid_str:
                    return tex
        if name_filter:
            name_l = str(name_filter).lower()
            for tex in textures:
                if name_l in str(tex.resourceId).lower():
                    return tex
        for tex in textures:
            rid_str = str(tex.resourceId)
            if rid_str and "Null" not in rid_str and rid_str != "ResourceId::0":
                return tex
        return None

