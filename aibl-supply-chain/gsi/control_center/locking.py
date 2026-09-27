"""Configuration lock using only the standard library (no encryption dependency)."""
import contextlib
import math
import os
import secrets
import time
from pathlib import Path

class FileLock:
    def __init__(self, path, timeout=2):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('مهلت قفل باید مثبت باشد.')
        self.path=Path(path);self.timeout=timeout;self.token=secrets.token_bytes(24);self.fd=None
    def __enter__(self):
        start=time.monotonic();self.path.parent.mkdir(parents=True,exist_ok=True)
        while True:
            try:
                self.fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                break
            except FileExistsError:
                if time.monotonic()-start>=self.timeout:
                    raise ValueError('تنظیمات قفل است؛ ابتدا پایان کار نشست دیگر را بررسی کنید.')
                time.sleep(.05)
        try:
            os.write(self.fd,self.token);os.fsync(self.fd)
        except OSError:
            os.close(self.fd);self.fd=None
            with contextlib.suppress(OSError):self.path.unlink()
            raise
        return self
    def __exit__(self,*args):
        if self.fd is not None:os.close(self.fd);self.fd=None
        with contextlib.suppress(OSError):
            if self.path.read_bytes()==self.token:self.path.unlink()
