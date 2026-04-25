"""FR-F4.3: POST/PATCH/DELETE/activate routes are gone."""

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/v1/reading-presets"),
        ("patch", "/api/v1/reading-presets/1"),
        ("delete", "/api/v1/reading-presets/1"),
        ("post", "/api/v1/reading-presets/1/activate"),
    ],
)
async def test_mutation_routes_are_gone(client, method, path):
    if method == "post":
        resp = await client.post(path, json={})
    elif method == "patch":
        resp = await client.patch(path, json={})
    elif method == "delete":
        resp = await client.delete(path)
    else:
        raise AssertionError(method)
    assert resp.status_code in (404, 405), (
        f"{method.upper()} {path} returned {resp.status_code}"
    )
