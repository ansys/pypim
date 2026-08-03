# Copyright (C) 2022 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from ansys.platform.instancemanagement.interceptor import (
    _ClientCallDetails,
    _GenericClientInterceptor,
    header_adder_interceptor,
)


def _details(metadata=None):
    return _ClientCallDetails(
        method="/ansys.platform.instancemanagement.v1.ProductInstanceManager/ListDefinitions",
        timeout=1.0,
        metadata=metadata,
        credentials=None,
    )


def test_header_adder_interceptor_keeps_existing_metadata():
    interceptor = header_adder_interceptor([("identity", "james bond")])

    def continuation(details, request):
        return details.metadata, request

    details = _details(metadata=(("existing", "value"),))
    metadata, request = interceptor.intercept_unary_unary(continuation, details, "request")

    assert request == "request"
    assert ("existing", "value") in metadata
    assert ("identity", "james bond") in metadata


def test_intercept_unary_stream_calls_postprocess():
    interceptor = _GenericClientInterceptor(
        lambda details, iterator, *_: (
            details,
            iterator,
            lambda response: ("postprocessed", response),
        )
    )

    def continuation(details, request):
        return (details.method, request)

    response = interceptor.intercept_unary_stream(continuation, _details(), "request")
    assert response == (
        "postprocessed",
        ("/ansys.platform.instancemanagement.v1.ProductInstanceManager/ListDefinitions", "request"),
    )


def test_intercept_stream_unary_calls_postprocess():
    interceptor = _GenericClientInterceptor(
        lambda details, iterator, *_: (
            details,
            iterator,
            lambda response: ("postprocessed", response),
        )
    )

    def continuation(details, iterator):
        return (details.method, list(iterator))

    response = interceptor.intercept_stream_unary(
        continuation, _details(), iter(("first", "second"))
    )
    assert response == (
        "postprocessed",
        (
            "/ansys.platform.instancemanagement.v1.ProductInstanceManager/ListDefinitions",
            ["first", "second"],
        ),
    )


def test_intercept_stream_stream_calls_postprocess():
    interceptor = _GenericClientInterceptor(
        lambda details, iterator, *_: (
            details,
            iterator,
            lambda response: ("postprocessed", response),
        )
    )

    def continuation(details, iterator):
        return (details.method, list(iterator))

    response = interceptor.intercept_stream_stream(
        continuation, _details(), iter(("first", "second"))
    )
    assert response == (
        "postprocessed",
        (
            "/ansys.platform.instancemanagement.v1.ProductInstanceManager/ListDefinitions",
            ["first", "second"],
        ),
    )
