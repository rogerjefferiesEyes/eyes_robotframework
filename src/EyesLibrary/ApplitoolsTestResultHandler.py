import re
import time
from math import floor

import logging
import requests
import shutil
import os
from enum import Enum
from enum import IntEnum
from email.utils import formatdate

__all__ = ('ApplitoolsTestResultsHandler',)

log = logging.getLogger('ApplitoolsTestResultsHandler')


class ResultStatus(Enum):
    PASSED = 'passed'
    FAILED = 'failed'
    NEW = 'new'
    MISSING = 'missing'


class StatusCode(IntEnum):
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    GONE = 410


class ApplitoolsTestResultsHandler:

    def _get_session_id(self, test_results):
        pattern = ('^' + re.escape(self.server_URL) +
                   r'\/app\/batches\/\d+\/(?P<sessionId>\d+).*$')
        return re.findall(pattern, test_results.url)[0]

    def _get_batch_id(self, test_results):
        pattern = ('^' + re.escape(self.server_URL) +
                   r'\/app\/batches\/(?P<batchId>\d+).*$')
        return re.findall(pattern, test_results.url)[0]

    def _get_server_url(self, test_results):
        return test_results.url[0:test_results.url.find("/app/batches")]

    def __init__(self, test_results, view_key):
        self.view_key = view_key
        self.test_results = test_results
        self.server_URL = self._get_server_url(test_results)
        self.session_ID = self._get_session_id(test_results)
        self.batch_ID = self._get_batch_id(test_results)
        self.test_JSON = self.get_test_json()
        self.retry_request_interval = 500
        self.long_request_delay = 2
        self.default_timeout = 30
        self.reduced_timeout = 15
        self.counter = 0

    def calculate_step_results(self):
        expected = self.test_JSON['expectedAppOutput']
        actual = self.test_JSON['actualAppOutput']
        steps = max(len(expected), len(actual))
        steps_result = list()
        for i in range(steps):
            if actual[i] is None:
                steps_result.append(ResultStatus.MISSING)
            elif expected[i] is None:
                steps_result.append(ResultStatus.NEW)
            elif actual[i]['isMatching']:
                steps_result.append(ResultStatus.PASSED)
            else:
                steps_result.append(ResultStatus.FAILED)
        return steps_result

    def download_diffs(self, path):
        path = self.prepare_path(path)
        step_states = self.calculate_step_results()
        for i in range(len(step_states)):
            if step_states[i] is ResultStatus.FAILED:
                image_url = self.server_URL + '/api/sessions/batches/' + self.batch_ID + '/' + self.session_ID + '/steps/' + str(
                    i + 1) + '/diff'
                diff_path = path + "/diff_step_" + str(i + 1) + ".jpg"
                self.image_from_url_to_file(url=image_url, path=diff_path)
            else:
                print("No Diff image in step " + str(i + 1) + '\n')

    def image_names(self):
        scenario_name = self.test_JSON['scenarioName']
        image_names = []
        for output in self.test_JSON['actualAppOutput']:
            if output is None:
                image_names.append(None)
            else:
                image_names.append(
                    scenario_name + '_applitools_step_' + output['tag'])
        return image_names

    def image_paths_and_names(self):
        test_name = self.test_JSON['scenarioName']
        screen = self.test_JSON['baselineEnv']['hostingApp']
        image_names = []
        for number, label in enumerate(self.test_JSON['actualAppOutput']):
            image_names.append('step_{}_{}.png'.format(number, label['tag']))
        return test_name, screen, image_names

    def download_images(self, path):
        self.download_baseline_images(path=path)
        self.download_current_images(path=path)

    def download_current_images(self, path):
        path = self.prepare_path(path)
        for i in range(self.test_results.steps):
            image_id = self.get_image_id("actualAppOutput", i)
            if image_id is not None:
                image_url = self.server_URL + '/api/images/' + image_id
                curr_path = path + "/current_step_" + str(i + 1) + ".jpg"
                self.image_from_url_to_file(url=image_url, path=curr_path)

    def download_baseline_images(self, path):
        path = self.prepare_path(path)

        for i in range(self.test_results.steps):
            image_id = self.get_image_id("expectedAppOutput", i)
            if image_id is not None:
                image_url = self.server_URL + '/api/images/' + image_id
                base_path = path + "/baseline_step_" + str(i + 1) + ".jpg"
                self.image_from_url_to_file(url=image_url, path=base_path)

    def image_from_url_to_file(self, url, path):
        with self.send_long_request('GET', url) as resp, \
                open(path, 'wb') as out_file:
            out_file.write(resp.content)
            out_file.flush()
            out_file.close()
            resp.raw.decode_content = True
            shutil.copyfileobj(resp.raw, out_file)

    def prepare_path(self, path):
        path = path + "/" + self.batch_ID + "/" + self.session_ID
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def get_image_id(self, image_type, step):
        try:
            return self.test_JSON[image_type][step]['image']['id']
        except TypeError:
            if image_type == "actualAppOutput":
                log.warning("The current image "
                            "in step {} is missing\n".format(step))
            elif image_type == "expectedAppOutput":
                log.warning("The baseline image "
                            "in step {} is missing\n".format(step))
        return None

    def get_test_json(self):
        request_url = (str(self.server_URL) + '/api/sessions/batches/' +
                       str(self.batch_ID) + '/' + str(self.session_ID) +
                       '/?apiKey=' + str(self.view_key) + '&format=json')
        test_json = requests.get(request_url.encode('ascii', 'ignore')).json()
        test_json = dict([(str(k), v) for k, v in test_json.items()])
        return test_json

    def send_long_request(self, request_type, url):
        request = self.create_request(request_type, url)
        response = self.send_request(request)
        return self.long_request_check_status(response)

    def create_request_headers(self, request_type, url, request=None):
        if request is None:
            request = {}
        current_date = formatdate(timeval=None, localtime=False, usegmt=True)
        headers = {
            "Eyes-Expect": "202+location",
            "Eyes-Date": current_date
        }
        request["headers"] = headers
        request["url"] = url
        request["request_type"] = request_type
        return request

    def create_request(self, request_type, url, request=None):
        if request is None:
            request = {}
        request["url"] = url
        request["request_type"] = request_type
        return request

    def send_request(self, request, retry=1, delay_before_retry=False):
        self.counter += 1

        request_type = request.get("request_type")
        url = request.get("url")
        url = url + "?apiKey=" + self.view_key

        try:
            if request_type == 'GET':
                response = requests.get(
                    url,
                    stream=True
                )
            elif request_type == 'POST':
                response = requests.post(
                    url,
                    stream=True
                )
            elif request_type == 'DELETE':
                response = requests.delete(
                    url,
                    stream=True
                )
            else:
                raise Exception("Not a valid request type")
            return response

        except Exception as e:
            log.error("Error: {}".format(e))
            if retry > 0:
                if delay_before_retry:
                    time.sleep(self.retry_request_interval)
                    return self.send_request(request, retry - 1,
                                             delay_before_retry)
                return self.send_request(request, retry - 1,
                                         delay_before_retry)
            raise Exception("Error: {}".format(e))

    def long_request_check_status(self, response):
        status = response.status_code

        # OK
        if status == StatusCode.OK:
            return response

        # Accepted
        elif status == StatusCode.ACCEPTED:
            url = response.headers.get("location")
            request = self.create_request('GET', url)
            request_response = self.long_request_loop(request,
                                                      self.long_request_delay)
            return self.long_request_check_status(request_response)

        # Created
        # The request has been fulfilled and has resulted in
        # one or more new resources being created
        elif status == StatusCode.CREATED:
            url = response.headers.get("location")
            request = self.create_request('DELETE', url)
            return self.send_request(request)

        # Gone
        # The target resource is no longer available
        elif status == StatusCode.GONE:
            raise Exception("The server task has gone")
        else:
            raise Exception("Unknown error during long request: {}".format(
                response.status_code))

    @staticmethod
    def _increment_delay(delay):
        return min(10, floor(delay * 1.5))

    @staticmethod
    def should_retry(response):
        status_code = response.status_code
        return status_code is StatusCode.ACCEPTED

    def long_request_loop(self, request, delay):
        delay = self._increment_delay(delay)
        log.info("The request has been accepted, but not completed.\n"
                 "Retrying in {} s".format(delay))
        time.sleep(delay)

        response = self.send_request(request)
        if self.should_retry(response):
            return self.long_request_loop(request, delay)
        return response
