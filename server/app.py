#!venv/bin/python
import sys, traceback
import os
import time
import uuid
import functools
from threading import Thread
from glob import glob
from werkzeug.utils import secure_filename
from flask import Flask, redirect, url_for, jsonify, send_file, flash, make_response, \
    copy_current_request_context, Response, request, send_from_directory
app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = set(['mp4'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

background_tasks = {}


@app.route('/api/v1/')
def index():
    return "VividWorlds!"

@app.errorhandler(404)
def not_found(e=None):
    return jsonify({'error': 'resource not found'}), 404

@app.errorhandler(500)
def internal_server_error(e=None):
    return jsonify({'error': 'internal server error'}), 500

def background(f):
    """Decorator that runs the wrapped function as a background task. It is
    assumed that this function creates a new resource, and takes a long time
    to do so. The response has status code 202 Accepted and includes a Location
    header with the URL of a task resource. Sending a GET request to the task
    will continue to return 202 for as long as the task is running. When the task
    has finished, a status code 303 See Other will be returned, along with a
    Location header that points to the newly created resource. The client then
    needs to send a DELETE request to the task resource to remove it from the
    system."""
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        # The background task needs to be decorated with Flask's
        # copy_current_request_context to have access to context globals.
        @copy_current_request_context
        def task():
            global background_tasks
            try:
                # invoke the wrapped function and record the returned
                # response in the background_tasks dictionary
                background_tasks[job_id] = make_response(f(*args, **kwargs))
            except Exception as e: 
                print 'asfasdfa'+str(e)
                traceback.print_exc(file=sys.stdout)
                # the wrapped function raised an exception, return a 500
                # response
                background_tasks[job_id] = make_response(internal_server_error())

        # store the background task under a randomly generated identifier
        # and start it
        global background_tasks
        job_id = uuid.uuid4().hex
        background_tasks[job_id] = Thread(target=task)
        background_tasks[job_id].start()
        print(background_tasks)

        # return a 202 Accepted response with the location of the task status
        # resource
        return '', 202, {'Location': url_for('get_task_status', job_id=job_id)}
    return wrapped

@app.route('/api/v1/stylize/status/<job_id>', methods=['GET'])
def get_task_status(job_id):
    """Query the status of an asynchronous task."""
    # obtain the task and validate it
    global background_tasks
    print(background_tasks)
    rv = background_tasks.get(job_id)
    if rv is None:
        return not_found(None)

    # if the task object is a Thread object that means that the task is still
    # running. In this case return the 202 status message again.
    if isinstance(rv, Thread):
        return '', 202, {'Location': url_for('get_task_status', job_id=job_id)}

    return rv

@app.route('/api/v1/stylize/status/<job_id>', methods=['DELETE'])
def delete_task_status(vid_id):
    """Delete an asynchronous task resource."""
    # obtain the task and validate it
    global background_tasks
    rv = background_tasks.get(job_id)
    if rv is None:
        return not_found(None)

    # if the task is still running it cannot be deleted
    if isinstance(rv, Thread):
        return bad_request()

    return '', 200

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/api/v1/stylize/<user_id>', methods=['POST'])
@background
def stylize_video(user_id):
    # check if the post request has the file part
    print 'stylin'
    if 'file' not in request.files:
        print('No file part')
        return redirect(request.url)
    file = request.files['file']
    # if user does not select file, browser also
    # submit a empty part without filename
    if file.filename == '':
        print('No selected file')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.root_path+'/uploads', filename))
        return '', 201, {'Location': url_for('get_stylized_video',
                                                      user_id=user_id,
                                                      vid_id=filename,
                                                      _external=True)} 


@app.route('/api/v1/stylize/<user_id>/result/<vid_id>', methods=['GET'])
def get_stylized_video(user_id, vid_id): 
    return send_from_directory('uploads', vid_id)

if __name__ == '__main__':
    app.secret_key = 'super secret key'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

    app.run(debug=True)

