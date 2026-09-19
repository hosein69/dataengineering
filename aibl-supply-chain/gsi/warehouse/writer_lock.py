"""OS advisory lock on local disk; released by the OS even after process termination."""
import os,time
class WriterLock:
    def __init__(self,path,timeout=5):self.path=path;self.timeout=timeout;self.file=None
    def __enter__(self):
        self.file=open(self.path,'a+b')
        if self.file.seek(0,2)==0:self.file.write(b'0');self.file.flush()
        start=time.monotonic()
        while True:
            try:
                self.file.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic()-start>=self.timeout:
                    self.file.close();raise TimeoutError('یک ورود داده یا اجرای خط لوله دیگر فعال است؛ پس از پایان آن دوباره تلاش کنید.')
                time.sleep(.05)
    def __exit__(self,*args):
        try:
            self.file.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_UN)
        finally:self.file.close()
