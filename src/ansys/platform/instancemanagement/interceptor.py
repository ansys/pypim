"""Interceptor that adds headers to outgoing requests.

This is a direct adaptation of the official gRPC example, but it supports multiple headers.
https://github.com/grpc/grpc/tree/master/examples/python/interceptors/headers
"""

import collections
from typing import Sequence, Tuple

import grpc


class _GenericClientInterceptor(
    grpc.UnaryUnaryClientInterceptor,
    grpc.UnaryStreamClientInterceptor,
    grpc.StreamUnaryClientInterceptor,
    grpc.StreamStreamClientInterceptor,
):
    def __init__(self, interceptor_function):
        self._fn = interceptor_function

    def intercept_unary_unary(self, continuation, client_call_details, request):
        new_details, new_request_iterator, postprocess = self._fn(
            client_call_details, iter((request,)), False, False
        )
        response = continuation(new_details, next(new_request_iterator))
        return postprocess(response) if postprocess else response

    def intercept_unary_stream(self, continuation, client_call_details, request):
        new_details, new_request_iterator, postprocess = self._fn(
            client_call_details, iter((request,)), False, True
        )
        response_it = continuation(new_details, next(new_request_iterator))
        return postprocess(response_it) if postprocess else response_it

    def intercept_stream_unary(self, continuation, client_call_details, request_iterator):
        new_details, new_request_iterator, postprocess = self._fn(
            client_call_details, request_iterator, True, False
        )
        response = continuation(new_details, new_request_iterator)
        return postprocess(response) if postprocess else response

    def intercept_stream_stream(self, continuation, client_call_details, request_iterator):
        new_details, new_request_iterator, postprocess = self._fn(
            client_call_details, request_iterator, True, True
        )
        response_it = continuation(new_details, new_request_iterator)
        return postprocess(response_it) if postprocess else response_it


class _ClientCallDetails(
    collections.namedtuple("_ClientCallDetails", ("method", "timeout", "metadata", "credentials")),
    grpc.ClientCallDetails,
):
    pass


def header_adder_interceptor(headers: Sequence[Tuple[str, str]]):
    """Interceptor adding a set of headers to the requests.

    Parameters
    ----------
    headers : Sequence[Tuple[str, str]]
        List of metadata to inject.
    """

    def intercept_call(client_call_details, request_iterator, *_):
        metadata = []
        if client_call_details.metadata is not None:
            metadata = list(client_call_details.metadata)

        for header, value in headers:
            metadata.append(
                (
                    header,
                    value,
                )
            )

        client_call_details = _ClientCallDetails(
            client_call_details.method,
            client_call_details.timeout,
            metadata,
            client_call_details.credentials,
        )
        return client_call_details, request_iterator, None

    return _GenericClientInterceptor(intercept_call)
