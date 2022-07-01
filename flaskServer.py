# Importing flask module in the project is mandatory
# An object of Flask class is our WSGI application.
from flask import Flask, jsonify, request, session, redirect, make_response
from scipy.spatial.distance import cosine
from flask_hashing import Hashing
from flask_mysqldb import MySQL
from functools import wraps
import numpy as np
import json


# Flask constructor takes the name of 
# current module (__name__) as argument.
app = Flask(__name__)
app.secret_key = '#d\xe9X\x00\xbe~Uq\xebX\xae\x81\x1fs\t\xb4\x49\xa3\x87\xe6.\xd1_'

app.config['MYSQL_HOST'] = 'ls-233f02a73a32464845fba409f8a6def9fa3625a7.cw88zhwx9uki.eu-west-3.rds.amazonaws.com'
app.config['MYSQL_USER'] = 'dbmasteruser'
app.config['MYSQL_PASSWORD'] = 'adminadmin1467'
app.config['MYSQL_DB'] = 'dbflask'

mysql = MySQL(app)
hashing = Hashing(app)

with app.app_context():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute(''' CREATE TABLE users (
            userID int(11) NOT NULL AUTO_INCREMENT,
            username varchar(25) NOT NULL,
            email varchar(50) NOT NULL,
            password char(64) NOT NULL,
            PRIMARY KEY (userID),
            UNIQUE KEY username (username),
            UNIQUE KEY email (email)
            )''')
        mysql.connection.commit()

    except Exception as e:
        # if table already exists we reach this error, we will ignore this part of the code as it will not affect the database
        # print(e)
        pass

    finally:
        cursor.close()

    try:
        cursor = mysql.connection.cursor()
        cursor.execute(''' CREATE TABLE encodings (
            encodingID int(11) NOT NULL AUTO_INCREMENT,
            encoding blob NOT NULL,
            userID int(11) NOT NULL,
            encodingName varchar(25) NOT NULL,
            PRIMARY KEY (encodingID),
            KEY user_id_idx (userID),
            FOREIGN KEY (userID) REFERENCES users (userID) ON DELETE CASCADE
            )''')
        mysql.connection.commit()

    except Exception as e:
        # if table already exists we reach this error, we will ignore this part of the code as it will not affect the database
        # print(e)
        pass

    finally:
        cursor.close()

def identify_face(encodings, userID):
    # get the encodings of user in db
    cursor = mysql.connection.cursor()
    table_name = 'encodings'
    cursor.execute(f' SELECT encodingName, encoding FROM {table_name} WHERE userID={userID}')
    data = cursor.fetchall()
    cursor.close()

    database = []
    for dataPoint in data:
        database.append([dataPoint[0], json.loads(dataPoint[1])])
    

    results = np.empty((len(encodings), len(database)))

    for i, feature in enumerate(encodings):
        for j, face in enumerate(database):
            # match the received face with db faces
            results[i][j] = cosine(feature, face[1]) * 0.5

    matches = []
    for i in range(len(encodings)):
        id = np.argmin(results[i])
        min_dist = results[i][id]
        matches.append((database[id][0], min_dist))

    return matches


# this function is a decorator to allow us to check if user has authenticated before trying to access
# pages that require authentication
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('username') is None:
            return redirect('/',code=302)
        return f(*args, **kwargs)
    return decorated_function
# EXAMPLE OF USING THE LOGIN DECORATOR:
    # @app.route('/', methods=['GET', 'POST'])
    # @login_required
    # def home():
    #    #blah_blah

# The route() function of the Flask class is a decorator, 
# which tells the application which URL should call 
# the associated function.
@app.route('/', methods=['GET'])
def index():
    if 'username' in session:
        return f'Logged in as {session["username"]}'
    return 'You are not logged in'

@app.route('/compute', methods=['POST'])
@login_required
def compute():
    match_threshold = 0.3

    data = request.json
    encodings = []
    for i in range(len(data)):
        encodings.append(data[str(i)])

    matches = identify_face(encodings, session['userID'])
    response_body = {}
    for i, match in enumerate(matches):
        if match_threshold > match[1]:
            response_body[i] = {'name': match[0], 'probability': 100.0 * (1 - match[1])}

    response = make_response(jsonify(response_body),200)
    response.headers["Content-Type"] = "application/json"
    return response


@app.route('/addenc', methods=['POST'])
@login_required
def addEncoding():
    data = request.json
    encodingName = data['name']
    userID = session['userID']
    encoding = json.dumps(data['encoding'])
    try:
        cursor = mysql.connection.cursor()
        table_name = 'encodings'
        cursor.execute(f' INSERT INTO {table_name} (encoding,userID,encodingName) VALUES(\'{encoding}\',\'{userID}\',\'{encodingName}\')')
        mysql.connection.commit()

        return jsonify({'status': 'success'})

    except Exception as e:
        return jsonify({'status': 'failed'})

    finally:
        cursor.close()

@app.route('/login', methods=['POST'])
def login():
    #TODO: add an authentication column to the users database and set it to true if the user has been authenticated
    # also in logout section set it to false to convey the user has been logged out
    username = request.form['username']
    password = request.form['password']
    my_dict = {}
    if 'username' in session:
        my_dict['msg'] = f'Already logged in as {session["username"]}'
        my_dict['valid'] = 1
        return jsonify(my_dict)

    cursor = mysql.connection.cursor()
    table_name = 'users'
    cursor.execute(f' SELECT * FROM {table_name}')
    data = cursor.fetchall()
    cursor.close()
    for elem in data:
        if username == elem[1] and hashing.hash_value(password, salt='grad') == elem[3]:
            # Sessions are unique objects that act as dictionaries to each individual that logs in (TODO: test if true)
            # Saving the current user's id, username and email in his own session object as this will be relevant data
            # throughout his login session
            session['userID'] = elem[0]
            session['username'] = elem[1]
            session['email'] = elem[2]
            my_dict['msg'] = f'logged in as {session["username"]}'
            my_dict['valid'] = 1 
            # return f'logged in as {session["username"]}'
            return jsonify(my_dict)
    my_dict['msg'] = 'wrong username or password'
    my_dict['valid'] = 0
    return jsonify(my_dict)


@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    hashed_password = hashing.hash_value(password, salt='grad') 

    return_str=''    
    try:
        cursor = mysql.connection.cursor()
        table_name = 'users'
        cursor.execute(f' INSERT INTO {table_name} (username,email,password) VALUES(\'{username}\',\'{email}\',\'{hashed_password}\')')
        mysql.connection.commit()
        return_str=f'ok'

    except Exception as e:
        return_str=f'error, user already in system'

    finally:
        cursor.close()
        return return_str

@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('userID', None)
    session.pop('username', None)
    session.pop('email', None)

    return f'succesfully logged out'

# main driver function
if __name__ == '__main__':
  
    # run() method of Flask class runs the application 
    # on the local development server.
    app.run()
