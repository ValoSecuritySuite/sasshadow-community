"""ISPM (Integration Security Posture Management) API.

Read-only access to the default ISPM category catalog and the
provider -> category mapping.
"""

from fastapi import APIRouter, Request

from app.analysis.ispm_classifier import load_ispm_config
from app.core.limiter import limiter
from app.models.saas_map_models import (
    IspmCategoriesResponse,
    IspmProviderEntry,
    IspmProvidersResponse,
)

router = APIRouter(prefix="/ispm", tags=["ISPM"])


@router.get(
    "/categories",
    response_model=IspmCategoriesResponse,
    summary="Get the ISPM category catalog",
)
@limiter.limit("60/minute")
def get_categories(request: Request) -> IspmCategoriesResponse:
    config = load_ispm_config()
    return IspmCategoriesResponse(config=config, customer_id=None)


@router.get(
    "/providers",
    response_model=IspmProvidersResponse,
    summary="Get provider -> category mapping",
)
@limiter.limit("60/minute")
def get_providers(request: Request) -> IspmProvidersResponse:
    config = load_ispm_config()
    cat_labels = {c.id: c.label for c in config.categories}
    entries = [
        IspmProviderEntry(
            provider_id=provider_id,
            category_id=category_id,
            label=cat_labels.get(category_id, category_id.replace("_", " ").title()),
        )
        for provider_id, category_id in sorted(config.provider_map.items())
    ]
    return IspmProvidersResponse(providers=entries)
