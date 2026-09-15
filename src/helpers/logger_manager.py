import logging

class LoggerManager:
    def __init__(self, log_enabled=True):
        self._log_enabled = log_enabled
        self._configure_logging()

    def _configure_logging(self):
        """Configure the logging based on the log_enabled flag."""
        if self._log_enabled:
            logging.basicConfig(level=logging.INFO)  # Change to DEBUG for detailed logs
        else:
            logging.disable(logging.CRITICAL)  # Disables all logging

    def enable_logging(self):
        """Enable logging."""
        self._log_enabled = True
        self._configure_logging()

    def disable_logging(self):
        """Disable logging."""
        self._log_enabled = False
        self._configure_logging()

    def log(self, level, message, *args, **kwargs):
        """Log a message if logging is enabled."""
        if self._log_enabled:
            if level == 'info':
                logging.info(message, *args, **kwargs)
            elif level == 'warning':
                logging.warning(message, *args, **kwargs)
            elif level == 'error':
                logging.error(message, *args, **kwargs)
            elif level == 'critical':
                logging.critical(message, *args, **kwargs)
