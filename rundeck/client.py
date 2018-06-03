'''
Python module for the Rundeck API
'''
from __future__ import absolute_import, print_function, unicode_literals # TODO: Test api, util and client classes
import os
import time
import errno
import datetime

from string import ascii_letters, digits
try:
    from string import maketrans
except ImportError:
    maketrans = str.maketrans # Python 3

from rundeck.api import RundeckApiTolerant, RundeckApi, RundeckNode
from rundeck.connection import RundeckConnection, RundeckResponse
from rundeck.transforms import transform
from rundeck.util import child2dict, attr2dict, cull_kwargs, StringType
from rundeck.exceptions import (
    RundeckServerError,
    JobNotFound,
    MissingProjectArgument,
    InvalidJobArgument,
    InvalidResponseFormat,
    InvalidJobDefinitionFormat,
    InvalidResourceSpecification)
from rundeck.defaults import (
    GET,
    POST,
    DELETE,
    Status,
    DupeOption,
    UuidOption,
    JobDefFormat,
    JOB_RUN_TIMEOUT,
    JOB_RUN_INTERVAL)



_JOB_TO_CHARS = ascii_letters + digits
_JOB_TO_TRANS_TAB = maketrans(_JOB_TO_CHARS, '#' * len(_JOB_TO_CHARS))
_JOB_ID_TEMPLATE = '########-####-####-####-############'
_RUNDECK_RESP_FORMATS = ('xml')
_EXECUTION_COMPLETED = (Status.FAILED, Status.SUCCEEDED, Status.ABORTED)
_EXECUTION_PENDING = (Status.RUNNING,)


def is_job_id(job_id):
    '''
    Checks if a job ID is a UUID

    Returns ``bool``
    
    :param job_id:
        (str) Rundeck job ID
    '''
    if job_id and isinstance(job_id, StringType):
        return job_id.translate(_JOB_TO_TRANS_TAB) == _JOB_ID_TEMPLATE

    return False


