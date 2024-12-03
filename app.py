from flask import Flask, request, render_template, redirect, session, url_for, jsonify, Response
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mnemonic import Mnemonic
import hashlib
import os
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
import shutil

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'

UPLOAD_FOLDER = 'static/uploads'
BACKUP_FOLDER = 'static/backup'
TRASH_FOLDER = 'static/trash'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(BACKUP_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


os.makedirs(TRASH_FOLDER, exist_ok=True)


conn = sqlite3.connect('usuarios.db', check_same_thread=False)
c = conn.cursor()


c.execute('''CREATE TABLE IF NOT EXISTS usuarios
             (email text, frase_semente text)''')
c.execute('''CREATE TABLE IF NOT EXISTS arquivos
             (user_email text, filename text)''')
conn.commit()

def hash_frase_semente(frase_semente):
    return hashlib.sha256(frase_semente.encode()).hexdigest()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


if not os.path.exists('chave.key'):
    chave = Fernet.generate_key()
    with open('chave.key', 'wb') as chave_file:
        chave_file.write(chave)
else:
    with open('chave.key', 'rb') as chave_file:
        chave = chave_file.read()

cipher = Fernet(chave)

@app.route('/')
def home():
    return render_template('pagina-inicial.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))
 
    #Começo do pedido no Trabalho 2
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        frase_semente = request.json.get('palavra_semente', None)
        
 
        print(f"Frase-semente recebida: {frase_semente}")


        if not frase_semente:
            return "A frase semente deve ser preenchida", 400


        frase_semente_hashed = hash_frase_semente(frase_semente)


        c.execute("SELECT email FROM usuarios WHERE frase_semente = ?", (frase_semente_hashed,))
        resultado = c.fetchone()

        if resultado:
            session['frase_semente'] = frase_semente
            session['email'] = resultado[0]
            return redirect('/oficial')
        else:
            return "Frase-semente incorreta", 400

    return render_template('pagina-login.html')
    # final

@app.route('/oficial')
def oficial():
    if 'email' in session:
        user_email = session.get('email')
        if user_email:
            user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_email)
            if not os.path.exists(user_folder):
                os.makedirs(user_folder)
            images = os.listdir(user_folder)
            return render_template('pagina-oficial.html', images=images)
    return redirect('/login')

@app.route('/lixeira')
def lixeira():
    if 'email' not in session:
        return redirect('/login')
    
    user_email = session.get('email')
    if not user_email:
        return redirect('/login')
    user_folder = os.path.join(TRASH_FOLDER, user_email)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    images = [f for f in os.listdir(user_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
    return render_template('lixeira.html', images=images)
    
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'email' not in session:
        return redirect('/login')

    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        user_email = session.get('email')
        if not user_email:
            return redirect('/login')
        filename = secure_filename(file.filename)
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_email)

        if not os.path.exists(user_folder):
            os.makedirs(user_folder)


        file_content = file.read()


        encrypted_content = cipher.encrypt(file_content)


        with open(os.path.join(user_folder, filename), 'wb') as encrypted_file:
            encrypted_file.write(encrypted_content)

 
        backup_path = os.path.join(BACKUP_FOLDER, filename)
        with open(backup_path, 'wb') as backup_file:
            backup_file.write(file_content)  

      
        c.execute("INSERT INTO arquivos (user_email, filename) VALUES (?, ?)", (user_email, filename))
        conn.commit()

        return redirect(url_for('oficial'))
    

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    if 'email' not in session:
        return redirect('/login')

    user_email = session.get('email')
    if not user_email:
        return redirect('/login')
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_email)
    file_path = os.path.join(user_folder, filename)

    if os.path.exists(file_path):

        with open(file_path, 'rb') as encrypted_file:
            encrypted_content = encrypted_file.read()


        decrypted_content = cipher.decrypt(encrypted_content)


        return Response(
            decrypted_content,
            mimetype='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    else:
        return "Arquivo não encontrado", 404
    
@app.route('/search', methods=['GET'])
def search_files():
    if 'email' not in session:
        return redirect('/login')

    user_email = session.get('email')
    if not user_email:
        return redirect('/login')
    
    query = request.args.get('q', '').lower()
    user_folder = os.path.join(UPLOAD_FOLDER, user_email)
    files = os.listdir(user_folder)

    matching_files = [file for file in files if query in file.lower()]

    return jsonify({'files': matching_files})



@app.route('/share_file', methods=['POST'])
def share_file():
    data = request.get_json()
    email_destino = data.get('email')
    filename = data.get('filename')
    email_origem = session.get('email')  

    if not email_destino or not filename:
        return jsonify({'status': 'error', 'message': 'Email ou arquivo não fornecido'}), 400


    user_dest_folder = os.path.join(app.config['UPLOAD_FOLDER'], email_destino)
    
  
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], email_origem, filename)

 
    if os.path.exists(file_path):
        os.makedirs(user_dest_folder, exist_ok=True)
        
 
        shutil.copy(file_path, os.path.join(user_dest_folder, filename))
        
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Arquivo não encontrado'}), 404
    
