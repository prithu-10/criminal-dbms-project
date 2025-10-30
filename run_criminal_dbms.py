import os
import psycopg2
import psycopg2.extras  # For dictionary cursors
import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
# We don't need these as we're using plain-text passwords per your schema
# from werkzeug.security import generate_password_hash, check_password_hash

# --- 1. APP SETUP ---
load_dotenv()

app = Flask(__name__)
# Make sure to set a strong, random secret key in your .env file
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'a_very_strong_default_secret_key_dev_only')

# --- 2. DATABASE & UTILITY FUNCTIONS ---

def get_db_connection():
    """Establishes a connection to the Supabase (PostgreSQL) database."""
    try:
        # This MUST be your Connection Pooler string (port 6543)
        conn_string = os.getenv('DATABASE_URL')
        if not conn_string:
            print("DATABASE_URL not found in .env file!")
            return None
        
        conn = psycopg2.connect(conn_string)
        # print("✅ Database connection successful!") # Optional: Can be noisy
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

@app.context_processor
def inject_now():
    """Makes the 'now' variable available to all templates (for copyright year, etc.)."""
    return {'now': datetime.datetime.utcnow()}

# --- 3. AUTHENTICATION ROUTES ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn:
            try:
                # Use DictCursor to get results as dictionaries (all lowercase keys)
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute('SELECT * FROM LawEnforcement WHERE Username = %s', (username,))
                user = cursor.fetchone()
                
                # Check plaintext password (as stored in your sample data)
                if user and user['passwordhash'] == password:
                    session['officer_id'] = user['officerid']
                    session['username'] = user['username']
                    session['officer_name'] = f"{user['firstname']} {user['lastname']}"
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid username or password! Use: admin / admin123', 'error')
            except Exception as e:
                flash(f'Login error: {str(e)}', 'error')
            finally:
                cursor.close()
                conn.close()
        else:
            flash('Database connection failed! Check .env file and network.', 'error')
    
    # Renders your standalone login.html page
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# --- 4. MAIN NAVIGATION ROUTES ---

