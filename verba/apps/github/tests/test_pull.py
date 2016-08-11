import json
import responses

import github
from github.exceptions import InvalidResponseException

from github.tests.test_base import BaseGithubTestCase


class BasePullTestCase(BaseGithubTestCase):
    def setUp(self):
        super(BasePullTestCase, self).setUp()

        self.data = {
            'number': 1,
            'url': self.get_github_api_repo_url('pulls/1'),
            'issue_url': self.get_github_api_repo_url('issues/1'),
            'title': 'pull title',
            'body': 'pull body',
            'head': {
                'ref': 'pull head ref'
            }
        }
        self.pull = github.PullRequest(self.TOKEN, self.data)


class PullDataTestCase(BasePullTestCase):
    def test_basic_data(self):
        self.assertEqual(self.pull.issue_nr, self.data['number'])
        self.assertEqual(self.pull.title, self.data['title'])
        self.assertEqual(self.pull.description, self.data['body'])
        self.assertEqual(self.pull.head_ref, self.data['head']['ref'])

    def test_branch(self):
        self.assertEqual(self.pull.branch.token, self.pull.token)
        self.assertEqual(self.pull.branch.name, self.pull.head_ref)

    @responses.activate
    def test_issue(self):
        responses.add(
            responses.GET, self.data['issue_url'],
            body=self.get_fixture('issue.json'), status=200,
            content_type='application/json'
        )

        issue = self.pull.issue
        self.assertEqual(issue.token, self.TOKEN)
        self.assertEqual(issue._data['title'], 'test1')


class GetAllPullTestCase(BasePullTestCase):
    @responses.activate
    def test_all(self):
        responses.add(
            responses.GET, self.get_github_api_repo_url('pulls'),
            body=self.get_fixture('pulls.json'), status=200,
            content_type='application/json'
        )

        pulls = github.PullRequest.all(self.TOKEN)

        self.assertEqual(len(pulls), 2)
        self.assertEqual(pulls[0].token, self.TOKEN)
        self.assertEqual(pulls[0].title, 'test1')

        self.assertEqual(pulls[1].token, self.TOKEN)
        self.assertEqual(pulls[1].title, 'test2')


class CreatePullTestCase(BasePullTestCase):
    @responses.activate
    def test_success(self):
        responses.add(
            responses.POST, self.get_github_api_repo_url('pulls'),
            body=self.get_fixture('open_pull.json'), status=201,
            content_type='application/json'
        )

        pull = github.PullRequest.create(
            token=self.TOKEN,
            title='test1', body='Pull Body',
            base='test-base', head='test-head'
        )
        self.assertEqual(pull.title, 'test1')

    @responses.activate
    def test_invalid_title(self):
        responses.add(
            responses.POST, self.get_github_api_repo_url('pulls'),
            body=json.dumps({
                'documentation_url': 'https://developer.github.com/v3/pulls/#create-a-pull-request',
                'errors': [{'code': 'missing_field', 'field': 'title', 'resource': 'Issue'}],
                'message': 'Validation Failed'
            }),
            status=422, content_type='application/json'
        )

        self.assertRaises(
            InvalidResponseException,
            github.PullRequest.create,
            token=self.TOKEN,
            title='', body='Pull Body',
            base='test-base', head='test-head'
        )

    @responses.activate
    def test_invalid_head(self):
        responses.add(
            responses.POST, self.get_github_api_repo_url('pulls'),
            body=json.dumps({
                'documentation_url': 'https://developer.github.com/v3/pulls/#create-a-pull-request',
                'errors': [{'resource': 'PullRequest', 'code': 'invalid', 'field': 'head'}],
                'message': 'Validation Failed'
            }),
            status=422, content_type='application/json'
        )

        self.assertRaises(
            InvalidResponseException,
            github.PullRequest.create,
            token=self.TOKEN,
            title='test1', body='Pull Body',
            base='test-head', head='invalid-head'
        )

    @responses.activate
    def test_invalid_base(self):
        responses.add(
            responses.POST, self.get_github_api_repo_url('pulls'),
            body=json.dumps({
                'documentation_url': 'https://developer.github.com/v3/pulls/#create-a-pull-request',
                'errors': [{'resource': 'PullRequest', 'code': 'invalid', 'field': 'base'}],
                'message': 'Validation Failed'
            }),
            status=422, content_type='application/json'
        )

        self.assertRaises(
            InvalidResponseException,
            github.PullRequest.create,
            token=self.TOKEN,
            title='test1', body='Pull Body',
            base='invalid-head', head='test-head'
        )


class EditPullTestCase(BasePullTestCase):
    @responses.activate
    def test_success(self):
        responses.add(
            responses.PATCH, self.data['url'],
            body=self.get_fixture('open_pull.json'), status=200,
            content_type='application/json'
        )

        self.pull.edit(title='new title', description='new description')
        self.assertDictEqual(
            json.loads(responses.calls[0].request.body), {
                'title': 'new title',
                'body': 'new description'
            }
        )
        self.assertEqual(self.pull.title, 'new title')
        self.assertEqual(self.pull.description, 'new description')

    @responses.activate
    def test_invalid(self):
        responses.add(
            responses.PATCH, self.data['url'],
            body=json.dumps({
                'documentation_url': 'https://developer.github.com/v3/pulls/#create-a-pull-request',
                'errors': [{'code': 'missing_field', 'field': 'title', 'resource': 'Issue'}],
                'message': 'Validation Failed'
            }),
            status=422, content_type='application/json'
        )

        self.assertRaises(
            InvalidResponseException,
            self.pull.edit,
            title='', description='new description'
        )


class ClosePullTestCase(BasePullTestCase):
    @responses.activate
    def test_success(self):
        responses.add(
            responses.PATCH, self.data['url'],
            body=self.get_fixture('closed_pull.json'), status=200,
            content_type='application/json'
        )

        self.pull.close()