class Rundeck(object):

    def __init__(self, server='localhost', protocol='http', port=4440, api_token=None, **kwargs):
        '''
        Initialize Rundeck API client

        :param server:
            [default: 'localhost']
            (str) hostname of the Rundeck server
        :param protocol:
            [default: 'http']
            (str) protocol to use (http or https)
        :param port:
            [default: 4440]
            (int) port number of Rundeck
        :param api_token:
            (str) Rundeck user API token

        :keyword args:
            base_path (str):
                [default: None]
                base URL path for Rundeck server URLs
            usr (str):
                Rundeck user name, used in place of ``api_token``
            pwd (str):
                Rundeck user password, used with ``usr``
            api_version (int)
                Rundeck API version
            api (``RundeckApi``):
                ``RundeckApi`` instance or subclass of ``RundeckApi``
            connection (``RundeckConnection``):
                instance of ``RundeckConnection`` instance or subclass of ``RundeckConnection``
        '''
        api = kwargs.pop('api', None)

        if api is None:
            self.api = RundeckApi(
                server, protocol=protocol, port=port, api_token=api_token, **kwargs
            )
        elif isinstance(api, RundeckApiTolerant):
            self.api = api
        else:
            raise Exception('Supplied api argument is not a valid RundeckApi: {0}'.format(api))

    @transform('system_info')
    def system_info(self, **kwargs):
        '''
        Get Rundeck server system info

        Returns ``dict`` of Rundeck system info
        '''
        return self.api.system_info(**kwargs)

    def get_job_id(self, project, name=None, **kwargs):
        '''
        Fetch job ID that matches the filter criteria specified

        Returns Rundeck job ID

        :param project:
            (str) name of a project
        :param name:
            [default: ``None``]
            (str) name of job to match
        
        :keyword args:
            idlist (str or list(str, ...)):
                comma separated string or list of job IDs to include
            groupPath (str):
                [default: '*']
                specify a group pf partial group path to include all jobs within that group path
                or '*' for all groups or '-' to match top level jobs only
            jobFilter (str):
                job name filter, matches any job name that contains ``jobFilter`` string
            jobExactFilter (str):
                specify an exact job name to match
            groupPathExact (str):
                specify exact group path to match or '-' to match top level jobs only
        '''
        if name is not None:
            kwargs['jobExactFilter'] = name

        try:
            job_list = self.get_job_ids(project, limit=1, **kwargs)
        except JobNotFound:
            raise JobNotFound('Job {0!r} not found in Project {1!r}'.format(name, project))
        else:
            return job_list[0]

    def get_job_ids(self, project, **kwargs):
        '''
        Fetch list of job IDs that match the filter criteria specified

        Returns ``list`` of job IDs

        :param project:
            (str) name of a project
        
        :keyword args:
            limit (int):
                limit the result set to 1 or more jobs
            idlist (str or list(str, ...)):
                specify comma-separated string or list of job IDs to include
            groupPath (str):
                [default: '*']
                specify a group or partial group path to include all jobs within that group path or '*'
                for all groups or '-' to match top level jobs only
            jobFilter (str):
                specify a job name filter, will match any job name containing ``jobFilter`` string
            jobExactFilter (str):
                specify exact job name to match
            groupPathExact (str):
                specify an exact group path to match or '-' to match top level jobs only
        '''
        limit = kwargs.pop('limit', None)
        resp = self.list_jobs(project, **kwargs)
        jobs = resp

        job_ids = []
        if len(jobs) > 0:
            job_ids = [job['id'] for job in jobs]
        else:
            raise JobNotFound(
                'No jobs in Project {0!r} matching criteria'.format(project)
            )

        # Return jobs limited by ``limit`` or all jobs if ``limit`` is ``None``
        return job_ids[:limit]

    @transform('jobs')
    def list_jobs(self, project, **kwargs):
        '''
        Fetch a list of jobs from ``project``

        Returns ``list`` of jobs

        :param project:
            (str) name of a project

        :keyword args:
            limit (int):
                limit the result set to 1 or more jobs
            idlist (str or list(str, ...)):
                comma-separated string or ``list`` of job IDs to include
            groupPath (str):
                [default: '*']
                group or partial group path to include all jobs within that group path
                or '*' for all groups, or '-' to match the top level jobs only
            jobFilter (str):
                job name filter, matches any job name that contains ``jobFilter`` string
            jobExactFilter (str):
                exact job name to match
            groupPathExact (str)
                exact group path to match or '-' to match the top level jobs only
        '''
        jobs = self.api.jobs(project, **kwargs)
        jobs.raise_for_error()
        return jobs

    def run_job(self, job_id, **kwargs):
        '''
        Wraps ``job_run`` method from ``rundeck.api.RundeckApi`` and implements
        a blocking mechanism to wait for the job to complete

        Returns ``self.execution_status``

        :param job_id:
            (str) Rundeck job ID

        :keyword args:
            timeout (int or float):
                [default: 60]
                number of seconds to wait for a completed status
            interval (int or float):
                [default: 3]
                number of seconds to sleep between polling cycles
        '''
        timeout = kwargs.pop('timeout', JOB_RUN_TIMEOUT)
        interval = kwargs.pop('interval', JOB_RUN_INTERVAL)

        execution = self._run_job(job_id, **kwargs)

        exec_id = execution['id']
        start = time.time()
        duration = 0

        while (duration < timeout):
            execution = self.execution_status(exec_id)
            try:
                exec_status = execution['status']
            except AttributeError:
                if duration == 0:
                    continue

            if exec_status in _EXECUTION_COMPLETED:
                break

            time.sleep(interval)
            duration = time.time() - start

        return execution

    @transform('execution')
    def _run_job(self, job_id, **kwargs):
        '''
        Executes Rundeck job

        Returns job execution info

        :param job_id:
            (str) Rundeck job ID

        :keyword args:
            argString (str or dict):
                argument string to pass to job, if ``str``, pass as is, otherwise
                if ``dict`` will be converted to compatible string
            loglevel (str):
                [default: 'INFO']
                logging level, i.e: 'DEBUG', 'VERBOSE', 'INFO', 'WARN', 'ERROR'
            asUser (str):
                user to execute the job as
            exclude-precedence (bool):
                [default: ``True``]
                set exclusion precedence
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
        return self.api.job_run(job_id, **kwargs)

    def jobs_export(self, project, **kwargs):
        '''
        Export job definitions for a project (XML or YAML)

        Returns job definition

        :param project:
            (str) name of a project

        :keyword args:
            fmt (str):
                [default: 'xml']
                format of the definition string
            idlist (list):
                list of job ids to return
            groupPath (str):
                group path, partial group path or special top level only character '-'
            jobFilter (str):
                find job names matching ``jobFilter`` string
        '''
        return self.api.jobs_export(project, **kwargs).text

    @transform('job_import_status')
    def import_job(self, definition, **kwargs):
        '''
        Import job definition string (XML or YAML)

        Return results of job import

        :param definition:
            ``string`` representing a job definition
        
        :keyword args:
            fmt (str):
                [default: 'xml']
                format of the definition sting
            dupeOption (str):
                [default: 'create']
                'skip', 'create' or 'update' value to indicate behavior when importing jobs that
                already exist
            project (str):
                the project all job definitions should be imported to, otherwise all job definitions
                must define a project
            uuidOption (str):
                'preserve' or 'remove', preserve or remove UUIDs in imported jobs, preserve may
                fail if a UUID already exists
        '''
        return self.api.jobs_import(definition, **kwargs)

    def import_job_file(self, file_path, **kwargs):
        '''
        Read contents of a job definition file to import

        Returns ``dict`` representing a set of Rundeck status messages

        :paam file_path:
            (str) path to a readable job definition file

        :keyword args:
            file_format (str):
                [default: 'xml']
                'xml' or 'yaml', if not specified, will be derived from the file extension
        '''
        fmt = kwargs.pop('file_format', None)
        if fmt is None:
            fmt = JobDefFormat.XML
            fmt_specified = False
        else:
            fmt_specified = True

        definition = open(file_path, 'r').read()

        if not fmt_specified:
            # Get file extension
            fmt = os.path.splitext(file_path.strip())[1][1:].lower()

        if fmt not in JobDefFormat.values:
            raise InvalidJobDefinitionFormat(
                'Invalid job definition format: \'{0}\''.format(fmt)
            )

        return self.import_job(definition, fmt=fmt, **kwargs)

    def export_job(self, job_id, **kwargs):
        '''
        Export job definition XML or YAMLL format

        Returns: job definition

        :param job_id:
            (str) Rundeck job ID

        :keyword args:
            fmt (str):
                [default: 'xml']
                format of the response of ``JobDefFormat.values``
        '''
        return self.api.job(job_id, **kwargs)

    def delete_job(self, job_id, **kwargs):
        '''
        Deletes a job

        Returns: ``bool``

        :param job_id:
            (str) Rundeck job ID
        '''
        result = self.api.delete_job(job_id, **kwargs)
        # API version 11 returns a 204 No Content, lder versions use the result xml node
        if self.api_version >= 11:
            if result.response.status_code == 204:
                return True
            else:
                return False
        else:
            rd_msg = RundeckResponse(result)
            return rd_msg.success

    def delete_jobs(self, idlist, **kwargs):
        '''
        Multi job deletion

        Returns: ``list`` of deleted jobs / response

        :param idlist:
            (str or list) ``str`` or ``list`` of job ids or string of comma separated job ids
            to delete

        Example response:
            {
            'requestCount': 3,
            'allsuccessful': False,
            'succeeded': {
                'id': '1234-456-789-012345',
                'message': 'success',
            },
            'failed': {
                'id': '9876-543-210-9876543',
                'message': 'Job ID 9876-543-210-9876543 does not exist',
            },
            }
        '''
        if isinstance(idlist, StringType):
            idlist = idlist.split(',')

        results = []
        for id in idlist:
            result = None
            try:
                result = self.delete_job(id)
            except RundeckServerError as exc:
                result = exc.rundeck_response
            results.append(result)

        return results

    @transform('executions')
    def list_job_executions(self, job_id, **kwargs):
        '''
        Get list of executions of a job

        Returns: ``list`` of job executions

        :param job_id:
            (str) job ID

        :keyword args:
            status (str):
                ``Status.values``
            max (int):
                [default: 20]
                max number of results to included in response
            offset (int):
                [default: 0]
                offset for result
        '''
        return self.api.job_executions(job_id, **kwargs)

    @transform('executions')
    def list_running_executions(self, project='*', **kwargs):
        '''
        Retrieve running executions

        Returns: ``list`` job executions

        :param project:
            (str) name of a project, use '*' for all project (API >= 9)
        '''
        return self.api.executions_running(project, **kwargs)

    @transform('execution')
    def execution_status(self, execution_id, **kwargs):
        '''
        Get status of an execution

        Returns ``dict`` execution

        :param execution_id:
            (int) Rundeck job execution ID
        '''
        return self.api.execution(execution_id, **kwargs)

    @transform('executions')
    def query_executions(self, project, **kwargs):
        '''
        Execution query

        Returns: ``list`` job executions

        :param project:
            (str) name of project

        :keyword args:
            statusFilter (str):
                ``Status.values``
            abortedbyFilter (str):
                username that aborted execution
            userFilter (str):
                username that initiated execution
            recentFilter (str):
                text format to filter executions completed within a period of time,
                format is 'XY' where 'X' is an integer and 'Y' is one of the
                following:

                    * 'h': hour
                    * 'd': day
                    * 'w': week
                    * 'm': month
                    * 'y': year

                value of '2w' would return executions completed from the past two weeks

            begin (int | str):
                unix millisecond timestamp or W3C date time 'yyyy-MM-ddTHH:mm:ssZ'
            end (int | str):
                unix millisecond timestamp or W3C date time 'yyyy-MM-ddTHH:mm:ssZ'
            adhoc (bool):
                if ``True`` includes adhoc executions
            jobIdListFilter (str | list):
                one or more job ids to include
            excludeJobIdListFilter (str | list):
                one or more job ids to exclude
            jobListFilter (str | list):
                one or more full job group/name to include
            excludeJobListFilter (str | list):
                one or more full job group/name to exclude
            groupPath (str):
                group or partial group path to include, special '-' setting matches top level
                jobs only
            excludeGroupPath (str):
                group or partial group path to exclude, special '-' setting matches top level
                jobs only
            excludeGroupPathExact (str):
                exact group path to exclude, special '-' setting matches top level jobs only
            jobExactFilter (str):
                exact job name
            excludeJobExactFilter (str):
                exact job name to exclude
            max (int):
                [default: 20]
                maximum number of results to include in response
            offset (int):
                [default: 0]
                offset for results
        '''
        return self.api.executions(project, **kwargs)

    @transform('execution_output')
    def _execution_output_json(self, execution_id, **kwargs):
        return self.api.execution_output(execution_id, **kwargs)

    def get_execution_output(self, execution_id, **kwargs):
        '''
        Get output for an execution in various formats

        Returns: ``str`` | ``dict`` | ``RundeckResponse``

        :param execution_id:
            (str) Rundeck job execution ID

        :keyword args:
            fmt (str):
                [default: 'json']
                format of the response of ``ExecutionOutputFormat.values``
            raw (bool):
                [default: ``False``]
                if ``True`` returns results of ``Exception`` output request unmodified
            offset (int):
                byte offset to read from in the file, 0 indicates the beginning
            lastlines (int):
                number of lines to retrieve from the end of available output, overrides offset
            lastmod (int):
                unix millisecond timestamp, return output data received after ``lastmod`` timestamp
            maxlines (int):
                maximum number of lines to retrieve forward from the specified ``offset``
        '''
        raw = kwargs.pop('raw', None)
        fmt = kwargs.pop('fmt', None)
        if fmt is None and raw is None:
            fmt = 'json'
            raw = False

        if fmt is None:
            fmt = 'xml'

        if raw or fmt == 'text':
            return self.api.execution_output(execution_id, fmt=fmt, **kwargs).text
        elif fmt == 'json':
            return self._execution_output_json(execution_id, fmt=fmt, **kwargs)
        elif fmt == 'xml':
            return self.api.execution_output(execution_id, fmt=fmt, parse_response=True, **kwargs)

    @transform('execution_abort')
    def abort_execution(self, execution_id, **kwargs):
        '''
        Abort running job execution

        Returns: ``dict`` abort status information

        :param execution_id:
            (str) Rundeck job execution ID

        :keyword args:
            asUser (str):
                username identifying the user who aborted job execution
        '''
        return self.api.execution_abort(execution_id, **kwargs)

    @transform('run_execution')
    def run_adhoc_command(self, project, command, **kwargs):
        '''
        Run a command

        Returns: ``int`` execution ID

        :param project:
            (str) name of the project
        :param command:
            (str) shell command string to execute

        :keyword args:
            nodeThreadcount (int):
                number of threads to use
            nodeKeepgoing (bool):
                if ``True`` continue execution on remaining nodes regardless of failures
            asUser (str):
                username identifying the user who ran the command, requires runAs permission
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
        return self.api.run_command(project, command, **kwargs)

    @transform('run_execution')
    def run_adhoc_script(self, project, scriptFile, **kwargs):
        '''
        Execute script via URL

        Returns: ``int`` execution ID

        :param project:
            (str) name of the project
        :param scriptFile:
            (str) string containg the script file content

        :keyword args:
            nodeThreadcount (int):
                number of threads to use
            nodeKeepgoing (bool):
                if ``True`` continue execution on remaining nodes regardless of failures
            asUser (str):
                username identifying the user who ran the command, requires runAs permission
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
        return self.api.run_script(project, scriptFile, **kwargs)

    @transform('run_execution')
    def run_adhoc_url(self, project, scriptUrl, **kwargs):
        '''
        Execute script via URL

        Returns: ``int`` execution ID

        :param project:
            (str) name of the project
        :param scriptUrl:
            (str) URL of the script to execute

        :keyword args:
            nodeThreadcount (int):
                number of threads to use
            nodeKeepgoing (bool):
                if ``True`` continue execution on remaining nodes regardless of failures
            asUser (str):
                username identifying the user who ran the command, requires runAs permission
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
        return self.api.run_url(project, scriptUrl, **kwargs)

    @transform('projects')
    def list_projects(self, **kwargs):
        '''
        Get list of projects

        Returns ``list`` of Rundeck projects
        '''
        return self.api.projects(GET, **kwargs)

    @transform('project')
    def get_project(self, project, **kwargs):
        '''
        Fetch ``project`` details

        Returns: ``dict`` project information

        :param project:
            (str) name of a project
        '''
        return self.api.project(project, **kwargs)
        
    @transform('project')
    def create_project(self, project, **kwargs):
        '''
        Creates a project

        Returns: ``dict`` project information of newly created project

        :param project:
            (str) name of the project

        :keyword args:
            config (dict):
                ``dict`` of key/value pairs for the project config
        '''
        return self.api.projects(POST, project=project, **kwargs)

    @transform('project_resources')
    def _project_resources(self, project, **kwargs):
        '''
        Transforms a ``Rundeck.project_resources`` response
        '''
        return self.api.project_resources(project, **kwargs)

    def list_project_resources(self, project, **kwargs):
        '''
        Retrieve list of resources for a project, if `fmt` is not supplied, ``dict``
        is returned

        Returns: ``list`` of resources or a string representing requested resources
        in requested format

        :param project:
            (str) name of the project

        :keyword args:
            nodeThreadcount (int):
                number of threads to use
            nodeKeepgoing (bool):
                if ``True`` continue execution on remaining nodes regardless of failures
            asUser (str):
                username identifying the user who ran the command, requires runAs permission
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
        fmt = kwargs.pop('fmt', 'python')

        if fmt is 'python':
            return self._project_resources(project, quiet=True, **kwargs)
        else:
            return self.api.project_resources(project, fmt=fmt, parse_response=False, **kwargs).text

    @transform('success_message')
    def update_project_resources(self, project, nodes, **kwargs):
        '''
        Update resources for a project

        Returns: ``dict`` success message

        :param project:
            (str) name of the project
        :param nodes:
            (list) list of nodes in the form of a three ``tuple`` (name, hostname, username) or
            ``dict`` with at least the following keys: 'name', 'hostname', and 'username'
        '''
        if isinstance(nodes, tuple):
            nodes = [nodes]
        elif isinstance(nodes, dict):
            nodes = [nodes]
        elif not isinstance(nodes, list):
            raise InvalidResourceSpecification(
                '\'nodes\' must be a tuple, dictionary or list of tuples / dictionaries'
            )

        required_keys = ('name', 'hostname', 'username')
        rundeck_nodes = []
        for node in nodes:
            if isinstance(node, dict) and set(node.keys()).issuperset(required_keys):
                rundeck_nodes.append(
                    RundeckNode(
                        node.pop('name'),
                        node.pop('hostname'),
                        node.pop('username'),
                        **node
                    )
                )
            elif isinstance(node, tuple) and len(node) == 3:
                rundeck_nodes.append(RundeckNode(*node))

        if len(rundeck_nodes) > 0:
            return self.api.project_resources_update(project, rundeck_nodes, **kwargs)
        else:
            return InvalidResourceSpecification('No valid nodes provided')

    @transform('success_message')
    def refresh_project_resources(self, project, providerURL=None, **kwargs):
        '''
        Refresh resources for a project via its Resource Model Provider URL

        Returns: ``dict`` success message

        :param project:
            (str) name of the project
        :param providerURL:
            (str) Resource Model Provider URL to refresh resources from, otherwsie
            the configured provider URL in ``project.properties`` file is used
        '''
        return self.api.project_resources_refresh(project, providerURL=providerURL, **kwargs)

    @transform('events')
    def get_project_history(self, project, **kwargs):
        '''
        List history events for ``project``

        Returns: ``RundeckResponse``

        :param project:
            (str) name of the project
        
        :keyword args:
            statusFilter (str):
                ``Status.values``
            abortedbyFilter (str):
                username that aborted execution
            userFilter (str):
                username that initiated execution
            recentFilter (str):
                text format to filter executions completed within a period of time,
                format is 'XY' where 'X' is an integer and 'Y' is one of the
                following:

                    * 'h': hour
                    * 'd': day
                    * 'w': week
                    * 'm': month
                    * 'y': year

                value of '2w' would return executions completed from the past two weeks

            begin (int | str):
                unix millisecond timestamp or W3C date time 'yyyy-MM-ddTHH:mm:ssZ'
            end (int | str):
                unix millisecond timestamp or W3C date time 'yyyy-MM-ddTHH:mm:ssZ'
            adhoc (bool):
                if ``True`` includes adhoc executions
            jobIdListFilter (str | list):
                one or more job ids to include
            excludeJobIdListFilter (str | list):
                one or more job ids to exclude
            jobListFilter (str | list):
                one or more full job group/name to include
            excludeJobListFilter (str | list):
                one or more full job group/name to exclude
            groupPath (str):
                group or partial group path to include, special '-' setting matches top level
                jobs only
            excludeGroupPath (str):
                group or partial group path to exclude, special '-' setting matches top level
                jobs only
            excludeGroupPathExact (str):
                exact group path to exclude, special '-' setting matches top level jobs only
            jobExactFilter (str):
                exact job name
            excludeJobExactFilter (str):
                exact job name to exclude
            max (int):
                [default: 20]
                maximum number of results to include in response
            offset (int):
                [default: 0]
                offset for results
        '''
        return self.api.history(project, **kwargs)