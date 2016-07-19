from django.core.urlresolvers import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.crypto import get_random_string

from .github_api import get_repo, create_file, update_file
from .exceptions import RevisionNotFoundException, RevisionFileNotFoundException

CONTENT_PATH = 'pages/'
REVISIONS_LOG_FOLDER = 'content-revision-logs/'
BRANCH_NAMESPACE = 'content-'
BASE_BRANCH = 'develop'

LABEL_IN_PROGRESS = 'do not merge'
LABEL_IN_REVIEW = 'for review'


def abs_path(path):
    if path.startswith('/'):
        return path
    return '/{}'.format(path)


def get_verba_branch_name(revision_id):
    return '{}{}'.format(BRANCH_NAMESPACE, revision_id)


def is_verba_branch(name):
    return name.startswith(BRANCH_NAMESPACE)


def get_revision_id(verba_branch_name):
    if not is_verba_branch(verba_branch_name):
        return None
    return verba_branch_name[len(BRANCH_NAMESPACE):]


class RevisionFile(object):
    def __init__(self, repo, revision_id, gitfile):
        assert gitfile.path.startswith(CONTENT_PATH)

        self.revision_id = revision_id
        self._repo = repo
        self._gitfile = gitfile

    @property
    def branch_name(self):
        return get_verba_branch_name(self.revision_id)

    @property
    def name(self):
        return self._gitfile.name

    @property
    def path(self):
        return self._gitfile.path[len(CONTENT_PATH):]

    @property
    def content(self):
        return self._gitfile.decoded_content

    def change_content(self, new_content):
        update_file(
            self._repo,
            path=abs_path(self._gitfile.path),
            message='[ci skip] Change file {}'.format(self.path),
            content=new_content,
            branch=self.branch_name
        )

    def get_absolute_url(self):
        return reverse('revision:file-detail', args=[self.revision_id, self.path])


class Revision(object):
    def __init__(self, repo, revision_id, pull):
        self.id = revision_id
        self._repo = repo
        self._pull = pull

    @property
    def _issue(self):
        issue_id = int(self._pull.issue_url.split('/')[-1].strip())
        return self._repo.get_issue(issue_id)

    @property
    def branch_name(self):
        return get_verba_branch_name(self.id)

    @property
    def title(self):
        return self._pull.title

    @property
    def description(self):
        return self._pull.body

    def is_content_file(self, file_name):
        # TODO review
        return file_name.split('.')[-1].lower() == 'md'

    def get_files(self):
        gitfiles = self._repo.get_dir_contents(
            abs_path(CONTENT_PATH), self.branch_name
        )

        files = []
        for gitfile in gitfiles:
            if self.is_content_file(gitfile.name):
                files.append(
                    RevisionFile(self._repo, self.id, gitfile)
                )

        return files

    def get_file_by_path(self, path):
        rev_files = self.get_files()
        for rev_file in rev_files:
            if rev_file.path.lower() == path.lower():
                return rev_file
        raise RevisionFileNotFoundException("File '{}' not found".format(path))

    def mark_as_in_progress(self):
        # get existing labels, remove the 'in review' one and add the 'in progress' one
        labels = [l.name for l in self._issue.get_labels()]
        if LABEL_IN_REVIEW in labels:
            labels.remove(LABEL_IN_REVIEW)
        labels.append(LABEL_IN_PROGRESS)

        self._issue.set_labels(*labels)

    def mark_as_in_review(self):
        # get existing labels, remove the 'in progress' one and add the 'in review' one
        labels = [l.name for l in self._issue.get_labels()]
        if LABEL_IN_PROGRESS in labels:
            labels.remove(LABEL_IN_PROGRESS)
        labels.append(LABEL_IN_REVIEW)

        self._issue.set_labels(*labels)

    def send_for_approval(self, title, description):
        self.mark_as_in_review()
        self._pull.edit(title=title, body=description)

    def get_absolute_url(self):
        return reverse('revision:detail', args=[self.id])


class RevisionManager(object):
    def __init__(self, token):
        self._repo = get_repo(token)

    def get_all(self):
        revisions = []
        for pull in self._repo.get_pulls():
            revision_id = get_revision_id(pull.head.ref)

            if not revision_id:
                continue

            revisions.append(
                Revision(self._repo, revision_id, pull)
            )
        return revisions

    def get_by_id(self, revision_id):
        revisions = self.get_all()
        for revision in revisions:
            if revision.id == revision_id:
                return revision

        raise RevisionNotFoundException("Revision '{}' not found".format(revision_id))

    def create(self, title):
        # generating branch name
        revision_id = '{}-{}'.format(slugify(title[:10]), get_random_string(length=10))
        branch_name = get_verba_branch_name(revision_id)

        # create branch
        branch_ref = 'refs/heads/{}'.format(branch_name)
        sha = self._repo.get_branch(BASE_BRANCH).commit.sha
        self._repo.create_git_ref(branch_ref, sha)

        # create revision log file in log folder
        revision_log_file_path = abs_path(
            '{}{}_{}'.format(
                REVISIONS_LOG_FOLDER,
                timezone.now().strftime('%Y.%m.%d_%H.%M'),
                branch_name
            )
        )
        create_file(
            self._repo,
            path=revision_log_file_path,
            message='Create revision log file',
            content='',
            branch=branch_name
        )

        # create PR
        pull = self._repo.create_pull(
            title=title,
            body='Content revision {}'.format(title),
            base=BASE_BRANCH,
            head=branch_name
        )

        revision = Revision(self._repo, revision_id, pull)
        revision.mark_as_in_progress()

        return revision
