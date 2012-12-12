#!/usr/bin/env python

import atexit
import os
import sys

from subprocess import *


def readline(prompt):
    try:
        return raw_input(prompt)
    except KeyboardInterrupt:
        sys.exit(1)


def execute(command, ignore_errors=False):
    process = Popen(command,
                    stdin=PIPE,
                    stdout=PIPE,
                    stderr=STDOUT,
                    shell=False)
    data = process.stdout.read()
    status = process.wait()
    if status != 0 and not ignore_errors:
        cmdline = ' '.join(command) if isinstance(command, list) else command
        print 'Failed to execute: \'' + cmdline + '\':'
        print data
        sys.exit(1)
    elif status != 0:
        return None
    return data


# TODO(benh): Make sure this is a git repository, apologize if not.
top_level_dir = execute(['git', 'rev-parse', '--show-toplevel']).strip()

repository = 'git://git.apache.org/mesos.git'

parent_branch = 'trunk'

branch_ref = execute(['git', 'symbolic-ref', 'HEAD']).strip()
branch = os.path.basename(branch_ref)

temporary_branch = '_post-reviews_' + branch

# Always delete the temporary branch.
atexit.register(lambda: execute(['git', 'branch', '-D', temporary_branch], True))

# Always put us back on the original branch.
atexit.register(lambda: execute(['git', 'checkout', branch]))

merge_base = execute(['git', 'merge-base', parent_branch, branch_ref]).strip()


print 'Running post-review across all of ...'

call(['git',
      'log',
      '--pretty=format:%Cred%H%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr)%Creset',
      merge_base + '..HEAD'])

log = execute(['git',
               'log',
               '--pretty=oneline',
               '--reverse',
               merge_base + '..HEAD']).strip()

shas = []

for line in log.split('\n'):
    sha = line.split()[0]
    shas.append(sha)


previous = 'trunk'
for i in range(len(shas)):
    sha = shas[i]

    execute(['git', 'branch', '-D', temporary_branch], True)

    message = execute(['git',
                       'log',
                       '--pretty=format:%B',
                       previous + '..' + sha])

    review_request_id = None

    if message.find('Review: ') != -1:
        url = message[(message.index('Review: ') + len('Review: ')):].strip()
        # TODO(benh): Handle bad (or not Review Board) URLs.
        review_request_id = os.path.basename(url.strip('/'))

    # Show the commit.
    if review_request_id is None:
        print '\nCreating diff of:\n'
        call(['git',
              'log',
              '--pretty=format:%Cred%H%Creset -%C(yellow)%d%Creset %s',
              previous + '..' + sha])
    else:
        print '\nUpdating diff of:\n'
        call(['git',
              'log',
              '--pretty=format:%Cred%H%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr)%Creset',
              previous + '..' + sha])

    # Show the "parent" commit(s).
    print '\n... with parent diff created from:\n'
    call(['git',
          'log',
          '--pretty=format:%Cred%H%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr)%Creset',
          parent_branch + '..' + previous])

    try:
        raw_input('\nPress enter to continue or \'Ctrl-C\' to skip.\n')
    except KeyboardInterrupt:
        i = i + 1
        previous = sha
        continue

    revision_range = previous + ':' + sha

    if review_request_id is None:
        output = execute(['post-review',
                          '--repository-url=' + repository,
                          '--tracking-branch=' + parent_branch,
                          '--revision-range=' + revision_range] + sys.argv[1:]).strip()
    else:
        output = execute(['post-review',
                          '--review-request-id=' + review_request_id,
                          '--repository-url=' + repository,
                          '--tracking-branch=' + parent_branch,
                          '--revision-range=' + revision_range] + sys.argv[1:]).strip()

    print output

    if review_request_id is not None:
        i = i + 1
        previous = sha
        continue

    lines = output.split('\n')
    url = lines[len(lines) - 1]
    url = url.strip('/')

    # Construct new commit message.
    message = message + '\n' + 'Review: ' + url + '\n'

    execute(['git', 'checkout', '-b', temporary_branch])
    execute(['git', 'reset', '--hard', sha])
    execute(['git', 'commit', '--amend', '-m', message])

    # Now rebase all remaining shas on top of this amended commit.
    j = i + 1
    old_sha = execute(['cat', os.path.join(top_level_dir, '.git/refs/heads', temporary_branch)]).strip()
    previous = old_sha
    while j < len(shas):
        execute(['git', 'checkout', shas[j]])
        execute(['git', 'rebase', temporary_branch])
        # Get the sha for our detached HEAD.
        new_sha = execute(['git', 'log', '--pretty=format:%H', '-n', '1', 'HEAD']).strip()
        execute(['git',
                 'update-ref',
                 'refs/heads/' + temporary_branch,
                 new_sha,
                 old_sha])
        old_sha = new_sha
        shas[j] = new_sha
        j = j + 1

    # Okay, now update the actual branch to our temporary branch.
    new_sha = old_sha
    old_sha = execute(['cat', os.path.join(top_level_dir, '.git/refs/heads', branch)]).strip()
    execute(['git', 'update-ref', 'refs/heads/' + branch, new_sha, old_sha])

    i = i + 1
