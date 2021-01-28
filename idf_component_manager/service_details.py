''' Helper function to init API client'''
import os
from collections import namedtuple
from typing import Optional

from idf_component_tools.api_client import APIClient
from idf_component_tools.errors import FatalError
from idf_component_tools.sources.web_service import default_component_service_url

from .config import ConfigManager

ServiceDetails = namedtuple('ServiceDetails', ['client', 'namespace'])


def service_details(namespace=None, service_profile=None):  # type: (Optional[str], Optional[str]) -> ServiceDetails
    config = ConfigManager().load()
    profile_name = service_profile or 'default'
    profile = config.profiles.get(profile_name, {})

    service_url = profile.get('url')
    if not service_url or service_url == 'default':
        service_url = default_component_service_url()

    # Priorities: idf.py option > IDF_COMPONENT_NAMESPACE env variable > profile value
    namespace = namespace or profile.get('default_namespace')
    if not namespace:
        raise FatalError('Namespace is required to upload component')

    # Priorities: IDF_COMPONENT_API_TOKEN env variable > profile value
    token = os.getenv('IDF_COMPONENT_API_TOKEN', profile.get('api_token'))
    if not token:
        raise FatalError('API token is required to upload component')

    client = APIClient(base_url=service_url, auth_token=token)

    return ServiceDetails(client, namespace)