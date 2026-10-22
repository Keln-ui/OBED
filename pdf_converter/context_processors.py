from urllib.parse import urlsplit

from django.conf import settings


def _hostname(value):
    return urlsplit(f'//{value}').hostname


def platform_links(request):
    academic_host = settings.ACADEMIC_HOST
    converter_host = settings.CONVERTER_HOST
    request_host = _hostname(request.get_host())
    is_converter_site = request_host == _hostname(converter_host)
    port = request.get_port()

    def absolute_url(host):
        hostname = _hostname(host)
        if settings.DEBUG and port not in ('80', '443'):
            hostname = f'{hostname}:{port}'
        return f'{settings.SITE_SCHEME}://{hostname}/'

    return {
        'is_converter_site': is_converter_site,
        'academic_home_url': absolute_url(academic_host),
        'converter_home_url': absolute_url(converter_host),
    }
