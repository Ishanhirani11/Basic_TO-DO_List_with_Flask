import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config, basedir
from models import db, User, Todo, Category
from forms import LoginForm, RegistrationForm, TaskForm, CategoryForm, ProfileForm

app = Flask(__name__)
app.config.from_object(Config)

UPLOAD_FOLDER = os.path.join(basedir, 'static/avatars')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route('/', methods=['GET'])
@login_required
def index():
    tasks = current_user.tasks.order_by(Todo.completed, Todo.order).all()
    return render_template('index.html', tasks=tasks)

@app.route('/create-task', methods=['GET', 'POST'])
@login_required
def create_task():
    form = TaskForm()
    categories = current_user.categories.all()
    form.category_id.choices = [(0, 'No Category')] + [(c.id, c.name) for c in categories]

    if form.validate_on_submit():
        cat_id = form.category_id.data if form.category_id.data != 0 else None
        
        last_task = current_user.tasks.order_by(Todo.order.desc()).first()
        new_order = last_task.order + 1 if last_task else 0
        
        task = Todo(
            content=form.content.data, 
            due_date=form.due_date.data, 
            priority=form.priority.data, 
            category_id=cat_id,
            author=current_user,
            order=new_order
        )
        db.session.add(task)
        db.session.commit()
        flash('Task added successfully!', 'success')
        return redirect(url_for('index'))
        
    return render_template('create_task.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not check_password_hash(user.password_hash, form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        flash('Logged in successfully.', 'success')
        return redirect(url_for('index'))
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, password_hash=generate_password_hash(form.password.data))
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/complete/<int:id>')
@login_required
def complete(id):
    task = Todo.query.get_or_404(id)
    if task.author != current_user:
        flash('Unauthorized', 'danger')
        return redirect(url_for('index'))
    task.completed = not task.completed
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    task = Todo.query.get_or_404(id)
    if task.author != current_user:
        flash('Unauthorized', 'danger')
        return redirect(url_for('index'))
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted!', 'success')
    return redirect(url_for('index'))

@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update(id):
    task = Todo.query.get_or_404(id)
    if task.author != current_user:
        flash('Unauthorized', 'danger')
        return redirect(url_for('index'))
    
    form = TaskForm(obj=task)
    categories = current_user.categories.all()
    form.category_id.choices = [(0, 'No Category')] + [(c.id, c.name) for c in categories]
    
    if request.method == 'GET':
        form.category_id.data = task.category_id if task.category_id else 0

    if form.validate_on_submit():
        task.content = form.content.data
        task.due_date = form.due_date.data
        task.priority = form.priority.data
        task.category_id = form.category_id.data if form.category_id.data != 0 else None
        db.session.commit()
        flash('Task updated!', 'success')
        return redirect(url_for('index'))
    
    return render_template('update.html', task=task, form=form)

@app.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    form = CategoryForm()
    if form.validate_on_submit():
        cat = Category(name=form.name.data, color=form.color.data, owner=current_user)
        db.session.add(cat)
        db.session.commit()
        flash('Category added.', 'success')
        return redirect(url_for('categories'))
    
    cats = current_user.categories.all()
    return render_template('categories.html', categories=cats, form=form)

@app.route('/categories/delete/<int:id>')
@login_required
def delete_category(id):
    cat = Category.query.get_or_404(id)
    if cat.owner != current_user:
        flash('Unauthorized', 'danger')
        return redirect(url_for('categories'))
    db.session.delete(cat)
    db.session.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('categories'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        
        pic = request.files.get('profile_pic')
        if pic and pic.filename:
            filename = secure_filename(pic.filename)
            # Create unique filename
            unique_filename = f"user_{current_user.id}_{filename}"
            pic.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            current_user.profile_pic = unique_filename
            
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
        
    return render_template('profile.html', form=form)

@app.route('/reorder', methods=['POST'])
@login_required
def reorder():
    data = request.get_json()
    for item in data:
        task = Todo.query.get(item['id'])
        if task and task.author == current_user:
            task.order = item['order']
    db.session.commit()
    return jsonify({'status': 'success'})

if __name__ == "__main__":
    app.run(debug=True)