@app.route('/move_to_trash/<filename>', methods=['POST'])
def move_to_trash(filename):
    if 'email' not in session:
        return redirect('/login')

    user_email = session.get('email')
    if not user_email:
        return redirect('/login')
    source_path = os.path.join(UPLOAD_FOLDER, user_email, filename)
    target_path = os.path.join(TRASH_FOLDER, user_email, filename)

    if os.path.exists(source_path):
        shutil.move(source_path, target_path)
        c.execute("UPDATE arquivos SET trashed = 1 WHERE user_email = ? AND filename = ?", (user_email, filename))
        conn.commit()
        return jsonify({'status': 'success'})
    else:
        return "Arquivo não encontrado", 404
    
@app.route('/restore_from_trash/<filename>', methods=['POST'])
def restore_from_trash(filename):
    if 'email' not in session:
        return redirect('/login')

    user_email = session.get('email')
    if not user_email:
        return redirect('/login')
    
    source_path = os.path.join(TRASH_FOLDER, user_email, filename)
    target_path = os.path.join(UPLOAD_FOLDER, user_email, filename)

    if os.path.exists(source_path):

        shutil.move(source_path, target_path)
        c.execute("UPDATE arquivos SET trashed = 0 WHERE user_email = ? AND filename = ?", (user_email, filename))
        conn.commit()
        return jsonify({'status': 'success'})
    else:
        return "Arquivo não encontrado", 404

@app.route('/delete_permanent/<filename>', methods=['DELETE'])
def delete_permanent(filename):
    if 'email' not in session:
        return redirect('/login')

    user_email = session.get('email')
    if not user_email:
        return redirect('/login')
    file_path = os.path.join(TRASH_FOLDER, user_email, filename)

    if os.path.exists(file_path):
        os.remove(file_path)
        c.execute("DELETE FROM arquivos WHERE user_email = ? AND filename = ?", (user_email, filename))
        conn.commit()
        return jsonify({'status': 'success'})
    else:
        return "Arquivo não encontrado", 404

    user_email = session.get('email')
    if not user_email:
        return redirect('/login')
    src_path = os.path.join(app.config['UPLOAD_FOLDER'], user_email, filename)
    dst_path = os.path.join(TRASH_FOLDER, filename)
    if os.path.exists(src_path):
        os.rename(src_path, dst_path)
    return jsonify({'status': 'success'})

@app.route('/files', methods=['GET'])
def list_files():
    if 'email' not in session:
        return redirect('/login')

    user_email = session.get('email')
    if not user_email:
        return jsonify({'files': []})
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_email)
    files = os.listdir(user_folder)
    return jsonify({'files': files})




@app.route('/signup', methods=['POST'])
def registrar():
    email = request.form.get('email')
    if email is None:
        return "Email não encontrado no formulário", 400

 
    frase_semente = gerar_frase_semente()


    frase_semente_hashed = hash_frase_semente(frase_semente)


    c.execute("INSERT INTO usuarios (email, frase_semente) VALUES (?, ?)", (email, frase_semente_hashed))
    conn.commit()

 
    enviar_email_verificacao(email, frase_semente)
    
    return redirect('/login')

def gerar_frase_semente():
    mnemo = Mnemonic("portuguese")
    return mnemo.generate(strength=128)

def enviar_email_verificacao(email, frase_semente):
    try:
        smtp_server = 'smtp.gmail.com'
        port = 587
        sender_email = 'cryptoarchives00@gmail.com'
        password = 'rydn shtk fwlg akyw'  

        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = email
        message['Subject'] = 'Verificação de email'
        body = (
            "Gostaríamos de informá-lo(a) que sua chave de acesso exclusiva foi gerada com sucesso. "
            "Para garantir a segurança e privacidade de seus dados, solicitamos que você utilize a chave abaixo ao acessar nossos serviços:\n\n"
            f"Chave de Acesso: {frase_semente}\n\n"
            "Por favor, mantenha esta chave em um local seguro e não a compartilhe com terceiros. "
            "Se tiver qualquer dúvida ou precisar de assistência adicional, não hesite em entrar em contato conosco.\n\n"
            "Agradecemos pela sua atenção e cooperação.\n\n"
            "Atenciosamente, CryptoArchives"
        )
        message.attach(MIMEText(body, 'plain', 'utf-8'))

        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, email, message.as_string())
        print("Email enviado com sucesso!")  
    except Exception as e:
        print(f"Erro ao enviar email: {e}")  


if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists(TRASH_FOLDER):
        os.makedirs(TRASH_FOLDER)
    app.run(debug=True)
