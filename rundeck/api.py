'''
Python module for the Rundeck API
'''
from __future__ import absolute_import, print_function, unicode_literals

from functools import partial
from xml.sax.saxutils import quoteattr
try:
    from urllib import quote as urlquote
except ImportError:
    # Python 3
    from urllib.parse import quote as urlquote

from rundeck.connection import RundeckConnectionTolerant, RundeckConnection
from rundeck.util import cull_kwargs, dict2argstring, StringType
from rundeck.exceptions import (
    InvalidResponseFormat,
    InvalidJobDefinitionFormat,
    InvalidDupeOption,
    InvalidUuidOption,
    HTTPError)
from rundeck.defaults import (
    GET,
    POST,
    DELETE,
    DupeOption,
    UuidOption,
    JobDefFormat,
    ExecutionOutputFormat,
    RUNDECK_API_VERSION)


def api_version_check(api_version, required_version):
    '''
    Raises ``NotImplementedError if the api_version of the connection isn't suffiecient
    '''
    if api_version < required_version:
        raise NotImplementedError(
            'Call requires API version \'{0}\' or higher'.format(required_version)
        )


class RundeckNode(object):
    '''
    Represents a Rundeck node for serializing XML
    '''

    def __init__(self, name, hostname, username, **kwargs):
        '''
        Initializes ``RundeckNode`` instance

        :param name:
            (str) name of the node
        :param hostname:
            (str) hostname of the node
        :param username:
            (str) user name used for the remote connection

        :keyword args:
            description (str):
                node description
            osArch (str):
                the nodes operating system architecture
            osFamily (str):
                the nodes operating system name
            tags (list):
                list of filtering tags
            editUrl (str):
                URL to an external resource model editor service
            remoteUrl (str):
                URL to an external resource model service
            attributes (dict):
                dictionary of name/value pairs to be used as node attributes
        '''
        self.name = name
        self.hostname = hostname
        self.username = username

        self.description = kwargs.get('description', None)
        self.osArch = kwargs.get('osArch', None)
        self.osFamily = kwargs.get('osFamily', None)
        self.osName = kwargs.get('osName', None)
        self.tags = kwargs.get('tags', None)
        self.editUrl = kwargs.get('editUrl', None)
        self.remoteUrl = kwargs.get('remoteUrl', None)
        self.attributes = kwargs.get('attributes', None)

    def serialize(self):
        '''
        Serializes the instance to XML and returns it as a ``string``
        '''
        node_attr_keys = (
            'name',
            'hostname',
            'username',
            'description',
            'osArch',
            'osFamily',
            'osName',
            'editUrl',
            'remoteUrl',
        )

        data = {k: getattr(self, k) for k in node_attr_keys if getattr(self, k, None) is not None}

        if self.tags is not None and hasattr(self.tags, '__iter__'):
            data['tags'] = ','.join(self.tags)
        elif isinstance(self.tags, StringType):
            data['tags'] = self.tags

        node_xml_attrs = ' '.join(['{0}={1}'.format(k, quoteattr(v)) for k, v in data.items()])

        node_attributes = ''
        if self.attributes is not None and isinstance(self.attributes, dict):
            node_attributes = ''.join(['<attribute name="{0}" value="{1}" />'.format(k, v)
                                        for k, v in self.attributes.items()])

        return '<node {0}>{1}</node>'.format(node_xml_attrs, node_attributes)

    @property
    def xml(self):
        return self.serialize()


