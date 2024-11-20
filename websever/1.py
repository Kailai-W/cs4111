import os
import random
import string
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, url_for, Response
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy import exc
from random import randint

# Set up template directory and initialize Flask app
tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

# Database credentials and URI
DB_USER = "kw3095"
DB_PASSWORD = "wkl4111"
DB_SERVER = "w4111.cisxo09blonu.us-east-1.rds.amazonaws.com"
DATABASEURI = "postgresql://kw3095:wkl4111@w4111.cisxo09blonu.us-east-1.rds.amazonaws.com/w4111"
engine = create_engine("postgresql://kw3095:wkl4111@w4111.cisxo09blonu.us-east-1.rds.amazonaws.com/w4111")

def generate_unique_ride_id():
    """Generate a unique 16-character alphanumeric Ride ID."""
    while True:
        new_ride_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        # Check if the Ride ID already exists in the database
        result = g.conn.execute(text("SELECT Ride_id FROM Ride_has WHERE Ride_id = :ride_id"), {'ride_id': new_ride_id}).fetchone()
        if not result:
            return new_ride_id
def parse_time(time_str):
    try:
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return None
    
@app.before_request
def before_request():
    """Setup a connection to the database before each request."""
    try:
        g.conn = engine.connect()
    except Exception as e:
        print("Error connecting to database:", e)
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    """Close the database connection after each request."""
    try:
        if g.conn:
            g.conn.close()
    except Exception as e:
        pass

# Routes for various pages and data retrieval
@app.route('/')
def index():
    return render_template("index.html")

@app.route('/stations')
def stations_menu():
    return render_template("stations.html")

@app.route('/stations/view_all')
def view_all_stations():
    cursor = g.conn.execute(text("SELECT * FROM stations"))
    stations = [dict(row) for row in cursor.mappings()]
    cursor.close()
    return render_template("view_all_stations.html", stations=stations)

@app.route('/stations/ride_counts')
def station_ride_counts():
    cursor = g.conn.execute(text("""
        SELECT S.Station_name, COUNT(H.Ride_id) AS Ride_Count
        FROM Has H
        JOIN Stations S ON H.Station_id_1 = S.Station_id
        GROUP BY S.Station_name
        ORDER BY Ride_Count DESC;
    """))
    station_ride_counts = [dict(row) for row in cursor.mappings()]
    cursor.close()
    return render_template("station_ride_counts.html", station_ride_counts=station_ride_counts)

@app.route('/rides')
def rides_menu():
    return render_template("rides.html")

@app.route('/view_all_rides')
def rides():
    cursor = g.conn.execute(text("""
        SELECT R.Ride_id, R.Start_time, R.End_time, S1.Station_name AS Start_Station, S2.Station_name AS End_Station
        FROM Ride_has R
        JOIN Has H ON R.Ride_id = H.Ride_id
        JOIN Stations S1 ON H.Station_id_1 = S1.Station_id
        LEFT JOIN Stations S2 ON H.Station_id_2 = S2.Station_id;
    """))
    rides = [dict(row) for row in cursor.mappings()] 
    cursor.close()
    return render_template("view_all_rides.html", rides=rides)

@app.route('/ride_feedback')
def ride_feedback():
    cursor = g.conn.execute(text("SELECT Ride_id, Comments FROM Rides_take"))
    feedback = [dict(row) for row in cursor.mappings()]
    cursor.close()
    return render_template("ride_feedback.html", feedback=feedback)

@app.route('/longest_ride')
def longest_ride():
    cursor = g.conn.execute(text("""
        SELECT R.Ride_id, S1.Station_name AS Start_Station, S2.Station_name AS End_Station,
               EXTRACT(EPOCH FROM (R.End_time - R.Start_time))/60 AS Ride_Duration_Minutes
        FROM Ride_has R
        JOIN Has H ON R.Ride_id = H.Ride_id
        JOIN Stations S1 ON H.Station_id_1 = S1.Station_id
        LEFT JOIN Stations S2 ON H.Station_id_2 = S2.Station_id
        ORDER BY Ride_Duration_Minutes DESC
        LIMIT 1;
    """))
    longest_ride = cursor.mappings().first()
    cursor.close()
    return render_template("longest_ride.html", longest_ride=longest_ride)

@app.route('/bikes')
def bikes():
    cursor = g.conn.execute(text("SELECT * FROM Bikes_Belong_to"))
    bikes = [dict(row) for row in cursor.mappings()]
    cursor.close()
    return render_template("bikes.html", bikes=bikes)

@app.route('/users')
def users():
    cursor = g.conn.execute(text("SELECT * FROM users"))
    users = [dict(row) for row in cursor.mappings()]
    cursor.close()
    return render_template("users.html", users=users)

@app.route('/issues')
def issues():
    cursor = g.conn.execute(text("SELECT * FROM Issues"))
    issues = [dict(row) for row in cursor.mappings()]
    cursor.close()
    return render_template("issues.html", issues=issues)

@app.route('/add_ride', methods=['POST'])

