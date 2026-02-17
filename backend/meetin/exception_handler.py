import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

logger = logging.getLogger('meetin')


def custom_exception_handler(exc, context):
    """Custom exception handler that prevents internal details from leaking."""
    response = exception_handler(exc, context)

    if response is not None:
        return response

    # Unhandled exceptions — log full details, return generic message
    logger.exception("Unhandled exception in %s", context.get('view', 'unknown'))

    if settings.DEBUG:
        return Response(
            {'error': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response(
        {'error': 'An internal error occurred. Please try again later.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
