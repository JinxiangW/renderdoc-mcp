"""Shared resource and hierarchy helpers for live bridge services."""


class ResourceSupportMixin:
    def _resource_meta(self, rid):
        tex = self.ctx.GetTexture(rid)
        if tex is not None:
            return {
                "kind": "tex",
                "fmt": str(tex.format.Name()),
                "dims": [int(tex.width), int(tex.height), int(tex.depth)],
                "arr": int(tex.arraysize),
                "ms": int(tex.msSamp),
            }

        buf = self.ctx.GetBuffer(rid)
        if buf is not None:
            return {
                "kind": "buf",
                "size": int(buf.length),
            }

        return None

    def _first_consumers(self, rid, after_eid, limit):
        consumers = []

        def collect(controller):
            usage_items = controller.GetUsage(rid)
            for use in usage_items:
                if use.eventId <= after_eid:
                    continue

                action = self.ctx.GetAction(use.eventId)
                if action is None:
                    continue

                consumers.append(
                    {
                        "eid": use.eventId,
                        "usage": str(use.usage).split(".")[-1],
                        "name": action.customName or action.GetName(self.ctx.GetStructuredFile()),
                        "pass": self._parent_pass_name(action) or self._find_top_level_pass_for_eid(use.eventId),
                    }
                )

                if len(consumers) >= limit:
                    break

        self.ctx.Replay().BlockInvoke(collect)
        return consumers

    def _first_read_info(self, rid, after_eid):
        info = None

        def collect(controller):
            nonlocal info
            usage_items = controller.GetUsage(rid)
            for use in usage_items:
                if use.eventId <= after_eid:
                    continue
                usage_name = str(use.usage)
                if self._usage_kind(usage_name) != "read":
                    continue
                action = self.ctx.GetAction(use.eventId)
                if action is None:
                    continue
                info = {
                    "eid": use.eventId,
                    "usage": usage_name.split(".")[-1],
                    "name": action.customName or action.GetName(self.ctx.GetStructuredFile()),
                    "pass": self._parent_pass_name(action) or self._find_top_level_pass_for_eid(use.eventId),
                }
                break

        self.ctx.Replay().BlockInvoke(collect)
        return info

    def _first_stage_read_info(self, rid, after_eid, prefix):
        info = None

        def collect(controller):
            nonlocal info
            usage_items = controller.GetUsage(rid)
            for use in usage_items:
                if use.eventId <= after_eid:
                    continue
                usage_name = str(use.usage).split(".")[-1]
                if not usage_name.startswith(prefix):
                    continue
                action = self.ctx.GetAction(use.eventId)
                if action is None:
                    continue
                info = {
                    "eid": use.eventId,
                    "usage": usage_name,
                    "name": action.customName or action.GetName(self.ctx.GetStructuredFile()),
                    "pass": self._parent_pass_name(action) or self._find_top_level_pass_for_eid(use.eventId),
                }
                break

        self.ctx.Replay().BlockInvoke(collect)
        return info

    def _first_non_compute_read_info(self, rid, after_eid):
        info = None

        def collect(controller):
            nonlocal info
            usage_items = controller.GetUsage(rid)
            for use in usage_items:
                if use.eventId <= after_eid:
                    continue
                usage_name = str(use.usage)
                if self._usage_kind(usage_name) != "read":
                    continue
                action = self.ctx.GetAction(use.eventId)
                if action is None:
                    continue
                name = action.customName or action.GetName(self.ctx.GetStructuredFile())
                if "Dispatch" in name:
                    continue
                info = {
                    "eid": use.eventId,
                    "usage": usage_name.split(".")[-1],
                    "name": name,
                    "pass": self._parent_pass_name(action) or self._find_top_level_pass_for_eid(use.eventId),
                }
                break

        self.ctx.Replay().BlockInvoke(collect)
        return info

    def _producer_info(self, rid, upto_eid):
        info = None

        def collect(controller):
            nonlocal info
            usage_items = controller.GetUsage(rid)
            for use in usage_items:
                if use.eventId > upto_eid:
                    continue
                usage_name = str(use.usage)
                if self._usage_kind(usage_name) != "write":
                    continue
                action = self.ctx.GetAction(use.eventId)
                if action is None:
                    continue
                info = {
                    "eid": use.eventId,
                    "usage": usage_name.split(".")[-1],
                    "name": action.customName or action.GetName(self.ctx.GetStructuredFile()),
                    "pass": self._parent_pass_name(action) or self._find_top_level_pass_for_eid(use.eventId),
                }

        self.ctx.Replay().BlockInvoke(collect)
        return info

    def _last_write_info(self, rid):
        info = None

        def collect(controller):
            nonlocal info
            usage_items = controller.GetUsage(rid)
            for use in usage_items:
                usage_name = str(use.usage)
                if self._usage_kind(usage_name) != "write":
                    continue
                action = self.ctx.GetAction(use.eventId)
                if action is None:
                    continue
                info = {
                    "eid": use.eventId,
                    "usage": usage_name.split(".")[-1],
                    "name": action.customName or action.GetName(self.ctx.GetStructuredFile()),
                    "pass": self._parent_pass_name(action) or self._find_top_level_pass_for_eid(use.eventId),
                }

        self.ctx.Replay().BlockInvoke(collect)
        return info

    def _binding_context_for_event(self, rid, eid):
        if eid is None:
            return []

        contexts = []

        def collect(controller):
            controller.SetFrameEvent(eid, True)
            pipe = controller.GetPipelineState()
            rid_str = str(rid)

            def add_ctx(role, stage, slot, name=""):
                contexts.append(
                    {
                        "role": role,
                        "stage": stage,
                        "slot": slot,
                        "name": name,
                    }
                )

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
                            add_ctx("SRV", stage_name, int(srv.access.index))
                            contexts[-1]["name"] = bind_name("SRV", int(srv.access.index))
                except Exception:
                    pass
                try:
                    for uav in pipe.GetReadWriteResources(stage_enum, False):
                        if str(uav.descriptor.resource) == rid_str:
                            add_ctx("UAV", stage_name, int(uav.access.index))
                            contexts[-1]["name"] = bind_name("UAV", int(uav.access.index))
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

        self.ctx.Replay().BlockInvoke(collect)
        return contexts

    @staticmethod
    def _parent_pass_name(action):
        parent = action.parent
        while parent is not None:
            try:
                name = parent.customName or ""
            except Exception:
                name = ""
            if name:
                return name
            parent = parent.parent
        return ""

    @staticmethod
    def _max_descendant_eid(action):
        max_eid = 0

        def visit(node):
            nonlocal max_eid
            if node.eventId > max_eid:
                max_eid = node.eventId
            for child in node.children:
                visit(child)

        for child in action.children:
            visit(child)

        if max_eid == 0:
            max_eid = action.eventId

        return max_eid

    def _find_top_level_pass_for_eid(self, eid):
        for root in self.ctx.CurRootActions():
            name = root.customName or root.GetName(self.ctx.GetStructuredFile())
            if not name:
                continue
            start, end = self._event_range(root)
            if start <= eid <= end:
                return name
        return ""

    @staticmethod
    def _event_range(action):
        min_eid = action.eventId
        max_eid = action.eventId

        def visit(node):
            nonlocal min_eid, max_eid
            if node.eventId < min_eid:
                min_eid = node.eventId
            if node.eventId > max_eid:
                max_eid = node.eventId
            for child in node.children:
                visit(child)

        visit(action)
        return min_eid, max_eid

    @staticmethod
    def _usage_kind(usage_name):
        write_tokens = [
            "RWResource",
            "ColorTarget",
            "DepthStencilTarget",
            "CopyDst",
            "ResolveDst",
            "Clear",
            "Discard",
            "CPUWrite",
            "GenMips",
            "StreamOut",
        ]
        read_tokens = [
            "Resource",
            "Constants",
            "VertexBuffer",
            "IndexBuffer",
            "Indirect",
            "InputTarget",
            "CopySrc",
            "ResolveSrc",
        ]
        for token in write_tokens:
            if token in usage_name:
                return "write"
        for token in read_tokens:
            if token in usage_name:
                return "read"
        return "other"

