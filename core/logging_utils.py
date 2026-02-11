"""Structured logging utilities for production debugging."""

import logging
import time
import uuid
from typing import Optional, Dict, Any
from contextlib import contextmanager


class StructuredLogger:
    """Provides structured logging with context for production debugging."""

    def __init__(self, logger_name: str):
        """
        Initialize structured logger.

        Args:
            logger_name: Name of the logger (typically module name)
        """
        self.logger = logging.getLogger(logger_name)
        self.correlation_id = str(uuid.uuid4())[:8]

    def _build_context(
        self,
        operation: str,
        show_name: Optional[str] = None,
        source: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Build structured context for logging.

        Args:
            operation: Operation being performed
            show_name: Name of the show being processed
            source: Source/scraper name
            **kwargs: Additional context fields

        Returns:
            Dictionary of context fields
        """
        context = {
            "correlation_id": self.correlation_id,
            "operation": operation,
        }

        if show_name:
            context["show_name"] = show_name
        if source:
            context["source"] = source

        context.update(kwargs)
        return context

    def _format_message(self, message: str, context: Dict[str, Any]) -> str:
        """
        Format log message with context.

        Args:
            message: Base log message
            context: Context dictionary

        Returns:
            Formatted message string
        """
        context_str = " | ".join(f"{k}={v}" for k, v in context.items())
        return f"{message} | {context_str}"

    def log_scraper_attempt(
        self,
        source: str,
        show_name: str,
        started: bool = True
    ) -> None:
        """
        Log scraper attempt.

        Args:
            source: Scraper source name
            show_name: Show being searched
            started: True if starting attempt, False if completed
        """
        context = self._build_context(
            operation="scraper_attempt",
            show_name=show_name,
            source=source,
            phase="started" if started else "completed"
        )
        message = f"{'Starting' if started else 'Completed'} scraper attempt"
        self.logger.info(self._format_message(message, context))

    def log_scraper_result(
        self,
        source: str,
        show_name: str,
        success: bool,
        duration: float,
        error: Optional[str] = None
    ) -> None:
        """
        Log scraper result with timing.

        Args:
            source: Scraper source name
            show_name: Show that was searched
            success: Whether the scraper succeeded
            duration: Duration in seconds
            error: Error message if failed
        """
        context = self._build_context(
            operation="scraper_result",
            show_name=show_name,
            source=source,
            success=success,
            duration_sec=f"{duration:.2f}"
        )

        if error:
            context["error"] = error

        message = f"Scraper {'succeeded' if success else 'failed'}"
        log_func = self.logger.info if success else self.logger.warning
        log_func(self._format_message(message, context))

    def log_download(
        self,
        source: str,
        show_name: str,
        file_size: int,
        duration: float,
        file_path: str
    ) -> None:
        """
        Log successful download with details.

        Args:
            source: Source that provided the download
            show_name: Show that was downloaded
            file_size: Size of downloaded file in bytes
            duration: Download duration in seconds
            file_path: Path to downloaded file
        """
        context = self._build_context(
            operation="download",
            show_name=show_name,
            source=source,
            file_size_bytes=file_size,
            file_size_mb=f"{file_size / 1_000_000:.2f}",
            duration_sec=f"{duration:.2f}",
            file_path=file_path
        )
        message = "Download completed successfully"
        self.logger.info(self._format_message(message, context))

    def log_conversion(
        self,
        show_name: str,
        input_format: str,
        output_format: str,
        duration: float,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Log audio conversion operation.

        Args:
            show_name: Show being processed
            input_format: Input file format
            output_format: Output file format
            duration: Conversion duration in seconds
            success: Whether conversion succeeded
            error: Error message if failed
        """
        context = self._build_context(
            operation="audio_conversion",
            show_name=show_name,
            input_format=input_format,
            output_format=output_format,
            duration_sec=f"{duration:.2f}",
            success=success
        )

        if error:
            context["error"] = error

        message = f"Audio conversion {'succeeded' if success else 'failed'}"
        log_func = self.logger.info if success else self.logger.error
        log_func(self._format_message(message, context))

    def log_error(
        self,
        operation: str,
        error: str,
        show_name: Optional[str] = None,
        source: Optional[str] = None,
        exc_info: bool = False,
        **kwargs
    ) -> None:
        """
        Log error with context.

        Args:
            operation: Operation that failed
            error: Error message
            show_name: Show being processed (if applicable)
            source: Source/scraper name (if applicable)
            exc_info: Whether to include exception traceback
            **kwargs: Additional context fields
        """
        context = self._build_context(
            operation=operation,
            show_name=show_name,
            source=source,
            error=error,
            **kwargs
        )
        message = f"Error in {operation}"
        self.logger.error(self._format_message(message, context), exc_info=exc_info)

    @contextmanager
    def operation_timer(
        self,
        operation: str,
        show_name: Optional[str] = None,
        source: Optional[str] = None
    ):
        """
        Context manager for timing operations.

        Args:
            operation: Operation being timed
            show_name: Show being processed
            source: Source/scraper name

        Yields:
            Dictionary to store operation results

        Example:
            with logger.operation_timer("download", show_name, source) as op:
                # perform download
                op["file_size"] = 1000000
        """
        start_time = time.time()
        result = {"success": False}

        try:
            yield result
        finally:
            duration = time.time() - start_time
            context = self._build_context(
                operation=operation,
                show_name=show_name,
                source=source,
                duration_sec=f"{duration:.2f}",
                success=result.get("success", False)
            )

            # Add any additional fields from result
            for key, value in result.items():
                if key != "success":
                    context[key] = value

            message = f"Operation {operation} completed"
            self.logger.info(self._format_message(message, context))