@app.route('/dashboard')
def dashboard():
    """Optimized dashboard function to match dashboard.html"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed!', 'error')
        return render_template('dashboard.html', 
                               officer_name=session.get('officer_name', 'Officer'),
                               total_criminals=0, open_cases=0, closed_cases=0,
                               crime_types=0, recent_activities=[])

    total_criminals, open_cases, closed_cases, crime_types = 0, 0, 0, 0
    recent_activities = []
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute('SELECT COUNT(*) as total FROM Criminal')
        total_criminals = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM CaseTable WHERE Status IN ('Open', 'Under Investigation')")
        open_cases = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as total FROM CaseTable WHERE Status LIKE 'Closed%'")
        closed_cases = cursor.fetchone()['total']

        cursor.execute('SELECT COUNT(*) as total FROM Crime')
        crime_types = cursor.fetchone()['total']

        cursor.execute("""
            SELECT c.FirstName, c.LastName, cc.Role, ct.CaseTitle, cc.DateAssociated
            FROM CriminalCase cc
            JOIN Criminal c ON cc.CriminalID = c.CriminalID
            JOIN CaseTable ct ON cc.CaseID = ct.CaseID
            ORDER BY cc.DateAssociated DESC
            LIMIT 5
        """)
        # We must use all-lowercase keys in the template
        recent_activities = cursor.fetchall()
        
    except Exception as e:
        flash(f'Error loading dashboard data: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return render_template('dashboard.html', 
                           officer_name=session.get('officer_name', 'Officer'),
                           total_criminals=total_criminals,
                           open_cases=open_cases,
                           closed_cases=closed_cases,
                           crime_types=crime_types,
                           recent_activities=recent_activities)
@app.route('/reports')
def reports():
    """Optimized reports function to match reports.html"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed!', 'error')
        # Provide empty lists to prevent render errors
        return render_template('reports.html', 
                               case_status_report=[], 
                               crime_stats=[], 
                               criminal_status_report=[])
        
    case_status_report, crime_stats, criminal_status_report = [], [], []
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Get case_status_report (FIXED: as total)
        cursor.execute('''
            SELECT Status, COUNT(*) as total 
            FROM CaseTable 
            GROUP BY Status 
            ORDER BY Status
        ''')
        case_status_report = cursor.fetchall()
        
        # 2. Get crime_stats (FIXED: as total)
        cursor.execute('''
            SELECT cr.CrimeType, COUNT(cci.CaseID) as total
            FROM Crime cr
            LEFT JOIN CaseCrime cci ON cr.CrimeID = cci.CrimeID
            GROUP BY cr.CrimeType
            ORDER BY total DESC
        ''')
        crime_stats = cursor.fetchall()
        
        # 3. Get criminal_status_report (FIXED: as total)
        cursor.execute('''
            SELECT Status, COUNT(*) as total 
            FROM Criminal 
            GROUP BY Status 
            ORDER BY Status
        ''')
        criminal_status_report = cursor.fetchall()
        
    except Exception as e:
        flash(f'Error loading reports: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    # Pass the EXACT variable names the HTML expects
    return render_template('reports.html', 
                           case_status_report=case_status_report, 
                           crime_stats=crime_stats, 
                           criminal_status_report=criminal_status_report)

@app.route('/search', methods=['GET', 'POST'])
def search():
    """Optimized search function to match search.html"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
    
    search_results = []
    search_type = request.form.get('search_type', '')
    query_term = request.form.get('query', '')
    
    if request.method == 'POST':
        if not query_term or not search_type:
            flash('Please select a search type and enter a query.', 'warning')
            return render_template('search.html', results=[], search_type=search_type, query=query_term)

        conn = get_db_connection()
        if not conn:
            flash('Database connection failed!', 'error')
            return render_template('search.html', results=[], search_type=search_type, query=query_term)
        
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            search_pattern = f"%{query_term}%" 

            if search_type == 'criminal':
                sql = """
                    SELECT * FROM Criminal 
                    WHERE LOWER(FirstName) LIKE LOWER(%s) 
                       OR LOWER(LastName) LIKE LOWER(%s) 
                       OR LOWER(NationalID) LIKE LOWER(%s)
                """
                cursor.execute(sql, (search_pattern, search_pattern, search_pattern))
                search_results = cursor.fetchall()
            
            elif search_type == 'case':
                sql = """
                    SELECT ct.*, l.Address, l.City 
                    FROM CaseTable ct
                    LEFT JOIN Location l ON ct.LocationID = l.LocationID
                    WHERE LOWER(ct.CaseTitle) LIKE LOWER(%s)
                       OR LOWER(ct.Description) LIKE LOWER(%s)
                       OR LOWER(ct.CaseNumber) LIKE LOWER(%s)
                """
                cursor.execute(sql, (search_pattern, search_pattern, search_pattern))
                search_results = cursor.fetchall()
            
            if not search_results:
                flash('No results found.', 'info')
            else:
                flash(f"Found {len(search_results)} result(s).", 'success')
                
        except Exception as e:
            flash(f'Search error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return render_template('search.html', 
                           results=search_results, 
                           search_type=search_type, 
                           query=query_term)

# --- 5. CRIMINAL CRUD ROUTES ---

@app.route('/criminals')
def criminals():
    """Matches criminals.html"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed!', 'error')
        return render_template('criminals.html', criminals=[])
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT * FROM Criminal ORDER BY CriminalID DESC')
    criminals_list = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('criminals.html', criminals=criminals_list)

@app.route('/criminals/add', methods=['GET', 'POST'], endpoint='add_criminal')
def add_criminal():
    """Matches add_criminal.html"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        dob = request.form['dob'] # Matches 'dob' from HTML
        gender = request.form['gender']
        national_id = request.form['national_id']
        address = request.form['address']
        status = request.form['status']
        danger_level = request.form['danger_level'] # Matches 'danger_level' from HTML
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed!', 'error')
            return redirect(url_for('criminals'))
            
        try:
            cursor = conn.cursor()
            # Use the stored procedure
            cursor.execute(
                "SELECT sp_AddCriminalWithCase(%s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL);",
                (first_name, last_name, dob, gender, national_id, address, status, danger_level)
            )
            conn.commit()
            flash(f"Successfully added criminal: {first_name} {last_name}", 'success')
        except Exception as e:
            conn.rollback() 
            flash(f'Error adding criminal: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('criminals'))
    
    return render_template('add_criminal.html')

@app.route('/criminals/edit/<int:criminal_id>', methods=['GET', 'POST'], endpoint='edit_criminal')
def edit_criminal(criminal_id):
    """Matches edit_criminal.html"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed!', 'error')
        return redirect(url_for('criminals'))
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        dob = request.form['dob'] # Matches 'dob' from HTML
        gender = request.form['gender']
        national_id = request.form['national_id']
        address = request.form['address']
        status = request.form['status']
        danger_level = request.form['danger_level']
        
        try:
            cursor.execute(
                """
                UPDATE Criminal 
                SET FirstName = %s, LastName = %s, DateOfBirth = %s, Gender = %s, 
                    NationalID = %s, Address = %s, Status = %s, DangerLevel = %s,
                    UpdatedAt = NOW()
                WHERE CriminalID = %s
                """,
                (first_name, last_name, dob, gender, national_id, address, status, danger_level, criminal_id)
            )
            conn.commit()
            flash('Criminal record updated successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error updating criminal: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('criminals'))
    
    # GET request: Fetch data to pre-fill the form
    try:
        cursor.execute("SELECT * FROM Criminal WHERE CriminalID = %s", (criminal_id,))
        criminal = cursor.fetchone()
        if not criminal:
            flash('Criminal not found!', 'error')
            return redirect(url_for('criminals'))
        # Pass the criminal object (with lowercase keys) to the template
        return render_template('edit_criminal.html', criminal=criminal)
    except Exception as e:
        flash(f'Error fetching criminal data: {str(e)}', 'error')
        return redirect(url_for('criminals'))
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

@app.route('/criminals/delete/<int:criminal_id>', methods=['POST'], endpoint='delete_criminal')
def delete_criminal(criminal_id):
    """Matches the <form> in criminals.html"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed!', 'error')
        return redirect(url_for('criminals'))
        
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Criminal WHERE CriminalID = %s", (criminal_id,))
        conn.commit()
        flash('Criminal record deleted successfully.', 'success')
    except Exception as e:
        conn.rollback()
        # A more helpful error for foreign key constraints
        if 'violates foreign key constraint' in str(e):
             flash(f'Error: Cannot delete criminal. They are still associated with one or more cases.', 'error')
        else:
            flash(f'Error deleting criminal: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('criminals'))

# --- 6. CASE CRUD ROUTES ---

@app.route('/cases')
def cases():
    """Optimized cases function to match cases.html"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed!', 'error')
        return render_template('cases.html', cases=[])
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # This query JOINS all related tables and aggregates data
        sql_query = """
            SELECT
                ct.CaseID, ct.CaseTitle, ct.DateReported, ct.Status,
                l.Address, l.City, l.State,
                STRING_AGG(DISTINCT CONCAT(c.FirstName, ' ', c.LastName), ', ') AS criminals,
                STRING_AGG(DISTINCT cr.CrimeType, ', ') AS crimes
            FROM CaseTable ct
            LEFT JOIN Location l ON ct.LocationID = l.LocationID
            LEFT JOIN CriminalCase cc ON ct.CaseID = cc.CaseID
            LEFT JOIN Criminal c ON cc.CriminalID = c.CriminalID
            LEFT JOIN CaseCrime cci ON ct.CaseID = cci.CaseID
            LEFT JOIN Crime cr ON cci.CrimeID = cr.CrimeID
            GROUP BY ct.CaseID, l.Address, l.City, l.State
            ORDER BY ct.CaseID DESC
        """
        cursor.execute(sql_query)
        cases_list = cursor.fetchall()
        
    except Exception as e:
        flash(f'Error loading cases: {str(e)}', 'error')
        cases_list = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('cases.html', cases=cases_list)

@app.route('/cases/add', methods=['GET', 'POST'], endpoint='add_case')
def add_case():
    """Matches add_case.html"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed!', 'error')
        return redirect(url_for('cases'))
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    if request.method == 'POST':
        try:
            case_title = request.form['case_title']
            description = request.form['description']
            date_reported = request.form['date_reported']
            status = request.form['status']
            priority = request.form['priority']
            location_id = request.form['location_id']
            officer = request.form['investigating_officer']
            
            case_number = f"CASE-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

            cursor.execute(
                """
                INSERT INTO CaseTable 
                (CaseTitle, Description, DateReported, Status, Priority, LocationID, InvestigatingOfficer, CaseNumber)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (case_title, description, date_reported, status, priority, location_id, officer, case_number)
            )
            conn.commit()
            flash('Case added successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error adding case: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('cases'))

    # GET request: Show the "add case" form, populating the location dropdown
    try:
        cursor.execute("SELECT LocationID, Address, City FROM Location ORDER BY City")
        locations = cursor.fetchall() # Used to populate <select> in HTML
        return render_template('add_case.html', locations=locations)
    except Exception as e:
        flash(f'Error loading page: {str(e)}', 'error')
        return redirect(url_for('cases'))
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

@app.route('/cases/edit/<int:case_id>', methods=['GET', 'POST'], endpoint='edit_case')
def edit_case(case_id):
    """Matches edit_case.html"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed!', 'error')
        return redirect(url_for('cases'))
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    if request.method == 'POST':
        try:
            case_title = request.form['case_title']
            description = request.form['description']
            date_reported = request.form['date_reported']
            date_closed = request.form.get('date_closed') or None # Handle optional field
            status = request.form['status']
            priority = request.form['priority']
            location_id = request.form['location_id']
            officer = request.form['investigating_officer']
            
            cursor.execute(
                """
                UPDATE CaseTable 
                SET CaseTitle = %s, Description = %s, DateReported = %s, DateClosed = %s, 
                    Status = %s, Priority = %s, LocationID = %s, InvestigatingOfficer = %s,
                    UpdatedAt = NOW()
                WHERE CaseID = %s
                """,
                (case_title, description, date_reported, date_closed, status, priority, location_id, officer, case_id)
            )
            conn.commit()
            flash('Case updated successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error updating case: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('cases'))

    # GET request: Fetch data to pre-fill the form
    try:
        cursor.execute("SELECT * FROM CaseTable WHERE CaseID = %s", (case_id,))
        case = cursor.fetchone()
        
        cursor.execute("SELECT LocationID, Address, City FROM Location ORDER BY City")
        locations = cursor.fetchall() # For the location dropdown
        
        if not case:
            flash('Case not found!', 'error')
            return redirect(url_for('cases'))
            
        return render_template('edit_case.html', case=case, locations=locations)
        
    except Exception as e:
        flash(f'Error fetching case data: {str(e)}', 'error')
        return redirect(url_for('cases'))
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

@app.route('/cases/delete/<int:case_id>', methods=['POST'], endpoint='delete_case')
def delete_case(case_id):
    """Matches the <form> in cases.html (if you add one)"""
    if 'officer_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed!', 'error')
        return redirect(url_for('cases'))
        
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM CaseTable WHERE CaseID = %s", (case_id,))
        conn.commit()
        flash('Case deleted successfully.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting case: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('cases'))

# --- 7. RUN THE APPLICATION ---

if __name__ == '__main__':
 
    print(f" Open: http://localhost:{os.getenv('PORT', 5000)}")
    print("Login: admin / admin123")
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))