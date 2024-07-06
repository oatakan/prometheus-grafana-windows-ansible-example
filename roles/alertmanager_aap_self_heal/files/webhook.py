from flask import Flask, request
from gevent.pywsgi import WSGIServer
import http.client
import http.server
import json
import ssl
import urllib.parse
import os
from dotenv import load_dotenv

# AAP/AWX connection and job template details:
project_folder = os.path.expanduser('/root/')
load_dotenv(os.path.join(project_folder, '.aap.cfg'))
AAP_HOST = os.getenv('AAP_HOST')
AAP_PORT = 443
AAP_TOKEN = os.getenv('AAP_OAUTH_TOKEN')
AAP_PROJECT = os.getenv('AAP_PROJECT')
AAP_TEMPLATE = os.getenv('AAP_TEMPLATE')

def process_alert(alert):

    # Build the query to find the job template:
    query = {
        "name": AAP_TEMPLATE,
        "project__name": AAP_PROJECT,
    }
    query = urllib.parse.urlencode(query)

    # Send the request to find the job template:
    response = send_request(
        method='GET',
        path="/api/v2/job_templates/?%s" % query,
        token=AAP_TOKEN,
    )

    # Get the identifier of the job template:
    template_id = response["results"][0]["id"]

    # Send the request to launch the job template, including all the labels
    # of the alert as extra variables for the AAP job template:
    extra_vars = alert["labels"]
    extra_vars = json.dumps(extra_vars)
    send_request(
        method='POST',
        path="/api/v2/job_templates/%s/launch/" % template_id,
        token=AAP_TOKEN,
        body={
            "extra_vars": extra_vars,
        },
    )


def send_request(method, path, token=None, body=None):
    print("AAP method: %s" % method)
    print("AAP path: %s" % path)
    if token is not None:
        print("AAP token: %s" % token)
    if body is not None:
        print("AAP request:\n%s" % indent(body))
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.verify_mode = ssl.CERT_NONE
        context.check_hostname = False
        connection = http.client.HTTPSConnection(
            host=AAP_HOST,
            port=AAP_PORT,
            context=context,
        )
        body = json.dumps(body)
        body = body.encode("utf-8")
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json",
        }
        if token is not None:
            headers["Authorization"] = "Bearer %s" % token
        print(headers)
        connection.request(
            method=method,
            url=path,
            headers=headers,
            body=body,
        )
        response = connection.getresponse()
        body = response.read()
        body = body.decode("utf-8")
        body = json.loads(body)
        print("AAP response:\n%s" % indent(body))
        return body
    finally:
        connection.close()


def indent(data):
    return json.dumps(data, indent=2)

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        prometheus_data = json.loads(request.data)
        print(prometheus_data)
        for k, v in prometheus_data.items():
            if k == 'alerts':
                for items in v:
                    if items['status'] == 'firing':
                        if items['labels']['alertname'] == 'Disk Usage':
                            process_alert(items)

        return "prometheus monitor"
    except Exception as e:
        raise e

if __name__ == '__main__':
    WSGIServer(('0.0.0.0', 5000), app).serve_forever()
