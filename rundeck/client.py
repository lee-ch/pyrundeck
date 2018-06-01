'''
Python module for the Rundeck API
'''
from __future__ import absolute_import, print_function, unicode_literals # TODO: Test api, util and client classes
import time
import errno
import datetime

from string import ascii_letters, digits
try:
    from string import maketrans
except ImportError:
    # Python 3
    maketrans = str.maketrans

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
    JobDefFromat,
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
        return job_id.translate(_JOB_TO_TRANS_TAB) == _JOB_TO_TEMPLATE

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