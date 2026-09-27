# -*- coding: utf-8 -*-
"""GSI Personal Intelligence persistence.

File-share first, encrypted-at-rest persistence. No HTTP/IP transport is used.
"""
from .identity import resolve_employee_code
from .store import (
    EncryptedUserStore,
    ProfileStoreError,
    ProfileConfigurationError,
    ProfileIntegrityError,
    generate_master_key,
    derive_user_key,
    derive_user_key_text,
)
from .service import PersonalWorkspace

__all__ = [
    "resolve_employee_code",
    "EncryptedUserStore",
    "PersonalWorkspace",
    "ProfileStoreError",
    "ProfileConfigurationError",
    "ProfileIntegrityError",
    "generate_master_key",
    "derive_user_key",
    "derive_user_key_text",
]
