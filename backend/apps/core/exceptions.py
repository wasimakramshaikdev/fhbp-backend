import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Standardizes all DRF and unhandled Python exceptions into uniform API response envelope:
    {
        "success": false,
        "message": "Human-readable error summary",
        "errors": { ... },
        "code": "ERROR_CODE"
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        errors = {}
        message = "An error occurred while processing your request."

        if isinstance(response.data, dict):
            if "detail" in response.data:
                message = str(response.data["detail"])
                errors = {"detail": [message]}
            else:
                errors = response.data
                # Pick first error as message summary
                first_key = next(iter(response.data))
                first_val = response.data[first_key]
                if isinstance(first_val, list) and len(first_val) > 0:
                    message = f"{first_key}: {first_val[0]}"
                else:
                    message = f"Invalid data for {first_key}"
        elif isinstance(response.data, list):
            errors = {"non_field_errors": response.data}
            message = str(response.data[0]) if response.data else "Validation error"
        else:
            message = str(response.data)
            errors = {"error": [message]}

        # Map HTTP Status code to string error code
        code_map = {
            400: "VALIDATION_ERROR",
            401: "AUTHENTICATION_FAILED",
            403: "PERMISSION_DENIED",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            429: "THROTTLED",
            500: "SERVER_ERROR",
        }
        error_code = code_map.get(response.status_code, "REQUEST_FAILED")

        response.data = {
            "success": False,
            "message": message,
            "errors": errors,
            "code": error_code,
        }
    else:
        # Unhandled 500 server error
        logger.error(f"Unhandled Exception: {exc}", exc_info=True)
        response = Response(
            {
                "success": False,
                "message": "An unexpected internal server error occurred. Our engineering team has been notified.",
                "errors": {"server": [str(exc)]},
                "code": "INTERNAL_SERVER_ERROR",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
