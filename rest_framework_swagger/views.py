import json
from django.conf.urls import patterns
from django.http.response import Http404
from django.utils.module_loading import import_by_path

from django.views.generic import View
from django.utils.safestring import mark_safe
from django.shortcuts import render_to_response, RequestContext
from django.core.exceptions import PermissionDenied
from django.conf import settings

from rest_framework.views import Response
from rest_framework_swagger.urlparser import UrlParser
from rest_framework_swagger.apidocview import APIDocView
from rest_framework.renderers import JSONRenderer
from rest_framework_swagger.docgenerator import DocumentationGenerator

from rest_framework_swagger import SWAGGER_SETTINGS


def get_router(version):
    """
    Return router defined in settings.API_ROUTERS according to version
    :param version: Version of api
    :type version: basestring
    :return: router
    :rtype: rest.routers.AdvancedSimpleRouter
    """

    routers = settings.API_ROUTERS
    if version:
        raise NotImplementedError()
    api_desc = routers[0]
    router_inst = api_desc['router']
    router = import_by_path(router_inst)
    return router


class SwaggerUIView(View):
    def get(self, request, *args, **kwargs):

        if not self.has_permission(request):
            raise PermissionDenied()

        template_name = "rest_framework_swagger/index.html"
        data = {
            'swagger_settings': {
                'discovery_url': "%sapi-docs/" % request.build_absolute_uri(),
                'api_key': SWAGGER_SETTINGS.get('api_key', ''),
                'enabled_methods': mark_safe(
                    json.dumps(SWAGGER_SETTINGS.get('enabled_methods')))
            }
        }
        response = render_to_response(template_name, RequestContext(request, data))

        return response

    def has_permission(self, request):
        if SWAGGER_SETTINGS.get('is_superuser') and not request.user.is_superuser:
            return False

        if SWAGGER_SETTINGS.get('is_authenticated') and not request.user.is_authenticated():
            return False

        return True


class SwaggerResourcesView(APIDocView):
    renderer_classes = (JSONRenderer,)

    def get(self, request):
        apis = []
        resources = self.get_resources()

        for path in resources:
            apis.append({
                'path': "/%s" % path,
                'name': path.replace('/', '-')
            })

        return Response({
            'apiVersion': SWAGGER_SETTINGS.get('api_version', ''),
            'swaggerVersion': '1.2',
            'basePath': self.host.rstrip('/'),
            'apis': apis
        })

    def get_resources(self, version=None):
        router = get_router(version)
        resources = []
        for prefix, viewset, base_name in router.get_full_registry():
            resources.append(prefix)

        return resources


class SwaggerApiView(APIDocView):
    renderer_classes = (JSONRenderer,)

    def get(self, request, path):
        apis = self.get_api_for_resource(path)
        generator = DocumentationGenerator()

        return Response({
            'apis': generator.generate(apis),
            'models': generator.get_models(apis),
            'basePath': self.api_full_uri.rstrip('/'),
        })

    def get_api_for_resource(self, filter_path, version=None):
        root_router = get_router(version)
        url_parser = UrlParser()
        fp = filter_path.split("/")
        route_name = fp[-1]
        nests = fp[:-1]
        router = root_router
        try:
            for nest in nests:
                router = next(cr for cr in router.children_routers if cr.parent_prefix == nest)
            route = next(r for r in router.registry if r[0] == route_name)
        except StopIteration:
            raise Http404

        return url_parser.get_apis(patterns=patterns("", *router.get_partial_urls([route])))
