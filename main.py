from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
# from email_validator import validate_email, EmailNotValidError
import secrets

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200), unique=True, nullable=False)
    first_name = db.Column(db.String(200), nullable=False)
    last_name = db.Column(db.String(200), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    money_spent = db.Column(db.Integer, nullable=False, default=0)
    secret_key = db.Column(db.String(200), nullable=False, default="")

    def __repr__(self):
        return f"{self.first_name} {self.last_name} - {self.username}"

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Foreign key to sender
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Foreign key to receiver
    sender = db.relationship('User', foreign_keys=[sender_id],
                             backref='sent_transactions')
    receiver = db.relationship('User', foreign_keys=[receiver_id],
                               backref='received_transactions')
    fulfilled = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"{self.description} - {self.amount}"

# login and signup

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data received'}), 400

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    try:
        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            return jsonify({'message': 'Login successful'}), 200
        else:
            return jsonify({'error': 'Invalid username or password'}), 401  # 401 Unauthorized

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'An error occurred during login'}), 500

''' 
test
@app.route('/create_account', methods=['POST'])
def create_account():
    data = request.get_json()

    return jsonify(data), 201
'''

# creating new user
# getting info from front end and creating new user on server (post request)

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data received'}), 400

    try:
        username = data.get('username')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        password = data.get('password')

        if not all([username, first_name, last_name, email, password]):
            return jsonify({'error': 'Missing required fields'}), 400

        if len(username) < 4 or len(username) > 20:
            return jsonify({'error': 'Username must be between 4 and 20 characters'}), 400

        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400

        new_user = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            secret_key= secrets.token_urlsafe(32)
        )
        db.session.add(new_user)
        db.session.commit()

        return jsonify({'message': 'User created successfully'}), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Username or email already exists'}), 409

    except Exception as e:
        db.session.rollback()
        print(f"An unexpected error occurred during signup: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

# create new transaction
# getting info from front end and creating new transaction on server (post request)

@app.route('/transactions/new', methods=['POST'])
def create_transaction():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data received'}), 400

    try:
        amount = data.get('amount')
        description = data.get('description')
        sender_username = data.get('sender_username')
        receiver_username = data.get('receiver_username')

        if not all([amount, description, sender_username, receiver_username]):
            return jsonify({'error': 'Missing required fields'}), 400

        if not isinstance(amount, (int, float)):
            return jsonify({'error': 'Amount must be a number'}), 400

        if amount <= 0:
            return jsonify({'error': 'Amount must be greater than zero'}), 400

        sender = User.query.filter_by(username=sender_username).first()
        receiver = User.query.filter_by(username=receiver_username).first()

        if not sender:
            return jsonify({'error': 'Sender does not exist'}), 404
        if not receiver:
            return jsonify({'error': 'Receiver does not exist'}), 404

        if sender == receiver:
            return jsonify({'error': 'Sender and receiver cannot be the same'}), 400

        new_transaction = Transaction(
            description=description,
            amount=amount,
            sender=sender,
            receiver=receiver
        )

        db.session.add(new_transaction)

        db.session.commit()

        transaction_data = {
            'id': new_transaction.id,
            'description': new_transaction.description,
            'amount': new_transaction.amount,
            'sender': new_transaction.sender.username,
            'receiver': new_transaction.receiver.username,
            'fulfilled': new_transaction.fulfilled
        }

        return jsonify(transaction_data), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Transaction could not be created'}), 400

    except Exception as e:
        db.session.rollback()
        print(f"An unexpected error occurred: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

# if transaction button is pressed on the front end
# updating fulfilled variable and money_spent amount on server (put request)

@app.route('/transactions/<int:id>/fulfilled', methods=['PUT'])
def fulfill_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    try:
        data = request.get_json()
        transaction.fulfilled = True
        receiver = transaction.receiver
        receiver.money_spent += transaction.amount
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        print(f"Error fulfilling transaction: {e}")
        return jsonify({'error': 'An error occurred'}), 500

# split transaction and send requests to other users
# creation of a transaction that is going to turn into two separate transactions (post request)
# to do

# getting all transactions, sends back json of all the transactions
# getting info from server and sending to front end (get request)

@app.route('/transactions', methods=['GET'])
def get_transactions():
    transactions = Transaction.query.all()

    output = []
    for transaction in transactions:
        transaction_data = {'description' : transaction.description, 'amount' : transaction.amount}
        output.append(transaction_data)

    return {"transactions": output}, 200

# getting all users, might want to add another route for getting users involved with each other through transactions
# sends back json of all users

@app.route('/users', methods=['POST'])
def get_users():
    users = User.query.all()

    output = []
    for user in users:
        user_data = {'user' : user.username, 'user first_name' : user.first_name,
                     'user last_name' : user.last_name, 'email' : user.email,
                     'password' : user.password, 'money spent' : user.money_spent}
        output.append(user_data)

    return jsonify({"users" : output}), 200

# getting a specific user based on id
# sends back json of one user based on id

@app.route('/users/<int:id>', methods=['GET', 'POST'])
def get_user(id):
    user = User.query.get_or_404(id)
    return jsonify({'user' : user.username, 'user first_name' : user.first_name,
                    'user last_name' : user.last_name, 'email' : user.email,
                    'password' : user.password, 'money spent' : user.money_spent})

@app.route('/users/<int:id>/update', methods=['GET', 'PUT'])
def update_user(id):
    user = User.query.get_or_404(id)

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data received'}), 400

    try:
        if 'username' in data:
            username = data['username']
            if len(username) < 4 or len(username) > 20:
                return jsonify({'error': 'Username must be between 4 and 20 characters'}), 400
            existing_user = User.query.filter_by(username=username).first()
            if existing_user and existing_user.id != user.id:  # Allow same username if it's the current user
                return jsonify({'error': 'Username already exists'}), 409

            user.username = username

        if 'first_name' in data:
            user.first_name = data['first_name']

        if 'last_name' in data:
            user.last_name = data['last_name']

        if 'email' in data:
            email = data['email']
            user.email = email

        if 'password' in data:
            password = data['password']
            if len(password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters'}), 400
            user.password = password

        db.session.commit()
        return jsonify({'message': 'User updated successfully'}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error updating user: {e}")
        return jsonify({'error': 'An error occurred while updating the user'}), 500


@app.route('/users/<int:id>/spending', methods=['GET', 'POST'])
def get_user_spending(id):
    user = User.query.get_or_404(id)
    return jsonify({"user" : user.name, "user spent" : user.money_spent}, 200)

@app.route('/users/<int:id>/transactions', methods=['GET', 'POST'])
def get_user_transactions(id):
    user = User.query.get_or_404(id)

    sent_transactions = []
    received_transactions = []

    for transaction in user.sent_transactions:
        sent_transactions.append({
            'description': transaction.description,
            'sender': transaction.sender.username,
            'receiver': transaction.receiver.username,
            'amount': transaction.amount
        })

    for transaction in user.received_transactions:
        received_transactions.append({
            'description': transaction.description,
            'sender': transaction.sender.username,
            'receiver': transaction.receiver.username,
            'amount': transaction.amount
        })

    return jsonify({
        'user' : user.username,
        'sent_transactions': sent_transactions,
        'received_transactions': received_transactions
    }), 200

@app.route("/spent", methods=['POST'])
def get_total_spent():
    users = User.query.all()

    total = 0
    individual_spent = {}

    for user in users:
        total += user.money_spent
        individual_spent[user.username] = user.money_spent

    return jsonify({"total spent" : total, "spending breakdown" : individual_spent})

# deleting a user will delete transactions !! Must consider how to move forward with this...
#@app.route('user/<int:id>/dashboard', methods=['GET'])
#def display():

'''
@app.route('/users/<int:id>', methods=['DELETE'])  
def delete_user(id):
    user = User.query.get_or_404(id) 

    try:
        # Delete associated transactions first (important for data integrity)
        Transaction.query.filter_by(sender_id=user.id).delete() 
        Transaction.query.filter_by(receiver_id=user.id).delete()  
        db.session.delete(user)  # Delete the user
        db.session.commit()
        return jsonify({'message': 'User deleted successfully'}), 204

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting user: {e}")
        return jsonify({'error': 'An error occurred while deleting the user'}), 500
'''

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)