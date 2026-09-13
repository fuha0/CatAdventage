class AnimationController:
    """Owns named Tk timer jobs so animation channels cancel deterministically."""

    def __init__(self, root, is_closing=None):
        self.root = root
        self._is_closing = is_closing or (lambda: False)
        self._jobs = {}

    def schedule(self, channel, delay_ms, callback, replace=True):
        if self._is_closing():
            return None
        if replace:
            self.cancel(channel)

        def run():
            self._jobs.pop(channel, None)
            if not self._is_closing():
                callback()

        token = self.root.after(max(0, int(delay_ms)), run)
        self._jobs[channel] = token
        return token

    def cancel(self, channel):
        token = self._jobs.pop(channel, None)
        if token is None:
            return False
        try:
            self.root.after_cancel(token)
        except Exception:
            pass
        return True

    def cancel_many(self, *channels):
        for channel in channels:
            self.cancel(channel)

    def cancel_all(self):
        for channel in tuple(self._jobs):
            self.cancel(channel)

    def has(self, channel):
        return channel in self._jobs

    def active_channels(self):
        return tuple(self._jobs)