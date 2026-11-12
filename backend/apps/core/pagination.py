from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class StandardPagination(PageNumberPagination):
    """Standardized page-number pagination with consistent metadata envelope."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_page_size(self, request):
        if self.page_size_query_param:
            try:
                params = getattr(request, 'query_params', getattr(request, 'GET', {}))
                requested_size = int(params[self.page_size_query_param])
                if requested_size > 0:
                    return min(requested_size, self.max_page_size)
            except (KeyError, ValueError, TypeError):
                pass
        return self.page_size

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'message': 'Data retrieved successfully.',
            'data': data,
            'meta': {
                'page': self.page.number,
                'page_size': self.get_page_size(self.request),
                'total_count': self.page.paginator.count,
                'total_pages': self.page.paginator.num_pages,
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
            }
        })
