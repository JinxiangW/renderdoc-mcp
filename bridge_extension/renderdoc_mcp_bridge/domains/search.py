"""Event and pass discovery services."""


class EventSearchMixin:
    def run(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        query = (params.get("q") or "").lower()
        marker_filter = (params.get("marker") or "").lower()
        exclude_markers = [m.lower() for m in params.get("exclude_markers", [])]
        eid_min = int(params.get("eid_min", 0) or 0)
        eid_max = int(params.get("eid_max", 0) or 0)
        limit = int(params.get("limit", 50) or 50)

        items = []

        def visit(actions, marker_stack):
            for action in actions:
                current_markers = marker_stack
                if action.flags == 0 and len(action.children) > 0:
                    current_markers = marker_stack + [action.customName]

                marker_path = " / ".join([m for m in current_markers if m])
                name = action.customName or action.GetName(self.ctx.GetStructuredFile())

                if self._matches(
                    action.eventId,
                    name,
                    marker_path,
                    query,
                    marker_filter,
                    exclude_markers,
                    eid_min,
                    eid_max,
                ):
                    items.append(
                        {
                            "eid": action.eventId,
                            "name": name,
                            "type": self._action_type(action),
                            "marker": marker_path,
                        }
                    )
                    if len(items) >= limit:
                        return True

                if len(action.children) > 0:
                    stop = visit(action.children, current_markers)
                    if stop:
                        return True

            return False

        visit(self.ctx.CurRootActions(), [])

        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "count": len(items),
                "items": items,
            },
            "err": None,
            "meta": {
                "cap": "active",
                "truncated": len(items) >= limit,
                "count": len(items),
            },
        }

    def list_passes(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        marker_filter = (params.get("marker") or params.get("pass") or "").lower()
        limit = int(params.get("limit", 50) or 50)
        markers = []

        def visit(actions, marker_stack):
            for action in actions:
                if len(action.children) > 0:
                    name = action.customName or action.GetName(self.ctx.GetStructuredFile())
                    marker_path = marker_stack + ([name] if name else [])
                    marker_l = " / ".join([m for m in marker_path if m]).lower()
                    if name and (not marker_filter or marker_filter in marker_l):
                        markers.append((name, action.eventId, action.children))
                        if len(markers) >= limit:
                            return True

                    if visit(action.children, marker_path):
                        return True

            return False

        visit(self.ctx.CurRootActions(), [])
        items = [self._summarize_marker(name, eid, children) for name, eid, children in markers]

        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "count": len(items),
                "items": items,
            },
            "err": None,
            "meta": {
                "cap": "active",
                "truncated": len(items) >= limit,
                "count": len(items),
            },
        }

    @staticmethod
    def _matches(event_id, name, marker_path, query, marker_filter, exclude_markers, eid_min, eid_max):
        if eid_min and event_id < eid_min:
            return False
        if eid_max and event_id > eid_max:
            return False

        marker_l = marker_path.lower()
        name_l = (name or "").lower()

        if query and query not in name_l and query not in marker_l:
            return False
        if marker_filter and marker_filter not in marker_l:
            return False
        for text in exclude_markers:
            if text and text in marker_l:
                return False
        return True

    @staticmethod
    def _action_type(action):
        flags = str(action.flags)
        if "Dispatch" in flags:
            return "Dispatch"
        if "Drawcall" in flags or "Draw" in flags:
            return "Draw"
        if len(action.children) > 0 and action.flags == 0:
            return "Marker"
        return "Action"

    def _summarize_marker(self, name, eid, children):
        stats = {
            "draw": 0,
            "dispatch": 0,
            "copy": 0,
            "clear": 0,
            "action": 0,
            "child": 0,
        }

        def count(actions):
            for action in actions:
                stats["child"] += 1
                kind = self._action_type(action)
                if kind == "Draw":
                    stats["draw"] += 1
                elif kind == "Dispatch":
                    stats["dispatch"] += 1
                else:
                    flags = str(action.flags)
                    if "Copy" in flags:
                        stats["copy"] += 1
                    elif "Clear" in flags:
                        stats["clear"] += 1
                    else:
                        stats["action"] += 1

                if len(action.children) > 0:
                    count(action.children)

        count(children)

        return {
            "eid": eid,
            "pass": name,
            "stats": stats,
        }

