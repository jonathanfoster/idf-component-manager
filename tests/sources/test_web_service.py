# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import filecmp
import os
import shutil
import tempfile

import pytest
import vcr

from idf_component_tools.errors import FetchingError
from idf_component_tools.hash_tools import hash_dir
from idf_component_tools.manifest import ComponentVersion, SolvedComponent
from idf_component_tools.sources import WebServiceSource


class TestComponentWebServiceSource(object):
    EXAMPLE_HASH = 'ed55692af0eed2feb68f6d7a2ef95a0142b20518a53a0ceb7c699795359d7dc5'
    LOCALHOST_HASH = '02d9269ed8690352e6bfc5f6a6c60e859fa6cbfc56efe75a1199b35bdd6c54c8'
    CMP_HASH = 'b9d411534df3fd6c6c6291d1e66e7b7f28921f76bc118c321651af1be60cc5d3'

    def test_service_is_me(self):
        assert WebServiceSource.is_me('test', None)
        assert WebServiceSource.is_me('test', {})
        assert WebServiceSource.is_me('test', {'path': '/'})

    def test_cache_path(self):
        source = WebServiceSource(source_details={'service_url': 'https://example.com/api'})
        component = SolvedComponent('cmp', ComponentVersion('1.0.0'), source=source, component_hash=self.CMP_HASH)
        assert source.component_cache_path(component).endswith(
            'service_{}/espressif__cmp_1.0.0_{}'.format(self.EXAMPLE_HASH[:8], self.CMP_HASH))

    @vcr.use_cassette('tests/fixtures/vcr_cassettes/test_fetch_webservice.yaml')
    def test_download(self, release_component_path):
        tempdir = tempfile.mkdtemp()
        cache_dir = os.path.join(tempdir, 'cache')
        source = WebServiceSource(
            source_details={'service_url': 'https://example.com/api'}, system_cache_path=cache_dir)
        cmp = SolvedComponent('test/cmp', '1.0.1', source, component_hash=self.CMP_HASH)

        try:
            source = WebServiceSource(source_details={'service_url': 'http://localhost:5000/'})
            download_path = os.path.join(tempdir, 'test_download')
            local_path = source.download(cmp, download_path)

            assert local_path == download_path
            assert os.path.isdir(local_path)
            downloaded_manifest = os.path.join(local_path, 'idf_component.yml')
            assert os.path.isfile(downloaded_manifest)
            cached_manifest = os.path.join(source.component_cache_path(cmp), 'idf_component.yml')
            assert os.path.isfile(cached_manifest)
            assert filecmp.cmp(downloaded_manifest, cached_manifest)

            # Download one more time, to check that nothing will happen
            source.download(cmp, download_path)

            # Check copy from the cache (NO http request)
            fixture_cmp = SolvedComponent('test/cmp', '1.0.0', source, component_hash=hash_dir(release_component_path))
            download_path = os.path.join(tempdir, 'test_cached')
            cache_path = source.component_cache_path(fixture_cmp)
            if os.path.exists(cache_path):
                shutil.rmtree(cache_path, ignore_errors=True)
            shutil.copytree(release_component_path, cache_path)

            local_path = source.download(fixture_cmp, download_path)

            assert os.path.isfile(os.path.join(local_path, 'idf_component.yml'))

        finally:
            shutil.rmtree(tempdir)

    @vcr.use_cassette('tests/fixtures/vcr_cassettes/test_webservice_pre_release.yaml')
    def test_pre_release_exists(self, monkeypatch, capsys):
        source = WebServiceSource(source_details={'service_url': 'http://localhost:5000/'})

        captured = capsys.readouterr()
        with pytest.raises(FetchingError):
            source.versions('example/cmp')
            assert 'HINT:' in captured.out
            assert 'pre_release' in captured.out

    @vcr.use_cassette('tests/fixtures/vcr_cassettes/test_webservice_versions.yaml')
    def test_skip_pre_release(self, monkeypatch):
        source = WebServiceSource(source_details={'service_url': 'http://localhost:5000/', 'pre_release': False})
        assert len(source.versions('example/cmp').versions) == 1

    @vcr.use_cassette('tests/fixtures/vcr_cassettes/test_webservice_versions.yaml')
    def test_select_pre_release(self, monkeypatch):
        source = WebServiceSource(source_details={'service_url': 'http://localhost:5000/', 'pre_release': True})
        assert len(source.versions('example/cmp').versions) == 2

    @vcr.use_cassette('tests/fixtures/vcr_cassettes/test_webservice_target.yaml')
    def test_target_exists(self, monkeypatch, capsys):
        source = WebServiceSource(source_details={'service_url': 'http://localhost:5000/'})

        captured = capsys.readouterr()
        with pytest.raises(FetchingError):
            source.versions('example/cmp', target='esp32s2')
            assert 'HINT:' in captured.out
            assert 'target' in captured.out