class RundeckApiTolerant(object):
    '''
    As close to the Rundeck API as possible. ``Tolerant`` class does not throw exceptions
    when HTTP status codes are returned.
    '''

    def __init__(self,
                 server='localhost',
                 protocol='http',
                 port=4440,
                 api_token=None,
                 **kwargs):
        '''
        Initializes a Rundeck API instance

        :param server:
            [default: 'localhost']
            (str) hostname of the Rundeck server
        :param protocol:
            [default: 'http']
            (str) protocol to be used (http/https)
        :param port:
            [default: 4440]
            (int) Rundeck server port
        :param api_token:
            [default: ``None``]
            (str) valid Rundeck user API token

        :keyword args:
            base_path (str):
                [default: ``None``]
                Custom base URL path for Rundeck server URLs
            usr (str):
                Rundeck user name to be used in place of ``api_token``
            pwd (str):
                Rundeck user password (used in conjunction with ``usr``)
            api_version (int):
                Rundeck API version
            connection (class):
                ``rundeck.connection.RundeckConnection`` or instance of a subclass of ``rundeck.connection.RundeckConnection``
        '''
        connection = kwargs.pop('connection', None)

        if connection is None:
            self.connection = RundeckConnection(
                server=server, protocol=protocol, port=port, api_token=api_token, **kwargs
            )
        elif isinstance(connection, RundeckConnectionTolerant):
            self.connection = connection
        else:
            raise Exception(
                'Supplied connection argument is not '
                'a valid RundeckConnection: {0}'.format(connection)
            )

        self.requires_version = partial(api_version_check, self.connection.api_version)

    def _exec(self,
              method,
              url,
              params=None,
              data=None,
              parse_response=True,
              **kwargs):
        '''
        Executes a request to Rundeck via ``RundeckConnection``

        Returns a class ``rundeck.connection.RundeckResponse``

        :param method:
            (str) either ``rundeck.defaults.GET or ``rundeck.defaults.POST``
        :param url:
            (str) Rundeck API endpoint URL
        :param params:
            [default: ``None``]
            (dict) dictionary of query string params
        :param data:
            [default: ``None``]
            (dict) dictionary of POST data
        :param parse_response:
            [default: ``True``]
            (bool) if specified, parses the response from the Rundeck server
        '''
        return self.connection.call(
            method, url, params=params, data=data, parse_response=parse_response, **kwargs
        )

    def system_info(self, **kwargs):
        '''
        Wraps Rundeck API GET /system/info <http://rundeck.org/docs/api/index.html#system-info>

        Returns a class ``rundeck.connection.RundeckResponse``
        '''
        return self._exec(GET, 'system/info', **kwargs)

    def jobs(self, project, **kwargs):
        '''
        Wraps Rundeck API GET /jobs <http://rundeck.org/docs/api/index.html#listing-jobs>

        Returns a class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of the project

        :keyword args:
            idlist (str) | (list(str, ...))
                specify a comma-separated string or a list of job IDs to include
            groupPath (str):
                [default: '*']
                specify a group or partial group path to include all jobs within that group path
                or '*' for all groups or '-' to match top level jobs only
            jobFilter (str):
                specify a job name filter, will match any job name that contains the ``jobFilter`` string
            jobExactFilter (str):
                specify an exact job name to match
            groupPathExact (str):
                specify an exact group to match or '-' to match the top level jobs only
        '''
        params = cull_kwargs(
            ('idlist', 'groupPath', 'jobFilter', 'jobExactFilter', 'groupPathExact', kwargs)
        )

        if 'jobExactFilter' in params or 'groupPathExact' in params:
            self.requires_version(2)

        params['project'] = project

        return self._exec(GET, 'jobs', params=params, **kwargs)

    def project_jobs(self, project, **kwargs):
        '''
        Simulates Rundeck API GET /project/[NAME]/jobs <http://rundeck.org/docs/api/index.html#listing-jobs-for-a-project>

        Returns a class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of the project

        :keyword args:
            idlist (list(str, ...)):
                list of job ids to return
            groupPath (str):
                a group path, partial group path or the special top level only char '-'
            jobFilter (str):
                find job names that include this string
            jobExactFilter (str):
                specific job name to return
            groupPathExact (str):
                exact group path to match or the special top level only char '-'
        '''
        return self.jobs(project, **kwargs)

    def job_run(self, job_id, **kwargs):
        '''
        Wraps Rundeck API GET /job/[ID]/run <http://rundeck.org/docs/api/index.html#running-a-job>

        Returns a class ``rundeck.connection.RundeckResponse``

        :param job_id:
            (str) Rundeck job ID

        :keyword args:
            argString (str) | (dict):
                argument string to pass to job if ``str``, it is passed as is if ``dict`` will be
                converted to compatible ``str``
            loglevel (str('DEBUG', 'VERBOSE', 'INFO', 'WARN', 'ERROR')):
                [default: 'INFO']
                logging level
            asUser (str):
                user to run specified job as
            exclude-precedence (bool):
                [default: ``True``]
                set the exclusion precedence
            hostname (str):
                hostname inclusion filter
            tags (str):
                tags inclusion filter
            os-name (str):
                os-name inclusion filter
            os-family (str):
                os-family inclusion filter
            os-arch (str):
                os-arch inclusion filter
            os-version (str):
                os-version inclusion filter
            name (str):
                name inclusion filter
            exclude-hostname (str):
                hostname exclusion filter
            exclude-tags (str):
                tags exclusion filter
            exclude-os-name (str):
                os-name exclusion filter
            exclude-os-family (str):
                os-family exclusion filter
            exclude-os-arch (str):
                os-arch exclusion filter
            exclude-os-version (str):
                os-version exclusion filter
            exclude-name (str):
                name exclusion filter
        '''
        params = cull_kwargs(('argString', 'loglevel', 'asUser', 'exclude-precedence',
            'hostname', 'tags', 'os-name', 'os-family', 'os-arch', 'os-version', 'name',
            'exclude-hostname', 'exclude-tags', 'exclude-os-name', 'exclude-os-family',
            'exclude-os-arch', 'exclude-os-version', 'exclude-name'), kwargs)

        argString = params.get('argString', None)
        if argString is not None:
            params['argString'] = dict2argstring(argString)

        return self._exec(GET, 'job/{0}/run'.format(job_id), params=params, **kwargs)

    def jobs_export(self, project, **kwargs):
        '''
        '''
