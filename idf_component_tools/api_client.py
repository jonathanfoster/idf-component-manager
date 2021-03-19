"""Classes to work with Espressif Component Web Service"""
import os
from collections import namedtuple
from functools import wraps
from io import open

import requests
import semantic_version as semver
from requests.adapters import HTTPAdapter
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from schema import Schema, SchemaError
from tqdm import tqdm

# Import whole module to avoid circular dependencies
import idf_component_tools as tools

try:
    from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

    if TYPE_CHECKING:
        from idf_component_tools.sources import BaseSource
except ImportError:
    pass

TaskStatus = namedtuple('TaskStatus', ['message', 'status', 'progress'])

DEFAULT_TIMEOUT = (
    6.05,  # Connect timeout
    30.1,  # Read timeout
)


class APIClientError(Exception):
    pass


def join_url(*args):  # type: (*str) -> str
    """
    Joins given arguments into an url and add trailing slash
    """
    parts = [part[:-1] if part and part[-1] == '/' else part for part in args]
    parts.append('')
    return '/'.join(parts)


def auth_required(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if not self.session.auth.token:
            raise APIClientError('API token is required')
        return f(self, *args, **kwargs)

    return wrapper


class TokenAuth(requests.auth.AuthBase):
    def __init__(self, token):  # type: (Optional[str]) -> None
        self.token = token

    def __call__(self, request):
        if self.token:
            request.headers['Authorization'] = 'Bearer %s' % self.token
        return request


class APIClient(object):
    def __init__(self, base_url, source=None, auth_token=None):
        # type: (str, Optional[BaseSource], Optional[str]) -> None
        self.base_url = base_url
        self.source = source

        api_adapter = HTTPAdapter(max_retries=3)

        session = requests.Session()
        session.auth = TokenAuth(auth_token)
        session.mount(base_url, api_adapter)
        self.session = session

    def _version_dependencies(self, version):
        dependencies = []
        for dependency in version.get('dependencies', []):
            # Support only idf and service sources
            if dependency['source'] == 'idf':
                source = tools.sources.IDFSource({})
            else:
                source = self.source or tools.sources.WebServiceSource({})

            dependencies.append(
                tools.manifest.ComponentRequirement(
                    name='{}/{}'.format(dependency['namespace'], dependency['name']),
                    version_spec=dependency['spec'],
                    public=dependency['is_public'],
                    source=source,
                ))

        return dependencies

    def _base_request(self, method, path, data=None, headers=None, schema=None):
        # type: (str, List[str], Optional[Dict], Optional[Dict], Schema) -> Dict
        endpoint = join_url(self.base_url, *path)

        timeout = DEFAULT_TIMEOUT  # type: Union[float, Tuple[float, float]]
        try:
            timeout = float(os.environ['IDF_COMPONENT_SERVICE_TIMEOUT'])
        except ValueError:
            raise APIClientError('Cannot parse IDF_COMPONENT_SERVICE_TIMEOUT. It should be a number in seconds.')
        except KeyError:
            pass

        try:
            response = self.session.request(
                method,
                endpoint,
                data=data,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            json = response.json()
        except requests.exceptions.RequestException:
            raise APIClientError('HTTP request error')

        try:
            if schema is not None:
                schema.validate(json)
        except SchemaError as e:
            raise APIClientError('API Enpoint "{}: returned unexpected JSON:\n{}'.format(endpoint, str(e)))

        except (ValueError, KeyError, IndexError):
            raise APIClientError('Unexpected component server response')

        return response.json()

    def versions(self, component_name, spec='*'):
        """List of versions for given component with required spec"""
        component_name = component_name.lower()
        body = self._base_request('get', ['components', component_name])

        return tools.manifest.ComponentWithVersions(
            name=component_name,
            versions=[
                tools.manifest.HashedComponentVersion(
                    version_string=version['version'],
                    component_hash=version['component_hash'],
                    dependencies=self._version_dependencies(version),
                ) for version in body['versions']
            ],
        )

    def component(self, component_name, version=None):
        """Manifest for given version of component, if version is None most recent version returned"""
        response = self._base_request('get', ['components', component_name.lower()])
        versions = response['versions']

        if version:
            requested_version = tools.manifest.ComponentVersion(str(version))
            best_version = [v for v in versions
                            if tools.manifest.ComponentVersion(v['version']) == requested_version][0]
        else:
            best_version = max(versions, key=lambda v: semver.Version(v['version']))

        return tools.manifest.Manifest(
            name=('%s/%s' % (response['namespace'], response['name'])),
            version=tools.manifest.ComponentVersion(best_version['version']),
            download_url=best_version['url'],
            dependencies=self._version_dependencies(best_version),
            maintainers=None,
        )

    @auth_required
    def upload_version(self, component_name, file_path):
        with open(file_path, 'rb') as file:
            filename = os.path.basename(file_path)

            encoder = MultipartEncoder({'file': (filename, file, 'application/octet-stream')})
            headers = {'Content-Type': encoder.content_type}

            progress_bar = tqdm(total=encoder.len, unit_scale=True, unit='B', disable=None)

            def callback(monitor, memo={'progress': 0}):  # type: (MultipartEncoderMonitor, dict) -> None
                progress_bar.update(monitor.bytes_read - memo['progress'])
                memo['progress'] = monitor.bytes_read

            data = MultipartEncoderMonitor(encoder, callback)

            try:
                return self._base_request(
                    'post',
                    ['components', component_name.lower(), 'versions'],
                    data=data,
                    headers=headers,
                )['job_id']
            finally:
                progress_bar.close()

    @auth_required
    def delete_version(self, component_name, component_version):
        self._base_request('delete', ['components', component_name.lower(), component_version])

    @auth_required
    def create_component(self, component_name):
        body = self._base_request('post', ['components', component_name.lower()])
        return (body['namespace'], body['name'])

    def task_status(self, job_id):  # type: (str) -> TaskStatus
        body = self._base_request('get', ['tasks', job_id])
        return TaskStatus(body['message'], body['status'], body['progress'])
