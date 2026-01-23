from __future__ import annotations

from main import create_app


def test_openapi_operation_ids_unique():
    app = create_app()
    schema = app.openapi()
    seen = set()
    dupes = set()
    for path_item in schema.get("paths", {}).values():
        for method_item in path_item.values():
            if not isinstance(method_item, dict):
                continue
            op_id = method_item.get("operationId")
            if not op_id:
                continue
            if op_id in seen:
                dupes.add(op_id)
            seen.add(op_id)
    assert not dupes, f"Duplicate operationIds: {sorted(dupes)}"
