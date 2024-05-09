from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_, or_
from datetime import datetime, timedelta, date
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, ValidationError


app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] =  "sqlite:///users.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config['SECRET_KEY'] = 'ax_345jiug!juhKO98_jut'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'home'  # Redirect users to the home page to login


db = SQLAlchemy(app)


gym_places = [
    "Grand Gymnase en entier",
    "Grand Gymnase : section 1",
    "Grand Gymnase : section 2",
    "Grand Gymnase : section 3",
    "Petit Gymnase en entier",
    "Petit Gymnase : section 1",
    "Petit Gymnase : section 2",
    "Mur d'escalade"
]

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    # reservations = db.relationship('Reservation', backref='user', lazy=True)  # This line is optional since it's defined in Reservation

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class LoginForm(FlaskForm):
    username = StringField('Nom d\'utilisateur', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField('Login')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), EqualTo('confirm', message='Passwords must match')])
    confirm = PasswordField('Repeat Password', validators=[DataRequired()])
    submit = SubmitField('Register')


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_of_reservation = db.Column(db.Date, nullable=False)
    time_of_reservation = db.Column(db.Time, nullable=False)
    end_time_of_reservation = db.Column(db.Time, nullable=False)
    booked_place = db.Column(db.String(50), nullable=False)
    user = db.relationship('User', backref=db.backref('reservations', lazy=True))


@app.route('/')
def home():
    form = LoginForm()
    return render_template('home.html', login_form = form)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if username already exists
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            flash('Username already exists. Please choose a different one.')
            return redirect(url_for('register'))
        
        # Create new user with hashed password
        hashed_password = generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('home'))
    return render_template('register.html', title='Register', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if user.check_password(form.password.data):
                login_user(user)
                return redirect(url_for('booking'))
            else:
                flash('Invalid password provided.', 'error')
        else:
            flash('Username does not exist.', 'error')
    return redirect(url_for('home'))  # Redirect back to home for any form issues


@app.route('/booking')
@login_required
def booking():
    all_reservations = Reservation.query.filter_by(user_id=current_user.id).all()
    return render_template('booking.html', reservations=all_reservations, gym_places = gym_places)



@app.route('/create_reservation', methods=['POST'])
@login_required
def create_reservation():
    booked_place = request.form['booked_place']
    date_of_reservation = datetime.strptime(request.form['date_of_reservation'], '%Y-%m-%d').date()
    start_time = datetime.strptime(request.form['time_of_reservation'], '%H:%M').time()
    end_time = datetime.strptime(request.form['end_time_of_reservation'], '%H:%M').time()
    user_id = current_user.id

    # Ensure end_time is within 1 hour of start_time
    max_end_time = (datetime.combine(date.min, start_time) + timedelta(hours=1)).time()
    if end_time > max_end_time:
        flash('End time must be within 1 hour of start time.')
        return redirect(url_for('booking'), gym_places=gym_places)
    
    # Check if the place is "Mur d'escalade"
    if booked_place == "Mur d'escalade":
        existing_reservations_count = Reservation.query.filter(
            Reservation.date_of_reservation == date_of_reservation,
            Reservation.booked_place == booked_place,
            or_(and_(Reservation.start_time <= start_time, Reservation.end_time > start_time),
                and_(Reservation.start_time < end_time, Reservation.end_time >= end_time))
        ).count()

        if existing_reservations_count >= 5:
            flash('Mur d\'escalade is fully booked for this time slot.', 'danger')
            return redirect(url_for('booking'), gym_places=gym_places)
        
    else:
        # For all other places, ensure no overlapping reservations
        existing_reservation = Reservation.query.filter(
            Reservation.date_of_reservation == date_of_reservation,
            Reservation.booked_place == booked_place,
            or_(and_(Reservation.time_of_reservation <= start_time, Reservation.end_time_of_reservation > start_time),
                and_(Reservation.time_of_reservation < end_time, Reservation.end_time_of_reservation >= end_time))
        ).first()

        if existing_reservation:
            flash('This place is already booked for the selected time slot.', 'danger')
            return redirect(url_for('booking'), gym_places=gym_places)

    new_reservation = Reservation(
        user_id=current_user.id,  # Set the user_id to the current user's ID
        date_of_reservation=date_of_reservation,
        time_of_reservation=start_time,
        end_time_of_reservation=end_time,
        booked_place=booked_place
    )

    db.session.add(new_reservation)
    db.session.commit()

    flash('Reservation successfully created!')
    return redirect(url_for('reservations'), gym_places=gym_places)

@app.route('/api/reservations', methods=['GET'])
def get_reservations():
    # Retrieve the date and place from the query parameters
    date_str = request.args.get('date')
    place_str = request.args.get('place')
    

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    if not place_str:
        return jsonify({'error': 'Place must be specified.'}), 400

    # Query reservations for the given date and place
    reservations = Reservation.query.filter_by(
        date_of_reservation=selected_date,
        booked_place=place_str
    ).all()

    if not reservations:
        return jsonify({'message': 'No reservations found for the specified date and place.'}), 404

    

    reservations_list = [
        {
            'id': r.id,
            'user_id': r.user_id,
            'date_of_reservation': r.date_of_reservation.isoformat(),
            'time_of_reservation': r.time_of_reservation.strftime('%H:%M'),
            'end_time_of_reservation': r.end_time_of_reservation.strftime('%H:%M'),
            'booked_place': r.booked_place
        }
        for r in reservations
    ]

    return jsonify(reservations_list)




# Delete a reservation
@app.route('/delete_reservation/<int:reservation_id>', methods=['POST'])
@login_required
def delete_reservation(reservation_id):
    print('Delete route called for ID:', reservation_id)
    reservation = Reservation.query.get_or_404(reservation_id)
    db.session.delete(reservation)
    db.session.commit()
    return jsonify({'message': 'Reservation deleted successfully'})



# Update a reservation
@app.route('/update_reservation/<int:reservation_id>', methods=['POST'])
@login_required
def update_reservation(reservation_id):
    # Flask-WTF: Validate CSRF token
    if not request.json:
        return jsonify({'message': 'Invalid JSON data'}), 400

    data = request.json
    reservation = Reservation.query.get_or_404(reservation_id)

    # Update reservation with the new details
    reservation.booked_place = data.get('booked_place')
    reservation.date_of_reservation = datetime.strptime(data.get('date_of_reservation'), '%Y-%m-%d').date()
    reservation.time_of_reservation = datetime.strptime(data.get('time_of_reservation'), '%H:%M').time()
    reservation.end_time_of_reservation = datetime.strptime(data.get('end_time_of_reservation'), '%H:%M').time()

    # Update the database
    db.session.commit()
    return jsonify({'message': 'Reservation updated successfully'})


@app.route('/reservations')
@login_required
def reservations():
    all_reservations = Reservation.query.filter_by(user_id=current_user.id).all()
    return render_template('booking.html', reservations=all_reservations, gym_places=gym_places)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)




