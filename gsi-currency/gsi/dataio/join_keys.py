"""Registry-backed join keys, shared by orchestration callers."""
from .logging_setup import log
def _key_column(join_on: str):
    """نام ستون کلید از رجیستری ``config/keys.yaml``.

    برای کلید مرکب، فهرست ستون‌های اجزا برگردانده می‌شود تا safe_merge
    بتواند روی چند ستون هم‌زمان ادغام کند.
    """
    from ..config.keys import get_keys
    kr = get_keys()
    try:
        spec = kr.get(join_on)
    except KeyError:
        log.error(f"❌ کلید «{join_on}» در config/keys.yaml تعریف نشده است.")
        return None
    if spec.is_composite:
        return [kr.get(p).column if p in kr.keys else p for p in spec.parts]
    return spec.column

