import os
import base64

import requests

from .ApplitoolsTestResultHandler import ApplitoolsTestResultsHandler, ResultStatus
import robot.api.logger as robot_logger


class ApplitoolsBase64TestResultHandler(ApplitoolsTestResultsHandler):

    _step_states = None
    _table_template_html = '''<table width="600" style="width:600px;">
                            <th colspan="5">{table_title}</th>
                            <tr>
                                <td style="width: 16%;padding: 2% 5% 2% 5%;text-align: center;">Step</td>
                                <td style="width: 20%;padding: 2% 5% 2% 5%;text-align: center;">Baseline Image</td>
                                <td style="width: 20%;padding: 2% 5% 2% 5%;text-align: center;">Checkpoint Image</td>
                                <td style="width: 20%;padding: 2% 5% 2% 5%;text-align: center;">Diff Image</td>
                                <td style="width: 24%;padding: 2% 2% 2% 2%;text-align: center;">Link</td>
                            </tr>
                            {step_image_table_rows}
                        </table>'''

    _table_title_template = '{test_name} - {host_os} - {host_app} - {display_width} x {display_height} - ({status})'

    _image_url_template = '{server_url}/api/images/{image_id}'
    _image_link_template = '{server_url}/api/images/{image_id}/?apiKey={api_key}'

    _diff_image_url_template = '{server_url}/api/sessions/batches/{batch_id}/{session_id}/steps/{step_number}/diff'

    _step_link_template = '<td style="width: 24%;padding: 2% 2% 2% 2%;text-align: center;"><a href="{step_url}">View in Dashboard</a></td>'

    _step_name_cell_html = '<td style="width: 16%;padding: 2% 5% 2% 5%;text-align: center;">{step_tag}</td>'

    _image_launch_html = '<td style="width: 20%;padding: 2% 5% 2% 5%;text-align: center;"><a ' \
                         'href="#" onclick=\'image = new Image();image.src = "{base64_url}";var w = window.open(' \
                         '"");w.document.write(image.outerHTML);w.document.close();\'><img id="baselineImage" ' \
                         'src="{base64_url}" style="display: block;width: 100%;object-fit: contain;"></a></td>'

    _image_popup_html = '<td style="width: 20%;padding: 2% 5% 2% 5%;text-align: center;"><img src="{base64_url}" ' \
                        'onclick="var w = window.open(\'\');w.document.write(this.outerHTML);w.document.close();" ' \
                        'style="display: block;width: 100%;object-fit: contain; cursor: pointer;border: 1px solid ' \
                        '#0000EE;"></td> '

    _image_download_html = '<td style="width: 20%;padding: 2% 5% 2% 5%;text-align: center;"><a ' \
                           'href="{base64_url}" download="{filename}"><img ' \
                           'id="{image_id}" src="{base64_url}" style="display: ' \
                           'block;width: 100%;object-fit: contain;"></a></td>'

    _image_link_cell_html = '<td style="width: 20%;padding: 2% 5% 2% 5%;text-align: center;"><a href="{' \
                            'image_url}"><img id="{image_id}" src="{image_url}" style="display: block;width: ' \
                            '100%;object-fit: contain;"></a></td> '

    _empty_image_cell_html = '<td style="width: 20%;padding: 2% 5% 2% 5%;text-align: center;">{message}</td>'

    def __init__(self, test_results, view_key):
        super().__init__(test_results, view_key)
        self._step_states = self.calculate_step_results()
        if(os.environ.get('APPLITOOLS_REQUEST_DELAY') is not None and os.environ.get('APPLITOOLS_REQUEST_DELAY').isnumeric()):
            self.long_request_delay = int(os.environ.get('APPLITOOLS_REQUEST_DELAY'))
        else:
            self.long_request_delay = 7

    def create_request_headers(self, request_type, url, request=None):
        if request is None:
            request = {}
        current_date = formatdate(timeval=None, localtime=False, usegmt=True)
        headers = {
            "Eyes-Expect": "202+location",
            "Eyes-Date": current_date,
            "X-Eyes-Api-Key": self.view_key
        }
        request["headers"] = headers
        request["url"] = url
        request["request_type"] = request_type
        return request

    def get_table_title(self, step_index=None):
        step_result = ''
        if(step_index == None):
            step_result = self.test_JSON["status"]
        else:
            step_result = str(self._step_states[step_index]).replace('ResultStatus.', '')

        test_name = self.test_JSON["startInfo"]['scenarioName']
        host_os = self.test_JSON["startInfo"]["environment"]['osInfo']
        host_app = self.test_JSON["startInfo"]["environment"]['hostingAppInfo']
        display_width = self.test_JSON["startInfo"]["environment"]['displaySize']['width']
        display_height = self.test_JSON["startInfo"]["environment"]['displaySize']['height']
        return self._table_title_template.format(test_name=test_name, host_os=host_os, host_app=host_app,
                                                 display_width=display_width, display_height=display_height, 
                                                 status=step_result)


    def image_from_url_to_base64(self, url):
        with self.send_long_request('GET', url) as resp:
            resp.raw.decode_content = True
            base64_url = "data:image/png;base64," + base64.b64encode(resp.content).decode('utf-8')
            return base64_url

    def get_base64_diff_image_list(self, step_number = None):
        image_list = list()
        if(self._step_states == None):
            self._step_states = self.calculate_step_results()

        file_name_prefix = self.batch_ID + '_' + self.session_ID

        step_range = []

        if(step_number == None):
            step_range = range(len(self._step_states))
        else:
            step_range = [step_number - 1]

        for i in step_range:
            tag = None
            step_base64_dict = {'baseline': None, 'checkpoint': None, 'diff': None,
                                'file_prefix': file_name_prefix + '_' + str(i + 1)}
            if self._step_states[i] is ResultStatus.PASSED or self._step_states[i] is ResultStatus.FAILED or \
                    self._step_states[i] is ResultStatus.MISSING:
                # Set step tag/label, if we have a baseline
                tag = self.test_JSON["expectedAppOutput"][i]['tag']

                image_id = self.get_image_id("expectedAppOutput", i)
                if image_id is not None:
                    baseline_image_url = self._image_url_template.format(server_url=self.server_URL, image_id=image_id)
                    step_base64_dict['baseline'] = self.image_from_url_to_base64(baseline_image_url)

            step_base64_dict['tag'] = tag

            if self._step_states[i] is ResultStatus.PASSED or self._step_states[i] is ResultStatus.FAILED or \
                    self._step_states[i] is ResultStatus.NEW:
                image_id = self.get_image_id("actualAppOutput", i)
                if image_id is not None:
                    checkpoint_image_url = self._image_url_template.format(server_url=self.server_URL,
                                                                           image_id=image_id)
                    step_base64_dict['checkpoint'] = self.image_from_url_to_base64(checkpoint_image_url)

            if self._step_states[i] is ResultStatus.FAILED:
                diff_image_url = self._diff_image_url_template.format(server_url=self.server_URL,
                                                                      batch_id=self.batch_ID,
                                                                      session_id=self.session_ID,
                                                                      step_number=str(i + 1))
                
                step_base64_dict['diff'] = self.image_from_url_to_base64(diff_image_url)

            image_list.append(step_base64_dict)

        return image_list

    def get_base64_table_rows_html(self, step_number=None):
        image_list = []

        step_number_tag = ""
        step_url = ""
        table_header = ""
        
        if(step_number == None):
            table_header = self.get_table_title()
            robot_logger.console('Downloading images for Test: ' + table_header + '...')
            image_list = self.get_base64_diff_image_list()
        else:
            step_number_tag = str(step_number)
            table_header = self.get_table_title(step_number - 1)
            robot_logger.console('Downloading images for Step ' + step_number_tag + ' of Test: ' + table_header + '...')
            image_list = self.get_base64_diff_image_list(step_number)
            step_url = self.test_results.steps_info[step_number - 1].app_urls.step

        
        output_html = ''
        for i in range(len(image_list)):
            if(step_number == None):
                step_number_tag = str(i + 1)
                step_url = self.test_results.steps_info[i].app_urls.step

            output_html += "<tr>"

            if image_list[i]['tag'] is not None:
                output_html += self._step_name_cell_html.format(step_tag=step_number_tag + ' - ' + image_list[i]['tag'])
            else:
                output_html += self._step_name_cell_html.format(step_tag=step_number_tag)

            if image_list[i]['baseline'] is not None:
                output_html += self._image_popup_html.format(base64_url=image_list[i]['baseline'])
            else:
                output_html += self._empty_image_cell_html.format(message="No Baseline Image")

            if image_list[i]['checkpoint'] is not None:
                output_html += self._image_popup_html.format(base64_url=image_list[i]['checkpoint'],
                                                                filename=image_list[i]['file_prefix'] + "_check.png",
                                                                image_id="checkpointImage")
            else:
                output_html += self._empty_image_cell_html.format(message="No Checkpoint Image")

            if image_list[i]['diff'] is not None:
                output_html += self._image_popup_html.format(base64_url=image_list[i]['diff'],
                                                                filename=image_list[i]['file_prefix'] + "_diff.png",
                                                                image_id="diffImage")
            else:
                output_html += self._empty_image_cell_html.format(message="No Diff Image")

            output_html += self._step_link_template.format(step_url=step_url)

            output_html += "</tr><br><br>"

        return self._table_template_html.format(table_title=table_header, step_image_table_rows=output_html)

    def get_test_image_urls(self, step_number = None):
        image_list = list()
        if(self._step_states == None):
            self._step_states = self.calculate_step_results()

        file_name_prefix = self.batch_ID + '_' + self.session_ID

        step_range = []

        if(step_number == None):
            step_range = range(len(self._step_states))
        else:
            step_range = [step_number - 1]

        
        for i in step_range:
            tag = None
            image_url_dict = {'baseline': None, 'checkpoint': None, 'diff': None,
                              'file_prefix': file_name_prefix + '_' + str(i + 1)}
            if self._step_states[i] is ResultStatus.PASSED or self._step_states[i] is ResultStatus.FAILED or \
                    self._step_states[i] is ResultStatus.MISSING:
                # Set step tag/label, if we have a baseline
                tag = self.test_JSON["expectedAppOutput"][i]['tag']
                image_id = self.get_image_id("expectedAppOutput", i)
                if image_id is not None:
                    image_url_dict['baseline'] = self._image_link_template.format(server_url=self.server_URL,
                                                                                  image_id=image_id,
                                                                                  api_key=self.view_key)
            image_url_dict['tag'] = tag

            if self._step_states[i] is ResultStatus.PASSED or self._step_states[i] is ResultStatus.FAILED or \
                    self._step_states[i] is ResultStatus.NEW:
                image_id = self.get_image_id("actualAppOutput", i)
                if image_id is not None:
                    image_url_dict['checkpoint'] = self._image_link_template.format(server_url=self.server_URL,
                                                                                    image_id=image_id,
                                                                                    api_key=self.view_key)

            if self._step_states[i] is ResultStatus.FAILED:
                image_url_dict['diff'] = self.server_URL + '/api/sessions/batches/' + \
                                         self.batch_ID + '/' + self.session_ID + \
                                         '/steps/' + str(i + 1) + '/diff' + "?apiKey=" + self.view_key
            else:
                print("No Diff image in step " + str(i + 1) + '\n')

            image_list.append(image_url_dict)

        return image_list

    def get_image_table_rows_html(self, step_number=None):
        image_list = []
        
        step_number_tag = ""
        step_url = ""
        table_header = ""
        
        if(step_number == None):
            table_header = self.get_table_title()
            robot_logger.console('Downloading images for Test: ' + table_header + '...')
            image_list = self.get_test_image_urls()
        else:
            step_number_tag = str(step_number)
            table_header = self.get_table_title(step_number - 1)
            robot_logger.console('Downloading images for Step ' + step_number_tag + ' of Test: ' + table_header + '...')
            image_list = self.get_test_image_urls(step_number)
            step_url = self.test_results.steps_info[step_number - 1].app_urls.step

        output_html = ''

        for i in range(len(image_list)):

            if(step_number == None):
                step_number_tag = str(i + 1)
                step_url = self.test_results.steps_info[i].app_urls.step

            output_html += "<tr>"

            if image_list[i]['tag'] is not None:
                output_html += self._step_name_cell_html.format(step_tag=step_number_tag + ' - ' + image_list[i]['tag'])
            else:
                output_html += self._step_name_cell_html.format(step_tag=step_number_tag)

            if image_list[i]['baseline'] is not None:
                output_html += self._image_link_cell_html.format(image_url=image_list[i]['baseline'],
                                                                 image_id="baselineImage")
            else:
                output_html += self._empty_image_cell_html.format(message="No Baseline Image")

            if image_list[i]['checkpoint'] is not None:
                output_html += self._image_link_cell_html.format(image_url=image_list[i]['checkpoint'],
                                                                 image_id="checkpointImage")
            else:
                output_html += self._empty_image_cell_html.format(message="No Checkpoint Image")

            if image_list[i]['diff'] is not None:
                output_html += self._image_link_cell_html.format(image_url=image_list[i]['diff'],
                                                                 image_id="diffImage")
            else:
                output_html += self._empty_image_cell_html.format(message="No Diff Image")

            output_html += self._step_link_template.format(step_url=step_url)

            output_html += "</tr><br><br>"

        return self._table_template_html.format(table_title=table_header, step_image_table_rows=output_html)

    def get_image_html(self, view_key):
        image_html = ''
        for test_result in self._test_results:
            html_test_result_handler = ApplitoolsBase64TestResultHandler(test_result, view_key)
            robot_logger.info("Retrieving Image Links for APPLITOOLS Test: " +
                              str(html_test_result_handler.get_table_title()), False, True)
            image_html += html_test_result_handler.get_image_table_rows_html()
        self._test_results.clear()
        return image_html

    def get_base64_image_html(self, view_key):
        base64_image_html = ''
        for test_result in self._test_results:
            base64_test_result_handler = ApplitoolsBase64TestResultHandler(test_result, view_key)
            robot_logger.info("Retrieving Images for APPLITOOLS Test: " +
                              str(base64_test_result_handler.get_table_title()), False, True)
            base64_image_html += base64_test_result_handler.get_base64_table_rows_html()
        self._test_results.clear()
        return base64_image_html

    def log_image_html(self, view_key):
        robot_logger.write(self.get_base64_image_html(view_key), html=True, level='ERROR')