def add_ride():
    start_time = parse_time(request.form.get("start_time")) or datetime.now()
    end_time = parse_time(request.form.get("end_time"))
    start_station_id = request.form.get("start_station_id")
    end_station_id = request.form.get("end_station_id")
    bike_id = request.form.get("bike_id")
    bike_type = request.form.get("bike_type")
    user_id = request.form.get("user_id")
    user_type = request.form.get("user_type")
    comments = request.form.get("comments")
    ride_id = generate_unique_ride_id()

    # Validate inputs
    if not start_station_id or not bike_id or not bike_type:
        return "Start station ID, bike ID, and bike type are required.", 400

    if end_time and end_time <= start_time:
        return "End time must be after start time.", 400

    try:
            g.conn.execute(text("""
                INSERT INTO Bikes_Belong_to (Bike_id, Station_id, Bike_type)
                VALUES (:bike_id, :station_id, :bike_type)
                ON CONFLICT (Bike_id) DO NOTHING
            """), {
                'bike_id': bike_id, 
                'station_id': end_station_id, 
                'bike_type': bike_type
            })

            # Insert user if they don't exist
            g.conn.execute(text("""
                INSERT INTO users (User_id, User_type)
                VALUES (:user_id, :user_type)
                ON CONFLICT (User_id) DO NOTHING
            """), {'user_id': user_id, 'user_type': user_type})

            g.conn.execute(text("""
                INSERT INTO Ride_has (Ride_id, Bike_id, Start_time, End_time, Comments)
                VALUES (:ride_id, :bike_id, :start_time, :end_time, :comments)
            """), {'ride_id': ride_id, 'bike_id': bike_id, 'start_time': start_time, 'end_time': end_time, 'comments': comments})
            
            # Insert ride and user association into Rides_Take
            g.conn.execute(text("""
                INSERT INTO Rides_Take (Ride_id, Start_time, End_time, Comments, User_id)
                VALUES (:ride_id, :start_time, :end_time, :comments, :user_id)
            """), {'ride_id': ride_id, 'start_time': start_time, 'end_time': end_time, 'comments': comments, 'user_id': user_id})

            # Insert into Has table
            g.conn.execute(text("""
                INSERT INTO Has (Ride_id, User_id, Station_id_1, Station_id_2)
                VALUES (:ride_id, :user_id, :start_station_id, :end_station_id)
            """), {'ride_id': ride_id, 'user_id': user_id, 'start_station_id': start_station_id, 'end_station_id': end_station_id})

            g.conn.commit()

          
    except Exception as e:
        g.conn.rollback()
        return f"Error adding ride: {str(e)}", 500

    # Redirect to the home page after adding the ride
    return redirect(url_for('index'))


@app.route('/report_issue', methods=['POST'])
def report_issue():
    user_id = request.form.get("user_id")
    issue_type = request.form.get("issue_type")
    photo = request.files.get("photo")  # Optional photo upload

    # Generate string-based IDs
    issue_id = randint(10000, 99999) 
    c_issue_id = randint(10000, 99999) if issue_type == "Charge Issue" else None  # Random 4-digit ID for charge issue
    t_issue_id = randint(10000, 99999) if issue_type == "Technical Issue" else None  # Random 4-digit ID for technical issue

    # Save the photo if provided
    photo_path = None
    if photo and photo.filename != '':
        try:
            filename = secure_filename(photo.filename)
            photo_path = os.path.join('static/uploads', filename)
            photo.save(photo_path)
        except Exception as e:
            return f"Error saving photo: {str(e)}", 500

    try:
        # Insert the issue into the Issues table
        g.conn.execute(text("""
            INSERT INTO Issues (issue_id, c_issue_id, t_issue_id)
            VALUES (:issue_id, :c_issue_id, :t_issue_id)
        """), {
            'issue_id': issue_id,
            'c_issue_id': c_issue_id,
            't_issue_id': t_issue_id
        })

        # Commit the transaction
        g.conn.commit()

    except Exception as e:
        g.conn.rollback()  # Rollback in case of error
        return f"Error reporting issue: {str(e)}", 500

    return redirect(url_for('issues'))

@app.route('/delete_user', methods=['POST'])
def delete_user():
    user_id = request.form.get("user_id")  # Get user ID from the form

    if not user_id:
        return "User ID is required.", 400

    try:
        # Delete related data from Rides_Take (if exists)
        g.conn.execute(text("""
            DELETE FROM Rides_Take WHERE User_id = :user_id
        """), {'user_id': user_id})

        # Delete the user
        g.conn.execute(text("""
            DELETE FROM users WHERE User_id = :user_id
        """), {'user_id': user_id})

        g.conn.commit()  # Commit the transaction

    except Exception as e:
        g.conn.rollback()  # Rollback in case of an error
        return f"Error deleting user: {str(e)}", 500

    return redirect(url_for('users'))


if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):
    """
    This function handles command line parameters.
    Run the server using

        python server.py

    Show the help text using

        python server.py --help

    """

    HOST, PORT = host, port
    print("running on %s:%d" % (HOST, PORT))
    app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


  run()


