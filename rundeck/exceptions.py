'''
Python module for the Rundeck API

Exception classes for PyRundeck
'''
from __future__ import absolute_import, print_function, unicode_literals
from requests.exceptions import HTTPError


class ApiVersionNotSupported(Exception):
    '''This library does not support the version of the API requested'''


class InvalidAuthentication(Exception):
    '''The method of authentication is not valid'''


class JobNotFound(Exception):
    '''The job could not be found in the Project'''


class MissingProjectArgument(Exception):
    '''The requested action requires a Project name to be specified'''


class InvalidJobArgument(Exception):
    '''The job name or ID is not valid'''


class InvalidResponseFormat(Exception):
    '''The requested response format is not supported'''


class InvalidJobDefinitionFormat(Exception):
    '''The specified job definition format is not supported'''


class RundeckServerError(Exception):
    '''Base exceptions generated by the Rundeck server'''
    def __init__(self, *args, **kwargs):
        self.rundeck_response = kwargs.pop('rundeck_response', None)
        super(RundeckServerError, self).__init__(*args)


class InvalidDupeOption(Exception):
    '''The dupeOption specified is invalid'''


class InvalidUuidOption(Exception):
    '''The uuidOption specified is invalid'''


class InvalidResourceSpecification(Exception):
    '''The resource specified does not meet requirements'''
