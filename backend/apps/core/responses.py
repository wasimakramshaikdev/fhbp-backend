from rest_framework.response import Response
from rest_framework import status

def api_response(data=None, message="Operation completed successfully.", status_code=status.HTTP_200_OK, meta=None, success=True, errors=None, code=None):
    """
    Standardized API response envelope generator.
    """
    payload = {
        "success": success,
        "message": message,
    }
    
    if success:
        payload["data"] = data if data is not None else {}
        if meta is not None:
            payload["meta"] = meta
    else:
        payload["errors"] = errors if errors is not None else {}
        if code:
            payload["code"] = code
        if data is not None:
            payload["data"] = data
            
    return Response(payload, status=status_code)
