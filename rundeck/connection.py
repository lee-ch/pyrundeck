'''
Python module for the Rundeck API
'''
from __future__ import absolute_import, print_function, unicode_literals
import requests

from functools import wraps
import xml.dom.minidom as xml_dom

from rundeck.transforms import ElementTree
from rundeck.defaults import RUNDECK_API_VERSION
from rundeck.exceptions import (InvalidAuthentication,
                                RundeckServerError,
                                ApiVersionNotSupported)


def memoize(obj):
    cache = obj.cache = {}

    @wraps
    def memoizer(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]
    return memoizer


class RundeckResponse(object):
    '''
    RundeckResponse class

    Handles the responses from the Rundeck API
    '''

    def __init__(self, response, client_api_version, as_dict_method=None):
        '''
        Parses an XML string into a Python object

        :param response:
            instance of the requests.Response returned by the associated command request
        '''
        self.client_api_version = client_api_version
        self._as_dict_method = None
        self.response = response
        self.body = self.response.text
        self.etree = ElementTree.fromstring(self.body.encode('utf-8'))

    @memoize
    def pprint(self):
        return xml_dom.parseString(self.body).toprettyxml()

    @property
    @memoize
    def as_dict(self):
        if self._as_dict_method is None:
            return None
        else:
            return self._as_dict_method(self)

    @property
    @memoize
    def api_version(self):
        return int(self.etree.attrib.get('apiversion', -1))

    @property
    @memoize
    def success(self):
        try:
            return 'success' in self.etree.attrib
        except Exception:
            return False

    @property
    @memoize
    def message(self):
        term = 'success' if self.success else 'error'
        message_el = self.etree.find(term)
        if message_el is None:
            return term
        else:
            return message_el.find('message').text

    def raise_for_error(self, msg=None):
        if msg is None:
            msg = self.message

        if not self.success:
            raise RundeckServerError(msg, rundeck_response=self)


