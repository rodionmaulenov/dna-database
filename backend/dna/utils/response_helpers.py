"""
API response utilities
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def error_response(
    status_code: int,
    message: str,
    log_message: Optional[str] = None,
    exc_info: bool = False
) -> tuple:
    """
    Generate standardized error response with logging

    Args:
        status_code: HTTP status code (400, 404, 500, etc.)
        message: User-facing error message
        log_message: Optional detailed message for logs (defaults to message)
        exc_info: Include exception traceback in logs

    Returns:
        (status_code, response_dict)
    """
    log_msg = log_message or message

    if status_code >= 500:
        logger.error(f"❌ {log_msg}", exc_info=exc_info)
    elif status_code >= 400:
        logger.warning(f"⚠️ {log_msg}")

    return status_code, {
        'success': False,
        'message': message
    }


def success_response(
    status_code: int,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    log_message: Optional[str] = None
) -> tuple:
    """
    Generate standardized success response with logging

    Args:
        status_code: HTTP status code (200, 201, etc.)
        message: Success message
        data: Optional response data
        log_message: Optional message for logs (defaults to message)

    Returns:
        (status_code, response_dict)
    """
    log_msg = log_message or message
    logger.info(f"✅ {log_msg}")

    response = {
        'success': True,
        'message': message
    }

    if data:
        response['data'] = data

    return status_code, response