import os
import json
import uuid
import shutil
from flask import Flask, request, render_template, send_from_directory, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
import datetime
import hashlib
import random
import string

app = Flask(__name__)

# 配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files')
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'file_data.json')
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', '7z', 'mp3', 'mp4', 'avi', 'mov'])
FORBIDDEN_EXTENSIONS = set(['php', 'exe', 'bat', 'cmd', 'sh', 'js', 'vbs', 'py'])
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 工具函数
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"file_groups": {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext not in FORBIDDEN_EXTENSIONS and (ext in ALLOWED_EXTENSIONS or '*' in ALLOWED_EXTENSIONS)

def generate_pickup_code(length=6):
    # 生成数字+字母的取件码
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def check_file_for_virus(file_path):
    # 此处应实现病毒检测逻辑，目前只检查文件扩展名
    filename = os.path.basename(file_path)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext not in FORBIDDEN_EXTENSIONS

def create_download_token(file_group_id):
    # 创建下载令牌
    token = str(uuid.uuid4())
    data = load_data()
    if file_group_id in data["file_groups"]:
        data["file_groups"][file_group_id]["download_token"] = token
        data["file_groups"][file_group_id]["token_created"] = datetime.datetime.now().isoformat()
        save_data(data)
    return token

def validate_token(file_group_id, token):
    # 验证下载令牌
    data = load_data()
    if file_group_id in data["file_groups"]:
        if data["file_groups"][file_group_id].get("download_token") == token:
            return True
    return False

def clean_expired_files():
    data = load_data()
    now = datetime.datetime.now()
    to_delete = []
    
    for file_id, info in data["file_groups"].items():
        # 检查有效期
        if "expiry_date" in info:
            expiry_date = datetime.datetime.fromisoformat(info["expiry_date"])
            if now > expiry_date:
                to_delete.append(file_id)
                continue
                
        # 检查下载次数
        if "max_downloads" in info and info.get("download_count", 0) >= info["max_downloads"]:
            to_delete.append(file_id)
    
    # 删除过期文件
    for file_id in to_delete:
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        if file_id in data["file_groups"]:
            del data["file_groups"][file_id]
    
    save_data(data)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        return render_template('upload.html')
        
    if request.method == 'POST':
        # 检查是否有文件
        if 'files[]' not in request.files:
            return jsonify({'error': '没有文件被上传'}), 400
            
        files = request.files.getlist('files[]')
        if not files or files[0].filename == '':
            return jsonify({'error': '没有选择文件'}), 400
            
        # 获取有效期和最大下载次数
        expiry_days = int(request.form.get('expiry_days', 7))
        max_downloads = int(request.form.get('max_downloads', 0))
        
        # 创建文件组ID和取件码
        file_group_id = str(uuid.uuid4())
        pickup_code = generate_pickup_code()
        
        # 确保目录存在
        group_folder = os.path.join(app.config['UPLOAD_FOLDER'], file_group_id)
        os.makedirs(group_folder, exist_ok=True)
        
        # 处理文件上传
        file_info = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(group_folder, filename)
                file.save(file_path)
                
                # 检查病毒
                if not check_file_for_virus(file_path):
                    shutil.rmtree(group_folder)  # 删除整个文件夹
                    return jsonify({'error': '发现潜在危险文件，上传已取消'}), 400
                
                file_size = os.path.getsize(file_path)
                file_info.append({
                    'name': filename,
                    'size': file_size,
                    'upload_time': datetime.datetime.now().isoformat()
                })
        
        # 保存文件组信息
        data = load_data()
        expiry_date = None
        if expiry_days > 0:
            expiry_date = (datetime.datetime.now() + datetime.timedelta(days=expiry_days)).isoformat()
            
        data["file_groups"][file_group_id] = {
            'pickup_code': pickup_code,
            'files': file_info,
            'created_at': datetime.datetime.now().isoformat(),
            'expiry_date': expiry_date,
            'max_downloads': max_downloads if max_downloads > 0 else None,
            'download_count': 0,
            'download_history': []
        }
        save_data(data)
        
        # 返回上传成功信息
        return jsonify({
            'success': True,
            'file_group_id': file_group_id,
            'pickup_code': pickup_code,
            'management_url': url_for('manage_files', file_group_id=file_group_id, _external=True)
        })

@app.route('/pickup', methods=['GET', 'POST'])
def pickup_file():
    if request.method == 'GET':
        return render_template('pickup.html')
        
    if request.method == 'POST':
        pickup_code = request.form.get('pickup_code')
        if not pickup_code:
            return jsonify({'error': '请输入取件码'}), 400
            
        # 清理过期文件
        clean_expired_files()
            
        # 查找对应文件组
        data = load_data()
        file_group_id = None
        
        for f_id, info in data["file_groups"].items():
            if info.get('pickup_code') == pickup_code:
                file_group_id = f_id
                break
        
        if not file_group_id:
            return jsonify({'error': '取件码无效或已过期'}), 404
            
        # 创建下载令牌
        token = create_download_token(file_group_id)
        
        # 返回文件列表和下载令牌
        file_info = data["file_groups"][file_group_id]['files']
        return jsonify({
            'success': True,
            'file_group_id': file_group_id,
            'token': token,
            'files': file_info
        })

@app.route('/download/<file_group_id>/<filename>')
def download_file(file_group_id, filename):
    token = request.args.get('token')
    if not token or not validate_token(file_group_id, token):
        return jsonify({'error': '无效或已过期的下载链接'}), 403
        
    # 记录下载信息
    data = load_data()
    if file_group_id in data["file_groups"]:
        download_info = {
            'filename': filename,
            'time': datetime.datetime.now().isoformat(),
            'ip': request.remote_addr
        }
        data["file_groups"][file_group_id]['download_history'].append(download_info)
        data["file_groups"][file_group_id]['download_count'] = data["file_groups"][file_group_id].get('download_count', 0) + 1
        save_data(data)
        
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_group_id)
    return send_from_directory(file_path, filename, as_attachment=True)

@app.route('/manage/<file_group_id>')
def manage_files(file_group_id):
    data = load_data()
    if file_group_id not in data["file_groups"]:
        return render_template('error.html', message='找不到指定的文件组')
        
    file_group = data["file_groups"][file_group_id]
    return render_template('manage.html', file_group=file_group, file_group_id=file_group_id)

@app.route('/api/delete/<file_group_id>', methods=['POST'])
def delete_file_group(file_group_id):
    data = load_data()
    if file_group_id not in data["file_groups"]:
        return jsonify({'error': '找不到指定的文件组'}), 404
        
    # 删除文件夹
    folder_path = os.path.join(app.config['UPLOAD_FOLDER'], file_group_id)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        
    # 删除数据记录
    del data["file_groups"][file_group_id]
    save_data(data)
    
    return jsonify({'success': True})

@app.route('/static/css/style.css')
def serve_css():
    return send_from_directory('static/css', 'style.css')

@app.route('/static/js/script.js')
def serve_js():
    return send_from_directory('static/js', 'script.js')

if __name__ == '__main__':
    # 确保文件夹存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # 确保数据文件存在
    if not os.path.exists(DATA_FILE):
        save_data({"file_groups": {}})
        
    app.run(debug=True, host='0.0.0.0', port=5000)
