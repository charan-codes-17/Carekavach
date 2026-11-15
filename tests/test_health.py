import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "carekavach"


@pytest.mark.asyncio
async def test_health_db_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "memory"
    assert data["write_read_delete"] == "ok"


@pytest.mark.asyncio
async def test_root_template_accessibility(async_client: AsyncClient) -> None:
    response = await async_client.get("/login")
    assert response.status_code == 200
    html = response.text

    # WCAG AA Landmarks and semantic structure
    assert '<html lang="en">' in html
    assert 'class="skip-link"' in html
    assert '<header role="banner"' in html
    assert '<main id="main-content" role="main"' in html
    assert '<footer role="contentinfo"' in html
    assert '<link rel="stylesheet" href="/static/css/styles.css">' in html
