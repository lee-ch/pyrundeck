'''
Python module for the Rundeck API
'''
from __future__ import absolute_import, print_function, unicode_literals


def enum(name, *seq, **named):
    values = dict(zip(seq, range(len(seq))), **named)
    values['values'] = list(values.values())
    values['keys'] = list(values.keys())
    # ``unicode_literals`` requires a ``str`` passed into ``type``
    # as first arg
    return type(str(name), (), values)


Status = enum(
    'Status',
    RUNNING='running',
    SUCCEEDED='succeeded',
    FAILED='failed',
    ABORTED='aborted',
    SKIPPED='skipped',
    PENDING='pending'
)

DupeOption = enum(
    'DupeOption',
    SKIP='skip',
    CREATE='create',
    UPDATE='update'
)

UuidOption = enum(
    'UuidOption',
    PRESERVE='preserve',
    REMOVE='remove'
)

JobDefFormat = enum(
    'JobDefFormat',
    XML='xml',
    YAML='yaml'
)

ExecutionOutputFormat = enum(
    'ExecutionOutputFormat',
    TEXT='text',
    **dict(zip(JobDefFormat.keys, JobDefFormat.values))
)

RUNDECK_API_VERSION = 11
GET = 'get'
POST = 'post'
DELETE = 'delete'
JOB_RUN_TIMEOUT = 60
JOB_RUN_INTERVAL = 3
