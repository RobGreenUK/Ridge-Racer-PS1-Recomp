"""Optional macOS stack sampler; never enabled by an ordinary launcher run."""
import subprocess
import warnings


class PresentationProfile:
    def __init__(self, pid, directory):
        self.report = directory / 'presentation-stacks.txt'
        self.log = (directory / 'presentation-sample.log').open('w')
        try:
            self.process = subprocess.Popen(
                ['/usr/bin/sample', str(pid), '600', '1', '-mayDie', '-file', str(self.report)],
                stdout=self.log, stderr=self.log)
        except Exception:
            self.log.close()
            raise

    def close(self):
        # Called after the owned viewer exits. sample writes its report on exit
        # of the target, or after ten minutes if the race is still running.
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        finally:
            self.log.close()
        if self.process.returncode != 0 or not self.report.is_file() or not self.report.stat().st_size:
            warnings.warn(f'Presentation stack sampling failed; see {self.log.name}. Frame timings remain available.')
