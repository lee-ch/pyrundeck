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
        Wraps Rundeck API GET /jobs/export <http://rundeck.org/docs/api/index.html#exporting-jobs>

        Returns a Requests response

        :param project:
            (str) name of the project

        :keyword args:
            [default: 'xml']
            fmt (str) 'xml' or 'yaml':
                format of the definition string
            idlist (list(str, ...)):
                list of job ids to return
            groupPath (str):
                group path, partial group path or the special top level only char '-'
            jobFilter (str):
                find job names that include this string
        '''
        params = cull_kwargs(('fmt', 'idlist', 'groupPath', 'jobFilter'), kwargs)
        if 'fmt' in params:
            params['format'] = params.pop('fmt')
        params['project'] = project

        return self._exec(GET, 'jobs/export', params=params, parse_response=False, **kwargs)


    def jobs_import(self, definition, **kwargs):
        '''
        Wraps Rundeck API POST /jobs/import <http://rundeck.org/docs/api/index.html#importing-jobs>

        Returns a class ``rundeck.connection.RundeckResponse``

        :param definition:
            (str) string representing a job definition

        :keyword args:
            fmt ((str) 'xml' or 'yaml'):
                [default: 'xml']
                format of the definition string
            dupeOption ((str) 'skip', 'create' or 'update'):
                [default: 'create']
                value to indicate the behavior when importing jobs that already exist
            project (str):
                specifies the project that all job definitions should be imported to, otherwise all job
                definitions must define a project
            uuidOption ((str) 'preserve' or 'remove'):
                preserve or remove UUIDs in imported jobs, preserve may fail if a UUID already exists
        '''
        data = cull_kwargs(('fmt', 'dupeOption', 'project', 'uuidOption'), kwargs)
        data['xmlBatch'] = definition
        if 'fmt' in data:
            data['format'] = data.pop('fmt')

        return self._exec(POST, 'jobs/import', data=data, **kwargs)

    def job(self, job_id, **kwargs):
        '''
        Wraps Rundeck API GET /job/[ID] <http://rundeck.org./docs/api/index.html#getting-a-job-definition>

        Returns a Requests response

        :param job_id:
            (str) Rundeck job ID

        :keyword args:
            fmt (str):
                [default: 'xml']
                format of the response of one of ``rundeck .defaults.JobDefFormat`` ``values``
        '''
        params = cull_kwargs(('fmt',), kwargs)

        if 'fmt' in params:
            params['format'] = params.pop('fmt')

        return self._exec(GET, 'job/{0}'.format(job_id), params=params, parse_response=False, **kwargs)

    def delete_job(self, job_id, **kwargs):
        '''
        Wraps Rundeck API DELETE /job/[ID] <http://rndeck.org/docs/api/index.html#deleting-a-job-definition>

        Returns a Requests response

        :param job_id:
            (str) Rundeck job ID
        '''
        return self._exec(DELETE, 'job/{0}'.format(job_id), parse_response=False, **kwargs)

    def jobs_delete(self, idlist, **kwargs):
        '''
        Wraps Rundeck API POST /jobs/delete <http://rundeck.ord/docs/api/index.hmtl#importing-jobs>

        Returns a class ``rundeck.connection.RundeckResponse``

        :param idlist:
            (str) or (list(str, ...)) list of job ids or a string of comma separated job ids to delete
        '''
        if not isinstance(idlist, StringType) and hasattr(idlist, '__iter__'):
            idlist = ','.join(idlist)

        data = {
            'idlist': idlist,
        }

        try:
            return self._exec(POST, 'jobs/delete', data=data, **kwargs)
        except Exception as e:
            raise

    def job_executions(self, job_id, **kwargs):
        '''
        Wraps Rundeck API GET /job/[ID]/executions <http://rundeck.org/docs/api/index.html#getting-executions-for-a-job>

        Returns a class ``rundeck.connection.RundeckResponse``

        :param job_id:
            (str) Rundeck job ID

        :keyword args:
            status (str):
                one of ``rundeck.defaults.Status`` values
            max (int):
                [default: 20]
                maximum number of results to include in response
            offset (int):
                [default: 0]
                offset for result set
        '''
        params = cull_kwargs(('status', 'max', 'offset'), kwargs)
        return self._exec(GET, 'job/{0}/executions'.format(job_id), params=params, **kwargs)

    def executions_running(self, project, **kwargs):
        '''
        Wraps Rundeck API GET /executions/running <http://rundeck.org/docs/api/index.html#listing-running-executions>

        Returns a class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of a Rundeck project
        '''
        params = {'project': project}
        return self._exec(GET, 'executions/running', params=params, **kwargs)

    def executions(self, project, **kwargs):
        '''
        Wraps Rundeck API GET /executions <http://rundeck.org/docs/api/index.html#getting-execution-info>

        Returns a class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of the Rundeck project

        :keyword args:
            statusFilter (str):
                one of ``rundeck.defaults.Status`` values
            abortedbyFilter (str):
                user that aborted the execution
            userFilter (str):
                user name that initiated the execution
            recentFilter (str):
                Use a text format to filter executions that completed within a period of time, the format is 'XY'
                where 'X' is an integer and 'Y' is one of the following:
                    * `h`: hour
                    * `d`: day
                    * `w`: week
                    * `m`: month
                    * `y`: year

                i.e:
                '2w' would return executions that completed within the last two weeks
            begin (int or str):
                either a unix millisecond timestamp or a W3C date time i.e 'yyyy-MM-ddTHH:mm:ssZ'
            end (int or str):
                either a unix millisecond timestamp or a W3C date time i.e 'yyyy-MM-ddTHH:mm:ssZ'
            adhoc (bool):
                includes adhoc executions if set to ``True``
            jobIdListFilter (str or list):
                one or more job ids to include
            excludeJobIdListFilter (str or list):
                one or more job ids to exclude
            jobListFilter (str or list):
                one or more full job group/name to include
            excludeJobListFilter (str or list):
                one or more full job group/name to exclude
            groupPath (str):
                a group or partial group path to include, special '-' setting matches top level jobs only
            groupPathExact (str):
                an exact group path to include, special '-' setting matches top level jobs only
            excludeGroupPath (str):
                a group or partial group path to exclude, special '-' setting matches top level jobs only
            excludeGroupPathExact (str):
                an exact group path to exclude, special '-' setting matches top level jobs only
            jobExactFilter (str):
                an exact job name
            excludeJobExactFilter (str):
                an exact job name to exclude
            max (int):
                [default: 20]
                maximum number of results to include in the response
            offset (int):
                [default: 0]
                offset for result set
            '''
        self.requires_version(5)

        params = cull_kwargs(('statusFilter', 'abortedbyFilter', 'userFilter', 'recentFilter',
                              'begin', 'end', 'adhoc', 'jobIdListFilter', 'excludeJobIdListFilter',
                              'jobListFilter', 'excludeJobListFilter', 'groupPath', 'groupPathExact',
                              'excludeGroupPath', 'excludeGroupPathExact', 'jobExactFilter',
                              'excludeJobExactFilter', 'max', 'offset'), kwargs)
        params['project'] = project

        return self._exec(GET, 'executions', params=params, **kwargs)

    def execution_output(self, execution_id, **kwargs):
        '''
        Wraps Rundeck API GET /execution/[ID]/output <http://rundeck.org/docs/api/index.html#execution-output>

        Returns a Requests response

        :param execution_id:
            (str) Rundeck job execution ID

        :keyword args:
            fmt (str):
                [default: 'text']
                format of the response of a ``rundeck.defaults.ExecutionOutputFormat`` values
            offset (int):
                byte offset to read from in the file, 0 indicates the beginning
            lastlines (int):
                number of lines to retrieve from the end of the available output (overrides offset)
            lastmod (int):
                a unix millisecond timestamp, return output data received after the specified timestamp
            maxlines (int):
                maximum number of lines to retrieve from the specified offset
        '''
        params = cull_kwargs(('fmt', 'offset', 'lastlines', 'lastmod', 'maxlines'), kwargs)
        if 'fmt' in params:
            params['format'] = params.pop('fmt')

        parse_response = kwargs.pop('parse_response', False)

        return self._exec(GET, 'execution/{0}/output'.format(execution_id), params=params, parse_response=parse_response, **kwargs)

    def execution_abort(self, execution_id, **kwargs):
        '''
        Wraps Rundeck API GET /execution/[ID]/output <http://rundeck.org/docs/api/index.html#execution-output>

        Returns a Requests response

        :param execution_id:
            (str) Rundeck job execution ID

        :keyword args:
            asUser (str):
                specifies a username identifying the user who aborted the execution of job ID ``execution_id``
        '''
        params = cull_kwargs(('asUser',), kwargs)
        return self._exec(GET, 'execution/{0}/abort'.format(execution_id), params=params, **kwargs)

    def run_command(self, project, command, **kwargs):
        '''
        Wraps Rundeck API GET /run/command <http://rundeck.org/docs/api/index.html#running-adhoc-commands>

        Returns a class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of the project
        :param command:
            (str) command in which to run

        :keyword args:
            nodeThreadcount (int):
                number of threads to use
            nodeKeepgoing (bool):
                if ``True``, continue executing on other nodes if command fails
            asUser (str):
                specifies a username in which to run the command, requires runAs permission
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
        params = cull_kwargs(('nodeThreadcount', 'nodeKeepgoing', 'asUser', 'hostname', 'tags',
                              'os-name', 'os-family', 'os-arch', 'os-version', 'name', 'exclude-hostname',
                              'exclude-tags', 'exclude-os-name', 'exclude-os-family', 'exclude-os-arch',
                              'exclude-os-version', 'exclude-name'), kwargs)

        params['project'] = project
        params['exec'] = command

        return self._exec(GET, 'run/command', params=params, **kwargs)

    def run_script(self, project, scriptFile, **kwargs):
        '''
        Wraps Rundeck API POST /run/script <http://rundeck.org/docs/api/index.html#running-adhoc-scripts>

        Returns a class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of the project
        :param scriptFile:
            (str) a string containing the script file content

        :keyword args:
            argString (str or dict):
                argument string to pass to the job, if ``str``, will be passed as is, otherwise ``dict``
                will be converted to compatible string
            nodeThreadcount (int):
                number of threads to use
            nodeKeepgoing (bool):
                if ``True``, continue execution on other nodes if script fails
            asUser (str):
                specifies username of the user in which to run the script, requires runAs permission
            scriptInterpreter (str):
                command to use to execute the script (requires API version 8 or higher)
            interpreterArgsQuoted (bool):
                if ``True`` the script file and arguments are quoted as the last argument to the ``scriptInterpreter``
                (requires API version 8 or higher)
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
        params = cull_kwargs(('argString', 'nodeThreadcount', 'nodeKeepgoing', 'asUser',
                              'scriptInterpreter', 'interpreterArgsQuoted', 'hostname', 'tags', 'os-name',
                              'os-family', 'os-arch', 'os-version', 'name', 'exclude-hostname', 'exclude-tags',
                              'exclude-os-name', 'exclude-os-family', 'exclude-os-arch', 'exclude-os-version',
                              'exclude-name'), kwargs)

        params['project'] = project
        files = {'scriptFile': scriptFile}

        if ('scriptInterpreter' in params) or ('interpreterArgsQuoted' in params):
            self.requires_version(8)

        argString = params.get('argString', None)
        if argString is not None:
            params['argString'] = dict2argstring(argString)

        return self._exec(POST, 'run/script', params=params, files=files, **kwargs)

    def run_url(self, project, scriptURL, **kwargs):
        '''
        Wraps Rundeck API POST /run/url <http://rundeck.org/docs/api/index.html#running-adhoc-script-urls>
        * Requires API version >4

        Returns a class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of the project
        :param scriptURL:
            (str) url of the script to download and execute

        :keyword args:
            argString (str or dict):
                argument string to pass to job, if ``str`` will be passed as is, if ``dict`` will be converted
                to compatible ``str``
            nodeThreadcount (int):
                number of threads to use
            nodeKeepgoing (bool):
                if ``True`` will continue execution on other nodes regardless of job failure
            asUser (str):
                username identifying the user who executed the command, requires runAs permission
            scriptInterpreter (str):
                command to use to execute the script (requires API version >= 8)
            interpreterArgsQuoted (bool):
                if ``True`` script and file args will be quoted and passed as the last argument to ``scriptInterpreter``
                (requires API version >= 8)
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
            exclude os-family (str):
                os-family exclusion filter
            exclude-os-arch (str):
                os-arch exclusion filter
            exclude-os-version (str):
                os-version exclusion filter
            exclude-name (str):
                name exclusion filter
        '''
        self.requires_version(4)

        data = cull_kwargs(('argString', 'nodeThreadcount', 'nodeKeepgoing', 'asUser',
                            'scriptInterpreter', 'interpreterArgsQuoted', 'hostname', 'tags', 'os-name',
                            'os-family', 'os-arch', 'os-version', 'name', 'exclude-hostname', 'exclude-tags',
                            'exclude-os-name', 'exclude-os-family', 'exclude-os-arch', 'exclude-os-version',
                            'exclude-name'), kwargs)

        data['project'] = project
        data['scriptURL'] = scriptURL

        if ('scriptInterpreter' in data) or ('interpreterArgsQuoted' in data):
            self.requires_version(8)

        argString = data.get('argString', None)
        if argString is not None:
            data['argString'] = dict2argstring(argString)

        return self._exec(POST, 'run/url', data=data, **kwargs)

    def _post_projects(self, project, **kwargs):
        '''
        Wraps Rundeck API POST /projects <http://rundeck.org/docs/api/index.html#project-creation>

        Returns class ``rundeck.connection.RundeckResponse``

        Requires API version > 11

        :param project:
            (str) name of the project

        :keyword args:
            config (dict):
                dictionary of key/value pairs of the project configuration
        '''
        self.requires_version(11)

        config = kwargs.pop('config', None)

        prop_tmpl = '<property key="{0}" value="{1}" />'
        config_tmpl = '  <config>\n' + \
                      '    {0}\n' + \
                      '  </config>\n'
        project_tmpl = '<project>\n' + \
                       '  <name>{0}</name>\n' + \
                       '{1}</project>'

        if config is not None:
            props_xml = '    \n'.join([prop_tmpl.format(k, v) for k, v in config.items()])
            config_xml = config_tmpl.format(props_xml)
        else:
            config_xml = ''

        xml = project_tmpl.format(project, config_xml)
        print(xml)

        headers = {'Content-Type': 'application/xml'}

        return self._exec(POST, 'projects', data=xml, headers=headers, **kwargs)

    def _get_projects(self, **kwargs):
        '''
        Wraps Rundeck API GET /projects <http://rundeck.org/docs/api/index.html#listing-projects>

        Returns class ``rundeck.connection.RundeckResponse``
        '''
        return self._exec(GET, 'projects', **kwargs)

    def project(self, project, **kwargs):
        '''
        Wraps Rundeck API /project/[NAME] <http://rundeck.org/docs/api/index.html#getting-project-info>

        Returns class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of the project
        
        :keyword args:
            create (bool):
                [default: ``True``]
                if ``True`` create the project if it does not exist (requires API version > 11)
        '''
        # Check if ``kwargs['create']`` is True
        create = kwargs.pop('create', None)
        if create is None:
            if self.connection.api_version >= 11:
                create = True
            else:
                create = False
        elif create == True:
            self.requires_version(11)

        rd_url = 'project/{0}'.format(urlquote(project))

        project = None
        try:
            project = self._exec(GET, rd_url, **kwargs)
        except HTTPError as exc:
            if create:
                project = self._exec(POST, rd_url, **kwargs)
            else:
                raise

        return project

    def project_resources(self, project, **kwargs):
        '''
        Wraprs Rundeck API GET /project/[NAME]/resources <http://rundeck.org/docs/api/index.html#updating-and-listing-resources-for-a-project>

        Returns class ``rundeck.conection.RundeckResponse``

        :param project:
            (str) name of the project

        :keyword args:
            fmt (str):
                [default: 'text']
                the format of the response of ``rundeck.defaults.ExecutionOutputFormat`` values
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
        self.requires_version(2)

        params = cull_kwargs(('fmt', 'scriptInterpreter', 'interpreterArgsQuoted', 'hostname',
                              'tags', 'os-name', 'os-family', 'os-arch', 'os-version', 'name', 'exclude-hostname',
                              'exclude-tags', 'exclude-os-name', 'exclude-os-family', 'exclude-os-arch',
                              'exclude-os-version', 'exclude-name'), kwargs)

        if 'fmt' in params:
            params['format'] = params.pop('fmt')

        return self._exec(GET, 'project/{0}/resources'.format(urlquote(project)), params=params, **kwargs)

    def project_resources_update(self, project, nodes, **kwargs):
        '''
        Wraps RUndeck API POST /project/[NAME]/resources <http://rundeck.org/docs/api/index.html#updating-and-listing-resources-for-a-projects>

        Returns class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of the project
        :param nodes:
            (list) list of RundeckNode objects
        '''
        headers = {'Content-Type': 'text/xml'}

        data = '<nodes>{0}</nodes>'.format('\n'.join([node.xml for node in nodes]))

        return self._exec(POST, 'project/{0}/resources'.format(urlquote(project)), data=data, headers=headers, **kwargs)

    def project_resources_refresh(self, project, providerURL=None, **kwargs):
        '''
        Wraps Rundeck API POST /project/[NAME]/resources/refresh <http://rundeck.org/docs/api/index.html#refreshing-resources-for-a-project>

        Returns class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of the project
        :param providerURL:
            (str) Resource Model Provider URL to refresh the resources from, if not specified, provider URL
            from ``project.properties`` file is used
        '''
        self.requires_version(2)

        data = {}
        if providerURL is not None:
            data['providerURL'] = providerURL

        return self._exec(POST, 'project/{0}/resources/refresh'.format(project), data=data, **kwargs)

    def history(self, project, **kwargs):
        '''
        Wraps Rundeck API GET /history <http://rundeck.org/docs/api/index.html#listing-history>

        Returns class ``rundeck.connection.RundeckResponse``

        :param project:
            (str) name of the project

        :keyword args:
            jobIdFilter (str):
                include event for a job ID
            reportIdFilter (str):
                include events for an event name
            userFilter (str):
                include events created by user in ``userFilter``
            startFilter (str):
                one of ``rundeck.defaults.Status`` values
            jobListFilter (str or list):
                one or more full job group/name to include
            excludeJobListFilter (str or list):
                one or more full job group/name to include
            recentFilter (str):
                Text format to filter executions that completed with certain period of time, format:
                'XY' where 'X' is an integer and 'Y' is one of the following:

                    * 'h': hour
                    * 'd': day
                    * 'w': week
                    * 'm': month
                    * 'y': year

                Value of '2w' returns executions that completed within the last two weeks
            begin (int or str):
                either a unix millisecond timestamp or W3C date time 'yyyy-MM-ddTHH:mm:ssZ'
            end (int or str):
                either a unix millisecond timestamp or a W3C date time 'yyyy-MM-ddTHH:mm:ssZ'
            max (int):
                [default: 20]
                max number of results to include in response
            offset (int):
                [default: 0]
                offset for result
        '''
        self.requires_version(4)
        params = cull_kwargs(('jobIdFilter', 'reportIdFilter', 'userFilter', 'startFilter',
                              'jobListFilter', 'excludeJobListFilter', 'recentFilter', 'begin', 'end', 'max',
                              'offset'), kwargs)

        params['project'] = project
        return self._exec(GET, 'history', params=params, **kwargs)


class RundeckApi(RundeckApiTolerant):
    '''
    Same as ``RundeckApiTolerant``
    '''
    def _exec(self, method, url, params=None, data=None, parse_response=True, **kwargs):
        quiet = kwargs.get('quiet', False)

        result = super(RundeckApi, self)._exec(
            method, url, params=params, data=data, parse_response=parse_response, **kwargs
        )

        if not quiet and parse_response:
            result.raise_for_error()

        return result