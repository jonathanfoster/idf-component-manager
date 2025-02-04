# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import pytest
from pytest import raises

from idf_component_manager.core_utils import parse_example
from idf_component_tools.errors import FatalError


@pytest.mark.parametrize(
    ('example', 'spec'), [
        ('test/cmp>=1.0.0.1:sample_project', '>=1.0.0.1'), ('test>=1.1.1/component:example', '>=1.1.1/component'),
        ('test/component>=1.2.2<=1.2.3:example', '>=1.2.2<=1.2.3')
    ])
def test_parse_example_spec_version_error(example, spec):
    with raises(FatalError,
                match='Invalid version specification: "{}". Please use format like ">=1" or "*".'.format(spec)):
        parse_example(example)


@pytest.mark.parametrize(
    'example', [
        'namespace/test/component:example',
        '/namespace/component:example',
        't@st/component:example',
        'test:component:example',
        'test/component/example',
    ])
def test_create_example_name_error(example):
    with raises(FatalError,
                match='Cannot parse EXAMPLE argument. Please use format like: namespace/component=1.0.0:example_name'):
        parse_example(example)
