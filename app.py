import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import os

import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-me-in-prod')

# 🗃 БАЗА ДАННЫХ: Только SQLite в /tmp/ для Render
# Это работает с любой версией Python, не требует psycopg2
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/school.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 🗃 База данных: автоматически переключается между SQLite (локально) и PostgreSQL (Render)
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)  # SQLAlchemy фикс


# 📁 Папка загрузок
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

ALLOWED_VIDEO = {'mp4', 'webm', 'ogg', 'mov', 'avi'}
ALLOWED_AUDIO = {'mp3', 'wav', 'ogg', 'aac', 'm4a'}
ALLOWED_FILES = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'zip', 'rar', 'png', 'jpg', 'jpeg'}


def allowed_file_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO


def allowed_file_audio(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO


def allowed_file_doc(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_FILES


# ==================== СВЯЗУЮЩИЕ ТАБЛИЦЫ ====================
theory_students = db.Table('theory_students',
    db.Column('theory_id', db.Integer, db.ForeignKey('theory.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

homework_students = db.Table('homework_students',
    db.Column('homework_id', db.Integer, db.ForeignKey('homework.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

# ==================== МОДЕЛИ ====================



# ==================== 1. ОСНОВНЫЕ МОДЕЛИ ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    birth_date = db.Column(db.String(20), nullable=False)
    grade = db.Column(db.String(20), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    agreed_terms = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Theory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    comment = db.Column(db.Text, default='')
    is_visible = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subtopics = db.relationship('Subtopic', backref='theory', cascade='all, delete-orphan', lazy=True)
    main_videos = db.relationship('TheoryVideo', backref='theory', cascade='all, delete-orphan', lazy=True)
    main_files = db.relationship('TheoryFile', backref='theory', cascade='all, delete-orphan', lazy=True)
    main_audios = db.relationship('TheoryAudio', backref='theory', cascade='all, delete-orphan', lazy=True)
    # ⬇️ ЭТА СТРОКА ОБЯЗАТЕЛЬНА:
    assigned_to = db.relationship('User', secondary=theory_students, backref='assigned_theories', lazy='dynamic')

class Subtopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    theory_id = db.Column(db.Integer, db.ForeignKey('theory.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    videos = db.relationship('Video', backref='subtopic', cascade='all, delete-orphan', lazy=True)
    files = db.relationship('FileAttachment', backref='subtopic', cascade='all, delete-orphan', lazy=True)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subtopic_id = db.Column(db.Integer, db.ForeignKey('subtopic.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)

class FileAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subtopic_id = db.Column(db.Integer, db.ForeignKey('subtopic.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)

class TheoryVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    theory_id = db.Column(db.Integer, db.ForeignKey('theory.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)

class TheoryFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    theory_id = db.Column(db.Integer, db.ForeignKey('theory.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)

class TheoryAudio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    theory_id = db.Column(db.Integer, db.ForeignKey('theory.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)

class Homework(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    deadline = db.Column(db.String(50), nullable=True)
    is_visible = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tasks = db.relationship('Task', backref='homework', cascade='all, delete-orphan', order_by='Task.position')
    # ⬇️ ЭТА СТРОКА ОБЯЗАТЕЛЬНА:
    assigned_to = db.relationship('User', secondary=homework_students, backref='assigned_homeworks', lazy='dynamic')

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    homework_id = db.Column(db.Integer, db.ForeignKey('homework.id'), nullable=False)
    task_type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    extra_data = db.Column(db.Text, default='{}')
    position = db.Column(db.Integer, default=0)
    files = db.relationship('TaskFile', backref='task', cascade='all, delete-orphan')

class TaskFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    homework_id = db.Column(db.Integer, db.ForeignKey('homework.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    answer = db.Column(db.Text)
    score = db.Column(db.Float, default=0)
    max_score = db.Column(db.Float, default=0)  # ⬅️ ДОБАВЬТЕ ЭТУ СТРОКУ
    is_correct = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    # ✅ НОВЫЕ ПОЛЯ ДЛЯ РУЧНОЙ ПРОВЕРКИ
    needs_manual = db.Column(db.Boolean, default=False)
    teacher_grade = db.Column(db.Float, nullable=True)
    teacher_comment = db.Column(db.Text, default='')
    student_files_json = db.Column(db.Text, default='[]')

# ==================== 2. ТАБЛИЦЫ СВЯЗЕЙ (СТРОГО ПОСЛЕ МОДЕЛЕЙ!) ====================


import re
from markupsafe import Markup


@app.template_filter('render_blanks')
def render_blanks_filter(text, hidden_words):
    if not text or not hidden_words: return text
    res = text
    # 1. Заменяем слова на уникальные плейсхолдеры (чтобы не сломать порядок)
    for i, word in enumerate(hidden_words):
        w = word.strip()
        if w:
            pattern = re.compile(re.escape(w), re.IGNORECASE)
            res = pattern.sub(f'___BLANK_{i}___', res, count=1)

    # 2. Заменяем плейсхолдеры на чистые input'ы с data-атрибутами
    for i in range(len(hidden_words)):
        placeholder = f'___BLANK_{i}___'
        inp = f'<input type="text" class="blank-input" data-blank-idx="{i}" style="border:none; border-bottom:2px solid #667eea; background:transparent; padding:2px 5px; text-align:center; width:100px;">'
        res = res.replace(placeholder, inp)

    return Markup(res)


# ==================== 3. ОБНОВЛЁННЫЕ СВЯЗИ В МОДЕЛЯХ ====================
# Добавьте эти строки внутрь классов Theory и Homework (если ещё не добавили):
# В class Theory:
# assigned_to = db.relationship('User', secondary=theory_students, backref=db.backref('assigned_theories', lazy='dynamic'))
# В class Homework:
# assigned_to = db.relationship('User', secondary=homework_students, backref=db.backref('assigned_homeworks', lazy='dynamic'))

import json

# Регистрируем фильтр для парсинга JSON в шаблонах
@app.template_filter('fromjson')
def fromjson_filter(value):
    try:
        return json.loads(value) if value else {}
    except:
        return {}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== АВТОРИЗАЦИЯ ====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        login = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        birth_date = request.form.get('birth_date', '')
        grade = request.form.get('grade', '')
        agreed = request.form.get('agreed_terms')

        # 1️⃣ Проверка заполнения всех полей
        if not all([login, password, confirm_password, birth_date, grade]):
            flash('⚠️ Заполните все поля!', 'error')
            return render_template('register.html')

        # 2️⃣ Проверка совпадения паролей
        if password != confirm_password:
            flash('⚠️ Пароли не совпадают!', 'error')
            return render_template('register.html')

        # 3️⃣ Проверка согласия с правилами
        if not agreed:
            flash('⚠️ Необходимо принять соглашение об обработке персональных данных!', 'error')
            return render_template('register.html')

        # 4️⃣ ✅ ПРОВЕРКА: Существует ли уже такой логин?
        if User.query.filter_by(login=login).first():
            flash(f'⚠️ Логин "{login}" уже занят! Выберите другой.', 'error')
            return render_template('register.html')

        # 5️⃣ Создание нового пользователя
        user = User(login=login, birth_date=birth_date, grade=grade, agreed_terms=True)
        user.set_password(password)

        # Первый пользователь автоматически становится админом
        if User.query.count() == 0:
            user.is_admin = True

        db.session.add(user)
        db.session.commit()  # Теперь коммит безопасен

        flash('✅ Регистрация успешна! Теперь войдите в систему.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(login=login).first()
        if user and user.check_password(password): login_user(user); return redirect(url_for('home'))
        flash('Неверный логин или пароль!', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))


# ==================== ГЛАВНАЯ ====================
# Главная страница ученика — теперь с двумя кнопками
# Главная страница ученика — теперь с двумя кнопками
@app.route('/')
@login_required
def home():
    if current_user.is_admin:
        return render_template('admin_panel.html')
    else:
        # Ученик видит только назначенное ему
        return render_template('student_home.html')

# Теория для ученика
@app.route('/student/theory')
@login_required
def student_theory():
    if current_user.is_admin:
        return redirect(url_for('admin_theory'))

    all_t = Theory.query.filter_by(is_visible=True).order_by(Theory.created_at.desc()).all()
    theories = [t for t in all_t
                if t.assigned_to.count() == 0 or t.assigned_to.filter_by(id=current_user.id).first()]
    return render_template('student_theory.html', theories=theories)

# ДЗ для ученика



@app.route('/profile')
@login_required
def profile():
    bd = current_user.birth_date
    try:
        dt = datetime.strptime(bd, '%Y-%m-%d'); formatted_date = dt.strftime('%d.%m.%Y')
    except:
        formatted_date = bd
    return render_template('profile.html', formatted_date=formatted_date)


# ==================== АДМИНКА ====================
@app.route('/admin/students')
@login_required
def admin_students():
    if not current_user.is_admin: abort(403)
    return render_template('students_list.html', students=User.query.filter_by(is_admin=False).all())


@app.route('/admin/students/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_student(user_id):
    if not current_user.is_admin: abort(403)
    user = User.query.get(user_id)
    if user and not user.is_admin: db.session.delete(user); db.session.commit()
    return redirect(url_for('admin_students'))


@app.route('/admin/theory')
@login_required
def admin_theory():
    if not current_user.is_admin: abort(403)
    return render_template('theory.html', theories=Theory.query.order_by(Theory.created_at.desc()).all())


# ⬇️ УДАЛИТЕ функцию _save_media, если она есть в вашем app.py

@app.route('/admin/theory/add', methods=['GET', 'POST'])
@login_required
def add_theory():
    if not current_user.is_admin: abort(403)
    students = User.query.filter_by(is_admin=False).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        comment = request.form.get('comment', '').strip()
        assign_to_all = request.form.get('assign_to_all') == 'on'
        selected_students = request.form.getlist('assigned_students')

        if not title:
            flash('Укажите название теории!', 'error')
            return render_template('theory_add.html', students=students)

        theory = Theory(title=title, comment=comment, created_by=current_user.id, is_visible=True)
        if not assign_to_all and selected_students:
            theory.assigned_to = User.query.filter(User.id.in_(selected_students)).all()
        db.session.add(theory)
        db.session.flush()  # Получаем theory.id

        # 1️⃣ СОХРАНЯЕМ ОСНОВНЫЕ ВЛОЖЕНИЯ (прямо к теории)
        for f in request.files.getlist('main_videos'):
            if f and f.filename:
                fn = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{secure_filename(f.filename)}"
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                db.session.add(TheoryVideo(theory_id=theory.id, filename=fn))

        for f in request.files.getlist('main_audios'):
            if f and f.filename:
                fn = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{secure_filename(f.filename)}"
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                db.session.add(TheoryAudio(theory_id=theory.id, filename=fn))

        for f in request.files.getlist('main_files'):
            if f and f.filename:
                fn = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{secure_filename(f.filename)}"
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                db.session.add(TheoryFile(theory_id=theory.id, filename=fn))

        # 2️⃣ СОХРАНЯЕМ ПОДТЕМЫ И ИХ ВЛОЖЕНИЯ
        sub_indices = request.form.getlist('subtopic_idx[]')
        sub_names = request.form.getlist('subtopic_name[]')

        for i, idx_str in enumerate(sub_indices):
            idx = int(idx_str)
            name = sub_names[i].strip()
            if not name: continue

            sub = Subtopic(theory_id=theory.id, name=name)
            db.session.add(sub)
            db.session.flush()  # Получаем sub.id для привязки файлов

            # Видео подтемы
            for f in request.files.getlist(f'sub_videos_{idx_str}'):
                if f and f.filename:
                    fn = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{secure_filename(f.filename)}"
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                    db.session.add(Video(subtopic_id=sub.id, filename=fn))

            # Файлы подтемы
            for f in request.files.getlist(f'sub_files_{idx_str}'):
                if f and f.filename:
                    fn = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{secure_filename(f.filename)}"
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                    db.session.add(FileAttachment(subtopic_id=sub.id, filename=fn))

        db.session.commit()
        flash('✅ Теория успешно добавлена!', 'success')
        return redirect(url_for('admin_theory'))

    return render_template('theory_add.html', students=students)
            # Упрощённая привязка (подставьте нужные foreign keys под ваши модели)
            # Лучше использовать прямую привязку, как в оригинале, но этот хелпер показывает логику.
            # Вернёмся к вашему оригинальному способу привязки, чтобы не ломать FK:

@app.route('/admin/theory/edit/<int:theory_id>', methods=['GET', 'POST'])
@login_required
def edit_theory(theory_id):
    if not current_user.is_admin: abort(403)
    theory = Theory.query.get_or_404(theory_id)

    if request.method == 'POST':
        theory.title = request.form.get('title', '').strip() or theory.title
        theory.comment = request.form.get('comment', '').strip()

        # 1. Собираем ID подтем, которые пользователь оставил в форме
        keep_sub_ids = set()
        sub_indices = request.form.getlist('subtopic_idx[]')
        sub_names = request.form.getlist('subtopic_name[]')

        for idx_str, name in zip(sub_indices, sub_names):
            name = name.strip()
            if not name: continue

            sub = None
            # Если idx - число, значит это существующая подтема из БД
            if idx_str.isdigit():
                sub = Subtopic.query.get(int(idx_str))
                if not sub or sub.theory_id != theory.id:
                    continue  # Пропускаем, если подтема удалена или не принадлежит этой теории
                sub.name = name
                keep_sub_ids.add(sub.id)
            else:
                # Новая подтема (idx начинается с "new_")
                sub = Subtopic(theory_id=theory.id, name=name)
                db.session.add(sub)
                db.session.flush()  # Получаем sub.id из БД
                keep_sub_ids.add(sub.id)

            # Загрузка ВИДЕО в подтему
            for f in request.files.getlist(f'sub_videos_{idx_str}'):
                if f and f.filename:
                    ext = f.filename.rsplit('.', 1)[-1].lower()
                    if ext in {'mp4', 'webm', 'mov', 'avi', 'ogg'}:
                        fn = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{secure_filename(f.filename)}"
                        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                        db.session.add(Video(subtopic_id=sub.id, filename=fn))

            # Загрузка ФАЙЛОВ в подтему
            for f in request.files.getlist(f'sub_files_{idx_str}'):
                if f and f.filename:
                    ext = f.filename.rsplit('.', 1)[-1].lower()
                    if ext in {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'zip', 'rar', 'png', 'jpg', 'jpeg'}:
                        fn = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{secure_filename(f.filename)}"
                        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                        db.session.add(FileAttachment(subtopic_id=sub.id, filename=fn))

        # 2. Удаляем подтемы, которых нет в форме
        for sub in list(theory.subtopics):
            if sub.id not in keep_sub_ids:
                for v in sub.videos:
                    p = os.path.join(app.config['UPLOAD_FOLDER'], v.filename)
                    if os.path.exists(p): os.remove(p)
                for f in sub.files:
                    p = os.path.join(app.config['UPLOAD_FOLDER'], f.filename)
                    if os.path.exists(p): os.remove(p)
                db.session.delete(sub)

        db.session.commit()
        flash('✅ Теория успешно обновлена!', 'success')
        return redirect(url_for('admin_theory'))

    return render_template('theory_edit.html', theory=theory)


@app.route('/admin/theory/toggle/<int:theory_id>')
@login_required
def toggle_theory(theory_id):
    if not current_user.is_admin: abort(403)
    t = Theory.query.get_or_404(theory_id);
    t.is_visible = not t.is_visible;
    db.session.commit()
    return redirect(url_for('admin_theory'))


@app.route('/admin/theory/delete/<int:theory_id>', methods=['POST'])
@login_required
def delete_theory(theory_id):
    if not current_user.is_admin: abort(403)
    t = Theory.query.get_or_404(theory_id)
    for m in t.main_videos + t.main_files + t.main_audios:
        p = os.path.join(app.config['UPLOAD_FOLDER'], m.filename);
        os.path.exists(p) and os.remove(p)
    for sub in t.subtopics:
        for m in sub.videos + sub.files:
            p = os.path.join(app.config['UPLOAD_FOLDER'], m.filename);
            os.path.exists(p) and os.remove(p)
    db.session.delete(t);
    db.session.commit()
    flash('Теория удалена!', 'success');
    return redirect(url_for('admin_theory'))


@app.route('/admin/media/delete/<int:media_id>/<string:media_type>')
@login_required
def delete_media(media_id, media_type):
    if not current_user.is_admin: abort(403)
    if media_type.startswith('main'):
        if 'video' in media_type:
            m = TheoryVideo.query.get_or_404(media_id)
        elif 'audio' in media_type:
            m = TheoryAudio.query.get_or_404(media_id)
        else:
            m = TheoryFile.query.get_or_404(media_id)
    else:
        if media_type == 'video':
            m = Video.query.get_or_404(media_id)
        else:
            m = FileAttachment.query.get_or_404(media_id)

    tid = m.subtopic.theory_id if hasattr(m, 'subtopic') else m.theory_id
    p = os.path.join(app.config['UPLOAD_FOLDER'], m.filename);
    os.path.exists(p) and os.remove(p)
    db.session.delete(m);
    db.session.commit()
    if hasattr(m, 'subtopic'): return redirect(url_for('edit_theory', theory_id=tid))
    return redirect(url_for('edit_theory', theory_id=tid))


from sqlalchemy.orm import joinedload


@app.route('/theory/view/<int:theory_id>')
@login_required
def view_theory(theory_id):
    theory = Theory.query.options(
        joinedload(Theory.subtopics).joinedload(Subtopic.videos),
        joinedload(Theory.subtopics).joinedload(Subtopic.files),
        joinedload(Theory.main_videos),
        joinedload(Theory.main_audios),
        joinedload(Theory.main_files)
    ).get_or_404(theory_id)

    if not theory.is_visible and not current_user.is_admin:
        flash('🔒 Этот материал временно недоступен', 'error')
        return redirect(url_for('student_theory'))

    return render_template('theory_view_single.html', theory=theory)


@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)




@app.route('/admin/stats')
@login_required
def stats():
    if not current_user.is_admin:
        abort(403)
    students_count = User.query.filter_by(is_admin=False).count()
    theories_count = Theory.query.count()
    return f'<h1>📊 Статистика</h1><p>Учеников: {students_count}</p><p>Теорий: {theories_count}</p><a href="/">← На главную</a>'

# ==================== ИНИЦИАЛИЗАЦИЯ ====================


import json


# ==================== МОДЕЛИ ДЗ ====================


# ==================== АВТОПРОВЕРКА ====================
def check_auto_answers(task, student_json):
    """Возвращает (всего, правильных, детализация)"""
    try:
        answers = json.loads(student_json)
        questions = json.loads(task.extra_data)
        results = []
        total = correct = 0

        for i, q in enumerate(questions):
            user_ans = str(answers.get(str(i), "")).strip().lower()
            correct_ans = str(q.get("correct", "")).strip().lower()
            is_ok = user_ans == correct_ans
            if is_ok: correct += 1
            total += 1
            results.append({
                "q_text": q["q"],
                "user_ans": user_ans or "(пусто)",
                "correct_ans": q["correct"],
                "is_correct": is_ok
            })
        return total, correct, results
    except Exception as e:
        print(f"Auto-check error: {e}")
    return 0, 0, []

# ==================== МАРШРУТЫ ДЗ ====================
# ==================== МАРШРУТЫ ДЗ ====================
# ==================== МАРШРУТЫ ДЗ (ЗАМЕНИТЕ ВСЕ СТАРЫЕ ДЗ-РОУТЫ НА ЭТОТ БЛОК) ====================
@app.route('/admin/homework')
@login_required
def admin_homework():
    if not current_user.is_admin: abort(403)
    hws = Homework.query.order_by(Homework.created_at.desc()).all()
    return render_template('admin_homework.html', hws=hws)

@app.route('/admin/homework/new', methods=['GET', 'POST'])
@login_required
def admin_homework_new():
    if not current_user.is_admin: abort(403)
    students = User.query.filter_by(is_admin=False).all()
    if request.method == 'POST':
        return _save_homework(request, students, None)
    return render_template('admin_homework_edit.html', students=students, hw=None, tasks=[])

@app.route('/admin/homework/edit/<int:hw_id>', methods=['GET', 'POST'])
@login_required
def admin_homework_edit(hw_id):
    if not current_user.is_admin: abort(403)
    hw = Homework.query.get_or_404(hw_id)
    students = User.query.filter_by(is_admin=False).all()
    # Парсим существующие задания для JS
    tasks_data = []
    for t in hw.tasks:
        td = {'type': t.task_type, 'title': t.title, 'content': t.content,
              'data': json.loads(t.extra_data) if t.extra_data else {}}
        tasks_data.append(td)
    if request.method == 'POST':
        return _save_homework(request, students, hw)
    return render_template('admin_homework_edit.html', students=students, hw=hw, tasks=tasks_data)


def _save_homework(req, students, hw):
    """Универсальная функция сохранения ДЗ"""
    title = req.form.get('title', '').strip()
    deadline = req.form.get('deadline', '').strip() or None
    selected = req.form.getlist('assigned_students')
    tasks_json = req.form.get('tasks_json', '[]')

    try:
        tasks_data = json.loads(tasks_json)
    except:
        flash('Ошибка формата заданий!', 'error'); return redirect(req.url)

    if hw is None:
        hw = Homework(title=title, deadline=deadline, created_by=current_user.id)
        db.session.add(hw)
    else:
        hw.title = title;
        hw.deadline = deadline
        hw.assigned_to = User.query.filter(User.id.in_(selected)).all() if selected else []
        # Удаляем старые задания и файлы
        for t in hw.tasks:
            for f in t.files:
                p = os.path.join(app.config['UPLOAD_FOLDER'], f.filename)
                if os.path.exists(p): os.remove(p)
            db.session.delete(t)
        db.session.flush()

    for pos, td in enumerate(tasks_data):
        t = Task(homework_id=hw.id, task_type=td['type'], title=td.get('title', ''),
                 content=td.get('content', ''), extra_data=json.dumps(td.get('data', {})), position=pos)
        db.session.add(t);
        db.session.flush()
        for f in req.files.getlist(f'task_files_{pos}'):
            if f and f.filename:
                fn = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{secure_filename(f.filename)}"
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                db.session.add(TaskFile(task_id=t.id, filename=fn))

    if selected: hw.assigned_to = User.query.filter(User.id.in_(selected)).all()
    db.session.commit()
    flash('✅ ДЗ сохранено!', 'success')
    return redirect(url_for('admin_homework'))

@app.route('/admin/homework/add', methods=['GET', 'POST'])
@login_required
def admin_homework_add():
    if not current_user.is_admin: abort(403)
    students = User.query.filter_by(is_admin=False).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        deadline = request.form.get('deadline', '').strip() or None
        selected_students = request.form.getlist('assigned_students')
        tasks_json = request.form.get('tasks_json', '[]')
        try:
            tasks_data = json.loads(tasks_json)
        except:
            flash('Ошибка формата заданий!', 'error'); return redirect(url_for('admin_homework_add'))

        hw = Homework(title=title, deadline=deadline, created_by=current_user.id)
        if selected_students:
            hw.assigned_to = User.query.filter(User.id.in_(selected_students)).all()
        db.session.add(hw);
        db.session.flush()

        for pos, td in enumerate(tasks_data):
            t = Task(homework_id=hw.id, task_type=td['type'], title=td.get('title', ''),
                     content=td.get('content', ''), extra_data=json.dumps(td.get('data', {})), position=pos)
            db.session.add(t);
            db.session.flush()
            files = request.files.getlist(f'task_files_{pos}')
            for f in files:
                if f and f.filename:
                    fn = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{secure_filename(f.filename)}"
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                    db.session.add(TaskFile(task_id=t.id, filename=fn))
        db.session.commit()
        flash('✅ ДЗ успешно создано!', 'success')
        return redirect(url_for('admin_homework'))
    return render_template('admin_homework_add.html', students=students)


@app.route('/admin/homework/attempts/<int:hw_id>')
@login_required
def admin_hw_attempts(hw_id):
    if not current_user.is_admin: abort(403)
    hw = Homework.query.get_or_404(hw_id)
    students = User.query.filter_by(is_admin=False).all()

    sel_id = request.args.get('student_id', type=int)
    attempts = []
    if sel_id:
        subs = Submission.query.filter_by(homework_id=hw_id, user_id=sel_id).order_by(
            Submission.submitted_at.desc()).all()
        for s in subs:
            task = Task.query.get(s.task_id)
            if task:
                _, _, s.details = check_auto_answers(task, s.answer)
                s.task_title = task.title
            s.student = User.query.get(sel_id)
            attempts.append(s)

    return render_template('admin_hw_attempts.html', hw=hw, students=students, sel_id=sel_id, attempts=attempts)


@app.route('/admin/homework/delete/<int:hw_id>', methods=['POST'])
@login_required
def admin_homework_delete(hw_id):
    if not current_user.is_admin: abort(403)
    hw = Homework.query.get_or_404(hw_id)
    for t in hw.tasks:
        for tf in t.files:
            p = os.path.join(app.config['UPLOAD_FOLDER'], tf.filename)
            if os.path.exists(p): os.remove(p)
    db.session.delete(hw); db.session.commit()
    flash('🗑 ДЗ удалено', 'success'); return redirect(url_for('admin_homework'))


@app.route('/student/homework')
@login_required
def student_homework():
    if current_user.is_admin:
        return redirect(url_for('admin_homework'))

    all_hws = Homework.query.filter_by(is_visible=True).order_by(Homework.deadline.asc()).all()
    # ✅ Исправлено: .count() для проверки пустоты, .filter_by().first() для проверки доступа
    hws = [hw for hw in all_hws
           if hw.assigned_to.count() == 0 or hw.assigned_to.filter_by(id=current_user.id).first()]
    return render_template('student_homework.html', hws=hws)


@app.route('/student/homework/do/<int:hw_id>', methods=['GET', 'POST'])
@login_required
def student_hw_do(hw_id):
    hw = Homework.query.get_or_404(hw_id)
    if not hw.is_visible or current_user not in hw.assigned_to:
        flash('ДЗ недоступно', 'error');
        return redirect(url_for('student_homework'))

    if request.method == 'POST':
        answers_raw = request.form.get('answers_json', '{}')
        try:
            answers = json.loads(answers_raw)
        except:
            answers = {}

        for task in hw.tasks:
            needs_manual = False
            files_list = []

            # 🔹 ТЕКСТОВЫЕ ЗАДАНИЯ
            if task.task_type in ['text', 'text_file']:
                needs_manual = True
                user_ans = request.form.get(f'manual_text_{task.id}', '').strip()
                for ftype in ['file', 'audio', 'video']:
                    f = request.files.get(f'manual_{ftype}_{task.id}')
                    if f and f.filename:
                        fn = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(f.filename)}"
                        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                        files_list.append({'type': ftype, 'filename': fn})
                db.session.add(Submission(
                    homework_id=hw.id, task_id=task.id, user_id=current_user.id,
                    answer=user_ans, needs_manual=True, student_files_json=json.dumps(files_list)
                ))
                continue

            # 🔹 АВТОПРОВЕРКА (QUIZ & ПРОПУСКИ)
            user_ans = answers.get(str(task.id), {})
            score = 0;
            max_score = 0;
            is_correct = False;
            details = []

            if task.task_type == 'blank':
                hidden = json.loads(task.extra_data).get('hidden_words', [])
                max_score = len(hidden)
                for i, word in enumerate(hidden):
                    u = str(user_ans.get(f'blank_{i}', '')).strip().lower()
                    c = word.strip().lower()
                    ok = u == c
                    if ok: score += 1
                    details.append({"q_text": f"Пропуск {i + 1}", "user_ans": u or "(пусто)", "correct_ans": word,
                                    "is_correct": ok})
                is_correct = (score == max_score) if max_score > 0 else True

            elif task.task_type == 'quiz':
                questions = json.loads(task.extra_data).get('questions', [])
                max_score = len(questions)
                for i, q in enumerate(questions):
                    # ✅ Робастное сравнение: убираем пробелы, неразрывные пробелы, приводим к нижнему регистру
                    s_val = str(user_ans.get(str(i), '')).replace('\u00A0', ' ').strip().lower()
                    c_val = str(q.get('correct', '')).replace('\u00A0', ' ').strip().lower()
                    ok = s_val == c_val and c_val != ''
                    if ok: score += 1
                    details.append({
                        "q_text": q.get("q", ""),
                        "user_ans": s_val or "(пусто)",
                        "correct_ans": q.get("correct", ""),  # Сохраняем ОРИГИНАЛЬНЫЙ текст для показа
                        "is_correct": ok
                    })
                is_correct = (score == max_score) if max_score > 0 else True

            db.session.add(Submission(
                homework_id=hw.id, task_id=task.id, user_id=current_user.id,
                answer=json.dumps(user_ans), score=score, max_score=max_score,
                is_correct=is_correct, needs_manual=False
            ))

        db.session.commit()
        flash(f'📤 Ответы отправлены! Автозадание проверено мгновенно.', 'success')
        return redirect(url_for('student_hw_results', hw_id=hw_id))

    for t in hw.tasks:
        try:
            t.parsed = json.loads(t.extra_data)
        except:
            t.parsed = {}
    return render_template('student_hw_do.html', hw=hw)


@app.route('/admin/homework/review/<int:hw_id>')
@login_required
def admin_hw_review(hw_id):
    if not current_user.is_admin: abort(403)
    hw = Homework.query.get_or_404(hw_id)
    students = User.query.filter_by(is_admin=False).all()
    sel_id = request.args.get('student_id', type=int)
    subs = []
    if sel_id:
        subs = Submission.query.filter_by(homework_id=hw_id, user_id=sel_id, needs_manual=True).order_by(Submission.submitted_at.desc()).all()
    return render_template('admin_hw_review.html', hw=hw, students=students, sel_id=sel_id, subs=subs)

@app.route('/admin/homework/review/save/<int:sub_id>', methods=['POST'])
@login_required
def admin_hw_review_save(sub_id):
    if not current_user.is_admin: abort(403)
    sub = Submission.query.get_or_404(sub_id)
    sub.teacher_grade = request.form.get('grade', type=float)
    sub.teacher_comment = request.form.get('comment', '')
    db.session.commit()
    flash('✅ Оценка и комментарий сохранены!', 'success')
    return redirect(request.referrer)


@app.route('/student/homework/results/<int:hw_id>')
@login_required
def student_hw_results(hw_id):
    hw = Homework.query.get_or_404(hw_id)
    subs = Submission.query.filter_by(homework_id=hw_id, user_id=current_user.id).order_by(
        Submission.submitted_at.desc()).all()

    for s in subs:
        t = next((task for task in hw.tasks if task.id == s.task_id), None)
        s.task_type = t.task_type if t else 'text'
        s.task_title = t.title if t else 'Задание'
        s.details = []
        if not t: continue

        try:
            user_data = json.loads(s.answer) if s.answer else {}
        except:
            user_data = {}
        if not isinstance(user_data, dict): user_data = {}

        if t.task_type == 'blank':
            hidden = json.loads(t.extra_data).get('hidden_words', [])
            for i, word in enumerate(hidden):
                u = str(user_data.get(f'blank_{i}', '')).strip().lower()
                c = word.strip().lower()
                s.details.append({"q_text": f"Пропуск {i + 1}", "user_ans": u or "(пусто)", "correct_ans": word,
                                  "is_correct": u == c})

        elif t.task_type == 'quiz':
            questions = json.loads(t.extra_data).get('questions', [])
            for i, q in enumerate(questions):
                s_val = str(user_data.get(str(i), '')).strip().lower()
                c_val = str(q.get('correct', '')).strip().lower()
                s.details.append({
                    "q_text": q.get("q", ""),
                    "user_ans": s_val or "(пусто)",
                    "correct_ans": q.get("correct", ""),  # ✅ Оригинальный текст всегда передается
                    "is_correct": s_val == c_val and c_val != ''
                })

    return render_template('student_hw_results.html', hw=hw, subs=subs)

import base64
import os

@app.route('/admin/whiteboard')
@login_required
def admin_whiteboard():
    if not current_user.is_admin: abort(403)
    return render_template('admin_whiteboard.html')

@app.route('/admin/whiteboard/save', methods=['POST'])
@login_required
def save_whiteboard():
    if not current_user.is_admin: abort(403)
    data = request.get_json()
    image_b64 = data.get('image', '')
    title = data.get('title', 'Доска').strip() or 'Без названия'

    if not image_b64.startswith('data:image/png;base64,'):
        return jsonify({'success': False, 'error': 'Неверный формат изображения'})

    try:
        img_bytes = base64.b64decode(image_b64.split(',')[1])
        fn = f"whiteboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(title)}.png"
        path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
        with open(path, 'wb') as f:
            f.write(img_bytes)
        return jsonify({'success': True, 'filename': fn})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

import os
import glob

@app.route('/admin/whiteboard/gallery')
@login_required
def whiteboard_gallery():
    if not current_user.is_admin: abort(403)
    folder = app.config['UPLOAD_FOLDER']
    # Ищем только файлы досок
    files = sorted([f for f in os.listdir(folder) if f.startswith('whiteboard_') and f.endswith('.png')], reverse=True)
    return render_template('admin_whiteboard_gallery.html', files=files)

@app.route('/admin/whiteboard/delete/<filename>', methods=['POST'])
@login_required
def delete_whiteboard(filename):
    if not current_user.is_admin: abort(403)
    if '..' in filename or not filename.endswith('.png'): return jsonify({'success': False})
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(path): os.remove(path)
    return jsonify({'success': True})


# ✅ БЕЗОПАСНАЯ ИНИЦИАЛИЗАЦИЯ АДМИНА
def init_admin():
    """Создаёт админа, если таблица существует и админа нет"""
    with app.app_context():
        try:
            # Проверяем, создана ли таблица (попытка запроса)
            if User.query.first() is None or not User.query.filter_by(login='admin').first():
                # Создаём админа только если его нет
                if not User.query.filter_by(login='admin').first():
                    admin = User(login='admin', grade='0', is_admin=True, agreed_terms=True)
                    admin.set_password('admin123')
                    db.session.add(admin)
                    db.session.commit()
                    print("✅ Admin user created")
        except Exception as e:
            # Если таблицы ещё не созданы — игнорируем, они создадутся при первом реальном запросе
            print(f"⏳ DB not ready yet: {e}")

# Запускаем инициализацию (безопасно, так как внутри with_app_context)
init_admin()



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)