class RundeckConnectionTolerant(object):
    '''
    Initializes a Rundeck API client connection
    '''

    def __init__(self,
                 server='localhost',
                 protocol='http',
                 port=4440,
                 api_token=None,
                 **kwargs):
        '''
        Initalizes the Rundeck API client connection

        :param server:
            [default: 'localhost']
            (str) server hostname or IP address to connect to
        :param protocol:
            [default: 'http']
            (str) the protocol to use for the connection
        :param port:
            [default: 4440]
            (int) the port number of the Rundeck server
        :param api_token:
            [default: ``None``]
            (str) valid Rundeck user API token
        :param kwargs:
            (kwargs) keyword arguments to pass in

        :keyword args:
            base_path (str):
                [default: ``None``]
                Custom base URL path for Rundeck server URLs
            usr (str):
                Rundeck username (used in place of ``api_token``)
            pwd (str):
                Rundeck user password (used with ``usr``)
            api_version (int):
                Rundeck API version
            verify_cert (bool):
                Server certificate verification (``https`` only)

        Example:
        >>> client = RundeckConnectionTolerant('somehost-or-ip.com', 'https', 4440, 'apitoken')
        '''
        self.protocol = protocol
        self.usr = usr = kwargs.get('usr', None)
        self.pwd = pwd = kwargs.get('pwd', None)
        self.server = server
        self.api_token = api_token
        self.api_version = int(kwargs.get('api_version', RUNDECK_API_VERSION))
        self.verify_cert = kwargs.get('verify_cert', True)
        self.base_path = kwargs.get('base_path', None)

        # Check the Rundeck API version
        if self.api_version < 1 or self.api_version > RUNDECK_API_VERSION:
            raise ApiVersionNotSupported(
                'The requested Rundeck API Version, \'{0}\' '
                'is not supported. Supported versions: 1-{1}'.format(
                    self.api_version, RUNDECK_API_VERSION
                )
            )

        if (protocol == 'http' and port != 80) or (protocol == 'https' and port != 443):
            # If the ports are not ``80`` or ``443`` set the server url correctly with
            # the port passed in
            self.server = '{0}:{1}'.format(server, port)

        self.base_url = '{0}://{1}'.format(self.protocol, self.server)
        if self.base_path is not None:
            self.base_url += '/' + self.base_path.strip('/')
        self.base_api_url = self.base_url + '/api'

        if api_token is None and usr is None and pwd is None:
            raise InvalidAuthentication(
                'You must supply either an \'api_token\' or username and password'
            )

        self.http = requests.Session()
        self.http.verify = self.verify_cert

        # Api version >11 does not include the results node for xml responses
        # so we're using a workaround here provided by rundeck - use a header
        # to specify that rundeck should include teh result node in the response
        # we get back
        # http://rundeck.org/docs/api/index.html#changes
        self.http.headers.update({'X-Rundeck-API-XML-Response-Wrapper': 'true'})

        if api_token is not None:
            self.http.headers['X-Rundeck-Auth-Token'] = api_token
        elif usr is not None and pwd is not None:
            url = self.make_url('j_security_check')
            data = {
                'j_username': usr,
                'j_password': pwd
            }

            response = self.http.request('POST', url, data=data)
            if (response.url.find('/user/error') != -1
                    or response.url.find('/user/login') != -1
                    or response.status_code != 200):
                raise InvalidAuthentication('Password or username is incorrect')

    def make_api_url(self, api_url):
        '''
        Cretes a valid Rundeck URL based on the API and the base URL of
        the ``RundeckConnection``

        Returns the full Rundeck API URL

        :param api_url:
            (str) the Rundeck API URL
        '''
        return '/'.join([self.base_api_url, str(self.api_version), api_url.lstrip('/')])

    def make_url(self, path):
        '''
        Creates a valid Rundeck URL based on the base url of the ``RundeckConnection``

        Returns the full Rundeck URL

        :param path:
            (str) the Rundeck http URL path
        '''
        return '/'.join([self.base_url, path.lstrip('/')])

    def call(self,
             method,
             url,
             params=None,
             headers=None,
             data=None,
             files=None,
             parse_response=True,
             **kwargs):
        '''
        Format the URL for making the HTTP request and return a ``RundeckResponse``
        if requested or needed

        Returns requests.Response

        :param method:
            (str) HTTP request method
        :param url:
            (str) Rundeck API URL
        :param params:
            [default: ``None``]
            (dict({str: str, ...})) dictionary of query string parameters
        :param headers:
            (dict({str: str, ...})) dictionary of HTTP headers
        :param data:
            [default: ``None``]
            (str) XML or YAML payload necessary for some commands
        :param files:
            (dict({str: str, ...})) dictionary of files to upload
        :param parse_response:
            (bool) if ``True`` parse the response as an XML message

        :keyword args:
            *Passed to RundeckConnection.request*
        '''
        url = self.make_api_url(url)
        auth_header = {'X-Rundeck-Auth-Token': self.api_token}
        if headers is None:
            headers = auth_header
        else:
            headers.update(auth_header)

        response = self.request(
            method, url, params=params, data=data, headers=headers, files=files, **kwargs
        )

        if parse_response:
            return RundeckResponse(response, self.api_version)
        else:
            return response

    def request(self,
                method,
                url,
                params=None,
                headers=None,
                data=None,
                files=None):
        '''
        Sends the HTTP request to Rundeck

        Returns requests.Response

        :param method:
            (str) HTTP request method
        :param url:
            (str) API URL
        :param params:
            [default: ``None``]
            (dict({str: str, ...})) dictionary of query string params
        :param headers:
            [default: ``None``]
            (dict({str: str, ...})) dictionary containing header information
        :param data:
            [default: ``None``]
            url encoded payload necessary for some commands
        :param files:
            [defaults: ``None``]
            (dict({str: str, ...})) dictionary of files to upload
        '''
        return self.http.request(
            method, url, params=params, data=data, headers=headers, files=files
        )


class RundeckConnection(RundeckConnectionTolerant):
    def request(self,
                method,
                url,
                params=None,
                headers=None,
                data=None,
                files=None,
                quiet=False):
        '''
        Override to call ``raise_for_status`` forcing non-successful HTTP responses to bubble
        up as exceptions

        Returns requests.Response

        :param method:
            (str) HTTP request method
        :param url:
            (str) API URL
        :param params:
            [default: ``None``]
            (dict({str: str, ...})) dictionary of query string params
        :param headers:
            [default: ``None``]
            (dict({str: str, ...})) dictionary containing header information
        :param data:
            [default: ``None``]
            url encoded payload necessary for some commands
        :param files:
            [default: ``None``]
            (dict({str: str, ...})) dictionary of files to upload
        :param quiet:
            [default: ``False``]
            (bool) suppress calling raise_for_status
        '''
        response = super(RundeckConnection, self).request(
            method, url, params=params, data=data, headers=headers, files=files
        )

        if not quiet:
            response.raise_for_status()

        return response
